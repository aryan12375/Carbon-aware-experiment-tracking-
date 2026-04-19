"""
check_gate.py
=============
EcoTrack — Green MLOps Framework
---------------------------------
The "Green Gate" — a CI/CD gate script that evaluates whether a new model
training run is ethically and efficiently deplorable from a carbon perspective.

Designed to be run as a GitHub Actions step after every training run.
Exits with code 0 (PASS), 1 (FAIL), or 2 (WARN) so the CI pipeline
can act accordingly.

Gate Logic
----------
  FAIL  if  Δaccuracy < 0.5%  AND  ΔCO₂ > 20%
             (Massive energy waste for negligible gain)

  WARN  if  ΔCO₂ > 40%  (large spike regardless of accuracy gain)
  WARN  if  Δaccuracy < 0.5%  AND  ΔCO₂ > 10%

  PASS  otherwise

Usage (CLI)
-----------
  # Pass JSON paths directly
  python check_gate.py --current emissions/run_abc123.json \\
                       --previous emissions/run_xyz789.json

  # Or point at the emissions directory (auto picks latest two)
  python check_gate.py --dir ./emissions

  # Dry-run mode (never exits non-zero — good for local dev)
  python check_gate.py --dir ./emissions --dry-run

  # Output GitHub Actions step summary
  python check_gate.py --dir ./emissions --github-summary

Author : Aryan (aryan12375) — MIT Manipal
License: MIT
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ── Exit codes ────────────────────────────────────────────────────────────
EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_WARN = 2

# ── Gate thresholds (all configurable via env vars) ───────────────────────
FAIL_ACCURACY_DELTA_MIN = float(os.getenv("GATE_FAIL_ACC_DELTA",  "0.005"))  # 0.5 %
FAIL_CO2_DELTA_MAX      = float(os.getenv("GATE_FAIL_CO2_DELTA",  "0.20"))   # 20 %
WARN_CO2_DELTA_MAX      = float(os.getenv("GATE_WARN_CO2_DELTA",  "0.40"))   # 40 %
WARN_SOFT_CO2_DELTA     = float(os.getenv("GATE_WARN_SOFT_CO2",   "0.10"))   # 10 %
ABSOLUTE_CO2_WARN_G     = float(os.getenv("GATE_ABS_CO2_WARN_G",  "2000"))   # 2 kg
ABSOLUTE_CO2_FAIL_G     = float(os.getenv("GATE_ABS_CO2_FAIL_G",  "10000"))  # 10 kg

# Human-readable equivalents (g CO₂ per unit)
_EQUIV = {
    "smartphone charges": 8.22,
    "km driven":          170.0,
    "cups of tea":        50.0,
}


# ── Data structures ───────────────────────────────────────────────────────

@dataclass
class RunSnapshot:
    """Lightweight view of a single emissions run."""
    run_id:          str
    model_name:      str
    project_name:    str
    commit_id:       str
    co2_grams:       float
    energy_kwh:      float
    accuracy:        Optional[float]
    loss:            Optional[float]
    gpu_model:       str
    duration_sec:    float
    finished_at:     str
    grid_intensity:  float
    grid_source:     str

    @classmethod
    def from_dict(cls, d: dict) -> "RunSnapshot":
        return cls(
            run_id=d.get("run_id", "unknown"),
            model_name=d.get("model_name", "unknown"),
            project_name=d.get("project_name", "unknown"),
            commit_id=d.get("commit_id", "no-git"),
            co2_grams=float(d.get("co2_grams", 0)),
            energy_kwh=float(d.get("energy_kwh", 0)),
            accuracy=d.get("accuracy"),
            loss=d.get("loss"),
            gpu_model=d.get("gpu_model", "unknown"),
            duration_sec=float(d.get("duration_seconds", 0)),
            finished_at=d.get("finished_at", ""),
            grid_intensity=float(d.get("grid_intensity_g_kwh", 0)),
            grid_source=d.get("grid_source", "unknown"),
        )

    @classmethod
    def from_json_file(cls, path: Path) -> "RunSnapshot":
        with open(path) as f:
            return cls.from_dict(json.load(f))


@dataclass
class GateVerdict:
    """Full gate evaluation result."""
    status:          str            # "PASS" | "WARN" | "FAIL"
    exit_code:       int
    reasons:         list[str]
    suggestions:     list[str]

    # Delta metrics
    delta_accuracy:  Optional[float]   # percentage points
    delta_co2_pct:   Optional[float]   # fractional (0.20 = 20%)
    delta_co2_grams: Optional[float]
    delta_energy_kwh: Optional[float]

    current:         RunSnapshot
    previous:        Optional[RunSnapshot]

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "exit_code": self.exit_code,
            "reasons": self.reasons,
            "suggestions": self.suggestions,
            "delta_accuracy_pp": self.delta_accuracy,
            "delta_co2_pct": self.delta_co2_pct,
            "delta_co2_grams": self.delta_co2_grams,
            "delta_energy_kwh": self.delta_energy_kwh,
            "current_run_id": self.current.run_id,
            "previous_run_id": self.previous.run_id if self.previous else None,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }


# ── Gate evaluation logic ─────────────────────────────────────────────────

def evaluate_gate(
    current: RunSnapshot,
    previous: Optional[RunSnapshot],
) -> GateVerdict:
    """
    Core gate logic. Pure function — no I/O, fully testable.

    Returns a GateVerdict with status, reasons, and suggestions.
    """
    reasons:     list[str] = []
    suggestions: list[str] = []
    status = "PASS"
    exit_code = EXIT_PASS

    # ── Compute deltas ────────────────────────────────────────────────────
    delta_accuracy:   Optional[float] = None
    delta_co2_pct:    Optional[float] = None
    delta_co2_grams:  Optional[float] = None
    delta_energy_kwh: Optional[float] = None

    if previous:
        # Accuracy delta in percentage points (e.g. 93.5 - 92.0 = 1.5 pp)
        if current.accuracy is not None and previous.accuracy is not None:
            delta_accuracy = current.accuracy - previous.accuracy

        # CO₂ deltas
        if previous.co2_grams > 0:
            delta_co2_pct   = (current.co2_grams - previous.co2_grams) / previous.co2_grams
            delta_co2_grams = current.co2_grams - previous.co2_grams
        if previous.energy_kwh > 0:
            delta_energy_kwh = current.energy_kwh - previous.energy_kwh

    # NOTE: FAIL_ACCURACY_DELTA_MIN is stored as a fraction (0.005 = 0.5pp)
    # but delta_accuracy is in raw percentage points — convert for comparison.
    _fail_acc_pp = FAIL_ACCURACY_DELTA_MIN * 100   # 0.005 → 0.5 pp

    # ── Absolute limits (always checked, no previous needed) ──────────────
    if current.co2_grams >= ABSOLUTE_CO2_FAIL_G:
        reasons.append(
            f"Absolute CO₂ limit exceeded: {current.co2_grams:.0f}g ≥ {ABSOLUTE_CO2_FAIL_G:.0f}g"
        )
        suggestions.append("Split training into smaller stages with gradient checkpointing.")
        suggestions.append("Switch to a more efficient architecture (e.g., EfficientNet → MobileNet).")
        status = "FAIL"
        exit_code = EXIT_FAIL

    elif current.co2_grams >= ABSOLUTE_CO2_WARN_G and status == "PASS":
        reasons.append(
            f"High absolute CO₂: {current.co2_grams:.0f}g ≥ {ABSOLUTE_CO2_WARN_G:.0f}g warning threshold"
        )
        suggestions.append("Consider mixed-precision training (FP16) to cut energy by ~30%.")
        status = "WARN"
        exit_code = EXIT_WARN

    # ── Relative delta gates (require a previous run) ─────────────────────
    if previous and delta_co2_pct is not None:

        # PRIMARY FAIL: low accuracy gain + high carbon spike
        if (
            delta_accuracy is not None
            and delta_accuracy < _fail_acc_pp
            and delta_co2_pct > FAIL_CO2_DELTA_MAX
        ):
            reasons.append(
                f"Carbon waste: ΔAccuracy={delta_accuracy:+.3f}pp "
                f"(< {_fail_acc_pp:.1f}pp threshold) "
                f"with ΔCO₂={delta_co2_pct*100:+.1f}% "
                f"(> {FAIL_CO2_DELTA_MAX*100:.0f}% limit)"
            )
            suggestions.append(
                "The accuracy gain does not justify the carbon cost. "
                "Try early stopping, learning rate scheduling, or reducing epochs."
            )
            suggestions.append(
                "Use knowledge distillation: distill this large model into a smaller one "
                "and only submit the student model."
            )
            status = "FAIL"
            exit_code = EXIT_FAIL

        # WARN: massive CO₂ spike regardless of accuracy
        elif delta_co2_pct > WARN_CO2_DELTA_MAX and status == "PASS":
            reasons.append(
                f"Large carbon spike: ΔCO₂={delta_co2_pct*100:+.1f}% "
                f"exceeds {WARN_CO2_DELTA_MAX*100:.0f}% warning threshold"
            )
            suggestions.append("Profile training loop for bottlenecks — large spikes often indicate inefficient data loading.")
            suggestions.append("Enable GPU memory optimization: torch.backends.cudnn.benchmark = True")
            status = "WARN"
            exit_code = EXIT_WARN

        # SOFT WARN: mild over-training signal
        elif (
            delta_accuracy is not None
            and delta_accuracy < _fail_acc_pp
            and WARN_SOFT_CO2_DELTA < delta_co2_pct <= FAIL_CO2_DELTA_MAX
            and status == "PASS"
        ):
            reasons.append(
                f"Soft warning: minimal accuracy gain ({delta_accuracy:+.3f}pp) "
                f"with moderate CO₂ increase ({delta_co2_pct*100:+.1f}%)"
            )
            suggestions.append("Consider halving the remaining epochs and monitoring validation loss closely.")
            status = "WARN"
            exit_code = EXIT_WARN

    # ── PASS: add positive context ─────────────────────────────────────────
    if status == "PASS":
        reasons.append("All carbon efficiency thresholds met.")
        if delta_accuracy is not None and delta_accuracy > 0:
            reasons.append(f"Accuracy improved by {delta_accuracy*100:+.3f}pp.")
        if delta_co2_pct is not None and delta_co2_pct < 0:
            reasons.append(f"Carbon footprint reduced by {abs(delta_co2_pct)*100:.1f}%.")

    return GateVerdict(
        status=status,
        exit_code=exit_code,
        reasons=reasons,
        suggestions=suggestions,
        delta_accuracy=delta_accuracy,
        delta_co2_pct=delta_co2_pct,
        delta_co2_grams=delta_co2_grams,
        delta_energy_kwh=delta_energy_kwh,
        current=current,
        previous=previous,
    )


# ── Reporting ─────────────────────────────────────────────────────────────

_STATUS_ICONS = {"PASS": "✅", "WARN": "⚠️ ", "FAIL": "❌"}
_STATUS_COLORS_ANSI = {
    "PASS": "\033[92m",   # bright green
    "WARN": "\033[93m",   # bright yellow
    "FAIL": "\033[91m",   # bright red
}
_RESET = "\033[0m"


def _human_co2(grams: float) -> str:
    best_label, best_val = "", 0.0
    for label, factor in _EQUIV.items():
        val = grams / factor
        if val > best_val:
            best_val, best_label = val, label
    return f"≈ {best_val:.1f} {best_label}"


def print_verdict(verdict: GateVerdict, use_color: bool = True) -> None:
    """Print a human-readable gate report to stdout."""
    c = _STATUS_COLORS_ANSI.get(verdict.status, "") if use_color else ""
    r = _RESET if use_color else ""
    icon = _STATUS_ICONS[verdict.status]
    cur = verdict.current
    prev = verdict.previous

    print()
    print("═" * 60)
    print(f"  {icon}  EcoTrack Green Gate — {c}{verdict.status}{r}")
    print("═" * 60)
    print(f"  Current run : {cur.run_id}  ({cur.model_name})")
    if prev:
        print(f"  Previous run: {prev.run_id}  ({prev.model_name})")
    print()

    print("  📊 Emissions")
    print(f"     CO₂       : {cur.co2_grams:.2f} g  {_human_co2(cur.co2_grams)}")
    print(f"     Energy    : {cur.energy_kwh:.4f} kWh")
    print(f"     Grid      : {cur.grid_intensity:.1f} gCO₂/kWh  [{cur.grid_source}]")
    print(f"     GPU       : {cur.gpu_model}")
    print(f"     Duration  : {cur.duration_sec:.1f}s")

    if cur.accuracy is not None:
        print(f"     Accuracy  : {cur.accuracy:.2f}%")

    if prev:
        print()
        print("  📈 Deltas vs previous run")
        if verdict.delta_accuracy is not None:
            arrow = "▲" if verdict.delta_accuracy >= 0 else "▼"
            print(f"     Δ Accuracy  : {arrow} {verdict.delta_accuracy*100:+.3f} pp")
        if verdict.delta_co2_pct is not None:
            arrow = "▲" if verdict.delta_co2_pct >= 0 else "▼"
            print(f"     Δ CO₂       : {arrow} {verdict.delta_co2_pct*100:+.1f}%  ({verdict.delta_co2_grams:+.1f}g)")
        if verdict.delta_energy_kwh is not None:
            print(f"     Δ Energy    : {verdict.delta_energy_kwh*1000:+.2f} Wh")

    print()
    print("  📋 Reasons")
    for reason in verdict.reasons:
        print(f"     • {reason}")

    if verdict.suggestions:
        print()
        print("  💡 Suggestions")
        for sug in verdict.suggestions:
            print(f"     → {sug}")

    print()
    print(f"  Gate decision: {c}{verdict.status}{r}  (exit {verdict.exit_code})")
    print("═" * 60)
    print()


def write_github_summary(verdict: GateVerdict) -> None:
    """
    Write a Markdown summary to $GITHUB_STEP_SUMMARY so it appears
    in the GitHub Actions run summary page.
    """
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    icon = _STATUS_ICONS[verdict.status]
    cur = verdict.current
    lines = [
        f"## {icon} EcoTrack Green Gate — {verdict.status}",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Run ID | `{cur.run_id}` |",
        f"| Model | {cur.model_name} |",
        f"| CO₂ | **{cur.co2_grams:.2f} g** ({_human_co2(cur.co2_grams)}) |",
        f"| Energy | {cur.energy_kwh:.4f} kWh |",
        f"| Grid intensity | {cur.grid_intensity:.1f} gCO₂/kWh [{cur.grid_source}] |",
        f"| GPU | {cur.gpu_model} |",
        f"| Accuracy | {cur.accuracy if cur.accuracy is not None else 'N/A'} |",
    ]
    if verdict.delta_co2_pct is not None:
        lines.append(f"| Δ CO₂ | {verdict.delta_co2_pct*100:+.1f}% |")
    if verdict.delta_accuracy is not None:
        lines.append(f"| Δ Accuracy | {verdict.delta_accuracy*100:+.3f} pp |")

    lines += ["", "### Reasons", ""]
    for r in verdict.reasons:
        lines.append(f"- {r}")

    if verdict.suggestions:
        lines += ["", "### Suggestions", ""]
        for s in verdict.suggestions:
            lines.append(f"- {s}")

    with open(summary_path, "a") as f:
        f.write("\n".join(lines) + "\n")


def write_verdict_json(verdict: GateVerdict, output_dir: Path) -> Path:
    """Persist the gate verdict as a JSON artefact."""
    out = output_dir / f"gate_{verdict.current.run_id}.json"
    out.write_text(json.dumps(verdict.to_dict(), indent=2))
    return out


def update_run_json_with_gate(run_path: Path, status: str) -> None:
    """Back-patch the gate_status field into the run's JSON file."""
    try:
        data = json.loads(run_path.read_text())
        data["gate_status"] = status
        run_path.write_text(json.dumps(data, indent=2))
    except Exception as exc:
        print(f"[WARN] Could not update gate_status in {run_path}: {exc}", file=sys.stderr)


