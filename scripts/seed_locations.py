"""
Seed script: Fetches tourism/nature/historic POIs from OpenStreetMap Overpass API
for all districts in the places table.

Logic per district:
- count=0 in locations → bulk insert all POIs
- count matches OSM → skip
- count mismatch → find missing place_names, insert only those

Retry: exponential backoff on 429/503/504, max 3 attempts.
"""

import math
import os
import time

import requests
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DATABASE_URL", "postgresql://trvlr_admin:trvlr2026!@localhost:5432/trvlr_db")

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

HEADERS = {
    "User-Agent": "trvlr-be/0.1 (seed-locations script)",
    "Accept": "application/json",
}

# OSM tags to query
TAGS = ["tourism", "historic", "leisure", "natural"]

# Default radius (metres) by location_type when geometry is not available
DEFAULT_RADIUS = {
    "tourism:attraction": 200,
    "tourism:museum": 100,
    "tourism:zoo": 300,
    "tourism:theme_park": 400,
    "tourism:viewpoint": 30,
    "tourism:artwork": 20,
    "tourism:hotel": 50,
    "tourism:guest_house": 30,
    "historic:fort": 400,
    "historic:monument": 50,
    "historic:castle": 300,
    "historic:ruins": 200,
    "historic:temple": 100,
    "historic:archaeological_site": 300,
    "natural:waterfall": 50,
    "natural:peak": 100,
    "natural:cave_entrance": 30,
    "natural:hot_spring": 30,
    "natural:water": 200,
    "leisure:park": 300,
    "leisure:nature_reserve": 500,
    "leisure:garden": 150,
    "leisure:water_park": 200,
    "leisure:playground": 50,
    "leisure:sports_centre": 150,
    "leisure:stadium": 200,
    "leisure:swimming_pool": 50,
}

FALLBACK_RADIUS = 100


# --- DB helpers ---


def get_districts_from_db() -> list[dict]:
    """Read all (district, state) pairs from the places table."""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("SELECT district, state FROM places ORDER BY state, district")
    rows = [{"district": r[0], "state": r[1]} for r in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


def get_location_count_for_district(district: str) -> int:
    """Get count of locations already in DB for a district."""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM locations WHERE district = %s", (district,))
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count


def get_existing_place_names_for_district(district: str) -> set[str]:
    """Get all place_names already in DB for a district."""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("SELECT place_name FROM locations WHERE district = %s", (district,))
    names = {r[0] for r in cur.fetchall()}
    cur.close()
    conn.close()
    return names


# --- Overpass/Nominatim helpers ---


def request_with_retry(method: str, url: str, **kwargs) -> requests.Response | None:
    """Make an HTTP request with retry on 429/503/504."""
    for attempt in range(3):
        try:
            if method == "get":
                resp = requests.get(url, headers=HEADERS, timeout=120, **kwargs)
            else:
                resp = requests.post(url, headers=HEADERS, timeout=120, **kwargs)

            if resp.status_code in (429, 503, 504):
                wait = 2 ** (attempt + 1) * 10  # 20s, 40s, 80s
                print(f"    Got {resp.status_code}, retrying in {wait}s (attempt {attempt + 1}/3)...")
                time.sleep(wait)
                continue

            return resp

        except requests.exceptions.Timeout:
            wait = 2 ** (attempt + 1) * 10
            print(f"    Timeout, retrying in {wait}s (attempt {attempt + 1}/3)...")
            time.sleep(wait)
            continue
        except Exception as e:
            print(f"    Exception: {e}")
            return None

    print("    Failed after 3 retries.")
    return None


def get_bbox_for_district(district: str, state: str) -> tuple | None:
    """Get bounding box for a district using Nominatim geocoding."""
    params = {
        "q": f"{district}, {state}, India",
        "format": "json",
        "limit": 1,
        "featuretype": "settlement",
    }
    resp = request_with_retry("get", NOMINATIM_URL, params=params)
    if not resp or resp.status_code != 200:
        return None

    results = resp.json()
    if not results:
        # Try without featuretype
        params.pop("featuretype")
        resp = request_with_retry("get", NOMINATIM_URL, params=params)
        if not resp or resp.status_code != 200:
            return None
        results = resp.json()
        if not results:
            return None

    bbox = results[0].get("boundingbox")
    if not bbox:
        return None

    # Nominatim returns [south, north, west, east] as strings
    south, north, west, east = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
    return (south, west, north, east)


# --- Core POI fetching logic ---


def build_query(bbox: tuple) -> str:
    """Build Overpass QL query using a bounding box."""
    south, west, north, east = bbox
    bbox_str = f"{south},{west},{north},{east}"

    tag_filters = []
    for tag in TAGS:
        tag_filters.append(f'  node["{tag}"]({bbox_str});')
        tag_filters.append(f'  way["{tag}"]({bbox_str});')

    filters = "\n".join(tag_filters)

    return f"""[out:json][timeout:90];
(
{filters}
);
out body geom;"""


def classify_element(tags: dict) -> str:
    """Determine location_type from OSM tags."""
    for tag in TAGS:
        if tag in tags:
            value = tags[tag]
            return f"{tag}:{value}"
    return "unknown"


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in metres between two lat/lon points."""
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def compute_radius_from_geometry(element: dict) -> int | None:
    """Compute approximate radius from a way's geometry."""
    geometry = element.get("geometry")
    if not geometry or len(geometry) < 3:
        return None

    lats = [node["lat"] for node in geometry]
    lons = [node["lon"] for node in geometry]

    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)

    max_dist = 0
    for node in geometry:
        dist = haversine_distance(center_lat, center_lon, node["lat"], node["lon"])
        if dist > max_dist:
            max_dist = dist

    radius = int(min(max_dist, 2000))
    return radius if radius > 10 else None


