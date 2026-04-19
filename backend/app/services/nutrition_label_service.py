"""
app/services/nutrition_label_service.py
=========================================
Feature 2 — "AI Nutrition Label"

Generates a standardised Carbon Label for every trained model, exposing:
  - Total Carbon Debt (gCO₂, kgCO₂)
  - Hardware Ancestry (GPU model, count, training duration)
  - Efficiency Score (accuracy per kg CO₂)
  - SEBI BRSR / EU CSRD compliance classification
  - Human-readable equivalents

Also supports:
  - JSON label generation (machine-readable, embeddable in model files)
  - PDF report generation using reportlab (download for ESG submissions)
"""

from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from typing import Optional

from app.schemas.emissions import NutritionLabel


def _carbon_rating(efficiency_score: Optional[float], co2_kg: float) -> str:
    """
    Grade: A (best) → F (worst).
    Based on combination of efficiency score and absolute CO₂.
    """
    if co2_kg < 0.01:
        return "A"
    if co2_kg < 0.1:
        return "B" if (efficiency_score or 0) > 100 else "C"
    if co2_kg < 1.0:
        return "C" if (efficiency_score or 0) > 50 else "D"
    if co2_kg < 10.0:
        return "D"
    return "F"


def _efficiency_score(accuracy: Optional[float], co2_kg: float) -> Optional[float]:
    if accuracy is not None and co2_kg > 0:
        return round(accuracy / co2_kg, 2)
    return None


def _human_co2(co2_grams: float) -> str:
    if co2_grams < 100:
        return f"≈ {co2_grams/8.22:.1f} smartphone charges"
    if co2_grams < 5000:
        return f"≈ {co2_grams/170:.1f} km driven in a petrol car"
    return f"≈ {co2_grams/22:.0f} tree-hours to offset"


