"""
app/services/scheduler_service.py
===================================
Feature 1 — "Green-Pause" Carbon-Aware Scheduler

Fetches real-time grid carbon intensity and generates a 24-hour forecast
to identify clean windows for scheduling GPU training jobs.

For India (IN-SO / Karnataka):
  - Dirtiest hours: 17:00–22:00 (evening peak, thermal plants)
  - Cleanest hours: 10:00–15:00 (solar peaking), 02:00–05:00 (low demand)

The heuristic model is based on CEA 2023-24 India grid data.
"""

from __future__ import annotations

import math
import os
from datetime import datetime, timezone
from typing import Optional

import requests

from app.schemas.emissions import GridForecastPoint, GridIntensityResponse, SchedulerWindow

# Grid API keys (from environment / .env)
CO2_SIGNAL_KEY = os.getenv("CO2SIGNAL_API_KEY", "")
ELECTRICITY_MAPS_KEY = os.getenv("ELECTRICITY_MAPS_KEY", "")
CARBON_API_TIMEOUT = 5

# India baseline grid intensity (CEA 2023-24)
_REGIONAL_BASELINE: dict[str, float] = {
    "IN":    713.0,
    "IN-SO": 680.0,   # Karnataka — more solar than north
    "IN-NO": 780.0,
    "IN-EA": 750.0,
    "DE":    385.0,
    "FR":    85.0,
    "US-CA": 260.0,
    "GB":    233.0,
}

# Hourly modifiers for India grid (0 = no change, negative = cleaner)
# Based on typical solar generation curve + demand curve
_INDIA_HOURLY_MODIFIERS = [
    +0.15,  # 00:00 — night, moderate demand
    +0.10,  # 01:00
    +0.05,  # 02:00 — lowest demand (clean window)
    -0.02,  # 03:00
    -0.05,  # 04:00
    -0.03,  # 05:00
    +0.00,  # 06:00 — demand rising
    +0.05,  # 07:00
    +0.02,  # 08:00
    -0.05,  # 09:00 — solar ramping up
    -0.20,  # 10:00 — solar peak starts ☀️
    -0.28,  # 11:00 — peak solar
    -0.32,  # 12:00 — cleanest hour
    -0.30,  # 13:00
    -0.25,  # 14:00
    -0.15,  # 15:00 — solar declining
    +0.05,  # 16:00 — demand spike evening
    +0.20,  # 17:00 — dirtiest: peak demand + no solar
    +0.30,  # 18:00
    +0.28,  # 19:00
    +0.22,  # 20:00
    +0.18,  # 21:00
    +0.12,  # 22:00 — gradual decline
    +0.10,  # 23:00
]


def _intensity_label(intensity: float) -> str:
    if intensity < 400:
        return "clean"
    if intensity < 600:
        return "moderate"
    return "dirty"


def _carbon_rating(intensity: float) -> str:
    if intensity < 300:
        return "A"
    if intensity < 450:
        return "B"
    if intensity < 600:
        return "C"
    if intensity < 750:
        return "D"
    return "F"


def _fetch_live_intensity(region: str) -> tuple[float, str]:
    """Fetch live carbon intensity from CO2Signal or ElectricityMaps."""
    # Try CO2Signal
    if CO2_SIGNAL_KEY:
        try:
            resp = requests.get(
                "https://api.co2signal.com/v1/latest",
                params={"countryCode": region.split("-")[0]},
                headers={"auth-token": CO2_SIGNAL_KEY},
                timeout=CARBON_API_TIMEOUT,
            )
            if resp.status_code == 200:
                data = resp.json()
                return float(data["data"]["carbonIntensity"]), "co2signal"
        except Exception:
            pass

    # Try ElectricityMaps
    if ELECTRICITY_MAPS_KEY:
        try:
            resp = requests.get(
                "https://api.electricitymap.org/v3/carbon-intensity/latest",
                params={"zone": region},
                headers={"auth-token": ELECTRICITY_MAPS_KEY},
                timeout=CARBON_API_TIMEOUT,
            )
            if resp.status_code == 200:
                data = resp.json()
                return float(data["carbonIntensity"]), "electricitymaps"
        except Exception:
            pass

    # Fallback: use baseline for the current hour
    baseline = _REGIONAL_BASELINE.get(region, _REGIONAL_BASELINE.get(region.split("-")[0], 713.0))
    now_hour = datetime.now(timezone.utc).hour
    # Adjust for IST (UTC+5:30 → add 5.5h)
    # We use integer approximation
    local_hour = (now_hour + 5) % 24
    modifier = _INDIA_HOURLY_MODIFIERS[local_hour]
    return round(baseline * (1 + modifier), 1), "heuristic_model"


