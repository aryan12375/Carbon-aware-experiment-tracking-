"""
app/main.py
============
EcoTrack FastAPI application.

Entry point — run with:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

API docs auto-available at:
    http://localhost:8000/docs        (Swagger UI)
    http://localhost:8000/redoc       (ReDoc)
    http://localhost:8000/api/v1/openapi.json
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.db.session import init_db

settings = get_settings()


# ── Lifespan ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create tables. Shutdown: nothing to do for SQLite."""
    await init_db()
    print(f"\nEcoTrack API v{settings.APP_VERSION} started")
    print(f"   DB  : {settings.DATABASE_URL}")
    print(f"   Env : {settings.ENVIRONMENT}")
    print(f"   Docs: http://localhost:8000/docs\n")
    yield


# ── App factory ───────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=settings.APP_DESCRIPTION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request timing middleware ─────────────────────────────────────────
    @application.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = (time.perf_counter() - start) * 1000
        response.headers["X-Process-Time-Ms"] = f"{elapsed:.2f}"
        return response

    # ── Global exception handler ──────────────────────────────────────────
    @application.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error.", "type": type(exc).__name__},
        )

    # ── Routes ────────────────────────────────────────────────────────────
    application.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # ── Health check ──────────────────────────────────────────────────────
    @application.get("/health", tags=["Health"], summary="Health check")
    async def health():
        return {
            "status": "ok",
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
        }

    @application.get("/", include_in_schema=False)
    async def root():
        return {
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "redoc": "/redoc",
        }

    return application


app = create_app()
