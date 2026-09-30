"""Central configuration loader for the project.

Reads environment variables from .env and exposes them as typed
constants for use across ingestion, ML, and optimisation scripts.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Repo root is two levels up from this file:
# config.py -> grid_intelligence/ -> src/ -> repo root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Load .env from repo root (does nothing if already loaded)
load_dotenv(PROJECT_ROOT / ".env")

# --- Database ---
POSTGRES_USER: str = os.getenv("POSTGRES_USER", "grid_admin")
POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "grid_password")
POSTGRES_DB: str = os.getenv("POSTGRES_DB", "grid_intelligence")
POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))

DATABASE_URL: str = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

# --- Schemas ---
SCHEMA_RAW = "raw"
SCHEMA_STAGING = "staging"
SCHEMA_INTERMEDIATE = "intermediate"
SCHEMA_MARTS = "marts"
SCHEMA_ML = "ml"

# --- External APIs ---
HF_TOKEN: str | None = os.getenv("HF_TOKEN")

# --- Paths ---
DBT_PROFILES_DIR: Path = PROJECT_ROOT / os.getenv("DBT_PROFILES_DIR", "./dbt")
MODELS_DIR: Path = PROJECT_ROOT / "models"
MODELS_DIR.mkdir(exist_ok=True)