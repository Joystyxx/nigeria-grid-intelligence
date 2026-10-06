"""Nigeria Grid & Mini-Grid Intelligence Platform — Streamlit dashboard.

Main entry point. Landing page with project overview and navigation.
Pages live in app/pages/ and are auto-discovered by Streamlit.
"""
import streamlit as st

from grid_intelligence.theme import apply_theme

st.set_page_config(
    page_title="Nigeria Grid Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_theme()

st.title("⚡ Nigeria Grid & Mini-Grid Intelligence Platform")
st.markdown(
    """
    **End-to-end data platform for Nigerian grid stability, BESS optimisation,
    and solar mini-grid viability.**
    """
)

st.divider()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Grid Load Records", "200K", help="Real HF snapshot, 2024")
    st.metric("Substations Monitored", "23")

with col2:
    st.metric("Outage Events", "60K", help="Real HF dataset")
    st.metric("Settlements Scored", "154K", help="World Bank DRE Atlas")

with col3:
    st.metric("ML Models Deployed", "2", help="Outage + load spike")
    st.metric("BESS Scenarios", "54", help="3 regions x 3 prices x 3 sizes x 2 sources")

with col4:
    st.metric(
        "Solar Mini-Grid Ready",
        "30,913",
        help="A+B tier settlements ready for solar mini-grid deployment (top 20%)",
    )
    st.metric("Top State", "Kano", help="4,668 viable settlements")

st.divider()

st.subheader("Solar Mini-Grid Viability Tiers")
st.caption(
    "154,319 Nigerian settlements scored on 5 weighted factors "
    "(solar resource 30%, population density 25%, distance from grid 20%, "
    "economic activity 15%, road accessibility 10%). Tiers are assigned "
    "by percentile rank. **A + B tiers** are the deployment-ready cohort "
    "for solar mini-grid investment."
)

tier_data = {
    "Tier": ["A — Highly viable", "B — Viable", "C — Borderline", "D — Not viable"],
    "Settlements": [7716, 23197, 46255, 77151],
    "Share": ["5%", "15%", "30%", "50%"],
    "Deployment status": [
        "Immediate investment",
        "Near-term pipeline",
        "Monitor for cost improvements",
        "Deprioritise — grid extension or wait",
    ],
}
st.dataframe(tier_data, use_container_width=True, hide_index=True)

st.divider()

st.subheader("Navigate the Dashboard")

col_a, col_b = st.columns(2)

with col_a:
    st.markdown(
        """
        ### 1. Grid Health
        Live grid load, outage patterns, and composite stress scores
        across 23 Nigerian substations.

        ### 2. Demand Accuracy
        Forecast error analysis by DisCo — which regions have the
        worst forecast accuracy, and what it costs.
        """
    )

with col_b:
    st.markdown(
        """
        ### 3. BESS Optimisation
        Battery dispatch economics across 3 Nigerian regions and 4
        deployment modes, with 54-cell sensitivity heatmap.

        ### 4. Solar Mini-Grid Viability
        Interactive map of Nigeria's 30,913 settlements most ready for
        solar mini-grid deployment (A + B tiers), scored on solar resource,
        population, grid distance, economic activity, and road access.
        """
    )

st.divider()

st.caption(
    "Built with: Python 3.12 · PostgreSQL 15 + TimescaleDB · dbt · Dagster · "
    "XGBoost · PuLP · Streamlit · Docker · GitHub Actions"
)
