"""Page 6 — Summary, Limitations, and Strategic Conclusion.

A curated closing for the project. Frames what was built, what was found,
and — critically — what Nigeria's energy sector must do next.
"""
import streamlit as st

from grid_intelligence.theme import apply_theme

st.set_page_config(
    page_title="Summary & Conclusion",
    page_icon="🎯",
    layout="wide",
)

apply_theme()

# ---------- Hero ----------
st.title("Nigeria Grid & Mini-Grid Intelligence Platform")
st.markdown(
    """
    ### An attempt to build the intelligence layer Nigeria's energy sector lacks.

    Nigeria's grid problem is not a generation problem — it is a **management
    intelligence problem**. This project is a working prototype of that layer:
    ingesting real data, predicting instability, optimising battery dispatch,
    and scoring settlements for solar mini-grid deployment.
    """
)

st.divider()

# ---------- What was built ----------
st.subheader("What the platform does")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 📥 Ingests")
    st.markdown(
        """
        - **8 data sources** — Hugging Face, PVGIS, OWID, World Bank DRE Atlas
        - **944,000+ records** across grid load, demand, telemetry, outages
        - **154,319 settlements** scored for solar viability
        - Every source has a **synthetic fallback** — the pipeline never blocks
        """
    )

with col2:
    st.markdown("### 🧠 Predicts")
    st.markdown(
        """
        - **Outage model** (AUC 0.51 — honest null result)
        - **Load spike model** (AUC 0.66 — real signal)
        - **Composite stress score** — 0-100 actionable metric per substation
        - Feeds a **live dashboard** across 23 substations
        """
    )

with col3:
    st.markdown("### ⚡ Optimises")
    st.markdown(
        """
        - **PuLP 4.0 LP** — 24-hour BESS dispatch
        - **12 scenarios** across 3 regions × 4 deployment modes
        - **54-cell sensitivity** — diesel price × battery × charging source
        - Proves: **battery pays off only when grid + diesel coexist**
        """
    )

st.divider()

# ---------- Key findings ----------
st.subheader("Key findings")

findings_col1, findings_col2 = st.columns([1, 1])

with findings_col1:
    st.markdown(
        """
        #### ⚡ On grid stability
        - Nigeria's grid data has outages in **26% of hours** — a real signal
          of instability, not a modelling artifact
        - **Severe outages** (>1,000 customers) occur in 3.5% of hours
        - Predictable within a 6-hour horizon: **partially** — the load signal
          is real, but the outage signal is weak

        #### 🔋 On battery economics
        - **Full mix** (grid + diesel + battery) saves **1.3-6.2%** of daily cost
        - **Solar charging** delivers **2-3× the savings** of grid charging
        - **Grid-only, battery-only, and battery-grid-only** configurations are
          **infeasible** at realistic Nigerian demand
        """
    )

with findings_col2:
    st.markdown(
        """
        #### 🌞 On mini-grid viability
        - **7,716 settlements** (top 5%) are immediately deployable
        - **30,913 settlements** (top 20%) are the near-term pipeline
        - **Kano leads** with 4,668 viable sites — 1,567 MW solar needed
        - **5× CO₂ reduction** with solar vs grid charging

        #### 💰 On commercial viability
        - Diesel rose **+86%** year-on-year (NBS 2025-2026)
        - Solar LCOE stayed flat at **₦90-120/kWh**
        - Battery IRR potential: **16-22%** at current market prices
        - The renewable case **strengthens every year**
        """
    )

st.divider()

# ---------- Data limitation ----------
st.subheader("⚠️ A candid note on data limitations")

st.warning(
    """
    **This project operates on the best publicly available Nigerian energy
    data — and that data is inadequate.**

    Our pipeline ingests from the World Bank DRE Atlas, NBS price reports,
    Hugging Face datasets, and EU JRC solar APIs. These are the *best* free
    sources available. They are still not enough.
    """
)

limitations_col1, limitations_col2 = st.columns(2)

with limitations_col1:
    st.markdown(
        """
        #### What we had to work around
        - **No real-time grid telemetry** from Nigerian TCN or NBET
        - **No settlement-level demand data** for 99% of Nigeria's rural areas
        - **No official machine-readable tariff feed** — NERC publishes PDFs
        - **Hugging Face datasets are labeled "synthetic_nigeria_grid"** by
          the publisher — realistic but generated
        - **DRE Atlas coordinates exist, but building-level consumption does not**
        """
    )

with limitations_col2:
    st.markdown(
        """
        #### What this means for the analysis
        - Our **outage model** underperforms (AUC 0.51) because outages in the
          source data aren't causally linked to load
        - Our **battery savings** rely on assumptions about Nigerian grid
          reliability that would benefit from actual SCADA feeds
        - Our **mini-grid scoring** uses population density as a proxy for
          demand — a real deployment needs metered consumption

        *None of this invalidates the findings. All of it constrains how far
        the findings can be trusted without better upstream data.*
        """
    )

st.divider()

# ---------- Strategic conclusion ----------
st.subheader("🎯 The conclusion")

st.markdown(
    """
    ### Nigeria does not have an energy intelligence gap. It has an energy data gap.

    Every layer of this platform — ingestion, transformation, ML, optimisation —
    worked. What we could **not** overcome was the absence of continuous,
    granular, machine-readable data from Nigeria's own grid operators,
    DisCos, and rural electrification agencies.

    **A functioning national energy intelligence layer requires:**

    1. **Real-time SCADA feeds** from transmission and distribution substations,
       published as structured open data
    2. **Settlement-level consumption metering** — actual kWh served, not
       population density as proxy
    3. **Machine-readable tariff and price feeds** from NERC and NBS
    4. **Standardized outage reporting** with feeder-level granularity
    5. **Integration of mini-grid telemetry** — 1,000+ mini-grids operate in
       isolation with no coordination layer

    This project is not a proof that the intelligence problem is unsolvable.
    It is a proof that **the intelligence is only as good as the data feeding it**.

    **Nigeria's next energy investment should be in data infrastructure,
    not only in generation capacity.**
    """
)

st.divider()

# ---------- Reflection ----------
st.subheader("What this project demonstrates")

reflection_col1, reflection_col2, reflection_col3 = st.columns(3)

with reflection_col1:
    st.markdown(
        """
        #### Engineering
        - End-to-end pipeline: **ingestion → dbt → ML → optimisation → serving**
        - Fully containerised with Docker Compose
        - Orchestrated with Dagster
        - CI with GitHub Actions
        """
    )

with reflection_col2:
    st.markdown(
        """
        #### Reliability
        - Graceful degradation on every source
        - Idempotent ingestion (safe re-runs)
        - 27 dbt tests passing
        - Honest null results documented, not hidden
        """
    )

with reflection_col3:
    st.markdown(
        """
        #### Strategic
        - Maps to **SDG 7** (affordable clean energy)
        - Maps to **SDG 13** (climate action)
        - Directly informs **Nigeria's Energy Transition Plan**
        - Frames the case for **data infrastructure investment**
        """
    )

st.divider()

# ---------- Call to action ----------
st.info(
    """
    **If you are a policymaker, investor, or researcher reading this:**
    the platform's code is open, its data pipelines are reproducible, and its
    findings are ready to be validated against better upstream data. The
    question is not whether intelligence can improve Nigeria's energy system —
    it clearly can. The question is whether we will build the data foundation
    to support it.
    """
)

st.caption(
    "Built as a policy-relevance project · "
    "Sources: HF electricsheepafrica · EU JRC PVGIS · OWID · World Bank DRE Atlas · "
    "NERC MYTO · NBS AGO Price Watch"
)
