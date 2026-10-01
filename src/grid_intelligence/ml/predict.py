"""Run inference: predict outage probability, load spike probability,
and composite stress score for the latest substation-hours.

Reads:   dbt_dev_marts.fct_grid_events
Models:  models/grid_instability_v1.pkl, models/load_spike_v1.pkl
Writes:  ml.grid_instability_predictions
"""
from __future__ import annotations

from datetime import datetime, timezone

import joblib
import pandas as pd

from grid_intelligence.config import MODELS_DIR
from grid_intelligence.db import read_df, write_df
from grid_intelligence.ml.features import NUMERIC_FEATURES
from grid_intelligence.ml.stress_score import compute as compute_stress
from grid_intelligence.utils.logging import get_logger

log = get_logger(__name__)

OUTAGE_MODEL = MODELS_DIR / "grid_instability_v1.pkl"
LOAD_SPIKE_MODEL = MODELS_DIR / "load_spike_v1.pkl"


def _load_latest_features() -> pd.DataFrame:
    """Load recent substation-hours and reproduce the training feature set."""
    sql = """
        SELECT
            event_ts,
            disco,
            substation_id,
            avg_load_mw,
            peak_load_mw,
            forecast_error_mw,
            load_avg_6h,
            load_std_6h,
            load_avg_24h,
            load_std_24h,
            avg_frequency_hz,
            avg_freq_dev_hz,
            avg_temp_c,
            avg_humidity,
            sensor_anomalies,
            sensor_anomaly_pct,
            had_outage,
            had_severe_outage
        FROM dbt_dev_marts.fct_grid_events
        ORDER BY substation_id, event_ts
    """
    df = read_df(sql)
    df["event_ts"] = pd.to_datetime(df["event_ts"], utc=True)
    df = df.sort_values(["substation_id", "event_ts"]).reset_index(drop=True)

    # Rebuild lag features exactly as features.py does
    for lag_h in [1, 6, 24]:
        df[f"lag_load_{lag_h}h"] = (
            df.groupby("substation_id")["avg_load_mw"].shift(lag_h)
        )

    df["hour_of_day"] = df["event_ts"].dt.hour
    df["day_of_week"] = df["event_ts"].dt.dayofweek
    df["month"] = df["event_ts"].dt.month
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

    df["severe_outages_last_24h"] = (
        df.groupby("substation_id")["had_severe_outage"]
        .transform(lambda s: s.rolling(24, min_periods=1).sum())
    )
    df["severe_outages_last_7d"] = (
        df.groupby("substation_id")["had_severe_outage"]
        .transform(lambda s: s.rolling(24 * 7, min_periods=1).sum())
    )

    def _hours_since(series, cap=168):
        out, last = [], None
        for i, v in enumerate(series):
            out.append(cap if last is None else min(i - last, cap))
            if v == 1:
                last = i
        return pd.Series(out, index=series.index)

    df["hours_since_last_severe_outage"] = (
        df.groupby("substation_id")["had_severe_outage"]
        .transform(_hours_since)
    )

    # Drop rows that are still missing lag features (first 24h per substation)
    df = df.dropna(
        subset=[f"lag_load_{h}h" for h in [1, 6, 24]]
    ).reset_index(drop=True)

    # Keep only the most recent N hours per substation for dashboard speed
    latest = (
        df.groupby("substation_id")
        .tail(24)
        .reset_index(drop=True)
    )
    log.info("predict: loaded %d recent substation-hours", len(latest))
    return latest


def run() -> int:
    """Score latest rows, write predictions to ml.grid_instability_predictions."""
    log.info("predict: loading models")
    outage_model = joblib.load(OUTAGE_MODEL)
    spike_model = joblib.load(LOAD_SPIKE_MODEL)

    df = _load_latest_features()
    if df.empty:
        log.warning("predict: no rows to score")
        return 0

    X = df[NUMERIC_FEATURES]

    log.info("predict: running outage model")
    outage_prob = outage_model.predict_proba(X)[:, 1]
    outage_pred = (outage_prob >= 0.5).astype(int)

    log.info("predict: running load spike model")
    spike_prob = spike_model.predict_proba(X)[:, 1]

    log.info("predict: computing composite stress score")
    scored = compute_stress(df, spike_prob, outage_prob)

    output = pd.DataFrame(
        {
            "predicted_at": datetime.now(timezone.utc),
            "event_ts": scored["event_ts"],
            "disco": scored["disco"],
            "substation_id": scored["substation_id"],
            "outage_probability": outage_prob.round(4),
            "outage_predicted": outage_pred,
            "load_spike_probability": spike_prob.round(4),
            "load_percentile": scored["load_percentile"].round(2),
            "freq_deviation_score": scored["freq_deviation_score"].round(2),
            "sensor_anomaly_score": scored["sensor_anomaly_score"].round(2),
            "stress_score": scored["stress_score"],
            "stress_tier": scored["stress_tier"],
        }
    )

    rows = write_df(output, "ml", "grid_instability_predictions")
    log.info("predict: wrote %d rows to ml.grid_instability_predictions", rows)

    # Summary stats
    tier_counts = output["stress_tier"].value_counts().to_dict()
    log.info("predict: stress tier distribution = %s", tier_counts)

    return rows


if __name__ == "__main__":
    n = run()
    print(f"\nWrote {n} prediction rows")

    # Show distribution
    df = read_df(
        "SELECT stress_tier, COUNT(*) AS n, "
        "ROUND(AVG(stress_score)::numeric, 2) AS avg_score "
        "FROM ml.grid_instability_predictions GROUP BY 1 ORDER BY 1"
    )
    print("\nStress tier distribution:")
    print(df.to_string(index=False))

    # Show top 5 most stressed substations
    print("\nTop 5 most stressed substations:")
    top = read_df(
        "SELECT substation_id, disco, stress_score, stress_tier "
        "FROM ml.grid_instability_predictions "
        "ORDER BY stress_score DESC LIMIT 5"
    )
    print(top.to_string(index=False))