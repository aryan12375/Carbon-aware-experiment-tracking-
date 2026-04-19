"""
tracker_utils.py
================
EcoTrack — Green MLOps Framework
---------------------------------
A production-grade emissions tracking utility that wraps CodeCarbon and
optionally enriches data with real-time grid carbon intensity from the
CO2Signal / ElectricityMaps API.

Usage (decorator):
    from tracker_utils import track_emissions

    @track_emissions(project_name="ResNet50-Finetune", model_name="ResNet-50")
    def train(model, dataloader, epochs):
        ...

Usage (context manager):
    from tracker_utils import EmissionsSession

    with EmissionsSession(project_name="ViT-Training") as session:
        train(...)
    print(session.result)

Usage (manual):
    from tracker_utils import EcoTracker
    tracker = EcoTracker(project_name="YOLO-Run")
    tracker.start()
    train(...)
    result = tracker.stop()

Author : Aryan (aryan12375) — MIT Manipal
License: MIT
"""

from __future__ import annotations

import functools
import json
import logging
import os
import platform
import socket
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import requests

# ── Optional deps — fail gracefully so the tracker doesn't crash training ──
try:
    from codecarbon import EmissionsTracker
    _CODECARBON_AVAILABLE = True
except ImportError:
    _CODECARBON_AVAILABLE = False
    logging.warning(
        "[EcoTrack] codecarbon not installed. "
        "Run: pip install codecarbon  —  falling back to stub tracker."
    )

try:
    import pynvml
    pynvml.nvmlInit()
    _NVML_AVAILABLE = True
except Exception:
    _NVML_AVAILABLE = False

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [EcoTrack] %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ecotrack")

# ── Constants ──────────────────────────────────────────────────────────────
EMISSIONS_DIR = Path(os.getenv("ECOTRACK_EMISSIONS_DIR", "./emissions"))
CO2_SIGNAL_KEY = os.getenv("CO2SIGNAL_API_KEY", "")          # free tier at co2signal.com
ELECTRICITY_MAPS_KEY = os.getenv("ELECTRICITY_MAPS_KEY", "") # electricitymaps.com
DEFAULT_REGION = os.getenv("ECOTRACK_REGION", "IN-SO")       # IN-SO = Karnataka / South India
CARBON_API_TIMEOUT = 5   # seconds

# Human-readable CO₂ equivalents (grams CO₂ per unit)
_EQUIVALENTS: dict[str, tuple[float, str]] = {
    "smartphone_charge":  (8.22,   "smartphone charges"),
    "km_driven":          (170.0,  "km driven in a petrol car"),
    "tree_day_absorbed":  (22.0,   "tree-days of carbon absorbed"),
    "cup_of_tea":         (50.0,   "cups of tea brewed"),
    "led_hour":           (5.0,    "hours of LED bulb usage"),
}


# ── Data model ─────────────────────────────────────────────────────────────

@dataclass
class EmissionsResult:
    """Structured result object returned after every tracked run."""

    # Identifiers
    run_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    project_name: str = ""
    model_name: str = ""
    commit_id: str = ""

    # Timing
    started_at: str = ""
    finished_at: str = ""
    duration_seconds: float = 0.0

    # Carbon
    co2_grams: float = 0.0          # primary metric — grams CO₂eq
    co2_kg: float = 0.0
    energy_kwh: float = 0.0
    grid_intensity_g_kwh: float = 0.0   # gCO₂/kWh from live API or CodeCarbon default
    grid_source: str = "codecarbon_default"

    # Hardware
    gpu_model: str = "unknown"
    gpu_count: int = 0
    cpu_model: str = ""
    ram_gb: float = 0.0
    cloud_provider: str = "local"
    region: str = DEFAULT_REGION

    # Model quality (filled by caller or decorator)
    accuracy: Optional[float] = None
    loss: Optional[float] = None
    extra_metrics: dict = field(default_factory=dict)

    # Human equivalents
    human_equivalents: dict[str, str] = field(default_factory=dict)

    # Gate signal (set by check_gate.py)
    gate_status: str = "pending"   # "pass" | "fail" | "warn" | "pending"

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def summary(self) -> str:
        lines = [
            "",
            "╔══════════════════════════════════════════════════╗",
            f"║  EcoTrack Emissions Report  ·  run {self.run_id}    ║",
            "╠══════════════════════════════════════════════════╣",
            f"║  Project   : {self.project_name:<35} ║",
            f"║  Model     : {self.model_name:<35} ║",
            f"║  Duration  : {self.duration_seconds:>8.1f}s                          ║",
            "╠══════════════════════════════════════════════════╣",
            f"║  CO₂       : {self.co2_grams:>10.2f} g                       ║",
            f"║  Energy    : {self.energy_kwh:>10.4f} kWh                     ║",
            f"║  Grid      : {self.grid_intensity_g_kwh:>10.1f} gCO₂/kWh ({self.grid_source:<8})  ║",
            f"║  GPU       : {self.gpu_model:<35} ║",
            "╠══════════════════════════════════════════════════╣",
        ]
        for label, val in self.human_equivalents.items():
            lines.append(f"║  ≈ {val:<46} ║")
        if self.accuracy is not None:
            lines.append(f"║  Accuracy  : {self.accuracy:>8.2f}%                        ║")
        lines += [
            f"║  Gate      : {self.gate_status.upper():<35} ║",
            "╚══════════════════════════════════════════════════╝",
            "",
        ]
        return "\n".join(lines)


