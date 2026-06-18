"""
Seed script: Fetches tourism/nature/historic POIs from OpenStreetMap Overpass API
for specified Karnataka districts and inserts them into the locations table.
"""

import os
import time

import requests
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DATABASE_URL", "postgresql://trvlr_admin:trvlr2026!@localhost:5432/trvlr_db")

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Districts with approximate bounding boxes (south, west, north, east)
# DISTRICTS = {
#     "Bengaluru Urban": (12.85, 77.45, 13.15, 77.75),
#     "Bengaluru South": (12.75, 77.50, 12.95, 77.70),
#     "Bengaluru North": (13.00, 77.45, 13.25, 77.70),
#     "Chikkaballapur": (13.20, 77.55, 13.75, 78.15),
#     "Chitradurga": (13.65, 76.10, 14.55, 77.05),
#     "Davanagere": (14.15, 75.75, 14.75, 76.35),
#     "Kolar": (12.85, 78.00, 13.35, 78.45),
#     "Shimoga": (13.55, 74.95, 14.45, 75.85),
#     "Tumakuru": (13.15, 76.55, 13.95, 77.40),
# }

DISTRICTS = {
    "Bengaluru Urban": (12.85, 77.45, 13.15, 77.75)
}

# OSM tags to query and the location_type we assign
TAGS = ["tourism", "historic", "leisure", "natural"]


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
out center;"""


def classify_element(tags: dict) -> str:
    """Determine location_type from OSM tags."""
    for tag in TAGS:
        if tag in tags:
            value = tags[tag]
            return f"{tag}:{value}"
    return "unknown"


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
        # Get coordinates (nodes have lat/lon directly, ways have center)
        lat = element.get("lat") or element.get("center", {}).get("lat")
        lon = element.get("lon") or element.get("center", {}).get("lon")

        if not lat or not lon:
            continue

        tags = element.get("tags", {})
        name = tags.get("name") or tags.get("name:en")

        if not name:
            continue

        location_type = classify_element(tags)

        results.append({
            "name": name,
            "latitude": lat,
            "longitude": lon,
            "location_type": location_type,
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
            INSERT INTO locations (coordinates, district, state, place_name, location_type, score)
            VALUES (ST_MakePoint(%s, %s)::geography, %s, %s, %s, %s, 0)
            ON CONFLICT (place_name) DO NOTHING
            """,
            (
                loc["longitude"],
                loc["latitude"],
                loc["district"],
                loc["state"],
                loc["name"],
                loc["location_type"],
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
