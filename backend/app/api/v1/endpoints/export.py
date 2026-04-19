"""
app/api/v1/endpoints/export.py
================================
Compliance export endpoints for SEBI BRSR and EU CSRD reporting.

GET  /export/brsr          — Full BRSR Principle 6 JSON report
GET  /export/brsr/csv      — Flat CSV of all runs for the financial year
GET  /export/runs/csv      — Raw run data CSV (all time or date range)
POST /export/brsr          — Generate report for custom FY + project filter
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.models.emissions import EmissionsRun
from app.schemas.emissions import BrsrReport, BrsrReportRequest
from app.services.emissions_service import BrsrExportService

router = APIRouter(prefix="/export", tags=["Compliance Export"])
settings = get_settings()


# ── GET /export/brsr ───────────────────────────────────────────────────────

@router.get(
    "/brsr",
    response_model=BrsrReport,
    summary="Generate SEBI BRSR Principle 6 compliance report (current FY)",
    description=(
        "Returns a structured JSON report aligned with SEBI's Business "
        "Responsibility & Sustainability Report (BRSR) Principle 6 requirements "
        "and EU CSRD ESRS E1 (Climate Change) disclosures.\n\n"
        "Financial year is the Indian fiscal year: April 1 → March 31."
    ),
)
async def get_brsr_report(
    fy: str = Query(
        f"{settings.REPORTING_YEAR - 1}-{str(settings.REPORTING_YEAR)[2:]}",
        pattern=r"^\d{4}-\d{2}$",
        description="Financial year, e.g. '2025-26'",
    ),
    include_failures: bool = Query(True, description="Include gate-failed runs in totals"),
    db: AsyncSession = Depends(get_db),
) -> BrsrReport:
    request = BrsrReportRequest(
        financial_year=fy,
        include_gate_failures=include_failures,
    )
    return await BrsrExportService.generate(db, request)


# ── POST /export/brsr ──────────────────────────────────────────────────────

@router.post(
    "/brsr",
    response_model=BrsrReport,
    summary="Generate BRSR report with custom filters",
    description="Filter by specific projects, financial year, and gate status inclusion.",
)
async def post_brsr_report(
    request: BrsrReportRequest,
    db: AsyncSession = Depends(get_db),
) -> BrsrReport:
    return await BrsrExportService.generate(db, request)


# ── GET /export/brsr/csv ───────────────────────────────────────────────────

@router.get(
    "/brsr/csv",
    summary="Download BRSR summary as CSV",
    response_class=StreamingResponse,
)
async def download_brsr_csv(
    fy: str = Query(
        f"{settings.REPORTING_YEAR - 1}-{str(settings.REPORTING_YEAR)[2:]}",
        pattern=r"^\d{4}-\d{2}$",
    ),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Download a flat CSV suitable for pasting into BRSR disclosure forms."""
    report = await BrsrExportService.generate(
        db,
        BrsrReportRequest(financial_year=fy),
    )

    output = io.StringIO()
    writer = csv.writer(output)

    # ── Header block ──────────────────────────────────────────────────────
    writer.writerow(["EcoTrack — BRSR Principle 6 Compliance Report"])
    writer.writerow(["Organisation", report.organisation_name])
    writer.writerow(["CIN", report.cin])
    writer.writerow(["Financial Year", report.financial_year])
    writer.writerow(["Reporting Period", f"{report.reporting_period_start} to {report.reporting_period_end}"])
    writer.writerow(["Generated At", report.generated_at.isoformat()])
    writer.writerow(["Framework", report.framework_version])
    writer.writerow(["SEBI BRSR Compliant", "Yes" if report.sebi_brsr_compliant else "No"])
    writer.writerow(["EU CSRD Aligned", "Yes" if report.csrd_aligned else "No"])
    writer.writerow([])

    # ── Section A — General ───────────────────────────────────────────────
    writer.writerow(["SECTION A — GENERAL DISCLOSURES"])
    writer.writerow(["Total ML Training Runs", report.total_ml_training_runs])
    writer.writerow(["Total Compute Hours", report.total_compute_hours])
    writer.writerow(["Green Gate Pass Rate (%)", report.gate_pass_rate_pct])
    writer.writerow([])

    # ── Section C — Environment ───────────────────────────────────────────
    writer.writerow(["SECTION C — PRINCIPLE 6: ENVIRONMENT"])
    p6 = report.principle_6
    writer.writerow(["Total Energy Consumed (kWh)", p6.total_energy_consumed_kwh])
    writer.writerow(["Energy from Renewables (%)", p6.energy_from_renewable_pct])
    writer.writerow(["Total CO₂ Equivalent (tonnes)", p6.total_co2_equivalent_tonnes])
    writer.writerow(["Scope 2 Emissions (tonnes CO₂eq)", p6.scope2_emissions_tonnes])
    writer.writerow([])
    writer.writerow(["CO₂ Reduction Initiatives"])
    for initiative in p6.co2_reduction_initiatives:
        writer.writerow(["", initiative])
    writer.writerow([])

    # ── Top emitters ──────────────────────────────────────────────────────
    writer.writerow(["TOP 5 EMITTING MODELS"])
    writer.writerow(["Rank", "Model Name", "CO₂ (grams)", "CO₂ (tonnes)"])
    for i, m in enumerate(report.top_5_emitting_models, 1):
        writer.writerow([i, m["model_name"], m["co2_grams"], m["co2_tonnes"]])
    writer.writerow([])

    # ── GPU fleet ─────────────────────────────────────────────────────────
    writer.writerow(["GPU FLEET SUMMARY"])
    writer.writerow(["GPU Model", "Runs", "Avg CO₂ (g)", "Avg Energy (kWh)", "Avg Accuracy (%)", "Total CO₂ (kg)"])
    for g in report.gpu_fleet_summary:
        writer.writerow([
            g.gpu_model, g.run_count, g.avg_co2_grams,
            g.avg_energy_kwh, g.avg_accuracy or "N/A", g.total_co2_kg,
        ])
    writer.writerow([])

    # ── Daily trend ───────────────────────────────────────────────────────
    writer.writerow(["DAILY CARBON TREND"])
    writer.writerow(["Date", "CO₂ (g)", "Energy (kWh)", "Runs", "Avg Accuracy (%)"])
    for t in report.carbon_trend:
        writer.writerow([t.date, t.co2_grams, t.energy_kwh, t.run_count, t.avg_accuracy or "N/A"])

    output.seek(0)
    filename = f"EcoTrack_BRSR_{fy.replace('-', '_')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── GET /export/runs/csv ───────────────────────────────────────────────────

