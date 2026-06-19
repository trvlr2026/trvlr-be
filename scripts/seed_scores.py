"""
Scoring script: Calculates a 1-100 score for each location based on:
1. Wikipedia pageviews (popularity signal)
2. location_type (type-based base score)
3. Wikipedia article existence (wiki bonus)

Only processes locations with score=0 (retryable).
Retries on 429/503/504 with exponential backoff.

Formula: score = min(100, max(1, type_base_score + pageview_score + wiki_bonus))
"""

import math
import os
import time
import urllib.parse

import requests
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DATABASE_URL", "postgresql://trvlr_admin:trvlr2026!@localhost:5432/trvlr_db")

WIKI_PAGEVIEWS_URL = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"
    "/en.wikipedia/all-access/all-agents/{title}/monthly/20250101/20260101"
)

HEADERS = {
    "User-Agent": "trvlr-be/0.1 (scoring script)",
}

# --- Type-based base scores (Tier E from scoring-system.md) ---

TYPE_BASE_SCORES = {
    "tourism:attraction": 30,
    "historic:fort": 28,
    "historic:castle": 28,
    "historic:monument": 25,
    "historic:archaeological_site": 25,
    "leisure:nature_reserve": 25,
    "natural:waterfall": 25,
    "tourism:museum": 22,
    "natural:peak": 20,
    "tourism:zoo": 20,
    "natural:cave_entrance": 18,
    "leisure:park": 18,
    "tourism:viewpoint": 15,
    "leisure:garden": 15,
    "historic:ruins": 15,
    "historic:temple": 20,
    "tourism:artwork": 12,
    "leisure:sports_centre": 10,
    "leisure:playground": 10,
    "leisure:swimming_pool": 8,
    "leisure:stadium": 12,
    "natural:hot_spring": 20,
    "natural:water": 15,
    "tourism:hotel": 5,
    "tourism:guest_house": 5,
    "tourism:camp_site": 10,
    "tourism:picnic_site": 8,
    "tourism:theme_park": 22,
    "leisure:water_park": 18,
}

DEFAULT_TYPE_SCORE = 10


# --- Helpers ---


def request_with_retry(url: str) -> requests.Response | None:
    """GET request with retry on 429/503/504, exponential backoff."""
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)

            if resp.status_code in (429, 503, 504):
                wait = 2 ** (attempt + 1) * 5  # 10s, 20s, 40s
                print(f"    Got {resp.status_code}, retrying in {wait}s (attempt {attempt + 1}/3)...")
                time.sleep(wait)
                continue

            return resp

        except requests.exceptions.Timeout:
            wait = 2 ** (attempt + 1) * 5
            print(f"    Timeout, retrying in {wait}s (attempt {attempt + 1}/3)...")
            time.sleep(wait)
            continue
        except Exception as e:
            print(f"    Exception: {e}")
            return None

    print("    Failed after 3 retries.")
    return None


def get_type_base_score(location_type: str) -> int:
    """Get base score from location_type."""
    return TYPE_BASE_SCORES.get(location_type, DEFAULT_TYPE_SCORE)


def normalize_name_for_wiki(name: str) -> str:
    """Convert a place name to a Wikipedia article title format."""
    # Replace spaces with underscores, capitalize first letter
    title = name.strip().replace(" ", "_")
    return title


