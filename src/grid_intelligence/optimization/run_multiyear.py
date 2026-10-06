"""Multi-year BESS economics comparison.

Runs the same power system (Lagos, Kano, Abuja) under 2024, 2025, and
2026 Nigerian prices to show how renewable economics evolve.

Reads historical prices from config/energy_prices.yaml, writes results
to ml.bess_multiyear.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from grid_intelligence.config import PROJECT_ROOT
from grid_intelligence.db import write_df
from grid_intelligence.optimization.bess_dispatch import ScenarioParams, solve
from grid_intelligence.optimization.run_scenarios import REGIONS
from grid_intelligence.utils.logging import get_logger

log = get_logger(__name__)

PRICE_PATH: Path = PROJECT_ROOT / "config" / "energy_prices.yaml"
with open(PRICE_PATH) as f:
    PRICES = yaml.safe_load(f)

HISTORICAL = PRICES["historical"]


def run() -> None:
    rows = []

    for year_key, prices in HISTORICAL.items():
        year = year_key.replace("y", "")

        for region in ["Lagos", "Kano", "Abuja"]:
            base = REGIONS[region]

            p = ScenarioParams(
                name=f"{region.lower()}_{year}_full_mix",
                region=region,
                demand_mw=base["demand_mw"],
                grid_available_mw=base["grid_available_mw"],
                grid_price_ngn_per_kwh=prices["grid_band_a_ngn_per_kwh"],
                diesel_price_ngn_per_kwh=prices["diesel_generation_ngn_per_kwh"],
                solar_price_ngn_per_kwh=prices["solar_lcoe_ngn_per_kwh"],
                bess_capacity_mwh=base["bess_capacity_mwh"],
                bess_power_mw=base["bess_power_mw"],
                allow_grid=True,
                allow_diesel=True,
                allow_battery=True,
            )
            result = solve(p)

            rows.append({
                "year": year,
                "region": region,
                "grid_price": prices["grid_band_a_ngn_per_kwh"],
                "diesel_price": prices["diesel_generation_ngn_per_kwh"],
                "solar_price": prices["solar_lcoe_ngn_per_kwh"],
                "savings_ngn": result.savings_ngn,
                "savings_pct": result.savings_pct,
                "emissions_saved_kg": result.emissions_saved_kg,
                "solver_status": result.solver_status,
            })

            log.info(
                "multiyear: %s %s -> savings=%.0f NGN (%.2f%%) CO2=%.0fkg",
                year,
                region,
                result.savings_ngn,
                result.savings_pct,
                result.emissions_saved_kg,
            )

    df = pd.DataFrame(rows)
    n = write_df(df, "ml", "bess_multiyear")
    log.info("multiyear: wrote %d rows to ml.bess_multiyear", n)


if __name__ == "__main__":
    run()

    from grid_intelligence.db import read_df

    df = read_df("""
        SELECT year, region,
               grid_price, diesel_price, solar_price,
               ROUND(savings_pct::numeric, 2) AS savings_pct,
               ROUND(emissions_saved_kg::numeric, 0) AS co2_saved_kg
        FROM ml.bess_multiyear
        ORDER BY year, region
    """)
    print("\n=== Multi-Year BESS Economics ===")
    print(df.to_string(index=False))
