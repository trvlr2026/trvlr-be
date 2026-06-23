"""
Image seed script: Downloads images from Wikimedia Commons for locations in the DB.
- Fetches place_name values from the locations table
- Main image: the primary Wikipedia article image
- Gallery images: additional images from Wikimedia Commons search
- Tracks completed locations in a CSV file for crash safety / resume support

Images are saved to downloads/<place_name>/main.jpg and downloads/<place_name>/gallery_1.jpg etc.
"""

import csv
import os
import re
import time

import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DATABASE_URL", "postgresql://trvlr_admin:trvlr2026!@localhost:5432/trvlr_db")

HEADERS = {
    "User-Agent": "trvlr-be/0.1 (image seed script; contact: dev@trvlr.app)",
}

DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "downloads")
PROGRESS_CSV = os.path.join(DOWNLOAD_DIR, "completed.csv")

MAX_GALLERY_IMAGES = 5


def sanitize_filename(name: str) -> str:
    """Make a filesystem-safe folder/file name."""
    return re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '_')


def search_wikipedia_title(place_name: str) -> str | None:
    """
    Search Wikipedia for the best matching article title.
    Useful when the exact place_name doesn't match a Wikipedia article.
    """
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "list": "search",
        "srsearch": place_name,
        "srlimit": "5",
        "format": "json",
    }

    resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        return None

    data = resp.json()
    results = data.get("query", {}).get("search", [])
    if results:
        return [r["title"] for r in results]
    return None


def verify_article_location(title: str, district: str, state: str) -> bool:
    """
    Verify that a Wikipedia article is about a place in the expected district/state.
    Checks the article extract for mentions of the district or state.
    """
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "titles": title,
        "prop": "extracts",
        "exintro": True,
        "explaintext": True,
        "format": "json",
    }

    resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        return False

    data = resp.json()
    pages = data.get("query", {}).get("pages", {})

    for page in pages.values():
        extract = (page.get("extract") or "").lower()
        # Check if either district or state is mentioned in the intro
        district_lower = district.lower()
        state_lower = state.lower()

        if state_lower in extract or district_lower in extract:
            return True

    return False


def fetch_main_image(place_name: str, district: str, state: str) -> str | None:
    """
    Fetch the main image URL from the Wikipedia article for the place.
    Uses the pageimages API to get the primary thumbnail.
    Falls back to Wikipedia search if exact title doesn't match.
    Verifies the article is about a place in the correct state/district.
    """
    url = "https://en.wikipedia.org/w/api.php"

    # Try exact title first, then fall back to search results
    titles_to_try = [place_name]
    searched_titles = search_wikipedia_title(place_name)
    if searched_titles:
        for t in searched_titles:
            if t != place_name:
                titles_to_try.append(t)

    for title in titles_to_try:
        # Verify the article is about the right location
        if title != place_name:
            if not verify_article_location(title, district, state):
                continue

        params = {
            "action": "query",
            "titles": title,
            "prop": "pageimages",
            "piprop": "original",
            "format": "json",
        }

        resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            continue

        data = resp.json()
        pages = data.get("query", {}).get("pages", {})

        for page in pages.values():
            # Skip missing pages
            if page.get("missing") is not None:
                continue
            original = page.get("original", {})
            if original.get("source"):
                if title != place_name:
                    print(f"  (matched via Wikipedia search: '{title}')")
                return original["source"]

    return None


def fetch_gallery_images(place_name: str, district: str, state: str, limit: int = MAX_GALLERY_IMAGES) -> list[str]:
    """
    Search Wikimedia Commons for actual photographs of the place.
    Filters out maps, logos, icons, diagrams, and other non-photo content.
    Uses district and state for more accurate search results.
    """
    url = "https://commons.wikimedia.org/w/api.php"

    # Try progressively broader searches
    search_terms = [
        f"{place_name} {district}",
        f"{place_name} {state}",
        place_name,
    ]

    # Patterns in filenames that indicate non-photo content
    junk_patterns = [
        "logo", "icon", "map", "diagram", "chart", "flag", "seal",
        "coat_of_arms", "symbol", "signature", "autograph", "svg",
        "plan", "layout", "sketch", "drawing", "illustration",
        "census", "graph", "table", "locator", "location_map",
        "india_", "karnataka_", "district_map", "blank_map",
    ]

    for search_term in search_terms:
        params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": search_term,
            "gsrnamespace": "6",  # File namespace
            "gsrlimit": str(limit * 4),  # Fetch extra since we'll filter many out
            "prop": "imageinfo",
            "iiprop": "url|mime|extmetadata",
            "iiurlwidth": "1200",
            "format": "json",
        }

        resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            continue

        data = resp.json()
        pages = data.get("query", {}).get("pages", {})

        image_urls = []
        for page in pages.values():
            imageinfo = page.get("imageinfo", [])
            if not imageinfo:
                continue

            info = imageinfo[0]
            mime = info.get("mime", "")

            # Only accept JPEG/PNG photos (skip SVG, GIF, etc.)
            if mime not in ("image/jpeg", "image/png", "image/webp"):
                continue

            # Check filename for junk patterns
            page_title = page.get("title", "").lower()
            if any(pat in page_title for pat in junk_patterns):
                continue

            # Check image dimensions — skip tiny images (likely icons/thumbnails)
            extmetadata = info.get("extmetadata", {})
            # Also check if the image description mentions the place or location
            description = extmetadata.get("ImageDescription", {}).get("value", "").lower()
            categories = extmetadata.get("Categories", {}).get("value", "").lower()

            # Relevance check: description or categories should mention the place, district, or state
            place_lower = place_name.lower()
            district_lower = district.lower()
            state_lower = state.lower()
            combined_text = f"{page_title} {description} {categories}"

            has_relevance = (
                place_lower in combined_text
                or district_lower in combined_text
                or state_lower in combined_text
            )

            if not has_relevance:
                continue

            # Prefer the thumbnail URL (resized) if available, else original
            thumb_url = info.get("thumburl") or info.get("url")
            if thumb_url:
                image_urls.append(thumb_url)

            if len(image_urls) >= limit:
                break

        if image_urls:
            return image_urls

    return []


