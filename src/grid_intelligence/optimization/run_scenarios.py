"""Run BESS dispatch scenarios across regions AND deployment modes.

Matrix: 3 regions (Lagos, Kano, Abuja) x 4 modes:
    battery_only       — no grid, no diesel
    battery_diesel     — off-grid Nigerian mini-grid
    battery_grid       — grid-tied BESS
    full_mix           — grid + diesel + battery (all three)

Results written to ml.bess_optimization_results (summary)
and ml.bess_dispatch_hourly (per-hour schedule).
"""
from __future__ import annotations

import math

import pandas as pd

from grid_intelligence.db import write_df
from grid_intelligence.optimization.bess_dispatch import ScenarioParams, solve
from grid_intelligence.utils.logging import get_logger

log = get_logger(__name__)


def _load_profile(
    base_mw: float,
    morning_peak_mult: float,
    evening_peak_mult: float,
    jaggedness: float = 0.08,
) -> list[float]:
    """Nigerian two-peak load shape: ~08h morning + ~19h evening."""
    shape = []
    for h in range(24):
        morning = math.exp(-((h - 8) ** 2) / 6)
        evening = math.exp(-((h - 19) ** 2) / 6)
        jag = 1.0 + jaggedness * math.sin(h * 1.3)
        val = (
            base_mw
            * (0.55 + 0.55 * morning_peak_mult * morning + 0.85 * evening_peak_mult * evening)
            * jag
        )
        shape.append(round(val, 2))
    return shape


def _grid_availability(
    base_mw: float, mean_frac: float, variance_frac: float = 0.15
) -> list[float]:
    """Grid availability dips during peak hours."""
    out = []
    for h in range(24):
        dip = (
            0.15 * math.exp(-((h - 8) ** 2) / 4)
            + 0.20 * math.exp(-((h - 19) ** 2) / 4)
        )
        avail = base_mw * (mean_frac - dip)
        avail = max(base_mw * 0.05, avail + variance_frac * base_mw * math.sin(h * 0.9))
        out.append(round(avail, 2))
    return out


# Region base parameters
REGIONS = {
    "Lagos": {
        "demand_mw": _load_profile(180, 1.15, 1.35),
        "grid_available_mw": _grid_availability(180, 0.55),
        "bess_capacity_mwh": 250.0,
        "bess_power_mw": 60.0,
    },
    "Kano": {
        "demand_mw": _load_profile(90, 1.05, 1.25),
        "grid_available_mw": _grid_availability(90, 0.75),
        "bess_capacity_mwh": 120.0,
        "bess_power_mw": 30.0,
    },
    "Abuja": {
        "demand_mw": _load_profile(130, 1.10, 1.30),
        "grid_available_mw": _grid_availability(130, 0.65),
        "bess_capacity_mwh": 180.0,
        "bess_power_mw": 45.0,
    },
}

# Deployment modes: (allow_grid, allow_diesel, allow_battery)
MODES = {
    "battery_only":   (False, False, True),
    "battery_diesel": (False, True,  True),
    "battery_grid":   (True,  False, True),
    "full_mix":       (True,  True,  True),
}


def _build_matrix() -> dict[str, ScenarioParams]:
    """Generate the full scenarios dict from regions x modes."""
    scenarios = {}
    for region, params in REGIONS.items():
        for mode, (g, d, b) in MODES.items():
            name = f"{region.lower()}_{mode}"
            scenarios[name] = ScenarioParams(
                name=name,
                region=region,
                demand_mw=params["demand_mw"],
                grid_available_mw=params["grid_available_mw"],
                bess_capacity_mwh=params["bess_capacity_mwh"],
                bess_power_mw=params["bess_power_mw"],
                allow_grid=g,
                allow_diesel=d,
                allow_battery=b,
            )
    return scenarios


def _result_to_summary_row(r, mode: str) -> dict:
    return {
        "scenario_id": r.scenario,
        "region": r.region,
        "mode": mode,
        "total_cost_ngn": r.total_cost_ngn,
        "baseline_cost_ngn": r.baseline_cost_ngn,
        "savings_ngn": r.savings_ngn,
        "savings_pct": r.savings_pct,
        "emissions_kg": r.emissions_kg,
        "baseline_emissions_kg": r.baseline_emissions_kg,
        "emissions_saved_kg": r.emissions_saved_kg,
        "solver_status": r.solver_status,
    }


def _result_to_hourly_rows(r, mode: str) -> list[dict]:
    return [
        {"scenario_id": r.scenario, "region": r.region, "mode": mode, **row}
        for row in r.hourly
    ]


def run() -> None:
    scenarios = _build_matrix()
    summaries = []
    hourly_rows = []

    for name, params in scenarios.items():
        mode = name.split("_", 1)[1]
        log.info("run_scenarios: executing %s", name)
        result = solve(params)
        summaries.append(_result_to_summary_row(result, mode))
        hourly_rows.extend(_result_to_hourly_rows(result, mode))
        log.info(
            "run_scenarios: %s status=%s savings=%.0f NGN (%.2f%%) emissions_saved=%.0f kg",
            name,
            result.solver_status,
            result.savings_ngn,
            result.savings_pct,
            result.emissions_saved_kg,
        )

    summary_df = pd.DataFrame(summaries)
    hourly_df = pd.DataFrame(hourly_rows)

    n1 = write_df(summary_df, "ml", "bess_optimization_results")
    n2 = write_df(hourly_df, "ml", "bess_dispatch_hourly")
    log.info("run_scenarios: wrote %d summary rows, %d hourly rows", n1, n2)


if __name__ == "__main__":
    run()

    from grid_intelligence.db import read_df

    df = read_df(
        "SELECT scenario_id, mode, savings_ngn, savings_pct, "
        "emissions_saved_kg, solver_status "
        "FROM ml.bess_optimization_results "
        "ORDER BY region, mode"
    )
    print("\n=== Scenario Summary (12 scenarios) ===")
    print(df.to_string(index=False))