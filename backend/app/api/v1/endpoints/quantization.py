"""
app/api/v1/endpoints/quantization.py
=======================================
Feature 3 — Automatic Quantization Gating endpoints.

POST /quantization/analyze          — analyze a run for quantization potential
GET  /quantization/recommend/{run_id} — get the recommendation for a specific run
GET  /quantization/code/{run_id}    — get a ready-to-use code snippet
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.emissions import QuantizationAnalysis, QuantizationRequest
from app.services.emissions_service import EmissionsRunService
from app.services.quantization_service import QuantizationService

router = APIRouter(prefix="/quantization", tags=["Quantization Gating"])


async def _get_run_dict(run_id: str, db: AsyncSession) -> dict:
    run = await EmissionsRunService.get_by_run_id(db, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")
    return {
        "run_id": run.run_id,
        "model_name": run.model_name,
        "co2_kg": run.co2_kg,
        "energy_kwh": run.energy_kwh,
        "accuracy": run.accuracy,
    }


@router.post(
    "/analyze",
    response_model=QuantizationAnalysis,
    summary="Analyze a run for quantization potential",
    description=(
        "Given a run_id, runs heuristic quantization analysis to determine "
        "whether the model should be automatically quantized before deployment. "
        "Returns a verdict: FORCE_QUANTIZED, RECOMMEND_QUANTIZED, or KEEP_FP32."
    ),
)
async def analyze_quantization(
    request: QuantizationRequest,
    target_precision: str = Query("INT8", pattern="^(INT8|INT4|FP16)$"),
    db: AsyncSession = Depends(get_db),
) -> QuantizationAnalysis:
    run_data = await _get_run_dict(request.run_id, db)
    return QuantizationService.analyze(run_data, request, target_precision)


@router.get(
    "/recommend/{run_id}",
    response_model=QuantizationAnalysis,
    summary="Quick quantization recommendation for a run (default thresholds)",
    description=(
        "Shorthand for POST /quantization/analyze with default thresholds "
        "(98% accuracy retention, 40% energy reduction). "
        "Returns the recommended action immediately."
    ),
)
async def quick_recommend(
    run_id: str,
    target_precision: str = Query("INT8", pattern="^(INT8|INT4|FP16)$"),
    db: AsyncSession = Depends(get_db),
) -> QuantizationAnalysis:
    run_data = await _get_run_dict(run_id, db)
    return QuantizationService.analyze(run_data, None, target_precision)


@router.get(
    "/code/{run_id}",
    summary="Get a ready-to-paste quantization code snippet for a run",
)
async def get_code_snippet(
    run_id: str,
    target_precision: str = Query("INT8", pattern="^(INT8|INT4|FP16)$"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    run_data = await _get_run_dict(run_id, db)
    analysis = QuantizationService.analyze(run_data, None, target_precision)
    snippet = QuantizationService.generate_code_snippet(analysis)
    return {
        "run_id": run_id,
        "verdict": analysis.verdict,
        "recommended_tool": analysis.recommended_tool,
        "code_snippet": snippet,
    }
