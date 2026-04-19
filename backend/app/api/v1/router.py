"""app/api/v1/router.py — API v1 main router."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    analytics,
    export,
    matchmaker,
    nutrition,
    projects,
    quantization,
    runs,
    scheduler,
)

api_router = APIRouter()

api_router.include_router(runs.router)
api_router.include_router(projects.router)
api_router.include_router(analytics.router)
api_router.include_router(export.router)
api_router.include_router(scheduler.router)
api_router.include_router(nutrition.router)
api_router.include_router(quantization.router)
api_router.include_router(matchmaker.router)

