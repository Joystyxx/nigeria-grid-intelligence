"""Page 4 — Solar Mini-Grid Viability.

Reads fct_minigrid_viability (154K settlements) and fct_state_summary.
Interactive map, state ranking, and settlement drill-down.
"""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from grid_intelligence.config import PROJECT_ROOT
from grid_intelligence.db import read_df
from grid_intelligence.theme import apply_theme

st.set_page_config(page_title="Mini-Grid Viability", page_icon="🗺️", layout="wide")

apply_theme()

st.title("🗺️ Solar Mini-Grid Viability")
st.caption(
    "154,319 Nigerian settlements scored on 5 weighted factors. "
    "Top 5% (tier A) and next 15% (tier B) are the deployment-ready cohort."
)


@st.cache_data(ttl=300)
def load_tier_summary() -> pd.DataFrame:
    sql = """
        SELECT
            viability_tier,
            COUNT(*) AS n,
            ROUND(AVG(viability_score)::numeric, 2) AS avg_score,
            SUM(population)::bigint AS total_population,
            ROUND(AVG(solar_pv_value)::numeric, 2) AS avg_solar_pv
        FROM dbt_dev_marts.fct_minigrid_viability
        GROUP BY 1
        ORDER BY 1
    """
    return read_df(sql)


@st.cache_data(ttl=300)
def load_state_summary() -> pd.DataFrame:
    sql = """
        SELECT state, viable_settlements, total_population, households_served,
               solar_capacity_mw_needed, bess_capacity_mwh_needed,
               capex_estimate_m_ngn, tco2_avoided_per_year,
               avg_viability_score, viability_rank
        FROM dbt_dev_marts.fct_state_summary
        ORDER BY viable_settlements DESC
    """
    return read_df(sql)


@st.cache_data(ttl=300)
def load_top_settlements(state: str, limit: int = 200) -> pd.DataFrame:
    sql = f"""
        SELECT settlement_id, settlement_name, state, lga,
               latitude, longitude, population,
               dist_transmission_km, solar_pv_value,
               viability_score, viability_tier
        FROM dbt_dev_marts.fct_minigrid_viability
        WHERE state = '{state}'
          AND viability_tier IN ('A_highly_viable', 'B_viable')
          AND latitude IS NOT NULL
          AND longitude IS NOT NULL
        ORDER BY viability_score DESC
        LIMIT {limit}
    """
    return read_df(sql)


@st.cache_data(ttl=300)
def load_geojson() -> dict:
    """Load the light GeoJSON for national map."""
    path = PROJECT_ROOT / "docs" / "minigrid_viability_top50.geojson"
    if not path.exists():
        return {"features": []}
    return json.loads(path.read_text())


# ---- Load data ----
tier_summary = load_tier_summary()
state_summary = load_state_summary()
geojson = load_geojson()

# ---- Metric cards ----
st.subheader("National Opportunity")

col1, col2, col3, col4 = st.columns(4)
with col1:
    total_ab = int(
        tier_summary[
            tier_summary["viability_tier"].isin(["A_highly_viable", "B_viable"])
        ]["n"].sum()
    )
    st.metric("Deployment-Ready Sites", f"{total_ab:,}", help="A + B tiers")
with col2:
    total_pop = int(
        tier_summary[
            tier_summary["viability_tier"].isin(["A_highly_viable", "B_viable"])
        ]["total_population"].sum()
    )
    st.metric(
        "Population Covered",
        f"{total_pop / 1e6:.1f}M",
        help="Residents in A+B tier settlements",
    )
with col3:
    total_mw = state_summary["solar_capacity_mw_needed"].sum()
    st.metric("Solar Capacity Needed", f"{total_mw:,.0f} MW")
with col4:
    total_co2 = state_summary["tco2_avoided_per_year"].sum()
    st.metric("CO₂ Avoidable / year", f"{total_co2 / 1e6:.1f}M t")

st.divider()

# ---- Tier distribution ----
st.subheader("Viability Tier Distribution")

col_left, col_right = st.columns([1, 1])

with col_left:
    tier_display = tier_summary.copy()
    tier_labels = {
        "A_highly_viable": "A — Highly viable",
        "B_viable": "B — Viable",
        "C_borderline": "C — Borderline",
        "D_not_viable": "D — Not viable",
    }
    tier_display["tier_label"] = tier_display["viability_tier"].map(tier_labels)
    fig = px.bar(
        tier_display,
        x="tier_label",
        y="n",
        color="tier_label",
        color_discrete_map={
            "A — Highly viable": "#2ecc71",
            "B — Viable": "#a3d977",
            "C — Borderline": "#f39c12",
            "D — Not viable": "#e74c3c",
        },
        labels={"n": "Settlements", "tier_label": "Tier"},
        text="n",
    )
    fig.update_traces(texttemplate="%{text:,}", textposition="outside")
    fig.update_layout(
        showlegend=False, height=350, margin=dict(l=20, r=20, t=20, b=20)
    )
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.markdown("**What each tier means:**")
    st.markdown(
        """
        - **A — Highly viable** (top 5%): Immediate investment candidates.
        - **B — Viable** (next 15%): Near-term pipeline.
        - **C — Borderline** (next 30%): Monitor for cost improvements.
        - **D — Not viable** (bottom 50%): Deprioritise — grid extension or wait.

        **Composite score factors:** solar resource (30%), population density (25%),
        distance from grid (20%), economic activity (15%), road accessibility (10%).
        """
    )

st.divider()

# ---- National map ----
st.subheader("National Map — Top 50 Settlements per State")

