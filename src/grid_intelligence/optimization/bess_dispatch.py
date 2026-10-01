"""BESS dispatch optimisation using PuLP 4.0.

Given a 24-hour demand profile and a battery, find the minimum-cost
schedule of grid import, solar generation, diesel generation, battery
charge, and battery discharge.

Components (all togglable):
    grid    — Nigeria DisCo supply at Band A tariff
    solar   — PV generation at Nigerian LCOE (~₦70/kWh)
    diesel  — fully-loaded generator cost (~₦600/kWh)
    battery — storage

Deployment modes model real Nigerian contexts:
    urban_grid_tied   (grid + diesel + battery)
    rural_off_grid    (solar + diesel + battery)
    battery_only      (infeasible at city scale)

Prices loaded from config/energy_prices.yaml.

PuLP 4.0 API notes:
  - LpVariable.dicts()     -> prob.add_variable_dicts()
  - prob.solve() returns   -> LpSolveStats
  - PULP_CBC_CMD           -> COIN_CMD (with pulp[cbc])
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pulp import (
    COIN_CMD,
    LpMinimize,
    LpProblem,
    LpSolveStatus,
    lpSum,
    value,
)

from grid_intelligence.config import PROJECT_ROOT
from grid_intelligence.utils.logging import get_logger

log = get_logger(__name__)

_PRICE_PATH: Path = PROJECT_ROOT / "config" / "energy_prices.yaml"
if _PRICE_PATH.exists():
    with open(_PRICE_PATH) as f:
        _PRICES = yaml.safe_load(f)
    log.info(
        "bess: loaded prices from %s (verified %s)",
        _PRICE_PATH.name,
        _PRICES.get("metadata", {}).get("last_verified", "unknown"),
    )
else:
    log.warning("bess: energy_prices.yaml not found, using built-in defaults")
    _PRICES = None


def _price(section: str, key: str, default: float) -> float:
    if _PRICES is None:
        return default
    try:
        return float(_PRICES[section][key])
    except (KeyError, TypeError):
        return default


@dataclass
class ScenarioParams:
    """All inputs for one BESS dispatch scenario."""

    name: str
    region: str
    demand_mw: list[float]
    grid_available_mw: list[float]

    grid_price_ngn_per_kwh: float = field(
        default_factory=lambda: _price("grid", "band_a_ngn_per_kwh", 225.0)
    )
    diesel_price_ngn_per_kwh: float = field(
        default_factory=lambda: _price("diesel", "generation_cost_ngn_per_kwh", 600.0)
    )
    diesel_emission_kg_per_kwh: float = field(
        default_factory=lambda: _price("diesel", "emission_kg_co2_per_kwh", 0.72)
    )
    grid_emission_kg_per_kwh: float = field(
        default_factory=lambda: _price("grid", "emission_kg_co2_per_kwh", 0.35)
    )

    # Solar — defaults to zero availability; caller sets profile when used
    solar_available_mw: list[float] = field(default_factory=lambda: [0.0] * 24)
    solar_price_ngn_per_kwh: float = field(
        default_factory=lambda: _price("solar", "lcoe_ngn_per_kwh", 70.0)
    )

    bess_capacity_mwh: float = 250.0
    bess_power_mw: float = 60.0
    bess_efficiency: float = 0.90
    soc_min_frac: float = 0.10
    soc_max_frac: float = 0.90
    soc_initial_frac: float = 0.50

    # Component toggles
    allow_grid: bool = True
    allow_solar: bool = False
    allow_diesel: bool = True
    allow_battery: bool = True

    hours: int = field(default=24)

    @property
    def soc_min(self) -> float:
        return self.bess_capacity_mwh * self.soc_min_frac

    @property
    def soc_max(self) -> float:
        return self.bess_capacity_mwh * self.soc_max_frac

    @property
    def soc_initial(self) -> float:
        return self.bess_capacity_mwh * self.soc_initial_frac


@dataclass
class DispatchResult:
    """Optimal schedule and KPIs for one scenario."""

    scenario: str
    region: str
    hourly: list[dict]
    total_cost_ngn: float
    baseline_cost_ngn: float
    savings_ngn: float
    savings_pct: float
    emissions_kg: float
    baseline_emissions_kg: float
    emissions_saved_kg: float
    solver_status: str


def _build_problem(p: ScenarioParams):
    """Construct the LP under PuLP 4.0 API with full component toggles."""
    m = LpProblem(f"bess_{p.name}", LpMinimize)
    T = list(range(p.hours))

    charge = m.add_variable_dicts("charge", T, lowBound=0, upBound=p.bess_power_mw)
    discharge = m.add_variable_dicts("discharge", T, lowBound=0, upBound=p.bess_power_mw)
    grid_import = m.add_variable_dicts("grid", T, lowBound=0)
    solar_gen = m.add_variable_dicts("solar", T, lowBound=0)
    diesel_gen = m.add_variable_dicts("diesel", T, lowBound=0)
    soc = m.add_variable_dicts("soc", T, lowBound=p.soc_min, upBound=p.soc_max)

    # Objective: minimise grid + solar + diesel operating cost
    m += lpSum(
        p.grid_price_ngn_per_kwh * grid_import[t] * 1000
        + p.solar_price_ngn_per_kwh * solar_gen[t] * 1000
        + p.diesel_price_ngn_per_kwh * diesel_gen[t] * 1000
        for t in T
    )

    # Demand balance
    for t in T:
        m += (
            grid_import[t] + solar_gen[t] + diesel_gen[t] + discharge[t] - charge[t]
            == p.demand_mw[t]
        )

    # Component constraints
    for t in T:
        if p.allow_grid:
            m += grid_import[t] <= p.grid_available_mw[t]
        else:
            m += grid_import[t] == 0

        if p.allow_solar:
            m += solar_gen[t] <= p.solar_available_mw[t]
        else:
            m += solar_gen[t] == 0

        if not p.allow_diesel:
            m += diesel_gen[t] == 0

    if p.allow_battery:
        for t in T:
            if t == 0:
                m += (
                    soc[t]
                    == p.soc_initial
                    + charge[t] * p.bess_efficiency
                    - discharge[t] / p.bess_efficiency
                )
            else:
                soc_t = soc[t - 1]
                m += (
                    soc[t]
                    == soc_t
                    + charge[t] * p.bess_efficiency
                    - discharge[t] / p.bess_efficiency
                )
        m += soc[p.hours - 1] >= p.soc_initial
    else:
        for t in T:
            m += charge[t] == 0
            m += discharge[t] == 0

    return m, {
        "charge": charge,
        "discharge": discharge,
        "grid_import": grid_import,
        "solar_gen": solar_gen,
        "diesel_gen": diesel_gen,
        "soc": soc,
    }


def _baseline(p: ScenarioParams) -> tuple[float, float]:
    """Same components minus battery. Returns (cost, emissions)."""
    total_cost = 0.0
    total_emissions = 0.0
    for t in range(p.hours):
        remaining = p.demand_mw[t]
        grid_used = 0.0
        solar_used = 0.0
        diesel_used = 0.0

        if p.allow_solar:
            solar_used = min(p.solar_available_mw[t], remaining)
            remaining -= solar_used

        if p.allow_grid:
            grid_used = min(p.grid_available_mw[t], remaining)
            remaining -= grid_used

        if p.allow_diesel and remaining > 0:
            diesel_used = remaining

        total_cost += (
            p.grid_price_ngn_per_kwh * grid_used * 1000
            + p.solar_price_ngn_per_kwh * solar_used * 1000
            + p.diesel_price_ngn_per_kwh * diesel_used * 1000
        )
        total_emissions += (
            p.grid_emission_kg_per_kwh * grid_used * 1000
            + p.diesel_emission_kg_per_kwh * diesel_used * 1000
        )
    return total_cost, total_emissions


def solve(p: ScenarioParams) -> DispatchResult:
    """Solve the LP for one scenario and return the optimal schedule."""
    log.info("bess: solving scenario=%s region=%s", p.name, p.region)
    prob, v = _build_problem(p)
    stats = prob.solve(COIN_CMD(msg=False))
    status = stats.status_str

    if status in ("Undefined", "Infeasible"):
        status = "Infeasible"
        log.info("bess: scenario %s is INFEASIBLE", p.name)
        return DispatchResult(
            scenario=p.name,
            region=p.region,
            hourly=[],
            total_cost_ngn=0.0,
            baseline_cost_ngn=0.0,
            savings_ngn=0.0,
            savings_pct=0.0,
            emissions_kg=0.0,
            baseline_emissions_kg=0.0,
            emissions_saved_kg=0.0,
            solver_status=status,
        )

    hourly = []
    for t in range(p.hours):
        hourly.append(
            {
                "hour": t,
                "demand_mw": round(p.demand_mw[t], 3),
                "grid_import_mw": round(v["grid_import"][t].value() or 0, 3),
                "solar_gen_mw": round(v["solar_gen"][t].value() or 0, 3),
                "diesel_gen_mw": round(v["diesel_gen"][t].value() or 0, 3),
                "charge_mw": round(v["charge"][t].value() or 0, 3),
                "discharge_mw": round(v["discharge"][t].value() or 0, 3),
                "soc_mwh": round(v["soc"][t].value() or 0, 3),
            }
        )

    total_cost = float(stats.objective or value(prob.objective) or 0.0)

    emissions = sum(
        p.grid_emission_kg_per_kwh * row["grid_import_mw"] * 1000
        + p.diesel_emission_kg_per_kwh * row["diesel_gen_mw"] * 1000
        for row in hourly
    )

    baseline_cost, baseline_emissions = _baseline(p)

    savings = baseline_cost - total_cost
    savings_pct = (savings / baseline_cost * 100) if baseline_cost > 0 else 0.0

    return DispatchResult(
        scenario=p.name,
        region=p.region,
        hourly=hourly,
        total_cost_ngn=round(total_cost, 2),
        baseline_cost_ngn=round(baseline_cost, 2),
        savings_ngn=round(savings, 2),
        savings_pct=round(savings_pct, 2),
        emissions_kg=round(emissions, 2),
        baseline_emissions_kg=round(baseline_emissions, 2),
        emissions_saved_kg=round(baseline_emissions - emissions, 2),
        solver_status=status,
    )