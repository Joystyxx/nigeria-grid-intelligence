"""Feature engineering for grid instability prediction.

Reads fct_grid_events from Postgres, engineers rolling/lag/time
features plus outage-history features, and constructs the binary
target `outage_within_6h`.

The output is a model-ready DataFrame with no nulls in feature
columns and a clean train/test split boundary by time.
"""
from __future__ import annotations

import pandas as pd

from grid_intelligence.db import read_df
from grid_intelligence.utils.logging import get_logger

log = get_logger(__name__)

# Feature columns after engineering
NUMERIC_FEATURES = [
    "avg_load_mw",
    "peak_load_mw",
    "forecast_error_mw",
    "load_avg_6h",
    "load_std_6h",
    "load_avg_24h",
    "load_std_24h",
    "avg_frequency_hz",
    "avg_freq_dev_hz",
    "avg_temp_c",
    "avg_humidity",
    "sensor_anomalies",
    "sensor_anomaly_pct",
    "lag_load_1h",
    "lag_load_6h",
    "lag_load_24h",
    "hour_of_day",
    "day_of_week",
    "month",
    "is_weekend",
    # Outage-history features (autocorrelation signal)
    "hours_since_last_severe_outage",
    "severe_outages_last_24h",
    "severe_outages_last_7d",
]

TARGET = "outage_within_6h"


def load_base() -> pd.DataFrame:
    """Load the ML feature table from Postgres."""
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
    """
    df = read_df(sql)
    log.info("features: loaded %d rows from fct_grid_events", len(df))
    return df


def _hours_since_last(series: pd.Series, cap: int = 168) -> pd.Series:
    """Hours elapsed since the last 1 in the series (capped)."""
    out = []
    last = None
    for i, v in enumerate(series):
        if last is None:
            out.append(cap)
        else:
            out.append(min(i - last, cap))
        if v == 1:
            last = i
    return pd.Series(out, index=series.index)


def _forward_window_max_6h(s: pd.Series) -> pd.Series:
    """target[i] = 1 if any s[i+1..i+6] == 1.

    Purely forward-looking. Must reverse-roll-reverse; the simpler
    s.shift(-1).rolling(6).max() looks BACKWARD 4 hours + forward 1,
    which leaks past outage signals into the target.
    """
    shifted = s.shift(-1)
    rev = shifted.iloc[::-1]
    rolled = rev.rolling(6, min_periods=1).max()
    return rolled.iloc[::-1].fillna(0).astype(int)


def engineer(df: pd.DataFrame) -> pd.DataFrame:
    """Add lag, time, outage-history, and target features."""
    df = df.copy()
    df["event_ts"] = pd.to_datetime(df["event_ts"], utc=True)

    # Sort by substation and time — essential for lag/rolling windows
    df = df.sort_values(["substation_id", "event_ts"]).reset_index(drop=True)

    # Lag features: load N hours ago per substation
    for lag_h in [1, 6, 24]:
        df[f"lag_load_{lag_h}h"] = (
            df.groupby("substation_id")["avg_load_mw"].shift(lag_h)
        )

    # Time features
    df["hour_of_day"] = df["event_ts"].dt.hour
    df["day_of_week"] = df["event_ts"].dt.dayofweek
    df["month"] = df["event_ts"].dt.month
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

    # Outage-history features (within-substation chronological)
    df["severe_outages_last_24h"] = (
        df.groupby("substation_id")["had_severe_outage"]
        .transform(lambda s: s.rolling(24, min_periods=1).sum())
    )
    df["severe_outages_last_7d"] = (
        df.groupby("substation_id")["had_severe_outage"]
        .transform(lambda s: s.rolling(24 * 7, min_periods=1).sum())
    )
    df["hours_since_last_severe_outage"] = (
        df.groupby("substation_id")["had_severe_outage"]
        .transform(_hours_since_last)
    )

    # Target: severe outage (customers_affected > 1000) in the NEXT 6 hours.
    # Raw HF data has outages in ~26% of hours; severity-filtered gives ~19%.
    df["outage_within_6h"] = (
        df.groupby("substation_id")["had_severe_outage"]
        .transform(_forward_window_max_6h)
    )

    # Drop rows with null lags (first 24h of each substation)
    before = len(df)
    df = df.dropna(
        subset=[f"lag_load_{h}h" for h in [1, 6, 24]]
    ).reset_index(drop=True)
    log.info("features: dropped %d rows with null lags", before - len(df))

    return df


def build_feature_matrix() -> pd.DataFrame:
    """Full pipeline: load -> engineer -> return."""
    df = load_base()
    df = engineer(df)
    log.info(
        "features: final shape %s, target positive rate=%.3f",
        df.shape,
        df[TARGET].mean(),
    )
    return df


if __name__ == "__main__":
    df = build_feature_matrix()
    print(f"Rows: {len(df)}")
    print(f"Features: {len(NUMERIC_FEATURES)}")
    print(f"Target positive rate: {df[TARGET].mean():.3%}")
    print(f"Date range: {df['event_ts'].min()} -> {df['event_ts'].max()}")
    print("\nSample:")
    print(df[NUMERIC_FEATURES + [TARGET]].head(3).to_string())
