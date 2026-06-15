from fastapi import FastAPI

from app.routers import locations

app = FastAPI(title="trvlr-be", version="0.1.0")

app.include_router(locations.router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