def download_image(url: str, filepath: str) -> bool:
    """Download an image from URL and save to filepath."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        if resp.status_code != 200:
            return False

        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"    Error downloading: {e}")
        return False


def get_extension_from_url(url: str) -> str:
    """Extract file extension from URL."""
    # Get extension from the URL path
    path = url.split("?")[0]
    if ".jpg" in path.lower() or ".jpeg" in path.lower():
        return ".jpg"
    elif ".png" in path.lower():
        return ".png"
    elif ".svg" in path.lower():
        return ".svg"
    elif ".webp" in path.lower():
        return ".webp"
    return ".jpg"  # Default


def process_place(place_name: str, district: str, state: str):
    """Fetch and download main + gallery images for a place."""
    print(f"\n{'='*50}")
    print(f"Processing: {place_name} ({district}, {state})")

    # Create folder
    folder_name = sanitize_filename(place_name)
    place_dir = os.path.join(DOWNLOAD_DIR, folder_name)
    os.makedirs(place_dir, exist_ok=True)

    # Fetch main image
    print("  Fetching main image...")
    main_url = fetch_main_image(place_name, district, state)
    if main_url:
        ext = get_extension_from_url(main_url)
        main_path = os.path.join(place_dir, f"main{ext}")
        if download_image(main_url, main_path):
            print(f"  ✓ Main image saved: {main_path}")
        else:
            print("  ✗ Failed to download main image")
    else:
        print("  ✗ No main image found on Wikipedia")

    time.sleep(1)

    # Fetch gallery images
    print(f"  Fetching gallery images (max {MAX_GALLERY_IMAGES})...")
    gallery_urls = fetch_gallery_images(place_name, district, state)

    for i, img_url in enumerate(gallery_urls, 1):
        ext = get_extension_from_url(img_url)
        gallery_path = os.path.join(place_dir, f"gallery_{i}{ext}")
        if download_image(img_url, gallery_path):
            print(f"  ✓ Gallery {i} saved")
        else:
            print(f"  ✗ Gallery {i} failed")
        time.sleep(0.5)

    print(f"  Done: {place_name} → {place_dir}")


def load_completed() -> set[int]:
    """Load the set of already-completed location IDs from the progress CSV."""
    if not os.path.exists(PROGRESS_CSV):
        return set()

    completed = set()
    with open(PROGRESS_CSV, "r", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header
        for row in reader:
            if row and row[0].isdigit():
                completed.add(int(row[0]))
    return completed


def mark_completed(location_id: int, place_name: str):
    """Append a location to the progress CSV immediately after it's done."""
    write_header = not os.path.exists(PROGRESS_CSV)
    with open(PROGRESS_CSV, "a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["id", "place_name"])
        writer.writerow([location_id, place_name])


def get_locations_from_db() -> list[dict]:
    """Fetch all (id, place_name, district, state) from the locations table."""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("SELECT id, place_name, district, state FROM locations ORDER BY id")
    rows = [{"id": r[0], "place_name": r[1], "district": r[2], "state": r[3]} for r in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


def main():
    locations = get_locations_from_db()
    completed_ids = load_completed()

    pending = [loc for loc in locations if loc["id"] not in completed_ids]

    print(f"Found {len(locations)} locations in DB")
    print(f"Already completed: {len(completed_ids)}")
    print(f"Pending: {len(pending)}")
    print(f"Save directory: {DOWNLOAD_DIR}\n")

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    for loc in pending:
        process_place(loc["place_name"], loc["district"], loc["state"])
        mark_completed(loc["id"], loc["place_name"])
        time.sleep(2)  # Be polite to Wikimedia

    print(f"\n{'='*50}")
    print("All done!")
    print(f"Images saved in: {DOWNLOAD_DIR}")


if __name__ == "__main__":
    main()
