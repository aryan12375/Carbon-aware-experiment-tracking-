"""
app/api/v1/endpoints/analytics.py
====================================
Read-only analytics endpoints for the EcoTrack dashboard.

GET /analytics/dashboard         — KPI summary cards
GET /analytics/frontier          — Accuracy vs CO₂ scatter data
GET /analytics/gpu-comparison    — Per-GPU aggregated stats
GET /analytics/trend             — Daily CO₂ time series
GET /analytics/gate-history      — Recent gate decisions
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.emissions import (
    DashboardStats,
    EfficiencyPoint,
    GateDecisionOut,
    GpuComparisonRow,
    TrendPoint,
)
from app.services.emissions_service import AnalyticsService, GateDecisionService

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get(
    "/dashboard",
    response_model=DashboardStats,
    summary="Dashboard KPI summary",
)
async def dashboard_stats(db: AsyncSession = Depends(get_db)) -> DashboardStats:
    return await AnalyticsService.dashboard_stats(db)


@router.get(
    "/frontier",
    response_model=list[EfficiencyPoint],
    summary="Efficiency frontier — Accuracy vs CO₂ scatter data",
)
async def efficiency_frontier(db: AsyncSession = Depends(get_db)) -> list[EfficiencyPoint]:
    return await AnalyticsService.efficiency_frontier(db)


@router.get(
    "/gpu-comparison",
    response_model=list[GpuComparisonRow],
    summary="Aggregated GPU efficiency comparison",
)
async def gpu_comparison(db: AsyncSession = Depends(get_db)) -> list[GpuComparisonRow]:
    return await AnalyticsService.gpu_comparison(db)


@router.get(
    "/trend",
    response_model=list[TrendPoint],
    summary="Daily carbon trend time series",
)
async def carbon_trend(
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    db: AsyncSession = Depends(get_db),
) -> list[TrendPoint]:
    return await AnalyticsService.carbon_trend(db, days=days)


@router.get(
    "/gate-history",
    response_model=list[GateDecisionOut],
    summary="Recent gate decisions across all runs",
)
async def gate_history(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[GateDecisionOut]:
    decisions = await GateDecisionService.list_recent(db, limit=limit)
    return [GateDecisionOut.model_validate(d) for d in decisions]