def fetch_pageviews(title: str) -> int | None:
    """
    Fetch average monthly pageviews from Wikipedia.
    Returns avg views/month, or None if we should retry later (API overloaded).
    Returns 0 if article doesn't exist (valid result — no pageviews).
    """
    encoded_title = urllib.parse.quote(title, safe="")
    url = WIKI_PAGEVIEWS_URL.format(title=encoded_title)

    for attempt in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)

            if resp.status_code == 404:
                return 0  # Article doesn't exist — valid, score by type only

            if resp.status_code in (429, 503, 504):
                wait = 2 ** (attempt + 1) * 5
                print(f"    Wiki API {resp.status_code}, retrying in {wait}s...")
                time.sleep(wait)
                continue

            if resp.status_code != 200:
                # Other errors (400, etc.) — treat as "no article"
                return 0

            data = resp.json()
            items = data.get("items", [])
            if not items:
                return 0
            total = sum(item.get("views", 0) for item in items)
            return total // len(items)

        except requests.exceptions.Timeout:
            wait = 2 ** (attempt + 1) * 5
            print(f"    Wiki API timeout, retrying in {wait}s...")
            time.sleep(wait)
            continue
        except Exception:
            return 0

    # All retries exhausted on 429/503/504 — this is a real failure
    return None


def calculate_pageview_score(avg_views: int) -> int:
    """
    Convert average monthly pageviews to a 0-60 score using log scale.
    - 0 views → 0
    - 100 views → ~15
    - 1000 views → ~30
    - 5000 views → ~45
    - 20000+ views → 55-60
    """
    if avg_views <= 0:
        return 0

    # Log scale: log10(views) mapped to 0-60
    # log10(100)=2, log10(1000)=3, log10(10000)=4, log10(100000)=5
    log_views = math.log10(avg_views)
    # Scale: 2→15, 3→30, 4→45, 5→60
    score = int((log_views - 1) * 15)
    return max(0, min(60, score))


def calculate_wiki_bonus(has_article: bool) -> int:
    """Bonus for having a Wikipedia article."""
    return 5 if has_article else 0


# --- DB operations ---


def get_unscored_locations() -> list[dict]:
    """Get all locations with score=0."""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, place_name, location_type, district, state
        FROM locations
        WHERE score = 0
        ORDER BY id
    """)
    rows = [
        {"id": r[0], "name": r[1], "location_type": r[2], "district": r[3], "state": r[4]}
        for r in cur.fetchall()
    ]
    cur.close()
    conn.close()
    return rows


def update_score(location_id: int, score: int):
    """Update score for a single location."""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("UPDATE locations SET score = %s WHERE id = %s", (score, location_id))
    conn.commit()
    cur.close()
    conn.close()


# --- Main ---


def compute_score(location: dict) -> int | None:
    """
    Compute score for a location.
    Returns score (1-100) or None if we should skip (API failure, retry later).
    """
    name = location["name"]
    location_type = location["location_type"]

    # Step 1: Type-based base score
    type_score = get_type_base_score(location_type)

    # Step 2: Try Wikipedia pageviews
    wiki_title = normalize_name_for_wiki(name)
    pageviews = fetch_pageviews(wiki_title)

    if pageviews is None:
        # API call failed after retries — skip, leave score=0 for next run
        return None

    # Step 3: Calculate components
    pageview_score = calculate_pageview_score(pageviews)
    wiki_bonus = calculate_wiki_bonus(pageviews > 0)

    # Step 4: Combine
    total = type_score + pageview_score + wiki_bonus
    final_score = max(1, min(100, total))

    return final_score


def main():
    locations = get_unscored_locations()
    print(f"Found {len(locations)} locations with score=0\n")

    if not locations:
        print("Nothing to score. All locations already have scores.")
        return

    scored = 0
    skipped = 0

    for i, loc in enumerate(locations, 1):
        print(f"[{i}/{len(locations)}] {loc['name']} ({loc['location_type']})")

        score = compute_score(loc)

        if score is None:
            print(f"  → Skipped (API failure, will retry next run)")
            skipped += 1
            continue

        update_score(loc["id"], score)
        print(f"  → Score: {score}")
        scored += 1

        # Rate limit: Wikipedia allows 200 req/s, but be polite
        time.sleep(0.2)

    print(f"\n{'='*50}")
    print(f"Done! Scored: {scored}, Skipped (retry later): {skipped}")
    print(f"Remaining unscored: {len(locations) - scored}")


if __name__ == "__main__":
    main()
