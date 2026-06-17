from fastapi import FastAPI

from app.routers import checkin, leaderboard, locations, nearby, places, visits

app = FastAPI(title="trvlr-be", version="0.1.0")

app.include_router(locations.router)
app.include_router(checkin.router)
app.include_router(nearby.router)
app.include_router(leaderboard.router)
app.include_router(visits.router)
app.include_router(places.router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
