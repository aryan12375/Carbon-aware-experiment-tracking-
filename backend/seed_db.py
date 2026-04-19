"""
backend/seed_db.py
==================
EcoTrack Demo Data Seeder. 
Populates the database with diverse runs (Image, NLP, Generative) 
so the portfolio dashboard, matchmaker, and nutrition label look full.
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

# Import models
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.models.emissions import EmissionsRun
from app.db.session import Base
from app.core.config import get_settings

settings = get_settings()

DEMO_RUNS = [
    {
        "run_id": "21223",
        "project_name": "ResNet-Baseline",
        "model_name": "resnet50",
        "started_at": datetime.now(timezone.utc) - timedelta(hours=24),
        "finished_at": datetime.now(timezone.utc) - timedelta(hours=22, minutes=30),
        "duration_seconds": 5400,
        "co2_grams": 420.5,
        "co2_kg": 0.4205,
        "energy_kwh": 0.85,
        "grid_intensity_g_kwh": 495.0,
        "grid_source": "co2signal",
        "grid_region": "IN-SO",
        "gpu_model": "NVIDIA T4",
        "gpu_count": 1,
        "cpu_model": "Intel(R) Xeon(R) CPU @ 2.20GHz",
        "accuracy": 92.4,
        "loss": 0.12,
        "extra_metrics_json": json.dumps({"epochs": 10, "batch_size": 32})
    },
    {
        "run_id": "bert-77a",
        "project_name": "Sentiment-NLP",
        "model_name": "bert-base-uncased",
        "started_at": datetime.now(timezone.utc) - timedelta(days=2),
        "finished_at": datetime.now(timezone.utc) - timedelta(days=1, hours=20),
        "duration_seconds": 14400,
        "co2_grams": 1250.0,
        "co2_kg": 1.25,
        "energy_kwh": 2.5,
        "grid_intensity_g_kwh": 500.0,
        "grid_source": "electricitymaps",
        "grid_region": "IN-NO",
        "gpu_model": "NVIDIA A100-SXM4-40GB",
        "gpu_count": 2,
        "cpu_model": "AMD EPYC 7742",
        "accuracy": 94.8,
        "loss": 0.08,
        "extra_metrics_json": json.dumps({"f1_score": 0.93, "precision": 0.94})
    },
    {
        "run_id": "sd-xl-9",
        "project_name": "Creative-Gen",
        "model_name": "stable-diffusion-xl",
        "started_at": datetime.now(timezone.utc) - timedelta(days=3),
        "finished_at": datetime.now(timezone.utc) - timedelta(days=2, hours=12),
        "duration_seconds": 43200,
        "co2_grams": 5800.0,
        "co2_kg": 5.8,
        "energy_kwh": 12.0,
        "grid_intensity_g_kwh": 483.0,
        "grid_source": "co2signal",
        "grid_region": "US-CAL-CISO",
        "gpu_model": "NVIDIA RTX 3090",
        "gpu_count": 1,
        "cpu_model": "Intel Core i9-12900K",
        "accuracy": 85.0, # CLIP Score proxy
        "loss": 0.02,
        "extra_metrics_json": json.dumps({"images_generated": 1000})
    },
    {
        "run_id": "llama-cheap",
        "project_name": "Llama-Finetune",
        "model_name": "llama-2-7b-int4",
        "started_at": datetime.now(timezone.utc) - timedelta(hours=5),
        "finished_at": datetime.now(timezone.utc) - timedelta(hours=1),
        "duration_seconds": 14400,
        "co2_grams": 45.0,
        "co2_kg": 0.045,
        "energy_kwh": 0.15,
        "grid_intensity_g_kwh": 300.0,
        "grid_source": "heuristic_model",
        "grid_region": "FR",
        "gpu_model": "NVIDIA RTX 4090",
        "gpu_count": 1,
        "cpu_model": "AMD Ryzen 9 7950X",
        "accuracy": 88.2,
        "loss": 0.5,
        "extra_metrics_json": json.dumps({"quantized": True, "bits": 4})
    }
]

async def seed():
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print(f"Seeding database at {settings.DATABASE_URL}...")

    async with engine.begin() as conn:
        # Import models here to ensure they are registered with Base metadata
        import app.models.emissions
        await conn.run_sync(Base.metadata.create_all)
        print("  Database tables verified/created.")

    async with async_session() as session:
        for run_data in DEMO_RUNS:
            # Check if exists
            result = await session.execute(
                select(EmissionsRun).where(EmissionsRun.run_id == run_data["run_id"])
            )
            if not result.scalar_one_or_none():
                run = EmissionsRun(**run_data)
                session.add(run)
                print(f"  + Added Run: {run_data['run_id']} ({run_data['model_name']})")
            else:
                print(f"  - Run {run_data['run_id']} already exists, skipping.")
        
        await session.commit()
    
    print("\nSeeding complete! Your EcoTrack dashboard is now ready for presentation.")

if __name__ == "__main__":
    asyncio.run(seed())
