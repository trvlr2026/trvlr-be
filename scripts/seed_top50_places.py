"""
All-in-one script to:
  1. Define top 50 places in India (with coordinates)
  2. Fetch polygon geofences from OpenStreetMap
  3. Download hero images from Wikipedia
  4. Output a single CSV with all details

Usage:
  python3 scripts/seed_top50_places.py

Output:
  data/top_50_places_india.csv        — final CSV with all data
  data/hero_images/<place>.jpg        — downloaded hero images

Requirements:
  pip3 install requests
"""

import csv
import json
import math
import re
import time
from pathlib import Path

import requests

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data"
IMAGES_DIR = OUTPUT_DIR / "hero_images"
OUTPUT_CSV = OUTPUT_DIR / "top_50_places_india.csv"

HEADERS = {
    "User-Agent": "trvlr-seed-top50/1.0 (contact@brainybaba.com)",
}

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
WIKI_API = "https://en.wikipedia.org/w/api.php"


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: Top 50 Places Data
# ─────────────────────────────────────────────────────────────────────────────

PLACES = [
    {"rank": 1, "place_name": "Taj Mahal", "city_or_area": "Agra", "state": "Uttar Pradesh", "category": "Monument", "latitude": 27.1751, "longitude": 78.0421, "description": "Iconic white marble mausoleum and UNESCO World Heritage Site"},
    {"rank": 2, "place_name": "Varanasi Ghats", "city_or_area": "Varanasi", "state": "Uttar Pradesh", "category": "Pilgrimage", "latitude": 25.3176, "longitude": 83.0064, "description": "Ancient city on the Ganges with sacred bathing ghats"},
    {"rank": 3, "place_name": "Jaipur (Pink City)", "city_or_area": "Jaipur", "state": "Rajasthan", "category": "Heritage", "latitude": 26.9124, "longitude": 75.7873, "description": "Royal palaces and forts including Hawa Mahal and Amer Fort"},
    {"rank": 4, "place_name": "Golden Temple", "city_or_area": "Amritsar", "state": "Punjab", "category": "Pilgrimage", "latitude": 31.6200, "longitude": 74.8765, "description": "Holiest Sikh gurdwara with stunning gold architecture"},
    {"rank": 5, "place_name": "Goa Beaches", "city_or_area": "Goa", "state": "Goa", "category": "Beach", "latitude": 15.2993, "longitude": 74.1240, "description": "Popular coastal destination with beaches and Portuguese heritage"},
    {"rank": 6, "place_name": "Kerala Backwaters", "city_or_area": "Alleppey", "state": "Kerala", "category": "Nature", "latitude": 9.4981, "longitude": 76.3388, "description": "Network of serene lagoons and canals with houseboat cruises"},
    {"rank": 7, "place_name": "Leh-Ladakh", "city_or_area": "Leh", "state": "Ladakh", "category": "Adventure", "latitude": 34.1526, "longitude": 77.5771, "description": "High-altitude desert with monasteries and mountain passes"},
    {"rank": 8, "place_name": "Hampi", "city_or_area": "Hampi", "state": "Karnataka", "category": "Heritage", "latitude": 15.3350, "longitude": 76.4600, "description": "Ruins of the Vijayanagara Empire and UNESCO site"},
    {"rank": 9, "place_name": "Rishikesh", "city_or_area": "Rishikesh", "state": "Uttarakhand", "category": "Pilgrimage", "latitude": 30.0869, "longitude": 78.2676, "description": "Yoga capital of the world on the banks of the Ganges"},
    {"rank": 10, "place_name": "Udaipur", "city_or_area": "Udaipur", "state": "Rajasthan", "category": "Heritage", "latitude": 24.5854, "longitude": 73.7125, "description": "Romantic lakeside city with grand palaces"},
    {"rank": 11, "place_name": "Mysore Palace", "city_or_area": "Mysuru", "state": "Karnataka", "category": "Heritage", "latitude": 12.3052, "longitude": 76.6552, "description": "Grand royal palace with Indo-Saracenic architecture"},
    {"rank": 12, "place_name": "Tirupati Balaji", "city_or_area": "Tirupati", "state": "Andhra Pradesh", "category": "Pilgrimage", "latitude": 13.6833, "longitude": 79.3472, "description": "Most visited Hindu temple in the world"},
    {"rank": 13, "place_name": "Manali", "city_or_area": "Manali", "state": "Himachal Pradesh", "category": "Hill Station", "latitude": 32.2396, "longitude": 77.1887, "description": "Popular Himalayan hill station with snow and adventure sports"},
    {"rank": 14, "place_name": "Darjeeling", "city_or_area": "Darjeeling", "state": "West Bengal", "category": "Hill Station", "latitude": 27.0360, "longitude": 88.2627, "description": "Tea gardens and Himalayan views with toy train"},
    {"rank": 15, "place_name": "Shimla", "city_or_area": "Shimla", "state": "Himachal Pradesh", "category": "Hill Station", "latitude": 31.1048, "longitude": 77.1734, "description": "Former British summer capital with colonial architecture"},
    {"rank": 16, "place_name": "Munnar", "city_or_area": "Munnar", "state": "Kerala", "category": "Hill Station", "latitude": 10.0889, "longitude": 77.0595, "description": "Rolling tea plantations in the Western Ghats"},
    {"rank": 17, "place_name": "Khajuraho Temples", "city_or_area": "Khajuraho", "state": "Madhya Pradesh", "category": "Heritage", "latitude": 24.8318, "longitude": 79.9199, "description": "UNESCO site with famous erotic sculptures"},
    {"rank": 18, "place_name": "Ajanta and Ellora Caves", "city_or_area": "Aurangabad", "state": "Maharashtra", "category": "Heritage", "latitude": 20.5519, "longitude": 75.7033, "description": "Rock-cut Buddhist and Hindu cave temples"},
    {"rank": 19, "place_name": "Red Fort", "city_or_area": "Delhi", "state": "Delhi", "category": "Monument", "latitude": 28.6562, "longitude": 77.2410, "description": "Mughal-era fort and symbol of India"},
    {"rank": 20, "place_name": "Qutub Minar", "city_or_area": "Delhi", "state": "Delhi", "category": "Monument", "latitude": 28.5245, "longitude": 77.1855, "description": "Tallest brick minaret in the world"},
    {"rank": 21, "place_name": "Gateway of India", "city_or_area": "Mumbai", "state": "Maharashtra", "category": "Monument", "latitude": 18.9220, "longitude": 72.8347, "description": "Iconic waterfront arch built during British era"},
    {"rank": 22, "place_name": "Meenakshi Temple", "city_or_area": "Madurai", "state": "Tamil Nadu", "category": "Pilgrimage", "latitude": 9.9195, "longitude": 78.1193, "description": "Ancient Dravidian temple with towering gopurams"},
    {"rank": 23, "place_name": "Rameswaram", "city_or_area": "Rameswaram", "state": "Tamil Nadu", "category": "Pilgrimage", "latitude": 9.2876, "longitude": 79.3129, "description": "One of the four sacred Char Dham pilgrimage sites"},
    {"rank": 24, "place_name": "Jagannath Temple", "city_or_area": "Puri", "state": "Odisha", "category": "Pilgrimage", "latitude": 19.8050, "longitude": 85.8181, "description": "One of the Char Dhams famous for Rath Yatra"},
    {"rank": 25, "place_name": "Konark Sun Temple", "city_or_area": "Konark", "state": "Odisha", "category": "Heritage", "latitude": 19.8876, "longitude": 86.0945, "description": "13th-century temple shaped as a giant chariot"},
    {"rank": 26, "place_name": "Valley of Flowers", "city_or_area": "Chamoli", "state": "Uttarakhand", "category": "Nature", "latitude": 30.7280, "longitude": 79.6050, "description": "UNESCO site with endemic Himalayan alpine flora"},
    {"rank": 27, "place_name": "Jim Corbett National Park", "city_or_area": "Nainital", "state": "Uttarakhand", "category": "Wildlife", "latitude": 29.5300, "longitude": 78.7747, "description": "India oldest national park famous for Bengal tigers"},
    {"rank": 28, "place_name": "Ranthambore National Park", "city_or_area": "Sawai Madhopur", "state": "Rajasthan", "category": "Wildlife", "latitude": 26.0173, "longitude": 76.5026, "description": "Tiger reserve with ancient fort ruins"},
    {"rank": 29, "place_name": "Kaziranga National Park", "city_or_area": "Kaziranga", "state": "Assam", "category": "Wildlife", "latitude": 26.5775, "longitude": 93.1711, "description": "UNESCO site home to one-horned rhinoceros"},
    {"rank": 30, "place_name": "Sundarbans", "city_or_area": "South 24 Parganas", "state": "West Bengal", "category": "Wildlife", "latitude": 21.9497, "longitude": 89.1833, "description": "Largest mangrove forest and Royal Bengal Tiger habitat"},
    {"rank": 31, "place_name": "Jaisalmer", "city_or_area": "Jaisalmer", "state": "Rajasthan", "category": "Heritage", "latitude": 26.9157, "longitude": 70.9083, "description": "Desert fort city with sand dunes and havelis"},
    {"rank": 32, "place_name": "Jodhpur", "city_or_area": "Jodhpur", "state": "Rajasthan", "category": "Heritage", "latitude": 26.2389, "longitude": 73.0243, "description": "Mehrangarh Fort and blue-painted old city"},
    {"rank": 33, "place_name": "Ooty", "city_or_area": "Ooty", "state": "Tamil Nadu", "category": "Hill Station", "latitude": 11.4102, "longitude": 76.6950, "description": "Queen of hill stations in the Nilgiri mountains"},
    {"rank": 34, "place_name": "Coorg", "city_or_area": "Kodagu", "state": "Karnataka", "category": "Nature", "latitude": 12.3375, "longitude": 75.8069, "description": "Coffee plantations and misty Western Ghats hills"},
    {"rank": 35, "place_name": "Andaman Islands", "city_or_area": "Port Blair", "state": "Andaman and Nicobar Islands", "category": "Beach", "latitude": 11.6234, "longitude": 92.7265, "description": "Pristine beaches and coral reefs"},
    {"rank": 36, "place_name": "Haridwar", "city_or_area": "Haridwar", "state": "Uttarakhand", "category": "Pilgrimage", "latitude": 29.9457, "longitude": 78.1642, "description": "Sacred city with Ganga Aarti at Har Ki Pauri"},
    {"rank": 37, "place_name": "Bodh Gaya", "city_or_area": "Gaya", "state": "Bihar", "category": "Pilgrimage", "latitude": 24.6961, "longitude": 84.9911, "description": "Place of Buddha enlightenment under the Bodhi Tree"},
    {"rank": 38, "place_name": "Shirdi", "city_or_area": "Shirdi", "state": "Maharashtra", "category": "Pilgrimage", "latitude": 19.7668, "longitude": 74.4778, "description": "Temple of Sai Baba visited by millions annually"},
    {"rank": 39, "place_name": "Dwarka", "city_or_area": "Dwarka", "state": "Gujarat", "category": "Pilgrimage", "latitude": 22.2394, "longitude": 68.9678, "description": "One of the Char Dhams associated with Lord Krishna"},
    {"rank": 40, "place_name": "Somnath Temple", "city_or_area": "Somnath", "state": "Gujarat", "category": "Pilgrimage", "latitude": 20.8880, "longitude": 70.4012, "description": "First among the twelve Jyotirlingas of Shiva"},
    {"rank": 41, "place_name": "Amarnath Cave", "city_or_area": "Pahalgam", "state": "Jammu and Kashmir", "category": "Pilgrimage", "latitude": 34.2148, "longitude": 75.5009, "description": "High-altitude ice Shiva lingam shrine"},
    {"rank": 42, "place_name": "Kedarnath", "city_or_area": "Kedarnath", "state": "Uttarakhand", "category": "Pilgrimage", "latitude": 30.7346, "longitude": 79.0669, "description": "Char Dham temple in the Himalayas at 3500m"},
    {"rank": 43, "place_name": "Badrinath", "city_or_area": "Badrinath", "state": "Uttarakhand", "category": "Pilgrimage", "latitude": 30.7433, "longitude": 79.4938, "description": "Sacred Char Dham temple dedicated to Lord Vishnu"},
    {"rank": 44, "place_name": "Nainital", "city_or_area": "Nainital", "state": "Uttarakhand", "category": "Hill Station", "latitude": 29.3919, "longitude": 79.4542, "description": "Lake town surrounded by Kumaon hills"},
    {"rank": 45, "place_name": "Mount Abu", "city_or_area": "Mount Abu", "state": "Rajasthan", "category": "Hill Station", "latitude": 24.5926, "longitude": 72.7156, "description": "Only hill station in Rajasthan with Dilwara Temples"},
    {"rank": 46, "place_name": "Hawa Mahal", "city_or_area": "Jaipur", "state": "Rajasthan", "category": "Monument", "latitude": 26.9239, "longitude": 75.8267, "description": "Palace of Winds with 953 small windows"},
    {"rank": 47, "place_name": "Charminar", "city_or_area": "Hyderabad", "state": "Telangana", "category": "Monument", "latitude": 17.3616, "longitude": 78.4747, "description": "Iconic 16th-century mosque and monument"},
    {"rank": 48, "place_name": "Victoria Memorial", "city_or_area": "Kolkata", "state": "West Bengal", "category": "Monument", "latitude": 22.5448, "longitude": 88.3426, "description": "Grand marble building dedicated to Queen Victoria"},
    {"rank": 49, "place_name": "Statue of Unity", "city_or_area": "Kevadia", "state": "Gujarat", "category": "Monument", "latitude": 21.8380, "longitude": 73.7191, "description": "World tallest statue at 182 meters"},
    {"rank": 50, "place_name": "Spiti Valley", "city_or_area": "Spiti", "state": "Himachal Pradesh", "category": "Adventure", "latitude": 32.2460, "longitude": 78.0190, "description": "Remote high-altitude cold desert with ancient monasteries"},
]


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: Fetch Polygon Geofences from OpenStreetMap
# ─────────────────────────────────────────────────────────────────────────────

