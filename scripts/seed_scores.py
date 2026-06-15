"""
Score script: Calculates a 1-100 popularity score for each location
using OSM tag signals + Wikipedia pageview data.

Scoring breakdown (1-100):
- OSM tag signals: 0-30 points (notability/richness)
- Wikipedia pageviews: 0-70 points (actual public interest)

Run after seed_locations.py has populated the locations table.
"""

import math
import time
import urllib.parse

import requests
import psycopg2

DB_URL = "postgresql://trvlr_admin:trvlr2026!@localhost:5432/trvlr_db"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
WIKI_PAGEVIEWS_URL = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"
    "/en.wikipedia/all-access/all-agents/{title}/monthly/20250101/20260101"
)

HEADERS = {
    "User-Agent": "trvlr-be/0.1 (scoring script; contact: dev@trvlr.app)",
}

# --- OSM Tag Scoring (0-30 points) ---

# Points for having these tags present
TAG_PRESENCE_SCORES = {
    "wikipedia": 8,
    "wikidata": 5,
    "website": 4,
    "contact:website": 4,
    "opening_hours": 3,
    "phone": 2,
    "contact:phone": 2,
    "description": 3,
    "image": 3,
}

# Points for specific tag values (tourism/historic significance)
TYPE_VALUE_SCORES = {
    "tourism:attraction": 6,
    "tourism:museum": 5,
    "tourism:zoo": 5,
    "tourism:theme_park": 5,
    "tourism:viewpoint": 4,
    "tourism:artwork": 3,
    "historic:fort": 6,
    "historic:monument": 5,
    "historic:castle": 6,
    "historic:ruins": 4,
    "historic:temple": 5,
    "historic:archaeological_site": 5,
    "natural:waterfall": 5,
    "natural:peak": 4,
    "natural:cave_entrance": 4,
    "natural:hot_spring": 4,
    "leisure:park": 3,
    "leisure:nature_reserve": 5,
    "leisure:garden": 3,
    "leisure:water_park": 4,
}

# Points for multiple language names
def language_name_score(tags: dict) -> int:
    """More translations = more internationally known."""
    lang_names = sum(1 for k in tags if k.startswith("name:"))
    if lang_names >= 5:
        return 5
    elif lang_names >= 3:
        return 3
    elif lang_names >= 1:
        return 1
    return 0


def calculate_osm_score(tags: dict) -> int:
    """Calculate OSM-based score (0-30) from element tags."""
    score = 0

    # Tag presence
    for tag, points in TAG_PRESENCE_SCORES.items():
        if tag in tags:
            score += points

    # Type value significance
    for key in ["tourism", "historic", "natural", "leisure"]:
        if key in tags:
            type_key = f"{key}:{tags[key]}"
            score += TYPE_VALUE_SCORES.get(type_key, 1)

    # Language names
    score += language_name_score(tags)

    return min(30, score)


# --- Wikipedia Pageview Scoring (0-70 points) ---

def get_wikipedia_title(tags: dict) -> str | None:
    """Extract Wikipedia article title from OSM tags."""
    wiki = tags.get("wikipedia", "")
    if wiki.startswith("en:"):
        return wiki[3:]
    elif ":" in wiki:
        # Non-English article, skip for now
        return None
    elif wiki:
        return wiki
    return None


def fetch_pageviews(title: str) -> int:
    """Fetch total monthly pageviews from Wikipedia API."""
    encoded_title = urllib.parse.quote(title.replace(" ", "_"), safe="")
    url = WIKI_PAGEVIEWS_URL.format(title=encoded_title)

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return 0
        data = resp.json()
        items = data.get("items", [])
        total = sum(item.get("views", 0) for item in items)
        # Return average monthly views
        months = len(items) if items else 1
        return total // months
    except Exception:
        return 0


def calculate_pageview_score(views: int, max_views: int) -> int:
    """Normalize pageviews to 0-70 using log scale."""
    if views <= 0 or max_views <= 0:
        return 0
    # Log scale normalization
    log_views = math.log1p(views)
    log_max = math.log1p(max_views)
    normalized = log_views / log_max
    return min(70, round(normalized * 70))


# --- Fetch OSM tags for existing locations ---

def fetch_osm_tags_for_location(place_name: str, lat: float, lon: float) -> dict:
    """Fetch OSM tags for a specific location by searching nearby."""
    query = f"""[out:json][timeout:30];
(
  node["name"="{place_name}"](around:500,{lat},{lon});
  way["name"="{place_name}"](around:500,{lat},{lon});
);
out tags;"""

    try:
        resp = requests.post(
            OVERPASS_URL,
            data={"data": query},
            headers=HEADERS,
            timeout=30,
        )
        if resp.status_code != 200:
            return {}
        data = resp.json()
        elements = data.get("elements", [])
        if elements:
            return elements[0].get("tags", {})
    except Exception:
        pass
    return {}


# --- Main ---

def get_locations():
    """Fetch all locations from the database."""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, place_name, ST_Y(coordinates::geometry) as lat, ST_X(coordinates::geometry) as lon
        FROM locations
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def update_score(location_id: int, score: int):
    """Update the score for a location."""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("UPDATE locations SET score = %s WHERE id = %s", (score, location_id))
    conn.commit()
    cur.close()
    conn.close()


def main():
    locations = get_locations()
    print(f"Scoring {len(locations)} locations...\n")

    # Phase 1: Collect OSM scores and Wikipedia pageviews
    scored = []

    for loc_id, place_name, lat, lon in locations:
        print(f"Processing: {place_name}...")

        # Fetch OSM tags
        tags = fetch_osm_tags_for_location(place_name, lat, lon)
        osm_score = calculate_osm_score(tags)

        # Fetch Wikipedia pageviews
        wiki_title = get_wikipedia_title(tags)
        pageviews = 0
        if wiki_title:
            pageviews = fetch_pageviews(wiki_title)
            print(f"  Wikipedia: '{wiki_title}' → {pageviews} avg views/month")
            time.sleep(0.1)  # Be polite to Wikipedia API

        print(f"  OSM score: {osm_score}/30, Pageviews: {pageviews}")

        scored.append({
            "id": loc_id,
            "name": place_name,
            "osm_score": osm_score,
            "pageviews": pageviews,
        })

        time.sleep(2)  # Be polite to Overpass API

    # Phase 2: Normalize pageviews and compute final scores
    max_views = max((s["pageviews"] for s in scored), default=1)
    if max_views == 0:
        max_views = 1

    print(f"\nMax pageviews: {max_views}")
    print("=" * 60)

    for item in scored:
        pageview_score = calculate_pageview_score(item["pageviews"], max_views)
        final_score = max(1, item["osm_score"] + pageview_score)  # Minimum score of 1
        final_score = min(100, final_score)  # Cap at 100

        print(f"{item['name']:40s} OSM={item['osm_score']:2d} + Wiki={pageview_score:2d} = {final_score:3d}")
        update_score(item["id"], final_score)

    print(f"\nDone! Updated scores for {len(scored)} locations.")


if __name__ == "__main__":
    main()
