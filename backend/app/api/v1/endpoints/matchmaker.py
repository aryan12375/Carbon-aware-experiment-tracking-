"""
app/api/v1/endpoints/matchmaker.py
=====================================
Feature 4 — Transfer Learning Matchmaker endpoints.

POST /matchmaker/find   — find the best model to fine-tune
GET  /matchmaker/zoo    — list all models in the zoo with carbon profiles
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.emissions import MatchRequest, MatchmakerResponse, ModelZooEntry
from app.services.matchmaker_service import MatchmakerService

router = APIRouter(prefix="/matchmaker", tags=["Transfer Learning Matchmaker"])


@router.post(
    "/find",
    response_model=MatchmakerResponse,
    summary="Find the best existing model to fine-tune instead of training from scratch",
    description=(
        "Scans all successful runs in the EcoTrack database and scores them "
        "by task similarity, accuracy proximity, and gate status. "
        "Returns a recommendation with estimated CO₂ savings. "
        "Fine-tuning typically costs ~20% of training from scratch → 80% CO₂ saving."
    ),
)
async def find_match(
    request: MatchRequest,
    db: AsyncSession = Depends(get_db),
) -> MatchmakerResponse:
    return await MatchmakerService.find_match(db, request)


@router.get(
    "/zoo",
    response_model=list[ModelZooEntry],
    summary="List all models in the training zoo",
    description=(
        "Returns all completed, gate-passing runs with their carbon profiles, "
        "accuracy, and inferred task type. Use this to browse available "
        "pre-trained checkpoints before starting a new training job."
    ),
)
async def get_model_zoo(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[ModelZooEntry]:
    return await MatchmakerService.get_model_zoo(db, limit)
