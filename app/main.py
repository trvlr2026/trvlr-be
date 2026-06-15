from fastapi import FastAPI

app = FastAPI(title="trvlr-be", version="0.1.0")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
