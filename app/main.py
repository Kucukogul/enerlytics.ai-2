from fastapi import FastAPI

from api.routes import router as api_router

app = FastAPI(title="Enerlytics.ai", version="0.1.0")
app.include_router(api_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