def build_polygon_wkt(element: dict) -> str | None:
    """Build a WKT POLYGON string from a way's geometry."""
    geometry = element.get("geometry")
    if not geometry or len(geometry) < 4:
        return None

    first = geometry[0]
    last = geometry[-1]
    if first["lat"] != last["lat"] or first["lon"] != last["lon"]:
        geometry = geometry + [first]

    coords = ", ".join(f"{node['lon']} {node['lat']}" for node in geometry)
    return f"SRID=4326;POLYGON(({coords}))"


def get_radius(element: dict, location_type: str) -> int:
    """Get radius: try computing from geometry first, fall back to defaults."""
    if element.get("type") == "way":
        computed = compute_radius_from_geometry(element)
        if computed:
            return computed
    return DEFAULT_RADIUS.get(location_type, FALLBACK_RADIUS)


def fetch_pois(district: str, state: str, bbox: tuple) -> list[dict]:
    """Fetch POIs from Overpass API for a given bounding box."""
    query = build_query(bbox)
    print(f"  Fetching POIs from Overpass...")

    resp = request_with_retry("post", OVERPASS_URL, data={"data": query})
    if not resp or resp.status_code != 200:
        print(f"  Failed to fetch POIs for {district}")
        return []

    data = resp.json()

    results = []
    for element in data.get("elements", []):
        if element.get("type") == "node":
            lat = element.get("lat")
            lon = element.get("lon")
        else:
            geometry = element.get("geometry", [])
            if geometry:
                lat = sum(n["lat"] for n in geometry) / len(geometry)
                lon = sum(n["lon"] for n in geometry) / len(geometry)
            else:
                lat = element.get("center", {}).get("lat")
                lon = element.get("center", {}).get("lon")

        if not lat or not lon:
            continue

        tags = element.get("tags", {})
        name = tags.get("name") or tags.get("name:en")
        if not name:
            continue

        location_type = classify_element(tags)
        radius_m = get_radius(element, location_type)

        boundary_wkt = None
        if element.get("type") == "way":
            boundary_wkt = build_polygon_wkt(element)

        results.append({
            "name": name,
            "latitude": lat,
            "longitude": lon,
            "location_type": location_type,
            "radius_m": radius_m,
            "boundary": boundary_wkt,
            "district": district,
            "state": state,
        })

    print(f"  Found {len(results)} named POIs from OSM")
    return results


# --- Insert logic ---


def insert_locations(locations: list[dict]):
    """Bulk insert locations, skipping duplicates by place_name."""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    inserted = 0
    skipped = 0
    for loc in locations:
        cur.execute(
            """
            INSERT INTO locations (coordinates, boundary, district, state, place_name, location_type, radius_m, score)
            VALUES (ST_MakePoint(%s, %s)::geography, %s::geography, %s, %s, %s, %s, %s, 0)
            ON CONFLICT (place_name) DO NOTHING
            """,
            (
                loc["longitude"],
                loc["latitude"],
                loc["boundary"],
                loc["district"],
                loc["state"],
                loc["name"],
                loc["location_type"],
                loc["radius_m"],
            ),
        )
        if cur.rowcount == 1:
            inserted += 1
        else:
            skipped += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"  Inserted {inserted}, skipped {skipped} duplicates.")


# --- Main orchestration ---


def process_district(district: str, state: str):
    """Process a single district: fetch, compare, insert as needed."""
    print(f"\n{'='*60}")
    print(f"Processing: {district}, {state}")

    # Get bounding box from Nominatim
    bbox = get_bbox_for_district(district, state)
    if not bbox:
        print(f"  Could not get bbox for {district}, skipping.")
        return

    time.sleep(1)  # Be polite to Nominatim

    # Fetch POIs from OSM
    pois = fetch_pois(district, state, bbox)
    if not pois:
        print(f"  No POIs found, skipping.")
        return

    osm_count = len(pois)
    db_count = get_location_count_for_district(district)

    print(f"  OSM count: {osm_count}, DB count: {db_count}")

    if db_count == 0:
        # Fresh insert
        print(f"  Bulk inserting all {osm_count} POIs...")
        insert_locations(pois)

    elif db_count == osm_count:
        # Counts match, assume synced
        print(f"  Counts match, skipping.")

    else:
        # Mismatch — find and insert missing ones
        existing_names = get_existing_place_names_for_district(district)
        missing = [p for p in pois if p["name"] not in existing_names]
        print(f"  Mismatch: {len(missing)} new POIs to insert.")
        if missing:
            insert_locations(missing)


def main():
    districts = get_districts_from_db()
    print(f"Found {len(districts)} districts in places table.")

    for place in districts:
        process_district(place["district"], place["state"])
        time.sleep(5)  # Be polite to Overpass API

    print("\nDone!")


if __name__ == "__main__":
    main()
