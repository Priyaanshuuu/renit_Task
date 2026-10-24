from fastapi import FastAPI

from .routes import router

app = FastAPI(
    title="Wind Forecast Analysis API",
    description="Great Britain national wind forecast analysis for January 2026 decisions.",
    version="0.1.0",
)
app.include_router(router)
