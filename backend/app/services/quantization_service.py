"""
app/services/quantization_service.py
======================================
Feature 3 — "Automatic Quantization Gating"

Analyses a training run and determines whether the model should be
automatically quantized (FP32 → INT8 / 4-bit) before deployment.

Gate decision:
  FORCE_QUANTIZED   — accuracy retention ≥ threshold AND energy saving ≥ threshold
  RECOMMEND_QUANTIZED — accuracy marginally above threshold
  KEEP_FP32         — quantization would significantly degrade accuracy

Quantization impact modelling:
  INT8 typically achieves:
    - 50–75% model size reduction (4× compression ratio)
    - 30–60% inference energy reduction
    - 0.5–2% accuracy drop on most classification models
    - Higher deviation on generative / attention-heavy models

Recommended tools:
  - BitsAndBytes  (HuggingFace ecosystem, 4-bit / 8-bit)
  - AutoGPTQ      (generative models)
  - ONNX Runtime  (cross-platform, highest inference performance)
  - TorchScript + torch.ao.quantization (built-in PyTorch)
"""

from __future__ import annotations

import math
from typing import Optional

from app.schemas.emissions import QuantizationAnalysis, QuantizationRequest

# Model architecture → quantization sensitivity mapping
# Lower = less accuracy degradation from quantization
_ARCH_SENSITIVITY: dict[str, float] = {
    "resnet":          0.3,   # ResNets are very quantization-friendly
    "efficientnet":    0.4,
    "mobilenet":       0.5,   # Already optimised — marginal gains
    "vit":             0.8,   # Transformers are more sensitive
    "bert":            0.9,
    "gpt":             1.2,   # Generative models most sensitive
    "llama":           1.2,
    "diffusion":       1.5,
    "stable":          1.5,
    "default":         0.6,   # Generic fallback
}

# Target precision → expected improvements
_PRECISION_PROFILE: dict[str, dict] = {
    "INT8": {
        "energy_reduction": 0.55,      # 55% energy reduction baseline
        "size_reduction": 0.75,        # 75% model size reduction
        "accuracy_drop_base": 1.0,     # 1% baseline accuracy drop
        "tool": "BitsAndBytes",
    },
    "INT4": {
        "energy_reduction": 0.70,
        "size_reduction": 0.875,       # 8× compression
        "accuracy_drop_base": 2.5,
        "tool": "AutoGPTQ",
    },
    "FP16": {
        "energy_reduction": 0.30,
        "size_reduction": 0.50,
        "accuracy_drop_base": 0.1,     # Almost no drop
        "tool": "ONNX Runtime",
    },
}


def _get_sensitivity(model_name: str) -> float:
    model_lower = model_name.lower()
    for key, sensitivity in _ARCH_SENSITIVITY.items():
        if key in model_lower:
            return sensitivity
    return _ARCH_SENSITIVITY["default"]


