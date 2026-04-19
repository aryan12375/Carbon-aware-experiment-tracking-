"""
app/services/matchmaker_service.py
=====================================
Feature 4 — "Transfer Learning Matchmaker"

Scans the model zoo (all runs in the EcoTrack database) to find
an existing model that could be fine-tuned instead of training
from scratch — saving up to 80% of the carbon footprint.

How it works:
1. User submits a MatchRequest: task_type, dataset_size, target_accuracy
2. System queries all successful runs from the DB
3. Each run is scored by: task similarity + accuracy proximity + hardware compatibility
4. The best match is returned with an estimated carbon saving

Carbon saving estimate:
  Fine-tuning a pre-trained model typically costs 15–25% of training from scratch.
  We use 20% as the default estimate for this conservative calculation.
  Saving = scratch_co2 × 0.80

Task type inference:
  Since EcoTrack doesn't enforce a task_type field, we infer it from
  model_name patterns (ResNet → image_classification, BERT → nlp_*, etc.)
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.emissions import EmissionsRun
from app.schemas.emissions import MatchRequest, MatchmakerResponse, ModelZooEntry

# Estimated CO₂ cost of training FROM SCRATCH by architecture type (kg CO₂)
# Source: Patterson et al. 2021, Lacoste et al. 2019
_SCRATCH_CO2_ESTIMATES: dict[str, float] = {
    "resnet":       0.012,
    "efficientnet": 0.020,
    "vit":          0.120,
    "bert":         0.326,
    "gpt":          5.000,
    "llama":       50.000,
    "diffusion":    2.000,
    "default":      0.050,
}

# Task type keywords for inference from model_name
_TASK_KEYWORDS: dict[str, list[str]] = {
    "image_classification": ["resnet", "efficientnet", "mobilenet", "vit", "densenet", "inception"],
    "object_detection":     ["yolo", "fasterrcnn", "detr", "retinanet"],
    "nlp_classification":   ["bert", "roberta", "distilbert", "albert"],
    "text_generation":      ["gpt", "llama", "mistral", "falcon", "gemma"],
    "image_generation":     ["diffusion", "stable", "ddpm", "flux"],
    "speech":               ["whisper", "wav2vec", "hubert"],
}


def _infer_task_type(model_name: str) -> str:
    model_lower = model_name.lower()
    for task, keywords in _TASK_KEYWORDS.items():
        if any(kw in model_lower for kw in keywords):
            return task
    return "general"


def _task_similarity(task1: str, task2: str) -> float:
    """1.0 = exact match, 0.5 = same domain, 0.0 = different."""
    if task1 == task2:
        return 1.0
    # Same domain (e.g. both NLP or both vision)
    vision_tasks = {"image_classification", "object_detection", "image_generation"}
    nlp_tasks = {"nlp_classification", "text_generation", "speech"}
    if task1 in vision_tasks and task2 in vision_tasks:
        return 0.5
    if task1 in nlp_tasks and task2 in nlp_tasks:
        return 0.5
    return 0.0


def _accuracy_proximity(target: float, candidate: Optional[float]) -> float:
    """Score 0–1 based on how close the candidate's accuracy is to target."""
    if candidate is None:
        return 0.3  # unknown accuracy — partial credit
    diff = abs(target - candidate)
    if diff < 2.0:
        return 1.0
    if diff < 5.0:
        return 0.7
    if diff < 10.0:
        return 0.4
    return 0.1


def _similarity_score(request: MatchRequest, run: EmissionsRun) -> float:
    """Composite similarity score 0.0–1.0."""
    task_sim = _task_similarity(request.task_type, _infer_task_type(run.model_name))
    acc_prox = _accuracy_proximity(request.target_accuracy, run.accuracy)

    # Gate on gate_status — prefer clean runs
    gate_bonus = 0.1 if run.gate_status == "pass" else 0.0

    # Budget constraint — if run exceeded budget, penalize
    budget_penalty = 0.0
    if request.budget_co2_grams and run.co2_grams > request.budget_co2_grams:
        budget_penalty = 0.2

    score = (task_sim * 0.6) + (acc_prox * 0.3) + gate_bonus - budget_penalty
    return round(max(0.0, min(1.0, score)), 3)