@router.get(
    "/runs/csv",
    summary="Download all run data as CSV",
    response_class=StreamingResponse,
)
async def download_runs_csv(
    since: Optional[str] = Query(None, description="ISO date, e.g. 2025-04-01"),
    until: Optional[str] = Query(None, description="ISO date, e.g. 2026-03-31"),
    project: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Raw emissions run data — full audit trail download."""
    q = select(EmissionsRun).order_by(EmissionsRun.created_at)

    if since:
        q = q.where(EmissionsRun.created_at >= datetime.fromisoformat(since).replace(tzinfo=timezone.utc))
    if until:
        q = q.where(EmissionsRun.created_at <= datetime.fromisoformat(until).replace(tzinfo=timezone.utc))
    if project:
        q = q.where(EmissionsRun.project_name.ilike(f"%{project}%"))

    result = await db.execute(q)
    runs = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)

    # CSV header
    writer.writerow([
        "run_id", "commit_id", "project_name", "model_name",
        "started_at", "finished_at", "duration_seconds",
        "co2_grams", "co2_kg", "energy_kwh",
        "grid_intensity_g_kwh", "grid_source", "grid_region",
        "gpu_model", "gpu_count", "ram_gb", "cloud_provider",
        "accuracy", "loss", "gate_status", "created_at",
    ])

    for r in runs:
        writer.writerow([
            r.run_id, r.commit_id, r.project_name, r.model_name,
            r.started_at.isoformat() if r.started_at else "",
            r.finished_at.isoformat() if r.finished_at else "",
            r.duration_seconds,
            r.co2_grams, r.co2_kg, r.energy_kwh,
            r.grid_intensity_g_kwh, r.grid_source, r.grid_region,
            r.gpu_model, r.gpu_count, r.ram_gb, r.cloud_provider,
            r.accuracy if r.accuracy is not None else "",
            r.loss if r.loss is not None else "",
            r.gate_status,
            r.created_at.isoformat() if r.created_at else "",
        ])

    output.seek(0)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"EcoTrack_runs_{ts}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
