"""Page 2 — Demand Forecast Accuracy by Region.

Reads dbt_dev_marts.fct_demand_accuracy. Shows which regions have the
worst forecast error, and what it means for grid planning.
"""
import pandas as pd
import plotly.express as px
import streamlit as st

from grid_intelligence.db import read_df
from grid_intelligence.theme import apply_theme

st.set_page_config(page_title="Demand Accuracy", page_icon="🎯", layout="wide")

apply_theme()

st.title("🎯 Demand Forecast Accuracy by Region")
st.caption(
    "Forecast error analysis across Nigerian regions. "
    "MAPE = Mean Absolute Percentage Error. Lower is better."
)


@st.cache_data(ttl=300)
def load_accuracy() -> pd.DataFrame:
    sql = """
        SELECT
            day_ts,
            region,
            num_readings,
            avg_actual_mw,
            avg_forecast_mw,
            bias_mw,
            mae_mw,
            mape_pct,
            max_abs_error_mw,
            mae_mw_7d_avg,
            worst_mae_rank,
            region_mae_rank
        FROM dbt_dev_marts.fct_demand_accuracy
        ORDER BY day_ts DESC
    """
    return read_df(sql)


df = load_accuracy()
df["day_ts"] = pd.to_datetime(df["day_ts"], utc=True)

# ---- Metric cards ----
st.subheader("Overall Forecast Performance")

region_stats = (
    df.groupby("region")
    .agg(
        avg_mape=("mape_pct", "mean"),
        avg_mae=("mae_mw", "mean"),
        days=("day_ts", "nunique"),
    )
    .reset_index()
    .sort_values("avg_mape")
)

col1, col2, col3, col4 = st.columns(4)
with col1:
    best = region_stats.iloc[0]
    st.metric("Best Region (MAPE)", f"{best['avg_mape']:.2f}%", help=best["region"])
with col2:
    worst = region_stats.iloc[-1]
    st.metric("Worst Region (MAPE)", f"{worst['avg_mape']:.2f}%", help=worst["region"])
with col3:
    overall = round(df["mape_pct"].mean(), 2)
    st.metric("Overall MAPE", f"{overall}%")
with col4:
    st.metric("Regions Tracked", region_stats.shape[0])

st.divider()

# ---- MAPE by region ----
st.subheader("Mean Absolute Percentage Error by Region")

fig = px.bar(
    region_stats,
    x="region",
    y="avg_mape",
    color="avg_mape",
    color_continuous_scale="Reds",
    labels={"avg_mape": "MAPE (%)", "region": "Region"},
    text="avg_mape",
)
fig.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
fig.update_layout(height=400, margin=dict(l=20, r=20, t=20, b=20), showlegend=False)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# ---- Actual vs Forecast over time ----
st.subheader("Actual vs Forecast Over Time")

regions = sorted(df["region"].unique())
selected = st.selectbox("Select region", regions, index=0)

subset = df[df["region"] == selected].sort_values("day_ts")

fig2 = px.line(
    subset,
    x="day_ts",
    y=["avg_actual_mw", "avg_forecast_mw"],
    labels={"value": "MW", "day_ts": "Date", "variable": "Series"},
    color_discrete_map={
        "avg_actual_mw": "#2c3e50",
        "avg_forecast_mw": "#e74c3c",
    },
)
fig2.update_layout(height=400, margin=dict(l=20, r=20, t=20, b=20))
st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ---- 7-day rolling MAE ----
st.subheader("7-Day Rolling MAE Trend")
st.caption("Shows whether forecast accuracy is improving or degrading over time.")

fig3 = px.line(
    df.sort_values("day_ts"),
    x="day_ts",
    y="mae_mw_7d_avg",
    color="region",
    labels={"mae_mw_7d_avg": "MAE (MW)", "day_ts": "Date"},
)
fig3.update_layout(height=400, margin=dict(l=20, r=20, t=20, b=20))
st.plotly_chart(fig3, use_container_width=True)

st.divider()

# ---- Worst days table ----
st.subheader("Top 10 Worst Forecast Days")

worst_days = (
    df.sort_values("mae_mw", ascending=False)
    .head(10)[["day_ts", "region", "avg_actual_mw", "avg_forecast_mw",
               "mae_mw", "mape_pct", "bias_mw"]]
)
worst_days["day_ts"] = worst_days["day_ts"].dt.strftime("%Y-%m-%d")
worst_days.columns = ["Date", "Region", "Actual (MW)", "Forecast (MW)",
                       "MAE (MW)", "MAPE (%)", "Bias (MW)"]
st.dataframe(worst_days, use_container_width=True, hide_index=True)

st.info(
    "**Why this matters:** Nigerian DisCos' forecast errors are a major driver "
    "of grid instability. Under-forecasting peak demand forces emergency load "
    "shedding; over-forecasting wastes generation capacity. Reducing MAPE by "
    "even 5 percentage points could materially reduce outages."
)

st.caption("Source: dbt_dev_marts.fct_demand_accuracy · HF electricsheepafrica")