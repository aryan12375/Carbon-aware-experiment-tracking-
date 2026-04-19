"""
app/api/v1/endpoints/runs.py
==============================
CRUD endpoints for EmissionsRun.

POST   /runs                 — ingest a new run from tracker_utils.py / CI
GET    /runs                 — paginated list with filters
GET    /runs/{run_id}        — single run detail
PATCH  /runs/{run_id}        — partial update (accuracy, gate_status, etc.)
DELETE /runs/{run_id}        — delete a run and its gate decision
POST   /runs/{run_id}/gate   — attach a gate decision to a run
GET    /runs/{run_id}/gate   — fetch the gate decision for a run
"""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.emissions import (
    EmissionsRunCreate,
    EmissionsRunOut,
    EmissionsRunSummary,
    EmissionsRunUpdate,
    GateDecisionCreate,
    GateDecisionOut,
    PaginatedRuns,
)
from app.services.emissions_service import EmissionsRunService, GateDecisionService

router = APIRouter(prefix="/runs", tags=["Emissions Runs"])


# ── POST /runs ─────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=EmissionsRunOut,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a new emissions run",
    description=(
        "Called by `tracker_utils.py` or the CI pipeline after every training job. "
        "Idempotent: if `run_id` already exists a 409 is returned."
    ),
)
async def create_run(
    payload: EmissionsRunCreate,
    db: AsyncSession = Depends(get_db),
) -> EmissionsRunOut:
    try:
        run = await EmissionsRunService.create(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return EmissionsRunOut.model_validate(run)


# ── GET /runs ──────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=PaginatedRuns,
    summary="List all runs (paginated)",
)
async def list_runs(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    project: str | None = Query(None, description="Filter by project name (partial match)"),
    model: str | None = Query(None, description="Filter by model name (partial match)"),
    gate_status: str | None = Query(None, pattern="^(pass|fail|warn|pending)$"),
    order_by: str = Query("created_at", pattern="^(created_at|co2_grams|accuracy|duration_seconds)$"),
    order_dir: str = Query("desc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedRuns:
    runs, total = await EmissionsRunService.list_runs(
        db,
        page=page,
        page_size=page_size,
        project_name=project,
        model_name=model,
        gate_status=gate_status,
        order_by=order_by,
        order_dir=order_dir,
    )
    return PaginatedRuns(
        items=[EmissionsRunSummary.model_validate(r) for r in runs],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


# ── GET /runs/{run_id} ─────────────────────────────────────────────────────

@router.get(
    "/{run_id}",
    response_model=EmissionsRunOut,
    summary="Get a single run by run_id",
)
async def get_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
) -> EmissionsRunOut:
    run = await EmissionsRunService.get_by_run_id(db, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")
    return EmissionsRunOut.model_validate(run)


# ── PATCH /runs/{run_id} ───────────────────────────────────────────────────

@router.patch(
    "/{run_id}",
    response_model=EmissionsRunOut,
    summary="Partially update a run (accuracy, gate_status, etc.)",
)
async def update_run(
    run_id: str,
    payload: EmissionsRunUpdate,
    db: AsyncSession = Depends(get_db),
) -> EmissionsRunOut:
    run = await EmissionsRunService.update(db, run_id, payload)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")
    return EmissionsRunOut.model_validate(run)


# ── DELETE /runs/{run_id} ──────────────────────────────────────────────────

@router.delete(
    "/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a run and its gate decision",
)
async def delete_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    deleted = await EmissionsRunService.delete(db, run_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")


# ── POST /runs/{run_id}/gate ───────────────────────────────────────────────

@router.post(
    "/{run_id}/gate",
    response_model=GateDecisionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Attach or update a gate decision for this run",
    description=(
        "Called by `check_gate.py` after evaluation. "
        "If a decision already exists it is overwritten (upsert)."
    ),
)
async def create_gate_decision(
    run_id: str,
    payload: GateDecisionCreate,
    db: AsyncSession = Depends(get_db),
) -> GateDecisionOut:
    if payload.run_id != run_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="run_id in body must match run_id in path.",
        )
    try:
        decision = await GateDecisionService.create_or_update(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return GateDecisionOut.model_validate(decision)


# ── GET /runs/{run_id}/gate ────────────────────────────────────────────────

@router.get(
    "/{run_id}/gate",
    response_model=GateDecisionOut,
    summary="Get the gate decision for a run",
)
async def get_gate_decision(
    run_id: str,
    db: AsyncSession = Depends(get_db),
) -> GateDecisionOut:
    decision = await GateDecisionService.get_by_run_id(db, run_id)
    if not decision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No gate decision found for run '{run_id}'.",
        )
    return GateDecisionOut.model_validate(decision)
