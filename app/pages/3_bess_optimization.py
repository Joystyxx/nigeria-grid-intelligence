"""Page 3 — BESS Optimisation Results.

Reads ml.bess_optimization_results (12 scenarios),
ml.bess_dispatch_hourly (dispatch schedule),
and ml.bess_sensitivity (54-cell sensitivity matrix).
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from grid_intelligence.db import read_df
from grid_intelligence.theme import apply_theme

st.set_page_config(page_title="BESS Optimisation", page_icon="🔋", layout="wide")
apply_theme()

st.title("🔋 BESS Dispatch Optimisation")
st.caption(
    "Minimum-cost battery dispatch across Nigerian regions and deployment "
    "modes. Solved with PuLP 4.0 linear programming, 24-hour horizon."
)

# Deployment mode labels — components shown explicitly everywhere on the page.
MODE_LABELS = {
    "full_mix": "Full mix (Grid + Diesel + Battery)",
    "battery_grid": "Battery + Grid (no diesel)",
    "battery_diesel": "Battery + Diesel (off-grid)",
    "battery_only": "Battery only",
}


@st.cache_data(ttl=300)
def load_summary() -> pd.DataFrame:
    sql = """
        SELECT scenario_id, region, mode,
               total_cost_ngn, baseline_cost_ngn, savings_ngn, savings_pct,
               emissions_kg, baseline_emissions_kg, emissions_saved_kg,
               solver_status
        FROM ml.bess_optimization_results
        ORDER BY region, mode
    """
    return read_df(sql)


@st.cache_data(ttl=300)
def load_hourly() -> pd.DataFrame:
    sql = """
        SELECT scenario_id, region, mode, hour, demand_mw,
               grid_import_mw, solar_gen_mw, diesel_gen_mw,
               charge_mw, discharge_mw, soc_mwh
        FROM ml.bess_dispatch_hourly
        ORDER BY scenario_id, hour
    """
    return read_df(sql)


@st.cache_data(ttl=300)
def load_sensitivity() -> pd.DataFrame:
    sql = """
        SELECT region, charging_source, diesel_price_ngn_per_kwh,
               battery_capacity_mwh, bess_power_mw,
               savings_ngn, savings_pct, emissions_saved_kg, solver_status
        FROM ml.bess_sensitivity
        ORDER BY region, charging_source, diesel_price_ngn_per_kwh, battery_capacity_mwh
    """
    return read_df(sql)


summary = load_summary()
hourly = load_hourly()
sensitivity = load_sensitivity()

# ---- Metric cards ----
st.subheader("Headline Results")

feasible = summary[summary["solver_status"] == "Optimal"]
best = feasible.loc[feasible["savings_ngn"].idxmax()]

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Scenarios Ran", len(summary), help="3 regions x 4 deployment modes")
with col2:
    st.metric("Feasible", len(feasible), help="Modes where LP found a solution")
with col3:
    st.metric(
        "Best Savings (₦/day)",
        f"₦{best['savings_ngn']:,.0f}",
        help=f"{best['region']} — {MODE_LABELS.get(best['mode'], best['mode'])}",
    )
with col4:
    max_co2 = feasible["emissions_saved_kg"].max()
    st.metric("Best CO₂ Saved (kg/day)", f"{max_co2:,.0f}")

st.divider()

# ---- Deployment modes explanation ----
with st.expander("What do the deployment modes mean?", expanded=True):
    st.markdown(
        """
        - **Full mix (Grid + Diesel + Battery)** — `full_mix`. Realistic hybrid
          for a grid-tied substation with a battery and diesel backup. This is
          the deployment pattern the model endorses.
        - **Battery + Grid (no diesel)** — `battery_grid`. Feasible only when
          grid availability covers peak demand. Infeasible at realistic Nigerian
          demand because grid drops during peak hours.
        - **Battery + Diesel (off-grid)** — `battery_diesel`. Off-grid mini-grid
          without grid connection. Feasible but not economical — charging the
          battery from diesel loses 10% in round-trip efficiency, so the LP
          correctly refuses to use the battery.
        - **Battery only** — `battery_only`. Battery as sole source. Infeasible:
          peak demand exceeds battery power rating.

        **Reading the charts:** Only the **Full mix** appears in savings charts —
        the other three are either infeasible (no solution) or economically zero
        (LP chooses not to use the battery). This is itself the finding:
        **batteries only pay off when grid and diesel coexist as complementary
        sources.**
        """
    )

st.divider()

# ---- Scenario comparison ----
st.subheader("Scenario Comparison — Savings by Region and Mode")

if not feasible.empty:
    plot_df = feasible.copy()
    plot_df["mode_label"] = plot_df["mode"].map(MODE_LABELS).fillna(plot_df["mode"])

    fig = px.bar(
        plot_df,
        x="region",
        y="savings_pct",
        color="mode_label",
        barmode="group",
        labels={
            "savings_pct": "Savings (%)",
            "region": "Region",
            "mode_label": "Deployment mode",
        },
    )
    fig.update_layout(height=400, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig, use_container_width=True)

    # Table with clear mode labels
    display = feasible[["region", "mode", "savings_ngn", "savings_pct",
                        "emissions_saved_kg", "solver_status"]].copy()
    display["mode"] = display["mode"].map(MODE_LABELS).fillna(display["mode"])
    display.columns = ["Region", "Deployment mode", "Savings (₦)", "Savings (%)",
                       "CO₂ Saved (kg)", "Status"]
    st.dataframe(display, use_container_width=True, hide_index=True)

st.divider()

# ---- Hourly dispatch for one scenario ----
st.subheader("Hourly Dispatch Schedule")

# Build readable selectbox labels — keep full scenario_id mapping intact
hourly_scenarios = sorted(hourly["scenario_id"].unique())
hourly["scenario_label"] = (
    hourly["region"] + " — " + hourly["mode"].map(MODE_LABELS).fillna(hourly["mode"])
)

scenario_labels = (
    hourly[["scenario_id", "scenario_label"]]
    .drop_duplicates()
    .sort_values("scenario_label")
)

selected_label = st.selectbox(
    "Select scenario",
    scenario_labels["scenario_label"].tolist(),
    index=0,
)
selected = scenario_labels.loc[
    scenario_labels["scenario_label"] == selected_label, "scenario_id"
].iloc[0]

sched = hourly[hourly["scenario_id"] == selected].sort_values("hour")

fig2 = go.Figure()
fig2.add_trace(go.Bar(x=sched["hour"], y=sched["grid_import_mw"], name="Grid import", marker_color="#3498db"))
fig2.add_trace(go.Bar(x=sched["hour"], y=sched["diesel_gen_mw"], name="Diesel generation", marker_color="#e74c3c"))
fig2.add_trace(go.Bar(x=sched["hour"], y=sched["discharge_mw"], name="Battery discharge", marker_color="#2ecc71"))
fig2.add_trace(go.Bar(x=sched["hour"], y=-sched["charge_mw"], name="Battery charge", marker_color="#f39c12"))
fig2.add_trace(go.Scatter(
    x=sched["hour"], y=sched["demand_mw"], name="Demand", mode="lines+markers",
    line=dict(color="#2c3e50", width=3),
))
fig2.update_layout(
    barmode="relative",
    xaxis_title="Hour of day",
    yaxis_title="Power (MW)",
    height=400,
    margin=dict(l=20, r=20, t=20, b=20),
    hovermode="x unified",
)
st.plotly_chart(fig2, use_container_width=True)

# SoC trajectory
fig3 = px.line(
    sched,
    x="hour",
    y="soc_mwh",
    labels={"soc_mwh": "Battery state of charge (MWh)", "hour": "Hour of day"},
    markers=True,
)
fig3.update_layout(height=300, margin=dict(l=20, r=20, t=20, b=20))
st.plotly_chart(fig3, use_container_width=True)

st.divider()

# ---- Sensitivity heatmap ----
st.subheader("Sensitivity: Diesel Price × Battery Capacity × Charging Source")
st.caption(
    "54-cell matrix showing how savings respond to fuel economics and "
    "storage size, under grid charging vs solar charging."
)

source = st.radio(
    "Charging source",
    sorted(sensitivity["charging_source"].unique()),
    horizontal=True,
)

region_choice = st.selectbox("Region", sorted(sensitivity["region"].unique()), index=0)

subset = sensitivity[
    (sensitivity["charging_source"] == source) & (sensitivity["region"] == region_choice)
]

if not subset.empty:
    pivot = subset.pivot_table(
        index="diesel_price_ngn_per_kwh",
        columns="battery_capacity_mwh",
        values="savings_pct",
        aggfunc="mean",
    )
    fig4 = px.imshow(
        pivot,
        text_auto=".2f",
        color_continuous_scale="Greens",
        labels={
            "x": "Battery capacity (MWh)",
            "y": "Diesel price (₦/kWh)",
            "color": "Savings %",
        },
    )
    fig4.update_layout(height=350, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig4, use_container_width=True)

st.info(
    "**Key finding:** Solar charging delivers 2-3x the savings of grid charging "
    "at the same diesel price. As diesel prices rise and battery capacity grows, "
    "savings scale super-linearly — reinforcing the investment case for "
    "solar + storage deployments in Nigeria."
)

st.caption("Model: PuLP 4.0 with CBC solver · Prices: config/energy_prices.yaml (2026 Nigerian market)")