# ── Grid carbon intensity ──────────────────────────────────────────────────

def _fetch_grid_intensity(region: str = DEFAULT_REGION) -> tuple[float, str]:
    """
    Fetch live grid carbon intensity (gCO₂/kWh).

    Priority:
      1. CO2Signal API  (free, 30-req/hr)
      2. ElectricityMaps API  (paid, more accurate)
      3. Hardcoded India defaults (fallback)

    Returns (intensity_g_kwh, source_label).
    """
    # ── CO2Signal ────────────────────────────────────────────────────────
    if CO2_SIGNAL_KEY:
        try:
            url = "https://api.co2signal.com/v1/latest"
            headers = {"auth-token": CO2_SIGNAL_KEY}
            resp = requests.get(
                url,
                params={"countryCode": region.split("-")[0]},  # e.g. "IN"
                headers=headers,
                timeout=CARBON_API_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            intensity = float(data["data"]["carbonIntensity"])
            log.info(f"Grid intensity from CO2Signal: {intensity:.1f} gCO₂/kWh ({region})")
            return intensity, "co2signal"
        except Exception as exc:
            log.warning(f"CO2Signal fetch failed: {exc} — trying ElectricityMaps...")

    # ── ElectricityMaps ───────────────────────────────────────────────────
    if ELECTRICITY_MAPS_KEY:
        try:
            url = "https://api.electricitymap.org/v3/carbon-intensity/latest"
            headers = {"auth-token": ELECTRICITY_MAPS_KEY}
            resp = requests.get(
                url,
                params={"zone": region},
                headers=headers,
                timeout=CARBON_API_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            intensity = float(data["carbonIntensity"])
            log.info(f"Grid intensity from ElectricityMaps: {intensity:.1f} gCO₂/kWh ({region})")
            return intensity, "electricitymaps"
        except Exception as exc:
            log.warning(f"ElectricityMaps fetch failed: {exc} — using hardcoded fallback.")

    # ── Hardcoded regional defaults (2024 CEA data) ───────────────────────
    _DEFAULTS: dict[str, float] = {
        "IN":    713.0,   # India national average (CEA 2023-24)
        "IN-SO": 724.0,   # Southern region (Karnataka-heavy)
        "IN-NO": 780.0,   # Northern region (coal-heavy)
        "DE":    385.0,   # Germany
        "FR":     85.0,   # France (nuclear-heavy)
        "US-CA": 260.0,   # California
        "GB":    233.0,   # Great Britain
    }
    intensity = _DEFAULTS.get(region, _DEFAULTS.get(region.split("-")[0], 713.0))
    log.warning(f"Using hardcoded grid intensity: {intensity} gCO₂/kWh ({region})")
    return intensity, "hardcoded_default"


# ── Hardware metadata ─────────────────────────────────────────────────────

def _collect_hardware_info() -> dict[str, Any]:
    """Collect GPU, CPU, RAM metadata using pynvml and platform."""
    info: dict[str, Any] = {
        "gpu_model":  "cpu_only",
        "gpu_count":  0,
        "cpu_model":  platform.processor() or "unknown",
        "ram_gb":     0.0,
        "hostname":   socket.gethostname(),
    }

    # RAM via /proc/meminfo (Linux) or fallback
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal"):
                    kb = int(line.split()[1])
                    info["ram_gb"] = round(kb / 1024 / 1024, 1)
                    break
    except Exception:
        pass

    if _NVML_AVAILABLE:
        try:
            count = pynvml.nvmlDeviceGetCount()
            info["gpu_count"] = count
            if count > 0:
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                info["gpu_model"] = pynvml.nvmlDeviceGetName(handle)
                if isinstance(info["gpu_model"], bytes):
                    info["gpu_model"] = info["gpu_model"].decode()
        except Exception as exc:
            log.debug(f"pynvml error: {exc}")

    return info


# ── Human equivalents ─────────────────────────────────────────────────────

def _compute_human_equivalents(co2_grams: float) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, (factor, label) in _EQUIVALENTS.items():
        count = co2_grams / factor
        if count >= 0.1:
            out[key] = f"{count:.1f} {label}"
    return out


# ── Git commit hash ────────────────────────────────────────────────────────

def _get_commit_id() -> str:
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=3,
        )
        return result.stdout.strip() or "no-git"
    except Exception:
        return "no-git"


# ── Core tracker class ────────────────────────────────────────────────────

class EcoTracker:
    """
    Low-level tracker. Wraps CodeCarbon and enriches results with live
    grid data, hardware metadata, and human-readable equivalents.
    """

    def __init__(
        self,
        project_name: str = "unnamed-project",
        model_name: str = "unnamed-model",
        region: str = DEFAULT_REGION,
        output_dir: str | Path = EMISSIONS_DIR,
        save_to_file: bool = True,
        offline: bool = False,
    ):
        self.project_name = project_name
        self.model_name = model_name
        self.region = region
        self.output_dir = Path(output_dir)
        self.save_to_file = save_to_file
        self.offline = offline

        self._tracker: Optional[Any] = None   # CodeCarbon instance
        self._start_time: float = 0.0
        self.result: Optional[EmissionsResult] = None

        self.output_dir.mkdir(parents=True, exist_ok=True)

    def start(self) -> "EcoTracker":
        log.info(f"Starting EcoTrack → project='{self.project_name}' model='{self.model_name}'")
        self._start_time = time.perf_counter()

        if _CODECARBON_AVAILABLE:
            self._tracker = EmissionsTracker(
                project_name=self.project_name,
                output_dir=str(self.output_dir),
                save_to_file=self.save_to_file,
                log_level="error",   # suppress codecarbon's own logs; we handle ours
                offline=self.offline,
                measure_power_secs=15,   # sample every 15s — good balance of accuracy vs overhead
            )
            self._tracker.start()
        else:
            log.warning("CodeCarbon unavailable — emissions will be estimated from TDP only.")
        return self

    def stop(
        self,
        accuracy: Optional[float] = None,
        loss: Optional[float] = None,
        extra_metrics: Optional[dict] = None,
    ) -> EmissionsResult:
        elapsed = time.perf_counter() - self._start_time
        now_utc = datetime.now(timezone.utc).isoformat()

        # ── Get CodeCarbon emissions ──────────────────────────────────────
        co2_kg_cc = 0.0
        energy_kwh_cc = 0.0

        if _CODECARBON_AVAILABLE and self._tracker:
            try:
                emissions = self._tracker.stop()   # returns kg CO₂
                co2_kg_cc = float(emissions or 0.0)
                # CodeCarbon stores kWh in its internal state
                energy_kwh_cc = getattr(self._tracker, "_total_energy", None)
                if energy_kwh_cc is None:
                    energy_kwh_cc = co2_kg_cc / 0.713   # fallback: India avg intensity
                energy_kwh_cc = float(energy_kwh_cc)
            except Exception as exc:
                log.error(f"CodeCarbon stop() failed: {exc}")

        # ── Fetch live grid intensity ─────────────────────────────────────
        grid_intensity, grid_source = (0.0, "none")
        if not self.offline:
            grid_intensity, grid_source = _fetch_grid_intensity(self.region)

        # Recompute CO₂ using live grid intensity if we have real energy usage
        co2_grams: float
        if energy_kwh_cc > 0 and grid_intensity > 0:
            co2_grams = energy_kwh_cc * grid_intensity          # our own computation
            co2_kg = co2_grams / 1000
        else:
            co2_grams = co2_kg_cc * 1000
            co2_kg = co2_kg_cc

        # ── Hardware ──────────────────────────────────────────────────────
        hw = _collect_hardware_info()

        # ── Build result ──────────────────────────────────────────────────
        result = EmissionsResult(
            project_name=self.project_name,
            model_name=self.model_name,
            commit_id=_get_commit_id(),
            started_at=datetime.fromtimestamp(
                self._start_time, tz=timezone.utc
            ).isoformat(),
            finished_at=now_utc,
            duration_seconds=round(elapsed, 2),
            co2_grams=round(co2_grams, 4),
            co2_kg=round(co2_kg, 6),
            energy_kwh=round(energy_kwh_cc, 6),
            grid_intensity_g_kwh=round(grid_intensity, 2),
            grid_source=grid_source,
            gpu_model=hw["gpu_model"],
            gpu_count=hw["gpu_count"],
            cpu_model=hw["cpu_model"],
            ram_gb=hw["ram_gb"],
            region=self.region,
            accuracy=accuracy,
            loss=loss,
            extra_metrics=extra_metrics or {},
            human_equivalents=_compute_human_equivalents(co2_grams),
        )

        self.result = result

        # ── Persist JSON ──────────────────────────────────────────────────
        if self.save_to_file:
            out_path = self.output_dir / f"run_{result.run_id}.json"
            out_path.write_text(result.to_json())
            log.info(f"Emissions saved → {out_path}")

        log.info(result.summary())
        return result


# ── Decorator ─────────────────────────────────────────────────────────────

def track_emissions(
    project_name: str = "ecotrack-project",
    model_name: str = "unnamed-model",
    region: str = DEFAULT_REGION,
    output_dir: str | Path = EMISSIONS_DIR,
    accuracy_kwarg: str = "accuracy",   # name of kwarg in wrapped fn that holds accuracy
    offline: bool = False,
):
    """
    Decorator factory. Wraps any training function and automatically
    tracks + logs carbon emissions.

    Example
    -------
    @track_emissions(project_name="EfficientNet-Run", model_name="EfficientNet-B4")
    def train(model, loader, epochs, accuracy=None):
        ...
        return {"accuracy": 94.1, "loss": 0.22}

    If the wrapped function returns a dict with keys "accuracy" or "loss",
    they are automatically captured in the EmissionsResult.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracker = EcoTracker(
                project_name=project_name,
                model_name=model_name,
                region=region,
                output_dir=output_dir,
                offline=offline,
            )
            tracker.start()
            try:
                retval = func(*args, **kwargs)
            except Exception as exc:
                log.error(f"Training function raised an exception: {exc}")
                tracker.stop()
                raise
            # Extract accuracy/loss from return value if it's a dict
            acc, loss = None, None
            if isinstance(retval, dict):
                acc = retval.get("accuracy") or retval.get("acc")
                loss = retval.get("loss")
            tracker.stop(accuracy=acc, loss=loss)
            return retval
        return wrapper
    return decorator


# ── Context manager ───────────────────────────────────────────────────────

class EmissionsSession:
    """
    Context manager version for more flexible usage.

    with EmissionsSession(project_name="BERT-Finetune") as session:
        train(...)
        session.set_accuracy(93.2)

    print(session.result.summary())
    """

    def __init__(self, **kwargs):
        self._tracker = EcoTracker(**kwargs)
        self.result: Optional[EmissionsResult] = None
        self._accuracy: Optional[float] = None
        self._loss: Optional[float] = None
        self._extra: dict = {}

    def set_accuracy(self, value: float):
        self._accuracy = value

    def set_loss(self, value: float):
        self._loss = value

    def set_metric(self, key: str, value: Any):
        self._extra[key] = value

    def __enter__(self) -> "EmissionsSession":
        self._tracker.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.result = self._tracker.stop(
            accuracy=self._accuracy,
            loss=self._loss,
            extra_metrics=self._extra,
        )
        return False   # don't suppress exceptions


# ── CLI quick-check ───────────────────────────────────────────────────────

if __name__ == "__main__":
    """Quick smoke-test: track a dummy sleep to verify the stack."""
    import argparse

    parser = argparse.ArgumentParser(description="EcoTrack smoke test")
    parser.add_argument("--seconds", type=float, default=5.0, help="Simulated training duration")
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()

    print(f"\n🌿 Running EcoTrack smoke test ({args.seconds}s simulated training)...\n")

    with EmissionsSession(
        project_name="smoke-test",
        model_name="null-model",
        region=args.region,
        offline=args.offline,
    ) as session:
        time.sleep(args.seconds)
        session.set_accuracy(99.0)
        session.set_metric("epochs", 1)

    print(session.result.summary())
    print(f"JSON output:\n{session.result.to_json()}")


# ── Green-Pause Scheduler ─────────────────────────────────────────────────

import signal
import threading


class GreenPauseContext:
    """
    Carbon-aware training pause/resume controller.

    Monitors the live grid carbon intensity every `poll_interval_seconds`
    and pauses your training job when the grid exceeds `threshold_g_kwh`.
    Resumes automatically when the grid cleans up.

    Cross-platform design:
      - Unix/Linux: sends SIGSTOP / SIGCONT to pause and resume
      - Windows / fallback: sets a threading.Event that your training loop
        must check via `session.should_pause.wait()` or `session.ok_to_train`

    Usage (automatic SIGSTOP — best for Linux GPU servers):
    --------------------------------------------------------
    with GreenPauseContext(
        threshold_g_kwh=450,
        region="IN-SO",
        poll_interval_seconds=300
    ) as ctx:
        train_model(...)   # will be paused/resumed automatically

    Usage (threading Event — cross-platform):
    -----------------------------------------
    ctx = GreenPauseContext(threshold_g_kwh=450, use_signal=False)
    ctx.start()
    for epoch in range(100):
        ctx.ok_to_train.wait()   # blocks if grid is dirty
        train_one_epoch(model, dataloader)
    ctx.stop()
    """

    def __init__(
        self,
        threshold_g_kwh: float = 450.0,
        region: str = DEFAULT_REGION,
        poll_interval_seconds: float = 300.0,   # check every 5 minutes
        use_signal: bool = True,
        on_pause: Optional[Callable] = None,
        on_resume: Optional[Callable] = None,
    ):
        self.threshold = threshold_g_kwh
        self.region = region
        self.poll_interval = poll_interval_seconds
        # On Windows, SIGSTOP is not available — fall back to Event-based
        self.use_signal = use_signal and (platform.system() != "Windows")
        self.on_pause = on_pause
        self.on_resume = on_resume

        self._paused = False
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.ok_to_train = threading.Event()
        self.ok_to_train.set()  # starts as "GO"

        self.pause_events: list[dict] = []
        self.total_paused_seconds = 0.0
        self._pause_start: float = 0.0

    def start(self) -> "GreenPauseContext":
        self._running = True
        self._thread = threading.Thread(target=self._monitor, daemon=True)
        self._thread.start()
        log.info(
            f"[GreenPause] Started — threshold={self.threshold}g/kWh "
            f"region={self.region} poll={self.poll_interval}s"
        )
        return self

    def stop(self) -> None:
        self._running = False
        self.ok_to_train.set()   # ensure training is not stuck
        if self._thread:
            self._thread.join(timeout=5)
        log.info(
            f"[GreenPause] Stopped. Total paused: {self.total_paused_seconds:.0f}s "
            f"across {len(self.pause_events)} pause event(s)."
        )

    def _monitor(self) -> None:
        """Poll grid intensity and pause/resume as needed."""
        while self._running:
            try:
                intensity, source = _fetch_grid_intensity(self.region)
                log.debug(f"[GreenPause] Grid: {intensity:.1f}g/kWh from {source}")

                if intensity > self.threshold and not self._paused:
                    self._pause_training(intensity, source)
                elif intensity <= self.threshold and self._paused:
                    self._resume_training(intensity, source)

            except Exception as exc:
                log.warning(f"[GreenPause] Monitor error: {exc}")

            time.sleep(self.poll_interval)

    def _pause_training(self, intensity: float, source: str) -> None:
        """Pause the training process."""
        self._paused = True
        self._pause_start = time.perf_counter()
        self.ok_to_train.clear()

        log.warning(
            f"[GreenPause] 🔴 PAUSING training — grid intensity {intensity:.1f}g/kWh "
            f"exceeds threshold {self.threshold:.0f}g/kWh [{source}]. "
            f"Will resume when grid cleans up."
        )

        if self.use_signal:
            try:
                import os
                os.kill(os.getpid(), signal.SIGSTOP)
            except (AttributeError, ProcessLookupError):
                pass  # SIGSTOP not available

        if self.on_pause:
            try:
                self.on_pause(intensity=intensity, source=source)
            except Exception:
                pass

    def _resume_training(self, intensity: float, source: str) -> None:
        """Resume the training process."""
        if self._pause_start > 0:
            paused_for = time.perf_counter() - self._pause_start
            self.total_paused_seconds += paused_for
            self.pause_events.append({
                "paused_at": datetime.now(timezone.utc).isoformat(),
                "paused_for_seconds": round(paused_for, 1),
                "intensity_at_pause": intensity,
                "source": source,
            })

        self._paused = False
        self.ok_to_train.set()

        log.info(
            f"[GreenPause] 🟢 RESUMING training — grid now {intensity:.1f}g/kWh "
            f"(below {self.threshold:.0f}g/kWh threshold). [{source}]"
        )

        if self.on_resume:
            try:
                self.on_resume(intensity=intensity, source=source)
            except Exception:
                pass

    def __enter__(self) -> "GreenPauseContext":
        return self.start()

    def __exit__(self, *args) -> None:
        self.stop()

    @property
    def summary(self) -> dict:
        return {
            "total_paused_seconds": round(self.total_paused_seconds, 1),
            "pause_count": len(self.pause_events),
            "pause_events": self.pause_events,
            "threshold_g_kwh": self.threshold,
            "region": self.region,
        }