def fetch_polygon(place_name: str, lat: float, lon: float, state: str) -> tuple[dict, str]:
    """
    Query OSM Nominatim for polygon boundary.
    Returns (geojson_dict, source_string).
    """
    params = {
        "q": f"{place_name}, {state}, India",
        "format": "jsonv2",
        "polygon_geojson": 1,
        "limit": 1,
    }

    try:
        resp = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        results = resp.json()

        if results and "geojson" in results[0]:
            geojson = results[0]["geojson"]
            if geojson.get("type") in ("Polygon", "MultiPolygon"):
                return geojson, "osm"
    except requests.RequestException:
        pass

    # Fallback: circular geofence
    return generate_circular_geofence(lat, lon, 500), "circular_fallback_500m"


def generate_circular_geofence(lat: float, lon: float, radius_m: int = 500, points: int = 16) -> dict:
    """Generate approximate circular polygon."""
    coords = []
    for i in range(points):
        angle = 2 * math.pi * i / points
        dlat = (radius_m * math.cos(angle)) / 111320
        dlon = (radius_m * math.sin(angle)) / (111320 * math.cos(math.radians(lat)))
        coords.append([round(lon + dlon, 6), round(lat + dlat, 6)])
    coords.append(coords[0])
    return {"type": "Polygon", "coordinates": [coords]}


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3: Fetch Hero Images from Wikipedia
# ─────────────────────────────────────────────────────────────────────────────

