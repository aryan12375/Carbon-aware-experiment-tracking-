"""
app/services/emissions_service.py
===================================
All business logic lives here. Endpoints are thin — they validate input,
call a service method, and return the result. Services own the queries.

Design principles
-----------------
  • No raw SQL — use SQLAlchemy 2.0 select() statements throughout
  • All methods are async
  • Raise HTTPException only at the endpoint layer; services raise ValueError
  • Every public method has a clear docstring
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.emissions import EmissionsRun, GateDecision, Project
from app.schemas.emissions import (
    BrsrPrincipleC,
    BrsrReport,
    BrsrReportRequest,
    DashboardStats,
    EfficiencyPoint,
    EmissionsRunCreate,
    EmissionsRunUpdate,
    GateDecisionCreate,
    GpuComparisonRow,
    TrendPoint,
)

settings = get_settings()


# ══════════════════════════════════════════════════════════════════════════
# Project Service
# ══════════════════════════════════════════════════════════════════════════

class ProjectService:

    @staticmethod
    async def create(db: AsyncSession, name: str, description: str | None, team: str | None) -> Project:
        existing = await db.scalar(select(Project).where(Project.name == name))
        if existing:
            raise ValueError(f"Project '{name}' already exists.")
        project = Project(name=name, description=description, team=team)
        db.add(project)
        await db.flush()
        return project

    @staticmethod
    async def get_all(db: AsyncSession) -> list[Project]:
        result = await db.execute(select(Project).order_by(Project.name))
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(db: AsyncSession, project_id: int) -> Project | None:
        return await db.scalar(select(Project).where(Project.id == project_id))

    @staticmethod
    async def get_run_count(db: AsyncSession, project_id: int) -> int:
        count = await db.scalar(
            select(func.count()).select_from(EmissionsRun).where(EmissionsRun.project_id == project_id)
        )
        return count or 0

    @staticmethod
    async def delete(db: AsyncSession, project_id: int) -> bool:
        project = await db.scalar(select(Project).where(Project.id == project_id))
        if not project:
            return False
        await db.delete(project)
        return True


# ══════════════════════════════════════════════════════════════════════════
# Emissions Run Service
# ══════════════════════════════════════════════════════════════════════════

class EmissionsRunService:

    @staticmethod
    async def create(db: AsyncSession, payload: EmissionsRunCreate) -> EmissionsRun:
        """Ingest a new emissions run. Idempotent on run_id."""
        existing = await db.scalar(
            select(EmissionsRun).where(EmissionsRun.run_id == payload.run_id)
        )
        if existing:
            raise ValueError(f"Run '{payload.run_id}' already exists. Use PUT to update.")

        # Resolve or create project
        project = await db.scalar(
            select(Project).where(Project.name == payload.project_name)
        )
        if not project:
            project = Project(name=payload.project_name)
            db.add(project)
            await db.flush()

        run = EmissionsRun(
            run_id=payload.run_id,
            commit_id=payload.commit_id,
            project_id=project.id,
            project_name=payload.project_name,
            model_name=payload.model_name,
            started_at=payload.started_at,
            finished_at=payload.finished_at,
            duration_seconds=payload.duration_seconds,
            co2_grams=payload.co2_grams,
            co2_kg=payload.co2_kg,
            energy_kwh=payload.energy_kwh,
            grid_intensity_g_kwh=payload.grid_intensity_g_kwh,
            grid_source=payload.grid_source,
            grid_region=payload.grid_region,
            gpu_model=payload.gpu_model,
            gpu_count=payload.gpu_count,
            cpu_model=payload.cpu_model,
            ram_gb=payload.ram_gb,
            cloud_provider=payload.cloud_provider,
            accuracy=payload.accuracy,
            loss=payload.loss,
            extra_metrics_json=json.dumps(payload.extra_metrics or {}),
        )
        db.add(run)
        await db.flush()
        return run

    @staticmethod
    async def get_by_run_id(db: AsyncSession, run_id: str) -> EmissionsRun | None:
        return await db.scalar(
            select(EmissionsRun)
            .where(EmissionsRun.run_id == run_id)
            .options(selectinload(EmissionsRun.gate_decision))
        )

    @staticmethod
    async def get_by_id(db: AsyncSession, run_pk: int) -> EmissionsRun | None:
        return await db.scalar(
            select(EmissionsRun)
            .where(EmissionsRun.id == run_pk)
            .options(selectinload(EmissionsRun.gate_decision))
        )

    @staticmethod
    async def list_runs(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        project_name: str | None = None,
        model_name: str | None = None,
        gate_status: str | None = None,
        order_by: str = "created_at",
        order_dir: str = "desc",
    ) -> tuple[list[EmissionsRun], int]:
        """Return (runs, total_count) with filtering and pagination."""
        q = select(EmissionsRun)

        if project_name:
            q = q.where(EmissionsRun.project_name.ilike(f"%{project_name}%"))
        if model_name:
            q = q.where(EmissionsRun.model_name.ilike(f"%{model_name}%"))
        if gate_status:
            q = q.where(EmissionsRun.gate_status == gate_status)

        # Total count
        count_q = select(func.count()).select_from(q.subquery())
        total = await db.scalar(count_q) or 0

        # Sorting
        sort_col = getattr(EmissionsRun, order_by, EmissionsRun.created_at)
        q = q.order_by(desc(sort_col) if order_dir == "desc" else asc(sort_col))

        # Pagination
        q = q.offset((page - 1) * page_size).limit(page_size)

        result = await db.execute(q)
        return list(result.scalars().all()), total

    @staticmethod
    async def update(
        db: AsyncSession, run_id: str, payload: EmissionsRunUpdate
    ) -> EmissionsRun | None:
        run = await db.scalar(select(EmissionsRun).where(EmissionsRun.run_id == run_id))
        if not run:
            return None

        if payload.accuracy is not None:
            run.accuracy = payload.accuracy
        if payload.loss is not None:
            run.loss = payload.loss
        if payload.gate_status is not None:
            run.gate_status = payload.gate_status
        if payload.extra_metrics is not None:
            run.extra_metrics_json = json.dumps(payload.extra_metrics)

        await db.flush()
        return run

    @staticmethod
    async def delete(db: AsyncSession, run_id: str) -> bool:
        run = await db.scalar(select(EmissionsRun).where(EmissionsRun.run_id == run_id))
        if not run:
            return False
        await db.delete(run)
        return True

    @staticmethod
    async def get_previous_run(
        db: AsyncSession, project_name: str, before_run_id: str
    ) -> EmissionsRun | None:
        """Fetch the run immediately preceding `before_run_id` in the same project."""
        current = await db.scalar(
            select(EmissionsRun).where(EmissionsRun.run_id == before_run_id)
        )
        if not current:
            return None

        prev = await db.scalar(
            select(EmissionsRun)
            .where(
                EmissionsRun.project_name == project_name,
                EmissionsRun.created_at < current.created_at,
                EmissionsRun.run_id != before_run_id,
            )
            .order_by(desc(EmissionsRun.created_at))
            .limit(1)
        )
        return prev


# ══════════════════════════════════════════════════════════════════════════
# Gate Decision Service
# ══════════════════════════════════════════════════════════════════════════

class GateDecisionService:

    @staticmethod
    async def create_or_update(
        db: AsyncSession, payload: GateDecisionCreate
    ) -> GateDecision:
        """Upsert a gate decision for a run. Also updates the run's gate_status."""
        # Verify the run exists
        run = await db.scalar(
            select(EmissionsRun).where(EmissionsRun.run_id == payload.run_id)
        )
        if not run:
            raise ValueError(f"Run '{payload.run_id}' not found.")

        existing = await db.scalar(
            select(GateDecision).where(GateDecision.run_id == payload.run_id)
        )

        decision = existing or GateDecision(run_id=payload.run_id)
        decision.status = payload.status
        decision.exit_code = payload.exit_code
        decision.delta_accuracy_pp = payload.delta_accuracy_pp
        decision.delta_co2_pct = payload.delta_co2_pct
        decision.delta_co2_grams = payload.delta_co2_grams
        decision.delta_energy_kwh = payload.delta_energy_kwh
        decision.reasons_json = json.dumps(payload.reasons)
        decision.suggestions_json = json.dumps(payload.suggestions)
        decision.previous_run_id = payload.previous_run_id
        decision.dry_run = payload.dry_run

        if not existing:
            db.add(decision)

        # Denormalise status onto the run itself
        run.gate_status = payload.status.lower()

        await db.flush()
        return decision

    @staticmethod
    async def get_by_run_id(db: AsyncSession, run_id: str) -> GateDecision | None:
        return await db.scalar(
            select(GateDecision).where(GateDecision.run_id == run_id)
        )

    @staticmethod
    async def list_recent(db: AsyncSession, limit: int = 20) -> list[GateDecision]:
        result = await db.execute(
            select(GateDecision)
            .order_by(desc(GateDecision.evaluated_at))
            .limit(limit)
        )
        return list(result.scalars().all())


