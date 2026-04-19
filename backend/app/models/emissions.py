"""
app/models/emissions.py
========================
SQLAlchemy ORM models for EcoTrack.

Tables
------
  emissions_runs   — one row per training job
  gate_decisions   — one row per CI/CD gate evaluation (FK → emissions_runs)
  projects         — optional project grouping
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Projects ──────────────────────────────────────────────────────────────

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    team: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )

    # Relationships
    runs: Mapped[list["EmissionsRun"]] = relationship(
        "EmissionsRun", back_populates="project", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Project id={self.id} name={self.name!r}>"


# ── Emissions runs ────────────────────────────────────────────────────────

class EmissionsRun(Base):
    """
    One row per ML training run.
    Written by tracker_utils.py (or POSTed directly by CI).
    """
    __tablename__ = "emissions_runs"

    # ── Identity ─────────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False)
    commit_id: Mapped[str] = mapped_column(String(40), nullable=False, default="no-git")
    project_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    project_name: Mapped[str] = mapped_column(String(120), nullable=False, default="unnamed")
    model_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)

    # ── Timing ───────────────────────────────────────────────────────────
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # ── Carbon metrics ───────────────────────────────────────────────────
    co2_grams: Mapped[float] = mapped_column(Float, nullable=False)
    co2_kg: Mapped[float] = mapped_column(Float, nullable=False)
    energy_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    grid_intensity_g_kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    grid_source: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
    grid_region: Mapped[str] = mapped_column(String(20), nullable=False, default="IN-SO")

    # ── Hardware ─────────────────────────────────────────────────────────
    gpu_model: Mapped[str] = mapped_column(String(80), nullable=False, default="unknown")
    gpu_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cpu_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ram_gb: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cloud_provider: Mapped[str] = mapped_column(String(40), nullable=False, default="local")

    # ── Model quality ────────────────────────────────────────────────────
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    extra_metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)   # JSON blob

    # ── Gate result (denormalised for quick queries) ──────────────────────
    gate_status: Mapped[str] = mapped_column(
        String(10), nullable=False, default="pending", index=True
    )   # "pass" | "fail" | "warn" | "pending"

    # ── Audit ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    # ── Relationships ─────────────────────────────────────────────────────
    project: Mapped["Project | None"] = relationship("Project", back_populates="runs")
    gate_decision: Mapped["GateDecision | None"] = relationship(
        "GateDecision", back_populates="run", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<EmissionsRun run_id={self.run_id!r} model={self.model_name!r} co2={self.co2_grams}g>"


# ── Gate decisions ────────────────────────────────────────────────────────

class GateDecision(Base):
    """
    One row per Green Gate evaluation.
    Foreign-keyed to the run being evaluated.
    """
    __tablename__ = "gate_decisions"
    __table_args__ = (
        UniqueConstraint("run_id", name="uq_gate_run_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("emissions_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Gate result
    status: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    exit_code: Mapped[int] = mapped_column(Integer, nullable=False)

    # Deltas
    delta_accuracy_pp: Mapped[float | None] = mapped_column(Float, nullable=True)
    delta_co2_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    delta_co2_grams: Mapped[float | None] = mapped_column(Float, nullable=True)
    delta_energy_kwh: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Context
    reasons_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    suggestions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    previous_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )

    # Relationship back to run
    run: Mapped["EmissionsRun"] = relationship("EmissionsRun", back_populates="gate_decision")

    def __repr__(self) -> str:
        return f"<GateDecision run_id={self.run_id!r} status={self.status!r}>"