# ── Discovery helpers ─────────────────────────────────────────────────────

def _find_latest_runs(emissions_dir: Path, count: int = 2) -> list[Path]:
    """Return the `count` most recently modified run_*.json files."""
    files = sorted(
        emissions_dir.glob("run_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files[:count]


# ── CLI ───────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="EcoTrack Green Gate — Carbon ethics CI/CD check",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples
--------
  # Auto-discover two latest runs in ./emissions
  python check_gate.py --dir ./emissions

  # Explicit file paths
  python check_gate.py --current run_abc.json --previous run_xyz.json

  # Only check current (no delta, only absolute thresholds)
  python check_gate.py --current run_abc.json

  # Don't fail CI, just report
  python check_gate.py --dir ./emissions --dry-run

  # Write GitHub Actions summary
  python check_gate.py --dir ./emissions --github-summary
        """,
    )
    p.add_argument("--current",  type=Path, default=None, help="Path to current run JSON")
    p.add_argument("--previous", type=Path, default=None, help="Path to previous run JSON")
    p.add_argument("--dir",      type=Path, default=Path("./emissions"), help="Emissions directory (auto-discovers latest two runs)")
    p.add_argument("--dry-run",  action="store_true", help="Never exit non-zero (safe for local dev)")
    p.add_argument("--no-color", action="store_true", help="Disable ANSI colors")
    p.add_argument("--github-summary", action="store_true", help="Write to $GITHUB_STEP_SUMMARY")
    p.add_argument("--json-out", action="store_true", help="Also write gate verdict JSON to --dir")
    p.add_argument(
        "--fail-threshold-accuracy", type=float, default=None,
        help=f"Override GATE_FAIL_ACC_DELTA (default {FAIL_ACCURACY_DELTA_MIN})"
    )
    p.add_argument(
        "--fail-threshold-co2", type=float, default=None,
        help=f"Override GATE_FAIL_CO2_DELTA (default {FAIL_CO2_DELTA_MAX})"
    )
    return p


def main() -> None:
    global FAIL_ACCURACY_DELTA_MIN, FAIL_CO2_DELTA_MAX

    parser = _build_parser()
    args = parser.parse_args()

    # ── Apply CLI overrides ───────────────────────────────────────────────
    if args.fail_threshold_accuracy is not None:
        FAIL_ACCURACY_DELTA_MIN = args.fail_threshold_accuracy
    if args.fail_threshold_co2 is not None:
        FAIL_CO2_DELTA_MAX = args.fail_threshold_co2

    # ── Resolve file paths ────────────────────────────────────────────────
    current_path:  Optional[Path] = args.current
    previous_path: Optional[Path] = args.previous

    if current_path is None:
        # Auto-discover from directory
        latest = _find_latest_runs(args.dir, count=2)
        if not latest:
            print(f"[ERROR] No run_*.json files found in {args.dir}", file=sys.stderr)
            sys.exit(EXIT_FAIL if not args.dry_run else 0)
        current_path = latest[0]
        previous_path = latest[1] if len(latest) > 1 else None

    # ── Load runs ─────────────────────────────────────────────────────────
    current = RunSnapshot.from_json_file(current_path)
    previous: Optional[RunSnapshot] = None
    if previous_path and previous_path.exists():
        previous = RunSnapshot.from_json_file(previous_path)

    # ── Evaluate ──────────────────────────────────────────────────────────
    verdict = evaluate_gate(current, previous)

    # ── Report ────────────────────────────────────────────────────────────
    print_verdict(verdict, use_color=not args.no_color)

    if args.github_summary:
        write_github_summary(verdict)

    if args.json_out:
        out_path = write_verdict_json(verdict, args.dir)
        print(f"Gate verdict JSON → {out_path}")

    # Back-patch gate_status into the current run's JSON
    update_run_json_with_gate(current_path, verdict.status)

    # ── Exit ──────────────────────────────────────────────────────────────
    if args.dry_run:
        print("[dry-run] Would exit with code", verdict.exit_code)
        sys.exit(EXIT_PASS)

    sys.exit(verdict.exit_code)


if __name__ == "__main__":
    main()
