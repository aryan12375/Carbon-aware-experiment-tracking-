"""
app/api/v1/endpoints/scheduler.py
====================================
Feature 1 — Green-Pause Scheduler endpoints.

GET /scheduler/grid-intensity        — live intensity + 24h carbon forecast
GET /scheduler/optimal-windows       — ranked low-carbon training windows
GET /scheduler/savings               — CO₂ savings for a given job shift
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from app.schemas.emissions import GridIntensityResponse, SchedulerWindow
from app.services.scheduler_service import SchedulerService

router = APIRouter(prefix="/scheduler", tags=["Carbon-Aware Scheduler"])


@router.get(
    "/grid-intensity",
    response_model=GridIntensityResponse,
    summary="Live grid carbon intensity + 24h forecast",
    description=(
        "Returns the current carbon intensity of the electricity grid "
        "and a synthetic 24-hour forecast. Source is CO2Signal → ElectricityMaps → "
        "heuristic model (India solar curve). Use the forecast to decide "
        "when to launch long-running GPU training jobs."
    ),
)
async def get_grid_intensity(
    region: str = Query("IN-SO", description="Grid zone (e.g. IN-SO, IN-NO, DE, FR, US-CA)"),
) -> GridIntensityResponse:
    return SchedulerService.get_grid_intensity_and_forecast(region)


@router.get(
    "/optimal-windows",
    response_model=list[SchedulerWindow],
    summary="Recommended low-carbon training windows for today",
    description=(
        "Returns a ranked list of contiguous time windows during which the "
        "grid is at least 10% cleaner than the regional baseline. "
        "Sort is cleanest-first. Use the first result for maximum savings."
    ),
)
async def optimal_windows(
    region: str = Query("IN-SO"),
) -> list[SchedulerWindow]:
    return SchedulerService.get_optimal_windows(region)


@router.get(
    "/savings",
    summary="Calculate CO₂ saving from scheduling a job at a different hour",
    description=(
        "Given a job's estimated energy consumption, current launch hour, and "
        "a prospective launch hour, returns how much CO₂ you'd save by shifting."
    ),
)
async def calculate_savings(
    energy_kwh: float = Query(..., description="Estimated energy consumption in kWh"),
    current_hour: int = Query(..., ge=0, le=23, description="Current hour (0–23, local time)"),
    optimal_hour: int = Query(..., ge=0, le=23, description="Target hour to shift to"),
    region: str = Query("IN-SO"),
) -> dict:
    return SchedulerService.calculate_job_savings(energy_kwh, current_hour, optimal_hour, region)
