# Database Setup

## Prerequisites

- Homebrew installed
- PostgreSQL 17+ (PostGIS requires pg17 or later via Homebrew)
- PostGIS extension

## 1. Install PostgreSQL 17 & PostGIS

```bash
brew install postgresql@17 postgis
brew services stop postgresql@15
brew services start postgresql@17
```

> If you were previously on pg15, the upgrade means starting fresh. No data migration needed for a new project.

## 2. Create User

```bash
psql -d postgres -c "CREATE USER trvlr_admin WITH PASSWORD 'your_password' SUPERUSER CREATEDB CREATEROLE;"
```

- **User:** `trvlr_admin`
- **Password:** `your_password`
- **Privileges:** Superuser, can create databases and roles

## 3. Create Database

```bash
psql -d postgres -c "CREATE DATABASE trvlr_db OWNER trvlr_admin;"
```

- **Database:** `trvlr_db`
- **Owner:** `trvlr_admin`

## 4. Enable PostGIS Extension

```bash
psql -U trvlr_admin -d trvlr_db -c "CREATE EXTENSION IF NOT EXISTS postgis;"
```

## 5. Create Locations Table

```bash
psql -U trvlr_admin -d trvlr_db -c "
CREATE TABLE locations (
    id SERIAL PRIMARY KEY,
    coordinates GEOGRAPHY(POINT, 4326) NOT NULL,
    district VARCHAR(255) NOT NULL,
    state VARCHAR(255) NOT NULL,
    place_name VARCHAR(255) NOT NULL,
    location_type VARCHAR(100) NOT NULL,
    score INTEGER DEFAULT 0
);"
psql -U trvlr_admin -d trvlr_db -c "ALTER TABLE locations ADD CONSTRAINT unique_place_name UNIQUE (place_name);"
```## 6. Add Unique Constraint on place_name

```bash
psql -U trvlr_admin -d trvlr_db -c "ALTER TABLE locations ADD CONSTRAINT unique_place_name UNIQUE (place_name);"
```

## 7. Create Visits Table

```bash
psql -U trvlr_admin -d trvlr_db -c "
CREATE TABLE visits (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    location_id INTEGER NOT NULL REFERENCES locations(id),
    photo_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    score INTEGER DEFAULT 0,
    CONSTRAINT unique_user_location UNIQUE (user_id, location_id)
);"
```

## 8. Create User Scores Table

```bash
psql -U trvlr_admin -d trvlr_db -c "
CREATE TABLE user_scores (
    user_id VARCHAR(255) PRIMARY KEY,
    score INTEGER DEFAULT 0
);"
```

## 9. Create Places Table

```bash
psql -U trvlr_admin -d trvlr_db -c "
CREATE TABLE places (
    id SERIAL PRIMARY KEY,
    district VARCHAR(255) NOT NULL UNIQUE,
    state VARCHAR(255) NOT NULL
);"
```

Seed with all Indian districts (names from OpenStreetMap):
```bash
.venv/bin/python scripts/seed_places.py
```

### Schema

| Column      | Type         | Notes                                    |
|-------------|--------------|------------------------------------------|
| id          | SERIAL       | Primary key                              |
| user_id     | VARCHAR(255) | Identifier of the user                   |
| location_id | INTEGER      | FK to locations.id                       |
| created_at  | TIMESTAMP    | Defaults to now                          |
| score       | INTEGER      | Default 0, points earned for this visit  |

### Schema

| Column        | Type                    | Notes                          |
|---------------|-------------------------|--------------------------------|
| id            | SERIAL (auto increment) | Primary key                    |
| coordinates   | GEOGRAPHY(POINT, 4326)  | PostGIS lat/long point         |
| district      | VARCHAR(255)            | District name                  |
| state         | VARCHAR(255)            | State name                     |
| place_name    | VARCHAR(255)            | Name of the place              |
| location_type | VARCHAR(100)            | e.g. tourism:attraction, natural:waterfall |
| score         | INTEGER                 | Default 0, rating/popularity   |

## Connection String

```
postgresql://trvlr_admin:your_password@localhost:5432/trvlr_db
```

This is configured in the `.env` file at the project root as `DATABASE_URL`.

## Example Geo Queries

```sql
-- Insert a location
INSERT INTO locations (coordinates, district, state, place_name, score)
VALUES (ST_MakePoint(77.5946, 12.9716)::geography, 'Bangalore Urban', 'Karnataka', 'Lalbagh', 8);

-- Find locations within 10km of a point
SELECT * FROM locations
WHERE ST_DWithin(coordinates, ST_MakePoint(77.5, 13.0)::geography, 10000);

-- Get distance between a location and a point (in meters)
SELECT place_name, ST_Distance(coordinates, ST_MakePoint(77.5, 13.0)::geography) AS distance_m
FROM locations
ORDER BY distance_m;
```

## Quick Setup (all commands in sequence)

```bash
# Install & start
brew install postgresql@17 postgis
brew services stop postgresql@15
brew services start postgresql@17

# Create user, db, extension, table
psql -d postgres -c "CREATE USER trvlr_admin WITH PASSWORD 'your_password' SUPERUSER CREATEDB CREATEROLE;"
psql -d postgres -c "CREATE DATABASE trvlr_db OWNER trvlr_admin;"
psql -U trvlr_admin -d trvlr_db -c "CREATE EXTENSION IF NOT EXISTS postgis;"
psql -U trvlr_admin -d trvlr_db -c "
CREATE TABLE locations (
    id SERIAL PRIMARY KEY,
    coordinates GEOGRAPHY(POINT, 4326) NOT NULL,
    district VARCHAR(255) NOT NULL,
    state VARCHAR(255) NOT NULL,
    place_name VARCHAR(255) NOT NULL,
    location_type VARCHAR(100) NOT NULL,
    score INTEGER DEFAULT 0
);"
```


## Schema Migrations (ALTER commands)

Run these after initial setup to add newer columns:

```bash
# Add radius_m column
psql -U trvlr_admin -d trvlr_db -c "ALTER TABLE locations ADD COLUMN radius_m INTEGER DEFAULT 100;"

# Add boundary polygon column
psql -U trvlr_admin -d trvlr_db -c "ALTER TABLE locations ADD COLUMN boundary GEOGRAPHY(POLYGON, 4326);"
```

## Reset Data

To wipe locations and visits and start fresh (re-seed):

```bash
psql -U trvlr_admin -d trvlr_db -c "TRUNCATE TABLE visits, locations CASCADE;"
```
