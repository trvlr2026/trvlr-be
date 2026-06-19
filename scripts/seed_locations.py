"""
Seed script: Fetches tourism/nature/historic POIs from OpenStreetMap Overpass API
for specified Karnataka districts and inserts them into the locations table.
Calculates approximate radius from way geometry, falls back to defaults for nodes.
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

# Districts with approximate bounding boxes (south, west, north, east)
DISTRICTS = {
    "Bengaluru Urban": (12.85, 77.45, 13.15, 77.75),
    "Bengaluru South": (12.75, 77.50, 12.95, 77.70),
    "Bengaluru North": (13.00, 77.45, 13.25, 77.70),
    "Chikkaballapur": (13.20, 77.55, 13.75, 78.15),
    "Chitradurga": (13.65, 76.10, 14.55, 77.05),
    "Davanagere": (14.15, 75.75, 14.75, 76.35),
    "Kolar": (12.85, 78.00, 13.35, 78.45),
    "Shimoga": (13.55, 74.95, 14.45, 75.85),
    "Tumakuru": (13.15, 76.55, 13.95, 77.40),
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

FALLBACK_RADIUS = 100  # Default when type not in the map


def build_query(bbox: tuple) -> str:
    """Build Overpass QL query using a bounding box. Request geometry for ways."""
    south, west, north, east = bbox
    bbox_str = f"{south},{west},{north},{east}"

    tag_filters = []
    for tag in TAGS:
        tag_filters.append(f'  node["{tag}"]({bbox_str});')
        tag_filters.append(f'  way["{tag}"]({bbox_str});')

    filters = "\n".join(tag_filters)

    # out geom for ways gives us the full node coordinates to compute area
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
    R = 6371000  # Earth radius in metres
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def compute_radius_from_geometry(element: dict) -> int | None:
    """
    Compute approximate radius from a way's geometry.
    Uses the bounding box of all nodes to estimate size.
    Returns radius in metres, or None if not computable.
    """
    geometry = element.get("geometry")
    if not geometry or len(geometry) < 3:
        return None

    lats = [node["lat"] for node in geometry]
    lons = [node["lon"] for node in geometry]

    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)

    # Compute max distance from center to any node
    max_dist = 0
    for node in geometry:
        dist = haversine_distance(center_lat, center_lon, node["lat"], node["lon"])
        if dist > max_dist:
            max_dist = dist

    # Cap at reasonable values
    radius = int(min(max_dist, 2000))  # Cap at 2km
    return radius if radius > 10 else None  # Ignore tiny computed radii


def get_radius(element: dict, location_type: str) -> int:
    """Get radius: try computing from geometry first, fall back to defaults."""
    if element.get("type") == "way":
        computed = compute_radius_from_geometry(element)
        if computed:
            return computed

    return DEFAULT_RADIUS.get(location_type, FALLBACK_RADIUS)


def build_polygon_wkt(element: dict) -> str | None:
    """
    Build a WKT POLYGON string from a way's geometry.
    Returns None if the way isn't a closed polygon or has fewer than 4 points.
    """
    geometry = element.get("geometry")
    if not geometry or len(geometry) < 4:
        return None

    # Close the polygon if not already closed
    first = geometry[0]
    last = geometry[-1]
    if first["lat"] != last["lat"] or first["lon"] != last["lon"]:
        geometry = geometry + [first]

    coords = ", ".join(f"{node['lon']} {node['lat']}" for node in geometry)
    return f"SRID=4326;POLYGON(({coords}))"


def fetch_pois(district: str, bbox: tuple) -> list[dict]:
    """Fetch POIs from Overpass API for a given bounding box with retry on 429/504."""
    query = build_query(bbox)
    print(f"Fetching POIs for {district}...")

    headers = {
        "User-Agent": "trvlr-be/0.1 (seed script)",
        "Accept": "application/json",
    }

    for attempt in range(3):
        try:
            resp = requests.post(
                OVERPASS_URL,
                data={"data": query},
                headers=headers,
                timeout=120,
            )
            if resp.status_code in (429, 504):
                wait = 2 ** (attempt + 1) * 10  # 20s, 40s, 80s
                print(f"  Got {resp.status_code}, retrying in {wait}s (attempt {attempt + 1}/3)...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            break
        except requests.exceptions.Timeout:
            wait = 2 ** (attempt + 1) * 10
            print(f"  Timeout, retrying in {wait}s (attempt {attempt + 1}/3)...")
            time.sleep(wait)
            continue
    else:
        print(f"  Failed after 3 retries for {district}, skipping.")
        return []

    results = []
    for element in data.get("elements", []):
        # Get coordinates (nodes have lat/lon directly, ways have center via geometry)
        if element.get("type") == "node":
            lat = element.get("lat")
            lon = element.get("lon")
        else:
            # For ways, compute center from geometry
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

        # Build polygon for ways with geometry
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
            "state": "Karnataka",
        })

    print(f"  Found {len(results)} named POIs in {district}")
    return results


def insert_locations(locations: list[dict]):
    """Bulk insert locations into the database, skipping duplicates by place_name."""
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
    print(f"Inserted {inserted} locations, skipped {skipped} duplicates.")


def main():
    all_locations = []

    for district, bbox in DISTRICTS.items():
        pois = fetch_pois(district, bbox)
        all_locations.extend(pois)
        time.sleep(5)  # Be polite to the Overpass API

    print(f"\nTotal POIs collected: {len(all_locations)}")
    if all_locations:
        insert_locations(all_locations)


if __name__ == "__main__":
    main()