if geojson["features"]:
    features = geojson["features"]
    map_df = pd.DataFrame(
        [
            {
                "lat": f["geometry"]["coordinates"][1],
                "lon": f["geometry"]["coordinates"][0],
                "state": f["properties"]["state"],
                "name": f["properties"]["name"],
                "population": f["properties"]["population"],
                "viability_score": f["properties"]["viability_score"],
                "viability_tier": f["properties"]["viability_tier"],
                "dist_grid_km": f["properties"]["dist_transmission_km"],
            }
            for f in features
        ]
    )

    color_map = {
        "A_highly_viable": "#2ecc71",
        "B_viable": "#f39c12",
    }

    fig_map = px.scatter_map(
        map_df,
        lat="lat",
        lon="lon",
        color="viability_tier",
        color_discrete_map=color_map,
        size="population",
        size_max=18,
        hover_name="name",
        hover_data={
            "state": True,
            "population": ":,",
            "viability_score": ":.1f",
            "dist_grid_km": ":.1f",
            "lat": False,
            "lon": False,
            "viability_tier": False,
        },
        zoom=5.2,
        center={"lat": 9.0820, "lon": 8.6753},
        height=600,
        labels={
            "viability_tier": "Tier",
            "population": "Population",
            "viability_score": "Score",
            "dist_grid_km": "Grid dist (km)",
        },
    )
    fig_map.update_layout(
        map_style="carto-darkmatter",
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    st.plotly_chart(fig_map, use_container_width=True)

    st.caption(
        f"Showing {len(map_df):,} settlements (top 50 per state). "
        "Download the full 30,913-site GeoJSON from `docs/minigrid_viability_full.geojson` "
        "in the repository."
    )
else:
    st.info(
        "GeoJSON file not found. Run `python scripts/export_minigrid_geojson.py` first."
    )

st.divider()

# ---- State ranking ----
st.subheader("State Ranking — Top 15 by Viable Settlements")

top_states = state_summary.head(15)

fig_states = px.bar(
    top_states,
    x="viable_settlements",
    y="state",
    orientation="h",
    color="viable_settlements",
    color_continuous_scale="Greens",
    labels={"viable_settlements": "Viable settlements (A+B)", "state": ""},
    text="viable_settlements",
)
fig_states.update_traces(texttemplate="%{text:,}", textposition="outside")
fig_states.update_layout(
    height=500,
    showlegend=False,
    margin=dict(l=20, r=20, t=20, b=20),
    yaxis=dict(autorange="reversed"),
)
st.plotly_chart(fig_states, use_container_width=True)

st.divider()

# ---- State drill-down ----
st.subheader("State Drill-Down")

selected_state = st.selectbox(
    "Select state",
    state_summary["state"].tolist(),
    index=0,
)

state_row = state_summary[state_summary["state"] == selected_state].iloc[0]

s1, s2, s3, s4 = st.columns(4)
with s1:
    st.metric("Viable Settlements", f"{int(state_row['viable_settlements']):,}")
with s2:
    st.metric("Households Served", f"{int(state_row['households_served']):,}")
with s3:
    st.metric("Solar Needed", f"{state_row['solar_capacity_mw_needed']:,.0f} MW")
with s4:
    st.metric("Est. CAPEX", f"₦{state_row['capex_estimate_m_ngn']:,.0f}M")

# Map of state settlements
state_data = load_top_settlements(selected_state, limit=200)

if not state_data.empty:
    # Center map on state's settlements, auto-zoom to fit the spread
    center_lat = float(state_data["latitude"].mean())
    center_lon = float(state_data["longitude"].mean())
    lat_span = float(state_data["latitude"].max() - state_data["latitude"].min())
    lon_span = float(state_data["longitude"].max() - state_data["longitude"].min())
    span = max(lat_span, lon_span)

    if span < 0.3:
        zoom_level = 9.5
    elif span < 0.6:
        zoom_level = 9
    elif span < 1.2:
        zoom_level = 8
    elif span < 2.0:
        zoom_level = 7
    elif span < 3.5:
        zoom_level = 6
    else:
        zoom_level = 5.5

    fig_state_map = px.scatter_map(
        state_data,
        lat="latitude",
        lon="longitude",
        color="viability_score",
        color_continuous_scale="Greens",
        size="population",
        size_max=15,
        hover_name="settlement_name",
        hover_data={
            "lga": True,
            "population": ":,",
            "viability_score": ":.1f",
            "dist_transmission_km": ":.1f",
            "latitude": False,
            "longitude": False,
        },
        zoom=zoom_level,
        center={"lat": center_lat, "lon": center_lon},
        height=450,
        labels={
            "population": "Population",
            "viability_score": "Score",
            "dist_transmission_km": "Grid dist (km)",
        },
    )
    fig_state_map.update_layout(
        map_style="carto-darkmatter",
        margin=dict(l=0, r=0, t=0, b=0),
    )
    st.plotly_chart(fig_state_map, use_container_width=True)

    st.markdown(f"**Top 10 settlements in {selected_state}:**")
    top10 = state_data.head(10)[
        [
            "settlement_name",
            "lga",
            "population",
            "dist_transmission_km",
            "solar_pv_value",
            "viability_score",
        ]
    ].copy()
    top10.columns = [
        "Settlement",
        "LGA",
        "Population",
        "Grid distance (km)",
        "Solar PV value",
        "Viability score",
    ]
    st.dataframe(top10, use_container_width=True, hide_index=True)

st.caption(
    "Data: World Bank DRE Atlas (154,319 settlements) · "
    "Scores: 5-factor weighted composite · Tiers: percentile-based"
)