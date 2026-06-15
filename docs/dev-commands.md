# Dev Commands

## Virtual Environment

```bash
# Create venv
python3 -m venv .venv

# Activate
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Run the App

```bash
# Make sure venv is activated first, then:
uvicorn app.main:app --reload

# Or run directly without activating:
.venv/bin/uvicorn app.main:app --reload

# Start on a specific port
.venv/bin/uvicorn app.main:app --reload --port 8080
```

App runs at http://127.0.0.1:8000 by default.  
Docs at http://127.0.0.1:8000/docs

## Kill Port

```bash
# Find process on port 8000
lsof -i :8000

# Kill it
kill -9 $(lsof -t -i :8000)
```

## PostgreSQL

```bash
# Start postgres
brew services start postgresql@17

# Stop postgres
brew services stop postgresql@17

# Connect to trvlr_db
psql -U trvlr_admin -d trvlr_db

# Quick check tables
psql -U trvlr_admin -d trvlr_db -c "\dt"
```

## Test Endpoints

```bash
# Health check
curl http://127.0.0.1:8000/health

# Create a location
curl -X POST http://127.0.0.1:8000/locations/ \
  -H "Content-Type: application/json" \
  -d '{"latitude": 12.9716, "longitude": 77.5946, "district": "Bangalore Urban", "state": "Karnataka", "place_name": "Lalbagh", "score": 8}'
```

## Dependencies

```bash
# Add a new package
pip install <package>

# Freeze current versions
pip freeze > requirements.txt
```
