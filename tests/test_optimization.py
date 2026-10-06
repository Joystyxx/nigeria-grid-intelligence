"""Tests for the BESS optimisation layer.

Solves a small linear program and verifies the constraints hold.
"""

from grid_intelligence.optimization.bess_dispatch import ScenarioParams, solve


def test_full_mix_solves_and_meets_demand():
    p = ScenarioParams(
        name="test_full_mix",
        region="Test",
        demand_mw=[100.0] * 24,
        grid_available_mw=[60.0] * 24,
        bess_capacity_mwh=250.0,
        bess_power_mw=60.0,
        allow_grid=True,
        allow_diesel=True,
        allow_battery=True,
    )
    result = solve(p)
    assert result.solver_status == "Optimal", f"Solver returned {result.solver_status}"
    assert len(result.hourly) == 24
    for row in result.hourly:
        supplied = (
            row["grid_import_mw"]
            + row["diesel_gen_mw"]
            + row["discharge_mw"]
            - row["charge_mw"]
        )
        assert abs(supplied - row["demand_mw"]) < 0.01, (
            f"Demand not met at hour {row['hour']}: supplied={supplied}, demand={row['demand_mw']}"
        )


def test_battery_only_is_infeasible_when_demand_exceeds_power():
    p = ScenarioParams(
        name="test_battery_only",
        region="Test",
        demand_mw=[500.0] * 24,
        grid_available_mw=[0.0] * 24,
        bess_capacity_mwh=250.0,
        bess_power_mw=60.0,
        allow_grid=False,
        allow_diesel=False,
        allow_battery=True,
    )
    result = solve(p)
    assert result.solver_status == "Infeasible"