def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*()]+', "", name)
    cleaned = re.sub(r"\s+", "_", cleaned.strip())
    return cleaned.lower()


def fetch_wiki_image(place_name: str, state: str) -> str | None:
    """Search Wikipedia and return the hero image URL."""
    # Search for page
    params = {
        "action": "query",
        "list": "search",
        "srsearch": f"{place_name} {state} India",
        "format": "json",
        "srlimit": 1,
    }
    try:
        resp = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        results = resp.json().get("query", {}).get("search", [])
        if not results:
            return None
        page_title = results[0]["title"]
    except requests.RequestException:
        return None

    time.sleep(0.5)

    # Get page image (1200px thumbnail)
    params = {
        "action": "query",
        "titles": page_title,
        "prop": "pageimages",
        "format": "json",
        "pithumbsize": 1200,
    }
    try:
        resp = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        pages = resp.json().get("query", {}).get("pages", {})
        for pid, pdata in pages.items():
            if pid == "-1":
                continue
            thumb = pdata.get("thumbnail", {})
            if thumb:
                return thumb.get("source")
    except requests.RequestException:
        pass

    return None


def download_image(url: str, dest: Path) -> bool:
    """Download image to destination."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        resp.raise_for_status()
        if "image" not in resp.headers.get("content-type", ""):
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        if dest.stat().st_size < 1000:
            dest.unlink()
            return False
        return True
    except requests.RequestException:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("SEED TOP 50 PLACES IN INDIA")
    print("=" * 60)
    print(f"Output CSV:    {OUTPUT_CSV}")
    print(f"Hero images:   {IMAGES_DIR}")
    print(f"Places:        {len(PLACES)}")
    print("=" * 60)

    results = []

    for i, place in enumerate(PLACES, 1):
        name = place["place_name"]
        state = place["state"]
        lat = place["latitude"]
        lon = place["longitude"]

        print(f"\n[{i}/{len(PLACES)}] {name} ({state})")

        # ── Geofence ──
        print("  Fetching geofence...", end=" ", flush=True)
        geojson, geofence_source = fetch_polygon(name, lat, lon, state)
        if geofence_source == "osm":
            num_pts = len(geojson.get("coordinates", [[]])[0]) if geojson["type"] == "Polygon" else "multi"
            print(f"OSM polygon ({num_pts} points)")
        else:
            print("Fallback circular (500m)")
        time.sleep(1.1)  # Nominatim rate limit

        # ── Hero Image ──
        print("  Fetching hero image...", end=" ", flush=True)
        image_url = fetch_wiki_image(name, state)
        time.sleep(0.5)

        image_filename = ""
        if image_url and ".svg" not in image_url.lower():
            safe_name = sanitize_filename(name)
            ext = ".png" if ".png" in image_url.lower() else ".jpg"
            image_filename = f"{safe_name}{ext}"
            dest = IMAGES_DIR / image_filename

            if download_image(image_url, dest):
                size_kb = dest.stat().st_size // 1024
                print(f"OK ({size_kb}KB)")
            else:
                image_filename = ""
                print("Download failed")
        else:
            print("Not found")

        time.sleep(0.5)

        # ── Build Row ──
        row = {
            "rank": place["rank"],
            "place_name": name,
            "city_or_area": place["city_or_area"],
            "state": state,
            "category": place["category"],
            "latitude": lat,
            "longitude": lon,
            "description": place["description"],
            "geofence_polygon": json.dumps(geojson),
            "geofence_source": geofence_source,
            "image_filename": image_filename,
        }
        results.append(row)

    # ── Write CSV ──
    fieldnames = [
        "rank", "place_name", "city_or_area", "state", "category",
        "latitude", "longitude", "description",
        "geofence_polygon", "geofence_source", "image_filename",
    ]

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    # ── Summary ──
    osm_count = sum(1 for r in results if r["geofence_source"] == "osm")
    img_count = sum(1 for r in results if r["image_filename"])

    print("\n" + "=" * 60)
    print("DONE!")
    print(f"  Total places:       {len(results)}")
    print(f"  OSM geofences:      {osm_count}/{len(results)}")
    print(f"  Circular fallback:  {len(results) - osm_count}/{len(results)}")
    print(f"  Images downloaded:  {img_count}/{len(results)}")
    print(f"  CSV:                {OUTPUT_CSV}")
    print(f"  Images:             {IMAGES_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
