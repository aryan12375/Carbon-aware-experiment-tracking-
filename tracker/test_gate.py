"""
test_gate.py
============
EcoTrack — Green MLOps Framework
---------------------------------
Unit tests for the Green Gate evaluation logic in check_gate.py.
28 tests covering all gate conditions, edge cases, and boundary values.

Run with:
    pytest test_gate.py -v
    pytest test_gate.py -v --cov=check_gate --cov-report=term-missing

Author : Aryan (aryan12375) — MIT Manipal
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from check_gate import (
    RunSnapshot,
    evaluate_gate,
    GateVerdict,
    EXIT_PASS,
    EXIT_FAIL,
    EXIT_WARN,
    FAIL_ACCURACY_DELTA_MIN,
    FAIL_CO2_DELTA_MAX,
    WARN_CO2_DELTA_MAX,
    ABSOLUTE_CO2_WARN_G,
    ABSOLUTE_CO2_FAIL_G,
    _find_latest_runs,
    _human_co2,
)


# ── Fixtures ──────────────────────────────────────────────────────────────

def _make_run(
    run_id="abc123",
    model_name="ResNet-50",
    co2_grams=300.0,
    energy_kwh=0.41,
    accuracy=92.0,
    loss=0.18,
    gpu_model="NVIDIA T4",
    duration_sec=420.0,
    grid_intensity=724.0,
    grid_source="hardcoded_default",
    commit_id="aabbcc",
) -> RunSnapshot:
    return RunSnapshot(
        run_id=run_id,
        model_name=model_name,
        project_name="test-project",
        commit_id=commit_id,
        co2_grams=co2_grams,
        energy_kwh=energy_kwh,
        accuracy=accuracy,
        loss=loss,
        gpu_model=gpu_model,
        duration_sec=duration_sec,
        finished_at="2026-04-18T10:00:00+00:00",
        grid_intensity=grid_intensity,
        grid_source=grid_source,
    )


@pytest.fixture
def baseline():
    return _make_run(run_id="prev-001", co2_grams=300.0, accuracy=92.0)


@pytest.fixture
def improved():
    """Better accuracy, modest CO₂ increase — should PASS."""
    return _make_run(run_id="curr-001", co2_grams=315.0, accuracy=93.5)


@pytest.fixture
def wasteful():
    """Tiny accuracy gain + massive CO₂ spike — should FAIL."""
    return _make_run(run_id="curr-002", co2_grams=420.0, accuracy=92.3)


@pytest.fixture
def big_spike():
    """Huge CO₂ spike even with good accuracy gain — should WARN."""
    return _make_run(run_id="curr-003", co2_grams=600.0, accuracy=95.0)


# ══════════════════════════════════════════════════════════════════════════
# 1. PASS cases
# ══════════════════════════════════════════════════════════════════════════

class TestPassCases:

    def test_pass_good_accuracy_small_co2(self, baseline, improved):
        verdict = evaluate_gate(improved, baseline)
        assert verdict.status == "PASS"
        assert verdict.exit_code == EXIT_PASS

    def test_pass_no_previous_run_low_co2(self):
        run = _make_run(co2_grams=500.0)
        verdict = evaluate_gate(run, previous=None)
        assert verdict.status == "PASS"
        assert verdict.exit_code == EXIT_PASS

    def test_pass_co2_decreased(self, baseline):
        efficient = _make_run(co2_grams=240.0, accuracy=92.8)
        verdict = evaluate_gate(efficient, baseline)
        assert verdict.status == "PASS"
        assert verdict.delta_co2_pct is not None
        assert verdict.delta_co2_pct < 0

    def test_pass_accuracy_improved_significantly(self, baseline):
        big_win = _make_run(co2_grams=360.0, accuracy=95.0)  # +3pp, +20% CO₂ — should PASS
        verdict = evaluate_gate(big_win, baseline)
        assert verdict.status == "PASS"

    def test_pass_reasons_populated(self, baseline, improved):
        verdict = evaluate_gate(improved, baseline)
        assert len(verdict.reasons) > 0
        assert any("threshold" in r.lower() or "met" in r.lower() for r in verdict.reasons)

    def test_pass_no_suggestions(self, baseline, improved):
        verdict = evaluate_gate(improved, baseline)
        assert len(verdict.suggestions) == 0

    def test_pass_delta_accuracy_computed(self, baseline, improved):
        verdict = evaluate_gate(improved, baseline)
        assert verdict.delta_accuracy == pytest.approx(1.5, rel=1e-3)

    def test_pass_delta_co2_computed(self, baseline, improved):
        verdict = evaluate_gate(improved, baseline)
        expected = (315 - 300) / 300
        assert verdict.delta_co2_pct == pytest.approx(expected, rel=1e-3)


# ══════════════════════════════════════════════════════════════════════════
# 2. FAIL cases
# ══════════════════════════════════════════════════════════════════════════

class TestFailCases:

    def test_fail_low_acc_gain_high_co2(self, baseline, wasteful):
        """Core gate: Δacc < 0.5pp AND ΔCO₂ > 20% → FAIL."""
        verdict = evaluate_gate(wasteful, baseline)
        assert verdict.status == "FAIL"
        assert verdict.exit_code == EXIT_FAIL

    def test_fail_has_reasons(self, baseline, wasteful):
        verdict = evaluate_gate(wasteful, baseline)
        assert len(verdict.reasons) > 0
        assert any("carbon" in r.lower() or "waste" in r.lower() for r in verdict.reasons)

    def test_fail_has_suggestions(self, baseline, wasteful):
        verdict = evaluate_gate(wasteful, baseline)
        assert len(verdict.suggestions) > 0

    def test_fail_absolute_co2_limit(self):
        """Absolute CO₂ over 10kg always FAILs, no previous needed."""
        massive = _make_run(co2_grams=ABSOLUTE_CO2_FAIL_G + 500)
        verdict = evaluate_gate(massive, previous=None)
        assert verdict.status == "FAIL"
        assert verdict.exit_code == EXIT_FAIL

    def test_fail_absolute_co2_exactly_at_limit(self):
        at_limit = _make_run(co2_grams=ABSOLUTE_CO2_FAIL_G)
        verdict = evaluate_gate(at_limit, previous=None)
        assert verdict.status == "FAIL"

    def test_fail_no_accuracy_improvement_huge_co2(self, baseline):
        """Accuracy DROPS + CO₂ spikes → FAIL."""
        regression = _make_run(co2_grams=500.0, accuracy=91.0)
        verdict = evaluate_gate(regression, baseline)
        assert verdict.status == "FAIL"

    def test_fail_boundary_exactly_at_thresholds(self, baseline):
        """
        Accuracy delta exactly at threshold (0.5pp), CO₂ just above limit (20.1%)
        → FAIL because delta_acc < FAIL_ACCURACY_DELTA_MIN is strict (<, not <=).
        """
        at_boundary = _make_run(
            co2_grams=300 * (1 + FAIL_CO2_DELTA_MAX + 0.001),
            accuracy=baseline.accuracy + FAIL_ACCURACY_DELTA_MIN * 100 - 0.001
        )
        verdict = evaluate_gate(at_boundary, baseline)
        assert verdict.status == "FAIL"


# ══════════════════════════════════════════════════════════════════════════
# 3. WARN cases
# ══════════════════════════════════════════════════════════════════════════

class TestWarnCases:

    def test_warn_large_co2_spike(self, baseline, big_spike):
        """ΔCO₂ > 40% → WARN regardless of accuracy."""
        verdict = evaluate_gate(big_spike, baseline)
        assert verdict.status == "WARN"
        assert verdict.exit_code == EXIT_WARN

    def test_warn_absolute_co2_threshold(self):
        """CO₂ between WARN and FAIL absolute thresholds → WARN."""
        medium = _make_run(co2_grams=ABSOLUTE_CO2_WARN_G + 100)
        verdict = evaluate_gate(medium, previous=None)
        assert verdict.status == "WARN"
        assert verdict.exit_code == EXIT_WARN

    def test_warn_soft_condition(self, baseline):
        """Soft WARN: small acc gain + modest CO₂ increase (10–20%)."""
        soft = _make_run(
            co2_grams=300 * 1.15,   # +15% CO₂
            accuracy=92.2           # +0.2pp — below 0.5pp threshold
        )
        verdict = evaluate_gate(soft, baseline)
        assert verdict.status == "WARN"

    def test_warn_has_suggestions(self, baseline, big_spike):
        verdict = evaluate_gate(big_spike, baseline)
        assert len(verdict.suggestions) > 0

    def test_warn_exit_code_is_two(self, baseline, big_spike):
        verdict = evaluate_gate(big_spike, baseline)
        assert verdict.exit_code == 2


# ══════════════════════════════════════════════════════════════════════════
# 4. Edge cases
# ══════════════════════════════════════════════════════════════════════════

class TestEdgeCases:

    def test_no_accuracy_in_current(self, baseline):
        """Gate should not crash when accuracy is None."""
        no_acc = _make_run(co2_grams=310.0, accuracy=None)
        verdict = evaluate_gate(no_acc, baseline)
        assert verdict.delta_accuracy is None
        # Should be PASS since no accuracy data to trigger fail
        assert verdict.status in ("PASS", "WARN")

    def test_no_accuracy_in_both(self):
        cur = _make_run(co2_grams=300.0, accuracy=None)
        prev = _make_run(co2_grams=250.0, accuracy=None)
        verdict = evaluate_gate(cur, prev)
        assert verdict.delta_accuracy is None

    def test_previous_co2_zero_no_crash(self):
        """If previous CO₂ is 0, delta computation should be skipped gracefully."""
        prev_zero = _make_run(co2_grams=0.0, accuracy=90.0)
        current = _make_run(co2_grams=200.0, accuracy=92.0)
        verdict = evaluate_gate(current, prev_zero)
        assert verdict.delta_co2_pct is None

    def test_zero_co2_always_passes(self):
        perfect = _make_run(co2_grams=0.0)
        verdict = evaluate_gate(perfect, previous=None)
        assert verdict.status == "PASS"

    def test_identical_runs_passes(self, baseline):
        same = _make_run(co2_grams=300.0, accuracy=92.0)
        verdict = evaluate_gate(same, baseline)
        # Identical: Δacc=0 (< 0.5pp) AND ΔCO₂=0 (not > 10%) → PASS
        assert verdict.status == "PASS"

    def test_to_dict_is_serialisable(self, baseline, improved):
        verdict = evaluate_gate(improved, baseline)
        d = verdict.to_dict()
        json_str = json.dumps(d)
        assert "status" in json.loads(json_str)

    def test_verdict_contains_human_readable_reason(self, baseline, wasteful):
        verdict = evaluate_gate(wasteful, baseline)
        # Reasons should be human-readable strings, not just codes
        for r in verdict.reasons:
            assert isinstance(r, str)
            assert len(r) > 10


# ══════════════════════════════════════════════════════════════════════════
# 5. Helper function tests
# ══════════════════════════════════════════════════════════════════════════

class TestHelpers:

    def test_human_co2_small(self):
        result = _human_co2(41.1)   # ≈ 5 smartphone charges
        assert "smartphone" in result

    def test_human_co2_medium(self):
        result = _human_co2(850.0)  # ≈ 5 km driven
        assert "km" in result or "smartphone" in result

    def test_find_latest_runs_empty_dir(self, tmp_path):
        runs = _find_latest_runs(tmp_path, count=2)
        assert runs == []

    def test_find_latest_runs_returns_two(self, tmp_path):
        for i in range(3):
            (tmp_path / f"run_abc{i}.json").write_text("{}")
        runs = _find_latest_runs(tmp_path, count=2)
        assert len(runs) == 2

    def test_run_snapshot_from_dict(self):
        d = {
            "run_id": "test123",
            "model_name": "ViT",
            "project_name": "proj",
            "commit_id": "abc",
            "co2_grams": 500.0,
            "energy_kwh": 0.69,
            "accuracy": 91.5,
            "loss": 0.25,
            "gpu_model": "A100",
            "duration_seconds": 600.0,
            "finished_at": "2026-04-18T10:00:00Z",
            "grid_intensity_g_kwh": 724.0,
            "grid_source": "co2signal",
        }
        snap = RunSnapshot.from_dict(d)
        assert snap.run_id == "test123"
        assert snap.co2_grams == 500.0
        assert snap.accuracy == 91.5

    def test_run_snapshot_from_json_file(self, tmp_path):
        data = {
            "run_id": "file-test",
            "model_name": "BERT",
            "project_name": "nlp",
            "commit_id": "deadbeef",
            "co2_grams": 200.0,
            "energy_kwh": 0.28,
            "accuracy": 88.0,
            "loss": 0.35,
            "gpu_model": "T4",
            "duration_seconds": 300.0,
            "finished_at": "2026-04-18T09:00:00Z",
            "grid_intensity_g_kwh": 385.0,
            "grid_source": "electricitymaps",
        }
        p = tmp_path / "run_filetest.json"
        p.write_text(json.dumps(data))
        snap = RunSnapshot.from_json_file(p)
        assert snap.run_id == "file-test"
        assert snap.grid_source == "electricitymaps"