# ══════════════════════════════════════════════════════════════════════════
# Analytics Service
# ══════════════════════════════════════════════════════════════════════════

class AnalyticsService:

    @staticmethod
    async def dashboard_stats(db: AsyncSession) -> DashboardStats:
        """Compute all KPIs for the dashboard in as few queries as possible."""
        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)
        fourteen_days_ago = now - timedelta(days=14)

        # ── Aggregate all-time ────────────────────────────────────────────
        agg = await db.execute(
            select(
                func.count(EmissionsRun.id).label("total_runs"),
                func.sum(EmissionsRun.co2_kg).label("total_co2_kg"),
                func.sum(EmissionsRun.energy_kwh).label("total_energy_kwh"),
                func.avg(EmissionsRun.accuracy).label("avg_accuracy"),
            )
        )
        row = agg.one()
        total_runs = row.total_runs or 0
        total_co2_kg = float(row.total_co2_kg or 0)
        total_energy_kwh = float(row.total_energy_kwh or 0)
        avg_accuracy = float(row.avg_accuracy) if row.avg_accuracy else None

        # ── Gate pass rate ────────────────────────────────────────────────
        pass_count = await db.scalar(
            select(func.count()).where(EmissionsRun.gate_status == "pass")
        ) or 0
        evaluated = await db.scalar(
            select(func.count()).where(EmissionsRun.gate_status.in_(["pass", "fail", "warn"]))
        ) or 0
        gate_pass_rate = (pass_count / evaluated) if evaluated > 0 else 0.0

        # ── Top emitter ───────────────────────────────────────────────────
        top_emitter_row = await db.execute(
            select(EmissionsRun.model_name, func.sum(EmissionsRun.co2_grams).label("total"))
            .group_by(EmissionsRun.model_name)
            .order_by(desc("total"))
            .limit(1)
        )
        top_emitter_row = top_emitter_row.first()
        top_emitter = top_emitter_row[0] if top_emitter_row else None

        # ── Best efficiency (accuracy / co2_kg) ───────────────────────────
        # Computed in Python from a small result set
        eff_rows = await db.execute(
            select(EmissionsRun.model_name, EmissionsRun.accuracy, EmissionsRun.co2_kg)
            .where(EmissionsRun.accuracy.is_not(None), EmissionsRun.co2_kg > 0)
        )
        best_eff_model: str | None = None
        best_eff_score = 0.0
        for model_name, accuracy, co2_kg in eff_rows:
            score = accuracy / co2_kg
            if score > best_eff_score:
                best_eff_score = score
                best_eff_model = model_name

        # ── 7-day trend ───────────────────────────────────────────────────
        recent_co2 = await db.scalar(
            select(func.sum(EmissionsRun.co2_kg))
            .where(EmissionsRun.created_at >= seven_days_ago)
        ) or 0.0
        prior_co2 = await db.scalar(
            select(func.sum(EmissionsRun.co2_kg))
            .where(
                EmissionsRun.created_at >= fourteen_days_ago,
                EmissionsRun.created_at < seven_days_ago,
            )
        ) or 0.0
        if prior_co2 > 0:
            co2_trend_7d = ((recent_co2 - prior_co2) / prior_co2) * 100
        else:
            co2_trend_7d = 0.0

        # ── Human equivalent ──────────────────────────────────────────────
        total_g = total_co2_kg * 1000
        if total_g < 100:
            human = f"≈ {total_g/8.22:.1f} smartphone charges"
        elif total_g < 5000:
            human = f"≈ {total_g/170:.1f} km driven"
        else:
            human = f"≈ {total_g/22:.0f} tree-days to offset"

        return DashboardStats(
            total_runs=total_runs,
            total_co2_kg=round(total_co2_kg, 4),
            total_energy_kwh=round(total_energy_kwh, 4),
            avg_accuracy=round(avg_accuracy, 2) if avg_accuracy else None,
            gate_pass_rate=round(gate_pass_rate, 4),
            top_emitter_model=top_emitter,
            best_efficiency_model=best_eff_model,
            co2_trend_7d=round(co2_trend_7d, 2),
            human_total_co2=human,
        )

    @staticmethod
    async def efficiency_frontier(db: AsyncSession) -> list[EfficiencyPoint]:
        """All runs with accuracy data for the scatter plot."""
        result = await db.execute(
            select(EmissionsRun)
            .order_by(desc(EmissionsRun.created_at))
            .limit(200)
        )
        runs = result.scalars().all()
        return [
            EfficiencyPoint(
                run_id=r.run_id,
                model_name=r.model_name,
                accuracy=r.accuracy,
                co2_grams=r.co2_grams,
                energy_kwh=r.energy_kwh,
                gpu_model=r.gpu_model,
                gate_status=r.gate_status,
                created_at=r.created_at,
            )
            for r in runs
        ]

    @staticmethod
    async def gpu_comparison(db: AsyncSession) -> list[GpuComparisonRow]:
        """Aggregate stats by GPU model."""
        rows = await db.execute(
            select(
                EmissionsRun.gpu_model,
                func.count(EmissionsRun.id).label("run_count"),
                func.avg(EmissionsRun.co2_grams).label("avg_co2"),
                func.avg(EmissionsRun.energy_kwh).label("avg_energy"),
                func.avg(EmissionsRun.accuracy).label("avg_accuracy"),
                func.sum(EmissionsRun.co2_kg).label("total_co2_kg"),
            )
            .group_by(EmissionsRun.gpu_model)
            .order_by(desc("run_count"))
        )
        result = []
        for row in rows:
            avg_acc = float(row.avg_accuracy) if row.avg_accuracy else None
            avg_co2 = float(row.avg_co2)
            eff = round(avg_acc / (avg_co2 / 1000), 2) if avg_acc and avg_co2 > 0 else None
            result.append(
                GpuComparisonRow(
                    gpu_model=row.gpu_model,
                    run_count=row.run_count,
                    avg_co2_grams=round(avg_co2, 2),
                    avg_energy_kwh=round(float(row.avg_energy), 4),
                    avg_accuracy=round(avg_acc, 2) if avg_acc else None,
                    avg_efficiency_score=eff,
                    total_co2_kg=round(float(row.total_co2_kg), 4),
                )
            )
        return result

    @staticmethod
    async def carbon_trend(
        db: AsyncSession, days: int = 30
    ) -> list[TrendPoint]:
        """Daily CO₂ aggregation for the trend chart."""
        since = datetime.now(timezone.utc) - timedelta(days=days)
        result = await db.execute(
            select(EmissionsRun)
            .where(EmissionsRun.created_at >= since)
            .order_by(asc(EmissionsRun.created_at))
        )
        runs = result.scalars().all()

        # Group by day
        buckets: dict[str, dict] = defaultdict(
            lambda: {"co2_grams": 0.0, "energy_kwh": 0.0, "count": 0, "acc_sum": 0.0, "acc_n": 0}
        )
        for r in runs:
            day = r.created_at.strftime("%Y-%m-%d") if r.created_at else "unknown"
            b = buckets[day]
            b["co2_grams"] += r.co2_grams
            b["energy_kwh"] += r.energy_kwh
            b["count"] += 1
            if r.accuracy is not None:
                b["acc_sum"] += r.accuracy
                b["acc_n"] += 1

        return [
            TrendPoint(
                date=day,
                co2_grams=round(b["co2_grams"], 2),
                energy_kwh=round(b["energy_kwh"], 4),
                run_count=b["count"],
                avg_accuracy=round(b["acc_sum"] / b["acc_n"], 2) if b["acc_n"] > 0 else None,
            )
            for day, b in sorted(buckets.items())
        ]


