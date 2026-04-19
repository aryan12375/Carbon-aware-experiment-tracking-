"""
app/api/v1/endpoints/nutrition.py
====================================
Feature 2 — AI Nutrition Label endpoints.

GET  /nutrition/{run_id}        — JSON carbon nutrition label
GET  /nutrition/{run_id}/pdf    — Download as PDF (reportlab)
GET  /nutrition/{run_id}/embed  — JSON formatted for embedding in model files
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.emissions import NutritionLabel
from app.services.emissions_service import EmissionsRunService
from app.services.nutrition_label_service import NutritionLabelService

router = APIRouter(prefix="/nutrition", tags=["AI Nutrition Label"])


async def _get_run_data(run_id: str, db: AsyncSession) -> dict:
    """Helper: fetch run from DB and convert to dict."""
    run = await EmissionsRunService.get_by_run_id(db, run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found.",
        )
    return {
        "run_id": run.run_id,
        "model_name": run.model_name,
        "co2_grams": run.co2_grams,
        "co2_kg": run.co2_kg,
        "energy_kwh": run.energy_kwh,
        "duration_seconds": run.duration_seconds,
        "grid_region": run.grid_region,
        "grid_intensity_g_kwh": run.grid_intensity_g_kwh,
        "gpu_model": run.gpu_model,
        "gpu_count": run.gpu_count,
        "cpu_model": run.cpu_model,
        "ram_gb": run.ram_gb,
        "cloud_provider": run.cloud_provider,
        "accuracy": run.accuracy,
    }


@router.get(
    "/{run_id}",
    response_model=NutritionLabel,
    summary="Generate AI Nutrition Label for a model run",
    description=(
        "Returns a standardised 'AI Nutrition Label' — analogous to a food nutrition "
        "label — showing total carbon debt, hardware ancestry, efficiency score, and "
        "ESG compliance classification (SEBI BRSR Scope 2, EU CSRD ESRS E1)."
    ),
)
async def get_nutrition_label(
    run_id: str,
    db: AsyncSession = Depends(get_db),
) -> NutritionLabel:
    run_data = await _get_run_data(run_id, db)
    return NutritionLabelService.generate(run_data)


@router.get(
    "/{run_id}/pdf",
    summary="Download Nutrition Label as a PDF report",
    response_class=StreamingResponse,
    description=(
        "Generates a PDF carbon label suitable for ESG submissions and BRSR disclosures. "
        "Requires `reportlab` to be installed (`pip install reportlab`). "
        "Falls back to JSON if reportlab is not available."
    ),
)
async def download_nutrition_pdf(
    run_id: str,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    run_data = await _get_run_data(run_id, db)
    label = NutritionLabelService.generate(run_data)
    pdf_bytes = NutritionLabelService.generate_pdf_bytes(label)

    # Detect if we got JSON fallback (no reportlab)
    is_pdf = pdf_bytes[:4] == b"%PDF"
    media_type = "application/pdf" if is_pdf else "application/json"
    ext = "pdf" if is_pdf else "json"
    filename = f"EcoTrack_NutritionLabel_{run_id}.{ext}"

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{run_id}/embed",
    summary="Get JSON formatted for embedding in .pt / .safetensors model files",
    description=(
        "Returns a compact JSON string formatted for embedding as metadata "
        "in PyTorch `.pt` files (via `torch.save(extra_files={...})`) "
        "or Safetensors metadata dicts."
    ),
)
async def get_embed_json(
    run_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    run_data = await _get_run_data(run_id, db)
    label = NutritionLabelService.generate(run_data)
    embedded = NutritionLabelService.to_embedded_json(label)
    return {
        "run_id": run_id,
        "embedded_json": embedded,
        "usage": {
            "pytorch": (
                "import torch; "
                "torch.save({'state_dict': model.state_dict()}, 'model.pt', "
                "_extra_files={'ecotrack_label.json': embedded_json})"
            ),
            "safetensors": (
                "from safetensors.torch import save_file; "
                "save_file(model.state_dict(), 'model.safetensors', "
                "metadata={'ecotrack': embedded_json})"
            ),
        },
    }
