"""
Seed script: Fetches all districts of India from OpenStreetMap Overpass API.
Uses admin_level=5 (district level) boundaries within India.
Names are exactly as used by OSM for consistency.
"""

import os
import time

import requests
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DATABASE_URL", "postgresql://trvlr_admin:trvlr2026!@localhost:5432/trvlr_db")

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

HEADERS = {
    "User-Agent": "trvlr-be/0.1 (seed places script)",
    "Accept": "application/json",
}

# India's states/UTs with their OSM names (admin_level=4)
# We'll query district (admin_level=5) for each state
STATES = [
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chhattisgarh",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
    "Andaman and Nicobar Islands",
    "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi",
    "Jammu and Kashmir",
    "Ladakh",
    "Lakshadweep",
    "Puducherry",
]


def fetch_districts_for_state(state: str) -> list[str]:
    """Fetch all district names (admin_level=5) for a given state from OSM."""
    query = f"""[out:json][timeout:120];
area["name"="{state}"]["admin_level"="4"]["boundary"="administrative"]->.state;
rel["admin_level"="5"]["boundary"="administrative"](area.state);
out tags;"""

    print(f"Fetching districts for {state}...")

    for attempt in range(3):
        try:
            resp = requests.post(
                OVERPASS_URL,
                data={"data": query},
                headers=HEADERS,
                timeout=120,
            )
            if resp.status_code in (429, 504):
                wait = 2 ** (attempt + 1) * 10  # 20s, 40s, 80s
                print(f"  Got {resp.status_code}, retrying in {wait}s (attempt {attempt + 1}/3)...")
                time.sleep(wait)
                continue
            if resp.status_code != 200:
                print(f"  Error {resp.status_code} for {state}, skipping...")
                return []

            data = resp.json()
            districts = []
            for element in data.get("elements", []):
                tags = element.get("tags", {})
                name = tags.get("name:en") or tags.get("name")
                if name:
                    districts.append(name)

            print(f"  Found {len(districts)} districts")
            return districts

        except requests.exceptions.Timeout:
            wait = 2 ** (attempt + 1) * 10
            print(f"  Timeout, retrying in {wait}s (attempt {attempt + 1}/3)...")
            time.sleep(wait)
            continue
        except Exception as e:
            print(f"  Exception for {state}: {e}")
            return []

    print(f"  Failed after 3 retries for {state}, skipping.")
    return []


def insert_places(places: list[dict]):
    """Bulk insert places into the database."""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    inserted = 0
    skipped = 0
    for place in places:
        cur.execute(
            """
            INSERT INTO places (district, state)
            VALUES (%s, %s)
            ON CONFLICT (district) DO NOTHING
            """,
            (place["district"], place["state"]),
        )
        if cur.rowcount == 1:
            inserted += 1
        else:
            skipped += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"\nInserted {inserted} places, skipped {skipped} duplicates.")


def get_seeded_states() -> set[str]:
    """Get list of states that already have districts in the places table."""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT state FROM places")
    states = {row[0] for row in cur.fetchall()}
    cur.close()
    conn.close()
    return states


def main():
    all_places = []
    already_seeded = get_seeded_states()

    for state in STATES:
        if state in already_seeded:
            print(f"Skipping {state} (already seeded)")
            continue

        districts = fetch_districts_for_state(state)
        for district in districts:
            all_places.append({"district": district, "state": state})
        time.sleep(5)  # Be polite to Overpass API

    print(f"\nTotal new districts collected: {len(all_places)}")
    if all_places:
        insert_places(all_places)
    else:
        print("Nothing new to insert.")


if __name__ == "__main__":
    main()
