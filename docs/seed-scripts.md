# Seed Scripts

Run these from the project root (`/opt/trvlr-be` on VPS or local).

## Seed Locations

Fetches tourism/nature/historic POIs from OpenStreetMap for Karnataka districts.

```bash
source .venv/bin/activate
.venv/bin/python scripts/seed_locations.py
```

- Sources: Overpass API (bounding box queries)
- Districts: Bengaluru Urban, Bengaluru South, Bengaluru North, Chikkaballapur, Chitradurga, Davanagere, Kolar, Shimoga, Tumakuru
- Skips duplicates (upsert on place_name)
- Takes ~1 minute (5s delay between districts)

## Seed Places

Fetches all Indian districts from OpenStreetMap (exact OSM names).

```bash
.venv/bin/python scripts/seed_places.py
```

- Sources: Overpass API (admin_level=5 boundaries per state)
- Covers all 36 states/UTs
- Retryable: skips states already seeded
- Takes ~3 minutes (5s delay between states)

## Randomize Scores

Assigns random scores (1-100) to all locations.

```bash
# On VPS
sudo -u postgres psql -d trvlr_db -c "UPDATE locations SET score = floor(random() * 100 + 1);"

# On local Mac
psql -U trvlr_admin -d trvlr_db -c "UPDATE locations SET score = floor(random() * 100 + 1);"
```

## Run Order

1. `seed_locations.py` (populate locations)
2. Randomize scores (assign scores to locations)
3. `seed_places.py` (populate districts/states reference table)

## Reset Data

To wipe locations and visits and start fresh:

```bash
# On VPS
sudo -u postgres psql -d trvlr_db -c "TRUNCATE TABLE visits, locations CASCADE;"

# On local Mac
psql -U trvlr_admin -d trvlr_db -c "TRUNCATE TABLE visits, locations CASCADE;"
```
