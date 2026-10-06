"""Dagster orchestration for the Nigeria Grid Intelligence Platform.

Defines software-defined assets for the entire pipeline:
  ingestion -> dbt -> ML -> optimisation -> export

Exposed as `defs` for dagster-webserver discovery.
Daily job scheduled at 06:00 UTC.
"""
from __future__ import annotations

import subprocess
import sys

from dagster import (
    Definitions,
    ScheduleDefinition,
    asset,
    define_asset_job,
)

from grid_intelligence.config import PROJECT_ROOT


def _run_module(module: str) -> str:
    """Run a Python module as a subprocess and return combined output."""
    cmd = [sys.executable, "-m", module]
    result = subprocess.run(
        cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, check=True
    )
    return (result.stdout or "") + (result.stderr or "")


def _run_dbt(args: list[str]) -> str:
    """Run a dbt command from the dbt/ directory."""
    result = subprocess.run(
        ["dbt", *args],
        cwd=PROJECT_ROOT / "dbt",
        capture_output=True,
        text=True,
        check=True,
    )
    return (result.stdout or "") + (result.stderr or "")


def _run_script(script_path: str) -> str:
    """Run a Python script by path."""
    cmd = [sys.executable, str(PROJECT_ROOT / script_path)]
    result = subprocess.run(
        cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, check=True
    )
    return (result.stdout or "") + (result.stderr or "")


# =========================================================
# INGESTION — 8 assets (one per source)
# =========================================================

@asset(group_name="ingestion", compute_kind="python")
def raw_grid_load() -> str:
    """Nigerian grid load — 200K rows from Hugging Face."""
    return _run_module("grid_intelligence.ingestion.ingest_grid_load")


@asset(group_name="ingestion", compute_kind="python")
def raw_demand_forecast() -> str:
    """Per-region demand forecast — 200K rows from Hugging Face."""
    return _run_module("grid_intelligence.ingestion.ingest_demand_forecast")


@asset(group_name="ingestion", compute_kind="python")
def raw_smart_grid_iot() -> str:
    """5-min substation telemetry — 250K rows from Hugging Face."""
    return _run_module("grid_intelligence.ingestion.ingest_smart_grid_iot")


@asset(group_name="ingestion", compute_kind="python")
def raw_outage_logs() -> str:
    """Outage and fault events — 60K rows from Hugging Face."""
    return _run_module("grid_intelligence.ingestion.ingest_outage_logs")


@asset(group_name="ingestion", compute_kind="python")
def raw_ai_optimization() -> str:
    """Pre-computed grid optimisation runs — 80K rows from Hugging Face."""
    return _run_module("grid_intelligence.ingestion.ingest_ai_optimization")


@asset(group_name="ingestion", compute_kind="python")
def raw_pvgis() -> str:
    """Solar irradiation for Lagos/Abuja/Kano — from EU JRC PVGIS API."""
    return _run_module("grid_intelligence.ingestion.ingest_pvgis")


@asset(group_name="ingestion", compute_kind="python")
def raw_owid() -> str:
    """Historical Nigerian energy mix — from Our World in Data."""
    return _run_module("grid_intelligence.ingestion.ingest_owid")


@asset(group_name="ingestion", compute_kind="python")
def raw_dre_atlas() -> str:
    """154K Nigerian settlements — from World Bank DRE Atlas."""
    return _run_module("grid_intelligence.ingestion.ingest_dre_atlas")


# =========================================================
# TRANSFORMATION — dbt (single asset runs all models + tests)
# =========================================================

@asset(
    group_name="transformation",
    compute_kind="dbt",
    deps=[
        raw_grid_load,
        raw_demand_forecast,
        raw_smart_grid_iot,
        raw_outage_logs,
        raw_ai_optimization,
        raw_pvgis,
        raw_owid,
        raw_dre_atlas,
    ],
)
def dbt_models() -> str:
    """Run the full dbt pipeline (staging -> intermediate -> marts) + tests."""
    run_output = _run_dbt(["run"])
    test_output = _run_dbt(["test"])
    return run_output + "\n\n=== dbt test ===\n\n" + test_output


# =========================================================
# ML — training, prediction
# =========================================================

@asset(group_name="ml", compute_kind="python", deps=[dbt_models])
def grid_instability_model() -> str:
    """Train XGBoost outage model (AUC 0.51) and load spike model (AUC 0.66)."""
    outage = _run_module("grid_intelligence.ml.train_grid_instability")
    spike = _run_module("grid_intelligence.ml.train_load_spike")
    return outage + "\n\n=== load spike ===\n\n" + spike


@asset(group_name="ml", compute_kind="python", deps=[grid_instability_model])
def grid_instability_predictions() -> str:
    """Predict outage probability, load spike probability, and stress score."""
    return _run_module("grid_intelligence.ml.predict")


# =========================================================
# OPTIMISATION — BESS dispatch, sensitivity, multi-year
# =========================================================

@asset(group_name="optimisation", compute_kind="python", deps=[dbt_models])
def bess_optimization() -> str:
    """Run 12-scenario BESS dispatch matrix across 3 regions x 4 modes."""
    return _run_module("grid_intelligence.optimization.run_scenarios")


@asset(group_name="optimisation", compute_kind="python", deps=[bess_optimization])
def bess_sensitivity() -> str:
    """54-cell sensitivity: diesel price x battery capacity x charging source."""
    return _run_module("grid_intelligence.optimization.run_sensitivity")


@asset(group_name="optimisation", compute_kind="python", deps=[bess_optimization])
def bess_multiyear() -> str:
    """Multi-year BESS economics: 2024 / 2025 / 2026 price comparison."""
    return _run_module("grid_intelligence.optimization.run_multiyear")


# =========================================================
# EXPORT — GeoJSON for mapping
# =========================================================

@asset(group_name="export", compute_kind="python", deps=[dbt_models])
def minigrid_geojson() -> str:
    """Export top-50-per-state and full A+B tier GeoJSON files."""
    return _run_script("scripts/export_minigrid_geojson.py")


# =========================================================
# JOB + SCHEDULE
# =========================================================

daily_pipeline = define_asset_job(
    name="daily_grid_intelligence",
    description="Full pipeline: ingest -> dbt -> ML -> optimisation -> export",
)

daily_schedule = ScheduleDefinition(
    name="daily_at_0600_utc",
    job=daily_pipeline,
    cron_schedule="0 6 * * *",
    execution_timezone="UTC",
)


defs = Definitions(
    assets=[
        raw_grid_load,
        raw_demand_forecast,
        raw_smart_grid_iot,
        raw_outage_logs,
        raw_ai_optimization,
        raw_pvgis,
        raw_owid,
        raw_dre_atlas,
        dbt_models,
        grid_instability_model,
        grid_instability_predictions,
        bess_optimization,
        bess_sensitivity,
        bess_multiyear,
        minigrid_geojson,
    ],
    jobs=[daily_pipeline],
    schedules=[daily_schedule],
)
