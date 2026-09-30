"""Synthetic fallback generators for Nigerian grid data.

Guarantees the pipeline never blocks on an unavailable data source.
All generators are deterministic (fixed seed) so re-runs are reproducible.

Nigerian realism baked in:
- 6 DisCos: Ikeja, Eko, Abuja, Kano, Port Harcourt, Enugu
- Two daily load peaks (~08:00 and ~19:00 local time)
- Weekday/weekend variation
- Frequency nominal 50 Hz with realistic deviation
- Voltage nominal 33 kV (transmission) / 11 kV (distribution)
- Outage causes weighted by Nigerian grid realities
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from grid_intelligence.utils.logging import get_logger

log = get_logger(__name__)

SEED = 42
DAYS = 30
INTERVAL_MINUTES = 15

DISCOS = {
    "Ikeja": {"substations": ["IKJ-01", "IKJ-02", "IKJ-03"], "base_load_mw": 850, "peak_factor": 1.35},
    "Eko": {"substations": ["EKO-01", "EKO-02", "EKO-03"], "base_load_mw": 780, "peak_factor": 1.30},
    "Abuja": {"substations": ["ABJ-01", "ABJ-02"], "base_load_mw": 620, "peak_factor": 1.25},
    "Kano": {"substations": ["KAN-01", "KAN-02"], "base_load_mw": 540, "peak_factor": 1.20},
    "Port Harcourt": {"substations": ["PHC-01", "PHC-02"], "base_load_mw": 480, "peak_factor": 1.22},
    "Enugu": {"substations": ["ENU-01", "ENU-02"], "base_load_mw": 410, "peak_factor": 1.18},
}

OUTAGE_CAUSES = [
    ("transmission_fault", 0.35),
    ("gas_shortage", 0.25),
    ("load_shedding", 0.20),
    ("equipment_failure", 0.12),
    ("weather", 0.08),
]


def _time_index() -> pd.DatetimeIndex:
    """15-minute UTC timestamps for the last DAYS days."""
    end = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    start = end - timedelta(days=DAYS)
    return pd.date_range(start=start, end=end, freq=f"{INTERVAL_MINUTES}min", tz="UTC")


def _daily_shape(idx: pd.DatetimeIndex) -> np.ndarray:
    """Return a multiplicative load shape with Nigerian two-peak profile.

    Peak 1: ~08:00 local (UTC+1) -> hour 7 UTC
    Peak 2: ~19:00 local (UTC+1) -> hour 18 UTC
    Weekend loads are ~15% lower.
    """
    hours = idx.hour + idx.minute / 60.0
    morning = np.exp(-((hours - 7) ** 2) / (2 * 1.5**2))
    evening = np.exp(-((hours - 18) ** 2) / (2 * 1.8**2))
    base = 0.55
    shape = base + 0.55 * morning + 0.85 * evening

    is_weekend = idx.dayofweek >= 5
    shape = shape * np.where(is_weekend, 0.85, 1.0)

    # Seasonal (harmonics over the 30-day window)
    day_of_year = idx.dayofyear.values
    seasonal = 1.0 + 0.06 * np.sin(2 * np.pi * day_of_year / 365.0)
    return shape * seasonal


def generate_grid_load() -> pd.DataFrame:
    """Per-substation load MW time series with realistic daily shape."""
    rng = np.random.default_rng(SEED)
    idx = _time_index()
    shape = _daily_shape(idx)

    rows = []
    for disco, cfg in DISCOS.items():
        for sub in cfg["substations"]:
            base = cfg["base_load_mw"] / len(cfg["substations"])
            noise = rng.normal(0, 0.04, len(idx))
            load = base * shape * (1 + noise) * cfg["peak_factor"]
            # Occasional dropouts (grid instability)
            dropouts = rng.random(len(idx)) < 0.005
            load = np.where(dropouts, load * 0.15, load)

            rows.append(
                pd.DataFrame(
                    {
                        "timestamp_utc": idx,
                        "disco": disco,
                        "substation_id": sub,
                        "load_mw": np.clip(load, 0, None).round(2),
                        "capacity_mw": round(base * 1.6, 2),
                    }
                )
            )
    df = pd.concat(rows, ignore_index=True)
    log.info("synthetic grid_load: %d rows", len(df))
    return df


def generate_demand_forecast() -> pd.DataFrame:
    """Per-DisCo actual vs forecast demand at hourly resolution."""
    rng = np.random.default_rng(SEED + 1)
    idx = _time_index()
    # Aggregate hourly
    hourly = idx.floor("h").unique()

    rows = []
    for disco, cfg in DISCOS.items():
        base = cfg["base_load_mw"]
        shape = _daily_shape(pd.DatetimeIndex(hourly))
        actual = base * shape * (1 + rng.normal(0, 0.05, len(hourly)))
        # Forecast has systematic + random error (Nigerian DisCos typically under-forecast peak)
        forecast = actual * (1 + rng.normal(-0.03, 0.08, len(hourly)))

        rows.append(
            pd.DataFrame(
                {
                    "timestamp_utc": hourly,
                    "disco": disco,
                    "actual_mw": np.clip(actual, 0, None).round(2),
                    "forecast_mw": np.clip(forecast, 0, None).round(2),
                }
            )
        )
    df = pd.concat(rows, ignore_index=True)
    log.info("synthetic demand_forecast: %d rows", len(df))
    return df


def generate_smart_grid_iot() -> pd.DataFrame:
    """5-minute substation telemetry: voltage, frequency, current, temperature."""
    rng = np.random.default_rng(SEED + 2)
    end = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    start = end - timedelta(days=7)
    idx = pd.date_range(start=start, end=end, freq="5min", tz="UTC")

    rows = []
    for disco, cfg in DISCOS.items():
        for sub in cfg["substations"]:
            n = len(idx)
            voltage = 33.0 + rng.normal(0, 0.6, n) - 0.4 * (rng.random(n) < 0.02)
            frequency = 50.0 + rng.normal(0, 0.08, n)
            frequency = np.where(rng.random(n) < 0.01, frequency - 0.5, frequency)
            current = 210 + rng.normal(0, 15, n)
            temperature = 42 + rng.normal(0, 3, n) + (current - 210) * 0.1

            rows.append(
                pd.DataFrame(
                    {
                        "timestamp_utc": idx,
                        "disco": disco,
                        "substation_id": sub,
                        "voltage_kv": voltage.round(3),
                        "frequency_hz": frequency.round(3),
                        "current_a": current.round(2),
                        "temperature_c": temperature.round(2),
                    }
                )
            )
    df = pd.concat(rows, ignore_index=True)
    log.info("synthetic smart_grid_iot: %d rows", len(df))
    return df


def generate_outage_logs() -> pd.DataFrame:
    """Outage events with realistic Nigerian causes and durations."""
    rng = np.random.default_rng(SEED + 3)
    idx = _time_index()
    end = idx.max()
    start = idx.min()

    causes, weights = zip(*OUTAGE_CAUSES)
    weights = np.array(weights) / sum(weights)

    n_events = 220
    rows = []
    for i in range(n_events):
        disco = rng.choice(list(DISCOS.keys()))
        sub = rng.choice(DISCOS[disco]["substations"])
        started = start + pd.Timedelta(
            seconds=int(rng.uniform(0, (end - start).total_seconds()))
        )
        duration_min = float(rng.gamma(shape=2.0, scale=45.0))  # heavy tail
        duration_min = float(np.clip(duration_min, 5, 720))
        cause = rng.choice(causes, p=weights)

        rows.append(
            {
                "outage_id": f"OUT-{i:05d}",
                "started_at_utc": started,
                "ended_at_utc": started + pd.Timedelta(minutes=duration_min),
                "duration_minutes": round(duration_min, 2),
                "disco": disco,
                "substation_id": sub,
                "cause": cause,
                "customers_affected": int(rng.integers(500, 25000)),
            }
        )
    df = pd.DataFrame(rows).sort_values("started_at_utc").reset_index(drop=True)
    log.info("synthetic outage_logs: %d rows", len(df))
    return df


def generate_ai_optimization() -> pd.DataFrame:
    """Pre-computed BESS dispatch scenarios for 3 Nigerian use cases.

    These are placeholder optimisation outputs — Day 4 replaces them
    with real PuLP-computed values written to ml.bess_optimization_results.
    """
    rng = np.random.default_rng(SEED + 4)
    scenarios = [
        ("A_lagos_commercial", "Lagos", 24, 180.0, 400.0),
        ("B_kano_residential", "Kano", 24, 90.0, 250.0),
        ("C_abuja_mixed", "Abuja", 24, 130.0, 320.0),
    ]
    rows = []
    for scenario_id, region, hours, demand_mw, bess_mwh in scenarios:
        for h in range(hours):
            rows.append(
                {
                    "scenario_id": scenario_id,
                    "region": region,
                    "hour_of_day": h,
                    "demand_mw": round(demand_mw * (1 + rng.normal(0, 0.08)), 2),
                    "grid_available_mw": round(demand_mw * rng.uniform(0.55, 0.95), 2),
                    "bess_capacity_mwh": bess_mwh,
                    "diesel_cost_ngn_per_kwh": 450.0,
                    "grid_cost_ngn_per_kwh": 225.0,
                }
            )
    df = pd.DataFrame(rows)
    log.info("synthetic ai_optimization: %d rows", len(df))
    return df


def main() -> None:
    """Generate all synthetic datasets and report row counts."""
    generators = {
        "grid_load": generate_grid_load,
        "demand_forecast": generate_demand_forecast,
        "smart_grid_iot": generate_smart_grid_iot,
        "outage_logs": generate_outage_logs,
        "ai_optimization": generate_ai_optimization,
    }
    for name, fn in generators.items():
        df = fn()
        print(f"{name:20s} rows={len(df):>8d}  cols={list(df.columns)}")


if __name__ == "__main__":
    main()