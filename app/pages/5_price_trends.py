"""Page 5 — Energy Price Trends (2024-2026).

Visualizes how Nigerian grid, diesel, and solar prices have evolved,
and how BESS savings respond. Reads from ml.bess_multiyear.
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from grid_intelligence.config import PROJECT_ROOT
from grid_intelligence.db import read_df
from grid_intelligence.theme import apply_theme

st.set_page_config(page_title="Price Trends", page_icon="📈", layout="wide")

apply_theme()

st.title("📈 Energy Price Trends — Nigeria 2024 to 2026")
st.caption(
    "Same power system modeled under 2024, 2025, and 2026 Nigerian prices. "
    "Shows how renewable economics evolve as diesel gets more expensive."
)


@st.cache_data(ttl=300)
def load_multiyear() -> pd.DataFrame:
    sql = """
        SELECT year, region, grid_price, diesel_price, solar_price,
               savings_ngn, savings_pct, emissions_saved_kg
        FROM ml.bess_multiyear
        ORDER BY year, region
    """
    return read_df(sql)


df = load_multiyear()

# ---- Price evolution line chart ----
st.subheader("Price per kWh — Grid vs Diesel vs Solar")

# Average prices by year
prices = (
    df.groupby("year")
    .agg(
        grid=("grid_price", "mean"),
        diesel=("diesel_price", "mean"),
        solar=("solar_price", "mean"),
    )
    .reset_index()
)

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=prices["year"], y=prices["grid"], mode="lines+markers",
    name="Grid (Band A)", line=dict(color="#3498db", width=3),
))
fig.add_trace(go.Scatter(
    x=prices["year"], y=prices["diesel"], mode="lines+markers",
    name="Diesel (generation)", line=dict(color="#e74c3c", width=3),
))
fig.add_trace(go.Scatter(
    x=prices["year"], y=prices["solar"], mode="lines+markers",
    name="Solar + battery (LCOE)", line=dict(color="#2ecc71", width=3),
))
fig.update_layout(
    xaxis_title="Year",
    yaxis_title="₦ per kWh",
    height=400,
    margin=dict(l=20, r=20, t=20, b=20),
    hovermode="x unified",
)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# ---- BESS savings by year ----
st.subheader("BESS Cost Savings % by Year")
st.caption(
    "Same Kano/Lagos/Abuja load profile, same battery, only prices differ. "
    "Savings rise as diesel becomes relatively more expensive."
)

fig2 = px.bar(
    df,
    x="year",
    y="savings_pct",
    color="region",
    barmode="group",
    labels={"savings_pct": "Savings (%)", "year": "Year"},
    color_discrete_map={
        "Lagos": "#3498db",
        "Kano": "#e67e22",
        "Abuja": "#9b59b6",
    },
)
fig2.update_layout(height=400, margin=dict(l=20, r=20, t=20, b=20))
st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ---- Data table ----
st.subheader("Underlying Data")
display_df = df.copy()
display_df.columns = [
    "Year", "Region", "Grid (₦/kWh)", "Diesel (₦/kWh)", "Solar (₦/kWh)",
    "Savings (₦)", "Savings %", "CO₂ Saved (kg)",
]
st.dataframe(display_df, use_container_width=True, hide_index=True)

st.divider()

# ---- Key insights ----
st.subheader("What the Numbers Say")

col1, col2, col3 = st.columns(3)

with col1:
    diesel_2024 = prices.loc[prices["year"] == "2024", "diesel"].iloc[0]
    diesel_2026 = prices.loc[prices["year"] == "2026", "diesel"].iloc[0]
    diesel_increase = (diesel_2026 - diesel_2024) / diesel_2024 * 100
    st.metric(
        "Diesel cost change",
        f"+{diesel_increase:.0f}%",
        help=f"2024: ₦{diesel_2024:.0f}/kWh → 2026: ₦{diesel_2026:.0f}/kWh",
    )

with col2:
    solar_2024 = prices.loc[prices["year"] == "2024", "solar"].iloc[0]
    solar_2026 = prices.loc[prices["year"] == "2026", "solar"].iloc[0]
    solar_change = (solar_2026 - solar_2024) / solar_2024 * 100
    st.metric(
        "Solar cost change",
        f"+{solar_change:.0f}%",
        help=f"2024: ₦{solar_2024:.0f}/kWh → 2026: ₦{solar_2026:.0f}/kWh",
    )

with col3:
    best = df.loc[df["savings_pct"].idxmax()]
    st.metric(
        "Best savings case",
        f"{best['savings_pct']:.1f}%",
        help=f"{best['region']} in {best['year']}",
    )

st.info(
    "**The renewable case strengthens over time.** Diesel costs grew faster "
    "than solar in naira terms. Every year, the battery's value in displacing "
    "diesel increases. This is the commercial thesis: BESS adoption in "
    "Nigeria is not just climate action — it's defensive economics against "
    "rising fuel prices."
)

st.caption(
    "Sources: NERC MYTO (grid tariffs) · NBS AGO Price Watch (diesel pump prices) · "
    "SurgePV / BusinessDay (solar LCOE) · Data: ml.bess_multiyear"
)