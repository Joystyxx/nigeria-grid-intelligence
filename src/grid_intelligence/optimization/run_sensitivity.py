"""Sensitivity analysis: diesel price x battery capacity x charging source.

Varies three dimensions across a grid to show how BESS investment value
responds to fuel economics, storage size, and charging source.

Dimensions:
  - Diesel price:    ₦500, ₦600, ₦800 per kWh    (3)
  - Battery size:    100, 250, 500 MWh           (3)
  - Charging source: grid_charge (₦225/kWh)      (2)
                     solar_charge (₦70/kWh)
Regions: Lagos, Kano, Abuja                      (3)

Total: 3 x 3 x 2 x 3 = 54 scenarios.
Writes to ml.bess_sensitivity.
"""
from __future__ import annotations

import math

import pandas as pd

from grid_intelligence.db import write_df
from grid_intelligence.optimization.bess_dispatch import ScenarioParams, solve
from grid_intelligence.optimization.run_scenarios import REGIONS
from grid_intelligence.utils.logging import get_logger

log = get_logger(__name__)

DIESEL_PRICES = [500.0, 600.0, 800.0]
BATTERY_CAPACITIES = [100.0, 250.0, 500.0]


def _solar_profile(peak_mw: float, hours: int = 24) -> list[float]:
    """Solar PV output: zero at night, sine-bell peak at noon."""
    out = []
    for h in range(hours):
        if h < 6 or h > 18:
            out.append(0.0)
        else:
            val = peak_mw * math.sin(math.pi * (h - 6) / 12)
            out.append(round(max(0.0, val), 2))
    return out


# Charging source configurations
CHARGING_SOURCES = {
    "grid_charge": {
        "allow_grid": True,
        "allow_solar": False,
    },
    "solar_charge": {
        "allow_grid": False,
        "allow_solar": True,
    },
}


def run() -> None:
    rows = []

    for region, base in REGIONS.items():
        peak_demand = max(base["demand_mw"])
        solar_peak = peak_demand * 1.5  # 1.5x peak demand PV capacity
        solar_profile = _solar_profile(solar_peak)

        for charging_name, toggles in CHARGING_SOURCES.items():
            for diesel_price in DIESEL_PRICES:
                for capacity in BATTERY_CAPACITIES:
                    power = capacity / 4.0  # 4-hour battery (C/4 rate)

                    p = ScenarioParams(
                        name=(
                            f"{region.lower()}_{charging_name}_"
                            f"d{int(diesel_price)}_c{int(capacity)}"
                        ),
                        region=region,
                        demand_mw=base["demand_mw"],
                        grid_available_mw=base["grid_available_mw"],
                        solar_available_mw=solar_profile,
                        diesel_price_ngn_per_kwh=diesel_price,
                        bess_capacity_mwh=capacity,
                        bess_power_mw=power,
                        allow_grid=toggles["allow_grid"],
                        allow_solar=toggles["allow_solar"],
                        allow_diesel=True,
                        allow_battery=True,
                    )

                    result = solve(p)

                    rows.append({
                        "region": region,
                        "charging_source": charging_name,
                        "diesel_price_ngn_per_kwh": diesel_price,
                        "battery_capacity_mwh": capacity,
                        "bess_power_mw": power,
                        "solar_peak_mw": solar_peak if toggles["allow_solar"] else 0.0,
                        "savings_ngn": result.savings_ngn,
                        "savings_pct": result.savings_pct,
                        "emissions_saved_kg": result.emissions_saved_kg,
                        "solver_status": result.solver_status,
                    })

                    log.info(
                        "sens: %s %s d=%.0f c=%.0fMWh -> %.0f NGN (%.2f%%) CO2=%.0fkg",
                        region,
                        charging_name,
                        diesel_price,
                        capacity,
                        result.savings_ngn,
                        result.savings_pct,
                        result.emissions_saved_kg,
                    )

    df = pd.DataFrame(rows)
    n = write_df(df, "ml", "bess_sensitivity")
    log.info("sensitivity: wrote %d rows to ml.bess_sensitivity", n)


if __name__ == "__main__":
    run()

    from grid_intelligence.db import read_df

    print("\n=== Savings % by charging source (averaged across regions) ===")
    df = read_df("""
        SELECT charging_source,
               diesel_price_ngn_per_kwh AS diesel,
               battery_capacity_mwh AS cap_mwh,
               ROUND(AVG(savings_pct)::numeric, 2) AS avg_savings_pct
        FROM ml.bess_sensitivity
        GROUP BY 1, 2, 3
        ORDER BY charging_source, diesel, cap_mwh
    """)
    print(df.to_string(index=False))

    print("\n=== Emissions saved (kg CO2/day) by charging source ===")
    df = read_df("""
        SELECT charging_source,
               ROUND(AVG(emissions_saved_kg)::numeric, 0) AS avg_co2_saved_kg
        FROM ml.bess_sensitivity
        GROUP BY 1
        ORDER BY charging_source
    """)
    print(df.to_string(index=False))
