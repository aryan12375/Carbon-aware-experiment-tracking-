"""
app/core/config.py
==================
All application settings loaded from environment variables or .env file.
Every setting has a sensible default so the app works out-of-the-box.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────────────────
    APP_NAME: str = "EcoTrack"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = (
        "Green MLOps Framework — Carbon emissions tracking, "
        "CI/CD gate, and SEBI BRSR / EU CSRD compliance reporting."
    )
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = True

    # ── API ───────────────────────────────────────────────────────────────
    API_V1_PREFIX: str = "/api/v1"
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000", "*"]

    # ── Database ──────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./ecotrack.db"
    # For PostgreSQL: postgresql+asyncpg://user:pass@localhost/ecotrack

    # ── External APIs ─────────────────────────────────────────────────────
    CO2SIGNAL_API_KEY: str = ""
    ELECTRICITY_MAPS_KEY: str = ""
    DEFAULT_GRID_REGION: str = "IN-SO"          # Karnataka / South India

    # ── Gate thresholds (can be overridden per-deployment) ────────────────
    GATE_FAIL_ACC_DELTA_PP: float = 0.5         # percentage points
    GATE_FAIL_CO2_DELTA_PCT: float = 20.0       # percent
    GATE_WARN_CO2_DELTA_PCT: float = 40.0       # percent
    GATE_ABS_CO2_WARN_G: float = 2_000.0        # grams
    GATE_ABS_CO2_FAIL_G: float = 10_000.0       # grams

    # ── BRSR / CSRD ───────────────────────────────────────────────────────
    ORGANISATION_NAME: str = "MIT Manipal — EcoTrack Lab"
    ORGANISATION_CIN: str = "U72900KA2024PTC000000"   # placeholder CIN
    REPORTING_YEAR: int = 2026

    # ── Paths ─────────────────────────────────────────────────────────────
    EMISSIONS_DIR: Path = Path("./emissions")

    @field_validator("EMISSIONS_DIR", mode="before")
    @classmethod
    def make_emissions_dir(cls, v: str | Path) -> Path:
        p = Path(v)
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached singleton settings instance."""
    return Settings()
