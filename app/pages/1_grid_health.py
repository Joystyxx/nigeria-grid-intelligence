"""Page 1 — Grid Health.

Live grid load, outage patterns, and composite stress scores.
Reads from fct_grid_events (dbt mart) and ml.grid_instability_predictions.
"""
import pandas as pd
import plotly.express as px
import streamlit as st

from grid_intelligence.db import read_df
from grid_intelligence.theme import apply_theme

st.set_page_config(page_title="Grid Health", page_icon="🔌", layout="wide")

apply_theme()

st.title("🔌 Grid Health")
st.caption(
    "Live grid load, outage patterns, and composite stress scores "
    "across Nigeria's monitored substations."
)


@st.cache_data(ttl=300)
def load_recent_events(days: int = 7) -> pd.DataFrame:
    sql = f"""
        SELECT
            event_ts,
            disco,
            substation_id,
            avg_load_mw,
            peak_load_mw,
            avg_frequency_hz,
            avg_freq_dev_hz,
            outage_count_this_hour,
            had_severe_outage
        FROM dbt_dev_marts.fct_grid_events
        WHERE event_ts >= (SELECT MAX(event_ts) FROM dbt_dev_marts.fct_grid_events)
                        - INTERVAL '{days} days'
        ORDER BY event_ts
    """
    return read_df(sql)


@st.cache_data(ttl=300)
def load_predictions() -> pd.DataFrame:
    sql = """
        SELECT
            predicted_at,
            event_ts,
            disco,
            substation_id,
            outage_probability,
            load_spike_probability,
            stress_score,
            stress_tier
        FROM ml.grid_instability_predictions
        ORDER BY event_ts DESC
    """
    return read_df(sql)


@st.cache_data(ttl=300)
def load_latest_substations() -> pd.DataFrame:
    """Latest stress reading per substation."""
    sql = """
        WITH ranked AS (
            SELECT
                substation_id,
                disco,
                event_ts,
                stress_score,
                stress_tier,
                outage_probability,
                load_spike_probability,
                ROW_NUMBER() OVER (
                    PARTITION BY substation_id ORDER BY event_ts DESC
                ) AS rn
            FROM ml.grid_instability_predictions
        )
        SELECT * FROM ranked WHERE rn = 1
    """
    return read_df(sql)


@st.cache_data(ttl=300)
def load_substation_coords() -> pd.DataFrame:
    sql = """
        SELECT substation_id, disco, latitude, longitude, voltage_class
        FROM dbt_dev_marts.dim_substation
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    """
    return read_df(sql)


# ---- Load data ----
try:
    events = load_recent_events(7)
    predictions = load_predictions()
    substations = load_latest_substations()
except Exception as e:
    st.error(f"Failed to load data from warehouse: {e}")
    st.stop()

# ---- Metric cards ----
st.subheader("Current Snapshot")

m1, m2, m3, m4 = st.columns(4)
with m1:
    avg_stress = round(substations["stress_score"].mean(), 1)
    st.metric(
        "Avg Stress Score",
        f"{avg_stress}",
        help="0-100 composite across all substations",
    )
with m2:
    high_stress = int((substations["stress_tier"] == "high").sum())
    critical = int((substations["stress_tier"] == "critical").sum())
    st.metric(
        "High / Critical",
        f"{high_stress} / {critical}",
        help="Substations above moderate tier",
    )
with m3:
    recent_outages = int(events["had_severe_outage"].sum())
    st.metric(
        "Severe Outage Hours",
        f"{recent_outages}",
        help="Last 7 days, >1000 customers affected",
    )
with m4:
    total_substations = substations["substation_id"].nunique()
    st.metric("Substations Monitored", f"{total_substations}")

st.divider()

# ---- 7-day load chart ----
st.subheader("Grid Load — Last 7 Days")

events["event_ts"] = pd.to_datetime(events["event_ts"], utc=True)
hourly = (
    events.groupby("event_ts")
    .agg(total_load_mw=("avg_load_mw", "sum"))
    .reset_index()
)

fig = px.line(
    hourly,
    x="event_ts",
    y="total_load_mw",
    labels={"event_ts": "Time (UTC)", "total_load_mw": "Total Load (MW)"},
)
fig.update_layout(height=350, margin=dict(l=20, r=20, t=20, b=20))
st.plotly_chart(fig, use_container_width=True)

st.divider()

# ---- Stress distribution + top stressed substations ----
col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("Stress Tier Distribution")
    tier_counts = (
        substations["stress_tier"]
        .value_counts()
        .reindex(["low", "moderate", "high", "critical"], fill_value=0)
        .reset_index()
    )
    tier_counts.columns = ["tier", "count"]
    fig2 = px.bar(
        tier_counts,
        x="tier",
        y="count",
        color="tier",
        color_discrete_map={
            "low": "#2ecc71",
            "moderate": "#f39c12",
            "high": "#e67e22",
            "critical": "#e74c3c",
        },
    )
    fig2.update_layout(
        showlegend=False, height=350, margin=dict(l=20, r=20, t=20, b=20)
    )
    st.plotly_chart(fig2, use_container_width=True)

with col_right:
    st.subheader("Top 10 Most Stressed")
    top10 = (
        substations.sort_values("stress_score", ascending=False)
        .head(10)[
            [
                "substation_id",
                "disco",
                "stress_score",
                "stress_tier",
                "outage_probability",
                "load_spike_probability",
            ]
        ]
    )
    st.dataframe(top10, use_container_width=True, hide_index=True)

st.divider()

# ---- Substation map ----
st.subheader("Substation Stress Map")

coords = load_substation_coords()
merged = substations.merge(
    coords, on="substation_id", how="inner", suffixes=("", "_dim")
)

if not merged.empty:
    color_map = {
        "low": "#2ecc71",
        "moderate": "#f39c12",
        "high": "#e67e22",
        "critical": "#e74c3c",
    }
    fig3 = px.scatter_map(
        merged,
        lat="latitude",
        lon="longitude",
        color="stress_tier",
        color_discrete_map=color_map,
        size="stress_score",
        hover_name="substation_id",
        hover_data=["disco", "stress_score", "outage_probability"],
        zoom=5.2,
        center={"lat": 9.0820, "lon": 8.6753},
        height=500,
    )
    fig3.update_layout(
        map_style="carto-darkmatter",
        margin=dict(l=0, r=0, t=0, b=0),
    )
    st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("Substation coordinates not available for mapping.")

st.caption(
    "Data: dbt marts · Model: XGBoost + composite stress score · "
    "Updates every 5 min from local warehouse"
)