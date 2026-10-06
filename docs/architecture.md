# Architecture

A short technical overview. For results and problem context, see the [README](../README.md).

---

## Layers

Sources → Ingestion → Storage → Transformation → ML & Optimisation → Serving


**Sources.** Eight external sources: five Hugging Face datasets, PVGIS (EU JRC solar API), OWID energy CSV, and the World Bank DRE Atlas.

**Ingestion.** Eight Python scripts in `src/grid_intelligence/ingestion/`. Each tries its primary source, falls back to synthetic data on failure, and writes to the `raw` schema. Idempotent (replace-on-rerun).

**Storage.** PostgreSQL 15 with TimescaleDB, running in Docker. Five schemas: `raw` (untouched source data), `staging` (cleaned views), `intermediate` (aggregated views), `marts` (business tables), `ml` (model outputs).

**Transformation.** dbt builds 16 models: 8 staging, 3 intermediate, 6 marts. All marts have schema tests. Only marts and raw hold physical tables.

**ML & Optimisation.** Two XGBoost classifiers (outage, load spike) plus a composite stress score. One PuLP linear program optimises BESS dispatch across 12 scenarios and a 54-cell sensitivity grid.

**Serving.** Six-page Streamlit dashboard with custom theming. Dagster orchestrates the full pipeline as 15 software-defined assets on a daily 06:00 UTC schedule.

---

## Data Flow

1. Dagster triggers `daily_grid_intelligence` job.
2. Eight ingestion assets write to `raw`.
3. dbt runs 16 models and 27 tests.
4. ML assets train, predict, and score.
5. Optimisation assets run 12 scenarios + sensitivity + multi-year.
6. GeoJSON export writes the map files.
7. Streamlit reads from `marts` and `ml` schemas.

Runtime on an 8 GB laptop: 15 to 25 minutes end to end.

---

## Containerisation

Three services in `docker-compose.yml`:

| Service | Port | Purpose |
|---|---|---|
| postgres | 5432 | TimescaleDB with healthcheck |
| dagster | 3000 | Orchestrator UI + job execution |
| streamlit | 8501 | Dashboard |

Dagster and Streamlit share the same custom image built from `Dockerfile` (`python:3.12-slim` + `pip install -e ".[dev]"`). Source code is volume-mounted so code changes appear without rebuilding.

For local development, run any Python module directly in a venv with `docker compose up -d postgres` providing just the database.

---

## Key Decisions

**PostgreSQL + TimescaleDB over SQLite/DuckDB.** Time-series data benefits from hypertables and time-bucket functions. It also gives the project a real production-grade database.

**dbt over pandas for transformation.** Declarative SQL, lineage tracking, built-in tests, auto-generated docs, and a queryable DAG.

**Dagster over Airflow.** Asset-based model fits this project: each asset is a raw table, a mart, or a model. Dependencies are Python objects, not DAG config files.

**Subprocess invocation in Dagster, not dagster-dbt.** Native integration requires manifest generation and per-model mapping. Subprocess works and keeps the DAG readable. Future work can migrate.

**Synthetic fallback on every ingester.** Nigerian public data sources are unstable. The pipeline must survive source failures without human intervention.

---

## What Runs Where

Everything runs inside Docker. The host machine only needs Docker Desktop. Python, dbt, Dagster, PuLP, XGBoost, and every dependency live in the containers.

The `postgres_data` Docker volume persists the database across restarts. The `dagster_home` volume persists Dagster run history.

---

## Extending the Platform

**Add a data source:** write an ingester in `ingestion/`, add it to `_sources.yml`, create a staging model, reference it downstream, add a Dagster asset.

**Add a dashboard page:** create `app/pages/N_name.py`, call `apply_theme()` after `st.set_page_config()`, query from `marts` or `ml`. Streamlit auto-discovers it.

**Change prices:** edit `config/energy_prices.yaml` and re-run the BESS scripts. No code changes needed.