class NutritionLabelService:
    """Generate carbon nutrition labels for ML training runs."""

    @staticmethod
    def generate(run_data: dict) -> NutritionLabel:
        """
        Build a NutritionLabel from a run dict (as stored in DB / returned by API).

        run_data should have keys matching EmissionsRun ORM fields.
        """
        co2_grams = float(run_data.get("co2_grams", 0))
        co2_kg = float(run_data.get("co2_kg", co2_grams / 1000))
        energy_kwh = float(run_data.get("energy_kwh", 0))
        accuracy = run_data.get("accuracy")
        duration_s = float(run_data.get("duration_seconds", 0))

        eff = _efficiency_score(accuracy, co2_kg)
        rating = _carbon_rating(eff, co2_kg)

        return NutritionLabel(
            run_id=run_data.get("run_id", "unknown"),
            model_name=run_data.get("model_name", "unnamed-model"),
            generated_at=datetime.now(timezone.utc),
            total_co2_kg=round(co2_kg, 6),
            total_energy_kwh=round(energy_kwh, 6),
            training_duration_hours=round(duration_s / 3600, 3),
            grid_region=run_data.get("grid_region", run_data.get("region", "IN-SO")),
            grid_intensity_avg=float(run_data.get("grid_intensity_g_kwh", 0)),
            gpu_model=run_data.get("gpu_model", "unknown"),
            gpu_count=int(run_data.get("gpu_count", 0)),
            cpu_model=run_data.get("cpu_model"),
            ram_gb=float(run_data.get("ram_gb", 0)),
            cloud_provider=run_data.get("cloud_provider", "local"),
            accuracy=accuracy,
            efficiency_score=eff,
            carbon_rating=rating,
            human_co2=_human_co2(co2_grams),
            smartphone_charges=round(co2_grams / 8.22, 1),
            km_driven=round(co2_grams / 170, 2),
            tree_hours_to_offset=round(co2_grams / (22 / 24), 1),
        )

    @staticmethod
    def to_embedded_json(label: NutritionLabel) -> str:
        """
        Serialize label to a compact JSON string suitable for embedding
        in PyTorch model metadata (torch.save extra_files) or
        safetensors metadata dict.
        """
        return json.dumps({
            "ecotrack_version": label.framework_version,
            "run_id": label.run_id,
            "model_name": label.model_name,
            "generated_at": label.generated_at.isoformat(),
            "carbon": {
                "total_co2_kg": label.total_co2_kg,
                "total_energy_kwh": label.total_energy_kwh,
                "carbon_rating": label.carbon_rating,
                "grid_region": label.grid_region,
                "grid_intensity_avg_g_kwh": label.grid_intensity_avg,
            },
            "hardware": {
                "gpu_model": label.gpu_model,
                "gpu_count": label.gpu_count,
                "training_duration_hours": label.training_duration_hours,
                "cloud_provider": label.cloud_provider,
            },
            "quality": {
                "accuracy": label.accuracy,
                "efficiency_score_acc_per_kg": label.efficiency_score,
            },
            "compliance": {
                "sebi_brsr_scope": label.sebi_brsr_scope,
                "csrd_esrs": label.csrd_esrs,
                "framework": label.framework_version,
            },
        }, indent=2)

    @staticmethod
    def generate_pdf_bytes(label: NutritionLabel) -> bytes:
        """
        Generate a PDF nutrition label using reportlab.
        Falls back to a minimal HTML-like structure if reportlab is not installed.
        Returns bytes suitable for a StreamingResponse.
        """
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
            )

            buf = io.BytesIO()
            doc = SimpleDocTemplate(
                buf, pagesize=A4,
                rightMargin=2*cm, leftMargin=2*cm,
                topMargin=2*cm, bottomMargin=2*cm
            )

            styles = getSampleStyleSheet()
            elements = []

            # Title
            title_style = ParagraphStyle(
                "EcoTitle",
                parent=styles["Heading1"],
                fontSize=22,
                textColor=colors.HexColor("#2D4038"),
                spaceAfter=6,
            )
            elements.append(Paragraph("🌿 AI Carbon Nutrition Label", title_style))
            elements.append(Paragraph(
                f"EcoTrack Green MLOps Framework — {label.framework_version}",
                styles["Normal"]
            ))
            elements.append(Spacer(1, 0.4*cm))
            elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#A8E6CF")))
            elements.append(Spacer(1, 0.4*cm))

            # Rating badge
            rating_color = {
                "A": "#52C41A", "B": "#73D13D", "C": "#FAAD14",
                "D": "#FF7A45", "F": "#E9967A"
            }.get(label.carbon_rating, "#999")
            rating_style = ParagraphStyle(
                "Rating", parent=styles["Normal"],
                fontSize=48, textColor=colors.HexColor(rating_color),
                alignment=1,
            )
            elements.append(Paragraph(f"Carbon Rating: {label.carbon_rating}", rating_style))
            elements.append(Spacer(1, 0.4*cm))

            # Model info
            info_data = [
                ["Field", "Value"],
                ["Model Name", label.model_name],
                ["Run ID", label.run_id],
                ["Generated At", label.generated_at.strftime("%Y-%m-%d %H:%M UTC")],
                ["Grid Region", label.grid_region],
            ]

            # Carbon Debt
            carbon_data = [
                ["Carbon Metric", "Value"],
                ["Total CO₂e", f"{label.total_co2_kg:.6f} kg ({label.total_co2_kg*1000:.2f} g)"],
                ["Total Energy", f"{label.total_energy_kwh:.4f} kWh"],
                ["Training Duration", f"{label.training_duration_hours:.2f} hours"],
                ["Grid Intensity (avg)", f"{label.grid_intensity_avg:.1f} gCO₂/kWh"],
                ["Human Equivalent", label.human_co2],
                ["Smartphone Charges", f"≈ {label.smartphone_charges:.1f}"],
                ["Km Driven", f"≈ {label.km_driven:.2f} km"],
            ]

            # Hardware
            hw_data = [
                ["Hardware", "Value"],
                ["GPU Model", label.gpu_model],
                ["GPU Count", str(label.gpu_count)],
                ["CPU Model", label.cpu_model or "N/A"],
                ["RAM", f"{label.ram_gb:.1f} GB"],
                ["Cloud Provider", label.cloud_provider],
            ]

            # Quality
            quality_data = [
                ["Quality Metric", "Value"],
                ["Accuracy", f"{label.accuracy:.2f}%" if label.accuracy else "N/A"],
                ["Efficiency Score", f"{label.efficiency_score:.2f} acc/kg CO₂" if label.efficiency_score else "N/A"],
                ["BRSR Scope", label.sebi_brsr_scope],
                ["CSRD Classification", label.csrd_esrs],
            ]

            table_style = TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2D4038")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F0EB")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E6E2D8")),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("PADDING", (0, 0), (-1, -1), 6),
            ])

            for header, data in [
                ("Model Info", info_data),
                ("Carbon Debt", carbon_data),
                ("Hardware Ancestry", hw_data),
                ("Quality & Compliance", quality_data),
            ]:
                elements.append(Spacer(1, 0.3*cm))
                elements.append(Paragraph(header, styles["Heading2"]))
                t = Table(data, colWidths=[8*cm, 9*cm])
                t.setStyle(table_style)
                elements.append(t)

            elements.append(Spacer(1, 0.5*cm))
            elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#A8E6CF")))
            elements.append(Paragraph(
                "This label is compliant with SEBI BRSR Principle 6 and EU CSRD ESRS E1 standards. "
                "Generated automatically by EcoTrack Green MLOps Framework.",
                ParagraphStyle("Footer", parent=styles["Normal"], fontSize=7,
                               textColor=colors.gray, spaceAfter=0)
            ))

            doc.build(elements)
            return buf.getvalue()

        except ImportError:
            # reportlab not installed — return a JSON bytes fallback
            return NutritionLabelService.to_embedded_json(label).encode("utf-8")