# ══════════════════════════════════════════════════════════════════════════
# BRSR / CSRD Export Service
# ══════════════════════════════════════════════════════════════════════════

class BrsrExportService:
    """
    Generates SEBI BRSR (Business Responsibility & Sustainability Report)
    compliant carbon data export for ML compute operations.

    BRSR Principle 6 — Businesses should respect and make efforts to protect
    and restore the environment. This covers Scope 2 electricity emissions
    from compute infrastructure.

    Also aligned with EU CSRD (Corporate Sustainability Reporting Directive)
    ESRS E1 — Climate change.
    """

    @staticmethod
    async def generate(
        db: AsyncSession, request: BrsrReportRequest
    ) -> BrsrReport:
        """Assemble the full BRSR report for the requested financial year."""
        now = datetime.now(timezone.utc)

        # ── Parse financial year ──────────────────────────────────────────
        # Format: "2025-26" → start = 2025-04-01, end = 2026-03-31
        fy_parts = request.financial_year.split("-")
        start_year = int(fy_parts[0])
        end_year = start_year + 1
        period_start = datetime(start_year, 4, 1, tzinfo=timezone.utc)
        period_end = datetime(end_year, 3, 31, 23, 59, 59, tzinfo=timezone.utc)

        # ── Base query ────────────────────────────────────────────────────
        q = select(EmissionsRun).where(
            EmissionsRun.created_at >= period_start,
            EmissionsRun.created_at <= period_end,
        )
        if request.project_names:
            q = q.where(EmissionsRun.project_name.in_(request.project_names))
        if not request.include_gate_failures:
            q = q.where(EmissionsRun.gate_status != "fail")

        result = await db.execute(q)
        runs = list(result.scalars().all())

        if not runs:
            # Return empty report — don't crash
            runs = []

        # ── Aggregate ─────────────────────────────────────────────────────
        total_energy_kwh = sum(r.energy_kwh for r in runs)
        total_co2_g = sum(r.co2_grams for r in runs)
        total_co2_tonnes = total_co2_g / 1_000_000
        scope2_tonnes = total_co2_tonnes   # all compute = scope 2 (purchased electricity)
        total_compute_hours = sum(r.duration_seconds for r in runs) / 3600

        # Gate stats
        gate_statuses = [r.gate_status for r in runs]
        pass_count = gate_statuses.count("pass")
        total_evaluated = sum(1 for s in gate_statuses if s in ("pass", "fail", "warn"))
        gate_pass_rate = (pass_count / total_evaluated * 100) if total_evaluated else 0.0

        # Top 5 emitters by model
        model_co2: dict[str, float] = defaultdict(float)
        for r in runs:
            model_co2[r.model_name] += r.co2_grams
        top_5 = sorted(model_co2.items(), key=lambda x: x[1], reverse=True)[:5]
        top_5_list = [
            {"model_name": m, "co2_grams": round(v, 2), "co2_tonnes": round(v / 1_000_000, 6)}
            for m, v in top_5
        ]

        # GPU summary (reuse analytics)
        gpu_rows = await AnalyticsService.gpu_comparison(db)

        # Carbon trend for the reporting period
        trend_days = (period_end - period_start).days
        trend = await AnalyticsService.carbon_trend(db, days=min(trend_days, 365))

        # Estimate renewable energy % using grid intensity
        # India grid mix: ~24% renewable in 2024-25 per CEA
        avg_grid = (
            sum(r.grid_intensity_g_kwh for r in runs) / len(runs)
            if runs else settings.GATE_FAIL_CO2_DELTA_PCT
        )
        # Lower grid intensity = more renewable (heuristic)
        renewable_pct = max(0.0, min(100.0, (500 - avg_grid) / 5 + 15))

        # Reduction initiatives (auto-generated from gate data)
        initiatives = [
            "Deployed Green Gate CI/CD check blocking high-carbon model merges",
            f"Carbon-aware scheduling recommendation for {settings.DEFAULT_GRID_REGION} grid",
            f"Gate pass rate of {gate_pass_rate:.1f}% indicating active carbon governance",
        ]
        if any(r.gpu_model and "T4" in r.gpu_model for r in runs):
            initiatives.append(
                "Preferential use of NVIDIA T4 GPUs for research runs (lower TDP vs A100)"
            )

        p6 = BrsrPrincipleC(
            total_energy_consumed_kwh=round(total_energy_kwh, 4),
            energy_from_renewable_pct=round(renewable_pct, 2),
            total_co2_equivalent_tonnes=round(total_co2_tonnes, 6),
            co2_reduction_initiatives=initiatives,
            scope2_emissions_tonnes=round(scope2_tonnes, 6),
        )

        return BrsrReport(
            organisation_name=settings.ORGANISATION_NAME,
            cin=settings.ORGANISATION_CIN,
            financial_year=request.financial_year,
            reporting_period_start=period_start.strftime("%Y-%m-%d"),
            reporting_period_end=period_end.strftime("%Y-%m-%d"),
            generated_at=now,
            total_ml_training_runs=len(runs),
            total_compute_hours=round(total_compute_hours, 2),
            principle_6=p6,
            gate_pass_rate_pct=round(gate_pass_rate, 2),
            top_5_emitting_models=top_5_list,
            gpu_fleet_summary=gpu_rows,
            carbon_trend=trend,
        )