class SchedulerService:
    """
    Carbon-aware scheduler intelligence.

    Methods are synchronous (no DB needed) — they call external APIs
    and run heuristic modelling. Designed to be fast (<100ms).
    """

    @staticmethod
    def get_grid_intensity_and_forecast(region: str = "IN-SO") -> GridIntensityResponse:
        """
        Get current grid intensity + 24-hour synthetic forecast.

        Returns a GridIntensityResponse that the frontend can use to
        render the heatmap and recommend scheduling windows.
        """
        current_intensity, source = _fetch_live_intensity(region)
        baseline = _REGIONAL_BASELINE.get(region, 713.0)

        now_hour = datetime.now(timezone.utc).hour
        local_now_hour = (now_hour + 5) % 24  # IST approximation

        forecast: list[GridForecastPoint] = []
        for h in range(24):
            modifier = _INDIA_HOURLY_MODIFIERS[h]
            intensity = round(baseline * (1 + modifier), 1)

            # Scale slightly around the live reading for realism
            if h == local_now_hour and source != "heuristic_model":
                intensity = current_intensity
            elif source != "heuristic_model":
                # Shift synthetic values to match live reading
                delta = current_intensity - baseline * (1 + _INDIA_HOURLY_MODIFIERS[local_now_hour])
                intensity = round(intensity + delta * 0.5, 1)

            intensity = max(50.0, intensity)  # floor at 50 g/kWh

            forecast.append(GridForecastPoint(
                hour=h,
                intensity_g_kwh=intensity,
                label=_intensity_label(intensity),
                is_optimal=intensity < baseline * 0.85,  # 15%+ cleaner than baseline
            ))

        # Find optimal windows (contiguous clean hours)
        optimal_windows = SchedulerService._find_windows(forecast, baseline)

        # Calculate potential saving: worst hour vs best available window
        max_intensity = max(p.intensity_g_kwh for p in forecast)
        min_intensity = min(p.intensity_g_kwh for p in forecast)
        saving_pct = round((max_intensity - min_intensity) / max_intensity * 100, 1)

        return GridIntensityResponse(
            region=region,
            current_intensity=current_intensity,
            current_label=_intensity_label(current_intensity),
            source=source,
            forecast=forecast,
            optimal_windows=optimal_windows,
            potential_saving_pct=saving_pct,
        )

    @staticmethod
    def _find_windows(forecast: list[GridForecastPoint], baseline: float) -> list[str]:
        """Find contiguous blocks of clean hours."""
        clean_hours = [p.hour for p in forecast if p.intensity_g_kwh < baseline * 0.85]
        if not clean_hours:
            return []

        windows = []
        start = clean_hours[0]
        prev = clean_hours[0]
        for h in clean_hours[1:]:
            if h == prev + 1:
                prev = h
            else:
                windows.append(f"{start:02d}:00–{prev+1:02d}:00")
                start = h
                prev = h
        windows.append(f"{start:02d}:00–{prev+1:02d}:00")
        return windows[:3]  # top 3 windows

    @staticmethod
    def get_optimal_windows(region: str = "IN-SO") -> list[SchedulerWindow]:
        """Return ranked list of optimal training windows for today."""
        response = SchedulerService.get_grid_intensity_and_forecast(region)
        baseline = _REGIONAL_BASELINE.get(region, 713.0)

        # Group consecutive clean hours into windows
        windows: list[SchedulerWindow] = []
        start = None
        intensities = []

        for point in response.forecast + [None]:  # sentinel to flush last window
            if point and point.intensity_g_kwh < baseline * 0.90:
                if start is None:
                    start = point.hour
                intensities.append(point.intensity_g_kwh)
            else:
                if start is not None and intensities:
                    avg = sum(intensities) / len(intensities)
                    saving = round((baseline - avg) / baseline * 100, 1)
                    windows.append(SchedulerWindow(
                        start_hour=start,
                        end_hour=(start + len(intensities)) % 24,
                        avg_intensity=round(avg, 1),
                        estimated_saving_pct=saving,
                        label=_intensity_label(avg),
                    ))
                start = None
                intensities = []

        # Sort by lowest average intensity (cleanest first)
        return sorted(windows, key=lambda w: w.avg_intensity)[:5]

    @staticmethod
    def calculate_job_savings(
        energy_kwh: float,
        current_hour: int,
        optimal_hour: int,
        region: str = "IN-SO",
    ) -> dict:
        """
        Calculate how much CO₂ you save by shifting a job from
        current_hour to optimal_hour.
        """
        baseline = _REGIONAL_BASELINE.get(region, 713.0)
        current_intensity = baseline * (1 + _INDIA_HOURLY_MODIFIERS[current_hour])
        optimal_intensity = baseline * (1 + _INDIA_HOURLY_MODIFIERS[optimal_hour])

        current_co2 = energy_kwh * current_intensity / 1000
        optimal_co2 = energy_kwh * optimal_intensity / 1000
        saved_co2 = current_co2 - optimal_co2

        return {
            "current_co2_kg": round(current_co2, 4),
            "optimal_co2_kg": round(optimal_co2, 4),
            "saved_co2_kg": round(saved_co2, 4),
            "saving_pct": round(saved_co2 / current_co2 * 100, 1) if current_co2 > 0 else 0,
            "region": region,
            "current_hour": current_hour,
            "optimal_hour": optimal_hour,
        }
