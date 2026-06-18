from fastapi import FastAPI

from app.routers import auth, checkin, leaderboard, locations, nearby, places, profile, visits

app = FastAPI(title="trvlr-be", version="0.1.0")

app.include_router(auth.router)
app.include_router(locations.router)
app.include_router(checkin.router)
app.include_router(nearby.router)
app.include_router(leaderboard.router)
app.include_router(visits.router)
app.include_router(places.router)
app.include_router(profile.router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
