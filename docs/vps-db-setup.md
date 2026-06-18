# VPS Database Setup (Ubuntu 24.04)

Complete guide to install PostgreSQL + PostGIS on the Contabo VPS and make it accessible externally.

## 1. Install PostgreSQL 17 + PostGIS

```bash
# Add PostgreSQL official repo
sudo apt install -y curl ca-certificates
sudo install -d /usr/share/postgresql-common/pgdg
sudo curl -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc --fail https://www.postgresql.org/media/keys/ACCC4CF8.asc
echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" | sudo tee /etc/apt/sources.list.d/pgdg.list

# Install PostgreSQL 17 + PostGIS
sudo apt update
sudo apt install -y postgresql-18 postgresql-contrib postgis postgresql-18-postgis-3
```

## 2. Start and Enable PostgreSQL

```bash
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

## 3. Create User and Database

```bash
sudo -u postgres psql -c "CREATE USER trvlr_admin WITH PASSWORD 'your_password' SUPERUSER CREATEDB CREATEROLE;"
sudo -u postgres psql -c "CREATE DATABASE trvlr_db OWNER trvlr_admin;"
sudo -u postgres psql -d trvlr_db -c "CREATE EXTENSION IF NOT EXISTS postgis;"
```

## 4. Create Tables

```bash
sudo -u postgres psql -d trvlr_db -c "
CREATE TABLE locations (
    id SERIAL PRIMARY KEY,
    coordinates GEOGRAPHY(POINT, 4326) NOT NULL,
    district VARCHAR(255) NOT NULL,
    state VARCHAR(255) NOT NULL,
    place_name VARCHAR(255) NOT NULL,
    location_type VARCHAR(100) NOT NULL,
    score INTEGER DEFAULT 0
);"

sudo -u postgres psql -d trvlr_db -c "ALTER TABLE locations ADD CONSTRAINT unique_place_name UNIQUE (place_name);"

sudo -u postgres psql -d trvlr_db -c "
CREATE TABLE visits (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    location_id INTEGER NOT NULL REFERENCES locations(id),
    photo_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    score INTEGER DEFAULT 0,
    CONSTRAINT unique_user_location UNIQUE (user_id, location_id)
);"

sudo -u postgres psql -d trvlr_db -c "
CREATE TABLE user_scores (
    user_id VARCHAR(255) PRIMARY KEY,
    score INTEGER DEFAULT 0
);"

sudo -u postgres psql -d trvlr_db -c "
CREATE TABLE places (
    id SERIAL PRIMARY KEY,
    district VARCHAR(255) NOT NULL UNIQUE,
    state VARCHAR(255) NOT NULL
);"

sudo -u postgres psql -d trvlr_db -c "
CREATE TABLE users (
    id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(255) UNIQUE,
    display_name VARCHAR(255) DEFAULT '',
    created_at TIMESTAMP DEFAULT NOW()
);"

sudo -u postgres psql -d trvlr_db -c "
CREATE TABLE auth_providers (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES users(id),
    provider VARCHAR(50) NOT NULL,
    provider_user_id VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255),
    CONSTRAINT unique_provider_user UNIQUE (provider, provider_user_id)
);"
```

## 5. Allow External Access

### 5a. Configure PostgreSQL to listen on all interfaces

```bash
sudo sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/" /etc/postgresql/18/main/postgresql.conf
echo "host    trvlr_db    trvlr_admin    0.0.0.0/0    md5" | sudo tee -a /etc/postgresql/18/main/pg_hba.conf
sudo systemctl restart postgresql
```

### 5b. Allow remote connections in pg_hba.conf

```bash
echo "host    trvlr_db    trvlr_admin    0.0.0.0/0    md5" | sudo tee -a /etc/postgresql/18/main/pg_hba.conf
```

### 5c. Restart PostgreSQL

```bash
sudo systemctl restart postgresql
```

### 5d. Open port 5432 in firewall

```bash
sudo ufw allow 5432/tcp
```

## 6. Verify External Access

From your Mac (or any other machine):

```bash
psql -h 213.136.67.24 -U trvlr_admin -d trvlr_db
```

Enter password: `your_password`

## 7. Connection String

For the app running on the VPS (localhost):
```
postgresql://trvlr_admin:your_password@localhost:5432/trvlr_db
```

For external access (from your Mac or other tools):
```
postgresql://trvlr_admin:your_password@213.136.67.24:5432/trvlr_db
```

## 8. Quick All-in-One Script

Copy and run everything in one go:

```bash
# Install
sudo apt update
sudo apt install -y postgresql postgresql-contrib postgis postgresql-16-postgis-3

# Start
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create user, db, extension
sudo -u postgres psql -c "CREATE USER trvlr_admin WITH PASSWORD 'your_password' SUPERUSER CREATEDB CREATEROLE;"
sudo -u postgres psql -c "CREATE DATABASE trvlr_db OWNER trvlr_admin;"
sudo -u postgres psql -d trvlr_db -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# Create tables
sudo -u postgres psql -d trvlr_db -c "
CREATE TABLE locations (
    id SERIAL PRIMARY KEY,
    coordinates GEOGRAPHY(POINT, 4326) NOT NULL,
    district VARCHAR(255) NOT NULL,
    state VARCHAR(255) NOT NULL,
    place_name VARCHAR(255) NOT NULL,
    location_type VARCHAR(100) NOT NULL,
    score INTEGER DEFAULT 0
);
ALTER TABLE locations ADD CONSTRAINT unique_place_name UNIQUE (place_name);

CREATE TABLE visits (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    location_id INTEGER NOT NULL REFERENCES locations(id),
    photo_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    score INTEGER DEFAULT 0,
    CONSTRAINT unique_user_location UNIQUE (user_id, location_id)
);

CREATE TABLE user_scores (
    user_id VARCHAR(255) PRIMARY KEY,
    score INTEGER DEFAULT 0
);

CREATE TABLE places (
    id SERIAL PRIMARY KEY,
    district VARCHAR(255) NOT NULL UNIQUE,
    state VARCHAR(255) NOT NULL
);

CREATE TABLE users (
    id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(255) UNIQUE,
    display_name VARCHAR(255) DEFAULT '',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE auth_providers (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES users(id),
    provider VARCHAR(50) NOT NULL,
    provider_user_id VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255),
    CONSTRAINT unique_provider_user UNIQUE (provider, provider_user_id)
);"

# Allow external access
sudo sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/" /etc/postgresql/18/main/postgresql.conf
echo "host    trvlr_db    trvlr_admin    0.0.0.0/0    md5" | sudo tee -a /etc/postgresql/18/main/pg_hba.conf
sudo systemctl restart postgresql
sudo ufw allow 5432/tcp
```

## Security Note

Exposing PostgreSQL to `0.0.0.0/0` means anyone can attempt to connect. For production:
- Use a strong password (done)
- Restrict to your IP: replace `0.0.0.0/0` with `YOUR_IP/32` in pg_hba.conf
- Consider using SSH tunneling instead of direct exposure