class QuantizationService:
    """
    Analyses model training runs to determine quantization potential.

    All analysis is heuristic-based (no actual model file required).
    To run actual quantization, use BitsAndBytes / AutoGPTQ directly.
    """

    @staticmethod
    def analyze(
        run_data: dict,
        request: Optional[QuantizationRequest] = None,
        target_precision: str = "INT8",
    ) -> QuantizationAnalysis:
        """
        Analyze a run and produce a quantization verdict.

        Parameters
        ----------
        run_data : dict
            EmissionsRun data (from DB or API response)
        request : QuantizationRequest, optional
            Custom thresholds; defaults to 98% retention, 40% energy saving
        target_precision : str
            "INT8", "INT4", or "FP16"
        """
        acc_threshold = request.accuracy_retention_threshold if request else 98.0
        energy_threshold = request.energy_reduction_threshold if request else 40.0

        model_name = run_data.get("model_name", "unknown")
        original_accuracy = run_data.get("accuracy")
        co2_kg = float(run_data.get("co2_kg", 0))
        energy_kwh = float(run_data.get("energy_kwh", 0))

        profile = _PRECISION_PROFILE.get(target_precision, _PRECISION_PROFILE["INT8"])
        sensitivity = _get_sensitivity(model_name)

        # ── Compute predictions ───────────────────────────────────────────
        # Accuracy drop = base_drop × architecture_sensitivity
        accuracy_drop_pct = profile["accuracy_drop_base"] * sensitivity
        accuracy_retention_pct = round(100.0 - accuracy_drop_pct, 2)

        # Energy reduction is modulated by architecture sensitivity
        # (more complex models have more overhead → larger relative savings)
        energy_reduction_pct = round(profile["energy_reduction"] * 100 * (1 + sensitivity * 0.1), 1)
        energy_reduction_pct = min(energy_reduction_pct, 85.0)  # cap at 85%

        co2_reduction_pct = round(energy_reduction_pct * 0.95, 1)  # CO₂ ≈ energy × grid intensity

        model_size_reduction_pct = round(profile["size_reduction"] * 100, 1)

        # ── Determine verdict ─────────────────────────────────────────────
        passes_threshold = (
            accuracy_retention_pct >= acc_threshold
            and energy_reduction_pct >= energy_threshold
        )

        if passes_threshold and accuracy_retention_pct >= 99.0:
            verdict = "FORCE_QUANTIZED"
            reason = (
                f"Quantization to {target_precision} maintains {accuracy_retention_pct:.1f}% "
                f"of original accuracy while reducing energy consumption by {energy_reduction_pct:.1f}%. "
                f"System will force deployment of the quantized model."
            )
        elif passes_threshold:
            verdict = "RECOMMEND_QUANTIZED"
            reason = (
                f"Quantization to {target_precision} meets thresholds "
                f"({accuracy_retention_pct:.1f}% retention, {energy_reduction_pct:.1f}% energy saving). "
                f"Strongly recommended for deployment."
            )
        elif accuracy_retention_pct < acc_threshold and accuracy_retention_pct >= 95.0:
            verdict = "KEEP_FP32"
            reason = (
                f"{model_name} is sensitivity class {sensitivity:.1f} — {target_precision} quantization "
                f"drops accuracy to {accuracy_retention_pct:.1f}% (below your {acc_threshold:.0f}% threshold). "
                f"Consider FP16 mixed precision instead (use torch.cuda.amp)."
            )
        else:
            verdict = "KEEP_FP32"
            reason = (
                f"This architecture shows high quantization sensitivity (score: {sensitivity:.1f}). "
                f"Estimated accuracy retention {accuracy_retention_pct:.1f}% is below threshold. "
                f"Suggested alternative: FP16 training with mixed precision."
            )

        estimated_co2_saved_kg = round(co2_kg * co2_reduction_pct / 100, 6)

        return QuantizationAnalysis(
            run_id=run_data.get("run_id", "unknown"),
            model_name=model_name,
            original_precision="FP32",
            target_precision=target_precision,
            accuracy_retention_pct=accuracy_retention_pct,
            energy_reduction_pct=energy_reduction_pct,
            co2_reduction_pct=co2_reduction_pct,
            model_size_reduction_pct=model_size_reduction_pct,
            passes_threshold=passes_threshold,
            verdict=verdict,
            reason=reason,
            estimated_co2_saved_kg=estimated_co2_saved_kg,
            recommended_tool=profile["tool"],
        )

    @staticmethod
    def generate_code_snippet(analysis: QuantizationAnalysis) -> str:
        """Return a ready-to-use code snippet for the recommended tool."""
        if analysis.recommended_tool == "BitsAndBytes":
            return f"""import torch
from transformers import AutoModelForImageClassification, BitsAndBytesConfig

# Load with 8-bit quantization — {analysis.energy_reduction_pct:.0f}% energy saving
bnb_config = BitsAndBytesConfig(load_in_8bit=True)
model = AutoModelForImageClassification.from_pretrained(
    "your-model-path",
    quantization_config=bnb_config,
    device_map="auto",
)
# EcoTrack Grade: {analysis.verdict} | CO₂ Saved: {analysis.estimated_co2_saved_kg:.4f} kg"""

        elif analysis.recommended_tool == "AutoGPTQ":
            return f"""from auto_gptq import AutoGPTQForCausalLM, BaseQuantizeConfig

quantize_config = BaseQuantizeConfig(bits=4, group_size=128)
model = AutoGPTQForCausalLM.from_pretrained("your-model-path", quantize_config)
# EcoTrack Grade: {analysis.verdict} | CO₂ Saved: {analysis.estimated_co2_saved_kg:.4f} kg"""

        else:
            return f"""import torch

# Enable automatic mixed precision (FP16)
with torch.cuda.amp.autocast():
    outputs = model(inputs)
# EcoTrack Grade: {analysis.verdict} | CO₂ Saved: {analysis.estimated_co2_saved_kg:.4f} kg"""
