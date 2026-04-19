"""
app/schemas/emissions.py
=========================
Pydantic v2 schemas for request validation and response serialisation.
Strict input validation, computed fields, and clean API contracts.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)


# ── Shared config ─────────────────────────────────────────────────────────
class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ══════════════════════════════════════════════════════════════════════════
# Project schemas
# ══════════════════════════════════════════════════════════════════════════

class ProjectCreate(_Base):
    name: str = Field(..., min_length=1, max_length=120, examples=["EfficientNet-Research"])
    description: Optional[str] = Field(None, max_length=500)
    team: Optional[str] = Field(None, max_length=80)


class ProjectUpdate(_Base):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    description: Optional[str] = None
    team: Optional[str] = None


class ProjectOut(_Base):
    id: int
    name: str
    description: Optional[str]
    team: Optional[str]
    created_at: datetime
    run_count: Optional[int] = None

    @classmethod
    def from_orm_with_count(cls, project: Any, count: int) -> "ProjectOut":
        obj = cls.model_validate(project)
        obj.run_count = count
        return obj


# ══════════════════════════════════════════════════════════════════════════
# Emissions Run schemas
# ══════════════════════════════════════════════════════════════════════════

class EmissionsRunCreate(_Base):
    """
    Schema for ingesting a new run — sent by tracker_utils.py or CI pipeline.
    Accepts the full JSON blob written by EcoTracker.stop().
    """
    run_id: str = Field(..., min_length=4, max_length=36)
    commit_id: str = Field("no-git", max_length=40)
    project_name: str = Field("unnamed", max_length=120)
    model_name: str = Field(..., min_length=1, max_length=120)

    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_seconds: float = Field(0.0, ge=0)

    # Carbon
    co2_grams: float = Field(..., ge=0, description="CO₂ in grams")
    co2_kg: float = Field(..., ge=0, description="CO₂ in kilograms")
    energy_kwh: float = Field(..., ge=0)
    grid_intensity_g_kwh: float = Field(0.0, ge=0)
    grid_source: str = Field("unknown", max_length=40)
    grid_region: str = Field("IN-SO", max_length=20)

    # Hardware
    gpu_model: str = Field("unknown", max_length=80)
    gpu_count: int = Field(0, ge=0)
    cpu_model: Optional[str] = Field(None, max_length=120)
    ram_gb: float = Field(0.0, ge=0)
    cloud_provider: str = Field("local", max_length=40)

    # Model quality
    accuracy: Optional[float] = Field(None, ge=0, le=100)
    loss: Optional[float] = Field(None, ge=0)
    extra_metrics: Optional[dict[str, Any]] = None

    @field_validator("run_id")
    @classmethod
    def strip_run_id(cls, v: str) -> str:
        return v.strip()

    @model_validator(mode="after")
    def co2_consistency(self) -> "EmissionsRunCreate":
        """Ensure co2_kg and co2_grams are consistent (within 1g tolerance)."""
        if abs(self.co2_grams - self.co2_kg * 1000) > 1.0:
            # Auto-fix: trust co2_grams as the source of truth
            self.co2_kg = self.co2_grams / 1000
        return self


class EmissionsRunUpdate(_Base):
    """Partial update — only supply fields to change."""
    accuracy: Optional[float] = Field(None, ge=0, le=100)
    loss: Optional[float] = Field(None, ge=0)
    gate_status: Optional[str] = Field(None, pattern="^(pass|fail|warn|pending)$")
    extra_metrics: Optional[dict[str, Any]] = None


class EmissionsRunOut(_Base):
    """Full response schema — what the API returns."""
    id: int
    run_id: str
    commit_id: str
    project_name: str
    model_name: str

    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    duration_seconds: float

    co2_grams: float
    co2_kg: float
    energy_kwh: float
    grid_intensity_g_kwh: float
    grid_source: str
    grid_region: str

    gpu_model: str
    gpu_count: int
    cpu_model: Optional[str]
    ram_gb: float
    cloud_provider: str

    accuracy: Optional[float]
    loss: Optional[float]

    gate_status: str
    created_at: datetime

    # Computed — human equivalents and efficiency score
    @computed_field
    @property
    def human_co2(self) -> str:
        g = self.co2_grams
        if g < 100:
            return f"≈ {g/8.22:.1f} smartphone charges"
        if g < 5000:
            return f"≈ {g/170:.1f} km driven"
        return f"≈ {g/22:.0f} tree-days to offset"

    @computed_field
    @property
    def efficiency_score(self) -> Optional[float]:
        """Accuracy per kg CO₂ — higher is better."""
        if self.accuracy is not None and self.co2_kg > 0:
            return round(self.accuracy / self.co2_kg, 2)
        return None


class EmissionsRunSummary(_Base):
    """Lightweight list item — used in paginated responses."""
    id: int
    run_id: str
    model_name: str
    co2_grams: float
    energy_kwh: float
    accuracy: Optional[float]
    gate_status: str
    created_at: datetime


# ══════════════════════════════════════════════════════════════════════════
# Gate Decision schemas
# ══════════════════════════════════════════════════════════════════════════

class GateDecisionCreate(_Base):
    run_id: str
    status: str = Field(..., pattern="^(PASS|FAIL|WARN)$")
    exit_code: int = Field(..., ge=0, le=2)
    delta_accuracy_pp: Optional[float] = None
    delta_co2_pct: Optional[float] = None
    delta_co2_grams: Optional[float] = None
    delta_energy_kwh: Optional[float] = None
    reasons: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    previous_run_id: Optional[str] = None
    dry_run: bool = False


def _parse_json_list(v: Any) -> list[str]:
    """Parse a JSON string into a list, or return the value as-is."""
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return []
    return v or []


class GateDecisionOut(_Base):
    id: int
    run_id: str
    status: str
    exit_code: int
    delta_accuracy_pp: Optional[float]
    delta_co2_pct: Optional[float]
    delta_co2_grams: Optional[float]
    delta_energy_kwh: Optional[float]
    reasons: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    previous_run_id: Optional[str]
    dry_run: bool
    evaluated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _coerce_from_orm(cls, data: Any) -> Any:
        # ORM stores reasons/suggestions as reasons_json/suggestions_json
        # Remap so Pydantic fields get the right values
        if hasattr(data, "reasons_json"):
            return {
                "id": data.id,
                "run_id": data.run_id,
                "status": data.status,
                "exit_code": data.exit_code,
                "delta_accuracy_pp": data.delta_accuracy_pp,
                "delta_co2_pct": data.delta_co2_pct,
                "delta_co2_grams": data.delta_co2_grams,
                "delta_energy_kwh": data.delta_energy_kwh,
                "reasons": _parse_json_list(data.reasons_json),
                "suggestions": _parse_json_list(data.suggestions_json),
                "previous_run_id": data.previous_run_id,
                "dry_run": data.dry_run,
                "evaluated_at": data.evaluated_at,
            }
        return data


# ══════════════════════════════════════════════════════════════════════════
# Analytics & Stats schemas
# ══════════════════════════════════════════════════════════════════════════

class DashboardStats(_Base):
    total_runs: int
    total_co2_kg: float
    total_energy_kwh: float
    avg_accuracy: Optional[float]
    gate_pass_rate: float          # 0–1
    top_emitter_model: Optional[str]
    best_efficiency_model: Optional[str]
    co2_trend_7d: float            # % change vs prior 7 days
    human_total_co2: str           # e.g. "≈ 420 smartphone charges"


class EfficiencyPoint(_Base):
    """One point on the Accuracy vs CO₂ scatter plot."""
    run_id: str
    model_name: str
    accuracy: Optional[float]
    co2_grams: float
    energy_kwh: float
    gpu_model: str
    gate_status: str
    created_at: datetime


class GpuComparisonRow(_Base):
    gpu_model: str
    run_count: int
    avg_co2_grams: float
    avg_energy_kwh: float
    avg_accuracy: Optional[float]
    avg_efficiency_score: Optional[float]
    total_co2_kg: float


class TrendPoint(_Base):
    date: str          # YYYY-MM-DD
    co2_grams: float
    energy_kwh: float
    run_count: int
    avg_accuracy: Optional[float]


# ══════════════════════════════════════════════════════════════════════════
# Advanced Features v2 (Simulation & Matchmaker)
# ══════════════════════════════════════════════════════════════════════════

class CloudSimulationPoint(_Base):
    region: str
    provider: str
    grid_intensity: float
    estimated_co2_grams: float
    carbon_rating: str  # A, B, C, D, F

class SimulationResult(_Base):
    base_energy_kwh: float
    simulations: list[CloudSimulationPoint]

class MatchmakerResponse(_Base):
    match_found: bool
    existing_model_name: Optional[str] = None
    existing_run_id: Optional[str] = None
    existing_accuracy: Optional[float] = None
    existing_co2_kg: Optional[float] = None
    potential_carbon_saving_kg: Optional[float] = None
    potential_saving_pct: Optional[float] = None
    recommendation: str
    similarity_score: Optional[float] = None


# ══════════════════════════════════════════════════════════════════════════
# Feature 1 — Green-Pause Scheduler schemas
# ══════════════════════════════════════════════════════════════════════════

class GridForecastPoint(_Base):
    """One hour slot of carbon intensity forecast."""
    hour: int                   # 0–23 in local time
    intensity_g_kwh: float      # gCO₂/kWh
    label: str                  # "clean" | "moderate" | "dirty"
    is_optimal: bool            # recommended window

class GridIntensityResponse(_Base):
    region: str
    current_intensity: float
    current_label: str
    source: str
    forecast: list[GridForecastPoint]
    optimal_windows: list[str]  # e.g. ["10:00-14:00", "02:00-05:00"]
    potential_saving_pct: float

class SchedulerWindow(_Base):
    start_hour: int
    end_hour: int
    avg_intensity: float
    estimated_saving_pct: float
    label: str


# ══════════════════════════════════════════════════════════════════════════
# Feature 2 — AI Nutrition Label schemas
# ══════════════════════════════════════════════════════════════════════════

class NutritionLabel(_Base):
    """Standardised carbon label — embeddable in model files."""
    run_id: str
    model_name: str
    generated_at: datetime

    # Carbon Debt section
    total_co2_kg: float
    total_energy_kwh: float
    training_duration_hours: float
    grid_region: str
    grid_intensity_avg: float

    # Hardware Ancestry
    gpu_model: str
    gpu_count: int
    cpu_model: Optional[str]
    ram_gb: float
    cloud_provider: str

    # Efficiency Score
    accuracy: Optional[float]
    efficiency_score: Optional[float]   # accuracy / CO₂kg
    carbon_rating: str                  # A–F

    # Compliance
    sebi_brsr_scope: str = "Scope 2"
    csrd_esrs: str = "ESRS E1"
    framework_version: str = "EcoTrack v1.0"

    # Human equivalents
    human_co2: str
    smartphone_charges: float
    km_driven: float
    tree_hours_to_offset: float


# ══════════════════════════════════════════════════════════════════════════
# Feature 3 — Quantization Gating schemas
# ══════════════════════════════════════════════════════════════════════════

class QuantizationAnalysis(_Base):
    run_id: str
    model_name: str
    original_precision: str = "FP32"
    target_precision: str = "INT8"

    # Predictions
    accuracy_retention_pct: float     # e.g. 99.1 (% of original accuracy kept)
    energy_reduction_pct: float       # e.g. 62.0
    co2_reduction_pct: float
    model_size_reduction_pct: float   # e.g. 75.0 (INT8 = 4x smaller)

    # Verdict
    passes_threshold: bool             # retention ≥ 98% AND energy_reduction ≥ 40%
    verdict: str                       # "FORCE_QUANTIZED" | "RECOMMEND_QUANTIZED" | "KEEP_FP32"
    reason: str
    estimated_co2_saved_kg: float

    # Tool recommendation
    recommended_tool: str = "BitsAndBytes"   # or "AutoGPTQ", "ONNX Runtime"


class QuantizationRequest(_Base):
    run_id: str
    accuracy_retention_threshold: float = Field(98.0, ge=90.0, le=100.0)
    energy_reduction_threshold: float = Field(40.0, ge=10.0, le=90.0)


# ══════════════════════════════════════════════════════════════════════════
# Feature 4 — Transfer Learning Matchmaker schemas
# ══════════════════════════════════════════════════════════════════════════

class MatchRequest(_Base):
    """Input for finding a matching pre-trained model."""
    task_type: str = Field(..., examples=["image_classification", "nlp_classification", "object_detection"])
    dataset_size_millions: float = Field(..., ge=0.001, description="Dataset size in millions of samples")
    target_accuracy: float = Field(..., ge=0.0, le=100.0)
    current_model_name: Optional[str] = None
    budget_co2_grams: Optional[float] = None    # max acceptable CO₂ for training


class ModelZooEntry(_Base):
    """A model in the zoo available for fine-tuning."""
    run_id: str
    model_name: str
    project_name: str
    accuracy: Optional[float]
    co2_kg: float
    energy_kwh: float
    gpu_model: str
    task_type_guess: str      # inferred from model_name
    created_at: datetime


# ══════════════════════════════════════════════════════════════════════════
# Pagination
# ══════════════════════════════════════════════════════════════════════════

class PaginatedRuns(_Base):
    items: list[EmissionsRunSummary]
    total: int
    page: int
    page_size: int
    pages: int


# ══════════════════════════════════════════════════════════════════════════
# BRSR / CSRD Export schemas
# ══════════════════════════════════════════════════════════════════════════

class BrsrReportRequest(_Base):
    financial_year: str = Field("2025-26", pattern=r"^\d{4}-\d{2}$")
    project_names: Optional[list[str]] = None    # None = all projects
    include_gate_failures: bool = True


class BrsrPrincipleC(_Base):
    """BRSR Principle 6 — Environment (relevant sub-section for ML compute)."""
    total_energy_consumed_kwh: float
    energy_from_renewable_pct: float
    total_co2_equivalent_tonnes: float
    co2_reduction_initiatives: list[str]
    scope2_emissions_tonnes: float


class BrsrReport(_Base):
    organisation_name: str
    cin: str
    financial_year: str
    reporting_period_start: str
    reporting_period_end: str
    generated_at: datetime

    # Section A — General Disclosures
    total_ml_training_runs: int
    total_compute_hours: float

    # Section C — Environment (Principle 6)
    principle_6: BrsrPrincipleC

    # EcoTrack-specific extended metrics
    gate_pass_rate_pct: float
    top_5_emitting_models: list[dict]
    gpu_fleet_summary: list[GpuComparisonRow]
    carbon_trend: list[TrendPoint]

    # Compliance flags
    sebi_brsr_compliant: bool = True
    csrd_aligned: bool = True
    framework_version: str = "EcoTrack v1.0"