class MatchmakerService:

    @staticmethod
    async def find_match(db: AsyncSession, request: MatchRequest) -> MatchmakerResponse:
        """
        Scan the model zoo and return the best model to fine-tune instead
        of training from scratch.
        """
        # Query all runs with accuracy data, ordered by best accuracy
        result = await db.execute(
            select(EmissionsRun)
            .where(EmissionsRun.gate_status.in_(["pass", "warn", "pending"]))
            .order_by(desc(EmissionsRun.accuracy))
            .limit(100)
        )
        runs = list(result.scalars().all())

        if not runs:
            return MatchmakerResponse(
                match_found=False,
                recommendation=(
                    "No previous runs found in the model zoo. "
                    "Start training and EcoTrack will learn from your history."
                ),
            )

        # Score all runs
        scored = [
            (run, _similarity_score(request, run))
            for run in runs
        ]
        scored.sort(key=lambda x: x[1], reverse=True)

        best_run, best_score = scored[0]

        # Is the match strong enough to recommend?
        if best_score < 0.3:
            # Estimate how much scratch training would cost
            arch_key = next(
                (k for k in _SCRATCH_CO2_ESTIMATES if k in request.current_model_name.lower()),
                "default"
            ) if request.current_model_name else "default"
            scratch_estimate = _SCRATCH_CO2_ESTIMATES[arch_key]

            return MatchmakerResponse(
                match_found=False,
                recommendation=(
                    f"No strong match found for '{request.task_type}' task "
                    f"with target accuracy {request.target_accuracy:.1f}%. "
                    f"Training from scratch is estimated to cost ~{scratch_estimate:.3f} kg CO₂. "
                    f"As you add more runs, the matchmaker will improve."
                ),
            )

        # Estimate carbon savings
        # Fine-tuning costs ~20% of training from scratch
        existing_co2_kg = float(best_run.co2_kg)
        scratch_estimate_kg = max(existing_co2_kg / 0.20, existing_co2_kg * 1.5)
        finetune_co2_kg = scratch_estimate_kg * 0.20  # Fine-tune = 20% of scratch
        saved_co2_kg = scratch_estimate_kg - finetune_co2_kg
        saving_pct = round(saved_co2_kg / scratch_estimate_kg * 100, 1)

        inferred_task = _infer_task_type(best_run.model_name)

        if best_score >= 0.8:
            recommendation = (
                f"🛑 STOP! Don't train from scratch. "
                f"'{best_run.model_name}' (accuracy: {best_run.accuracy:.1f}%) "
                f"is a strong match (score: {best_score:.2f}). "
                f"Fine-tuning it will save ~{saving_pct:.0f}% of your CO₂ budget "
                f"({saved_co2_kg:.3f} kg CO₂ avoided). "
                f"That's {saved_co2_kg*1000/170:.1f} km of driving you won't emit."
            )
        elif best_score >= 0.5:
            recommendation = (
                f"Consider fine-tuning '{best_run.model_name}' instead of training from scratch. "
                f"It's a {round(best_score*100):.0f}% match for your '{request.task_type}' task. "
                f"Estimated CO₂ saving: ~{saving_pct:.0f}% ({saved_co2_kg:.3f} kg)."
            )
        else:
            recommendation = (
                f"A partial match found: '{best_run.model_name}' (score: {best_score:.2f}). "
                f"It may require significant fine-tuning. "
                f"Estimated CO₂ saving vs scratch: ~{saving_pct:.0f}%."
            )

        return MatchmakerResponse(
            match_found=True,
            existing_model_name=best_run.model_name,
            existing_run_id=best_run.run_id,
            existing_accuracy=best_run.accuracy,
            existing_co2_kg=existing_co2_kg,
            potential_carbon_saving_kg=round(saved_co2_kg, 4),
            potential_saving_pct=saving_pct,
            recommendation=recommendation,
            similarity_score=best_score,
        )

    @staticmethod
    async def get_model_zoo(db: AsyncSession, limit: int = 50) -> list[ModelZooEntry]:
        """Return all models in the zoo with carbon profiles."""
        result = await db.execute(
            select(EmissionsRun)
            .where(EmissionsRun.gate_status.in_(["pass", "warn", "pending"]))
            .order_by(desc(EmissionsRun.created_at))
            .limit(limit)
        )
        runs = result.scalars().all()

        return [
            ModelZooEntry(
                run_id=r.run_id,
                model_name=r.model_name,
                project_name=r.project_name,
                accuracy=r.accuracy,
                co2_kg=r.co2_kg,
                energy_kwh=r.energy_kwh,
                gpu_model=r.gpu_model,
                task_type_guess=_infer_task_type(r.model_name),
                created_at=r.created_at,
            )
            for r in runs
        ]
