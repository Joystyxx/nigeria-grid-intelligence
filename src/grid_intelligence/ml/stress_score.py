"""Composite grid stress score (0-100) per substation-hour.

Combines multiple weak signals into one actionable metric. Weights
reflect signal quality from model evaluation:
  - load_spike_probability  (35%) — best real signal, AUC 0.66
  - load_percentile         (20%) — relative load rank within snapshot
  - freq_deviation          (20%) — grid stability indicator
  - sensor_anomaly          (15%) — equipment health
  - outage_probability      (10%) — weak model, low weight

Normalization: physical-state components (load, frequency, sensor)
use PERCENTILE RANK within the current snapshot. This gives each
component a uniform 0-100 spread, ensuring the composite score
actually differentiates rows. Model outputs stay absolute.

The score is NOT a replacement for the ML models. It's a decision
surface for operators: what's happening now, how bad, and what to watch.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

WEIGHTS = {
    "load_spike_prob": 0.35,
    "load_percentile": 0.20,
    "freq_deviation": 0.20,
    "sensor_anomaly": 0.15,
    "outage_prob": 0.10,
}


def _rank_100(s: pd.Series) -> pd.Series:
    """Percentile rank within series, scaled to 0-100."""
    if s.nunique() <= 1:
        return pd.Series(50.0, index=s.index)
    return s.rank(pct=True) * 100


def compute(
    df: pd.DataFrame,
    load_spike_prob: np.ndarray,
    outage_prob: np.ndarray,
) -> pd.DataFrame:
    """Compute composite stress score.

    Expects df with columns:
        avg_load_mw, avg_freq_dev_hz, sensor_anomaly_pct
    And pre-computed arrays for the two model probabilities.
    """
    out = df.copy()
    out["load_spike_probability"] = load_spike_prob
    out["outage_probability"] = outage_prob

    # Percentile-rank normalized physical components (0-100 relative)
    out["load_percentile"] = _rank_100(out["avg_load_mw"])
    out["freq_deviation_score"] = _rank_100(out["avg_freq_dev_hz"])
    out["sensor_anomaly_score"] = _rank_100(out["sensor_anomaly_pct"])

    # Weighted composite
    out["stress_score"] = (
        WEIGHTS["load_spike_prob"] * (out["load_spike_probability"] * 100)
        + WEIGHTS["load_percentile"] * out["load_percentile"]
        + WEIGHTS["freq_deviation"] * out["freq_deviation_score"]
        + WEIGHTS["sensor_anomaly"] * out["sensor_anomaly_score"]
        + WEIGHTS["outage_prob"] * (out["outage_probability"] * 100)
    ).round(2)

    # Tier labels for dashboard display
    out["stress_tier"] = pd.cut(
        out["stress_score"],
        bins=[-0.01, 40, 60, 80, 100],
        labels=["low", "moderate", "high", "critical"],
    ).astype(str)

    return out
