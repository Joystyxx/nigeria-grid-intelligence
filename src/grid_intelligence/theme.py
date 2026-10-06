"""Custom theme CSS for the Streamlit dashboard.

Streamlit doesn't support deep visual customization via config.toml alone.
This module injects a curated stylesheet to give the platform a distinct
"energy operations console" identity — subtle, professional, and consistent
across light and dark themes.

Usage in any page:
    from grid_intelligence.theme import apply_theme
    apply_theme()
"""
from __future__ import annotations

import streamlit as st

# ---------- Brand palette ----------
# Chosen to echo both the Nigerian flag (green) and the solar/energy sector
# (amber). Alerts use a deep red for critical states.
COLORS = {
    "solar_amber": "#F5A623",
    "grid_emerald": "#10B981",
    "alert_red": "#DC2626",
    "ink": "#1A1A1A",
    "muted": "#6B7280",
    "surface": "#FFFFFF",
    "border": "#E5E7EB",
}


_CSS = """
<style>
/* ---------- Typography ---------- */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, 'Segoe UI', 'Helvetica Neue', sans-serif;
    -webkit-font-smoothing: antialiased;
    letter-spacing: -0.01em;
}

/* ---------- Headings ---------- */
h1, h2, h3 {
    letter-spacing: -0.02em;
    font-weight: 700;
}

h1 {
    background: linear-gradient(90deg, #F5A623 0%, #10B981 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    padding-bottom: 0.25rem;
}

h2 {
    border-bottom: 2px solid #F5A623;
    padding-bottom: 0.5rem;
    margin-top: 1.5rem !important;
}

h3 {
    color: #1A1A1A;
}

/* ---------- Metric cards ---------- */
[data-testid="stMetric"] {
    background: linear-gradient(180deg, #FFFFFF 0%, #FAFAFA 100%);
    border: 1px solid #E5E7EB;
    border-left: 4px solid #F5A623;
    border-radius: 8px;
    padding: 1rem 1.2rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}

[data-testid="stMetric"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(245, 166, 35, 0.15);
    border-left-color: #10B981;
}

[data-testid="stMetricLabel"] {
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #6B7280 !important;
}

[data-testid="stMetricValue"] {
    font-size: 1.8rem !important;
    font-weight: 700 !important;
    color: #1A1A1A !important;
}

/* ---------- Buttons ---------- */
.stButton > button {
    border-radius: 6px;
    font-weight: 600;
    border: 1px solid #E5E7EB;
    transition: all 0.15s ease;
}

.stButton > button:hover {
    border-color: #F5A623;
    color: #F5A623;
    box-shadow: 0 2px 8px rgba(245, 166, 35, 0.2);
}

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #FAFAFA 0%, #F0F0F0 100%);
    border-right: 1px solid #E5E7EB;
}

[data-testid="stSidebar"] h1 {
    background: none;
    -webkit-text-fill-color: #F5A623;
    font-size: 1.1rem !important;
    border-bottom: 2px solid #10B981;
    padding-bottom: 0.4rem;
}

/* ---------- Dividers ---------- */
hr {
    border: none;
    height: 1px;
    background: linear-gradient(90deg, transparent, #E5E7EB 20%, #E5E7EB 80%, transparent);
    margin: 1.5rem 0;
}

/* ---------- Expander (mode definitions) ---------- */
[data-testid="stExpander"] {
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    background: #FAFAFA;
}

[data-testid="stExpander"] summary {
    font-weight: 600;
    color: #1A1A1A;
}

/* ---------- Info / Warning / Error callouts ---------- */
[data-testid="stAlert"] {
    border-radius: 8px;
    border-left-width: 4px;
}

/* ---------- Dataframes ---------- */
[data-testid="stDataFrame"] {
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    overflow: hidden;
}

/* ---------- Caption ---------- */
.stCaption, [data-testid="stCaptionContainer"] {
    color: #6B7280;
    font-style: italic;
}

/* ---------- Tabs ---------- */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    border-bottom: 2px solid #E5E7EB;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 6px 6px 0 0;
    padding: 0.5rem 1rem;
    font-weight: 600;
}

.stTabs [aria-selected="true"] {
    background: linear-gradient(180deg, #F5A623 0%, #E09615 100%);
    color: #FFFFFF !important;
}

/* ---------- Plotly chart containers ---------- */
.js-plotly-plot .plotly {
    border-radius: 8px;
}

/* ---------- Scrollbar ---------- */
::-webkit-scrollbar {
    width: 10px;
    height: 10px;
}

::-webkit-scrollbar-track {
    background: #F0F0F0;
}

::-webkit-scrollbar-thumb {
    background: #CBD5E1;
    border-radius: 5px;
}

::-webkit-scrollbar-thumb:hover {
    background: #F5A623;
}

/* ---------- Dark mode overrides ---------- */
@media (prefers-color-scheme: dark) {
    [data-testid="stMetric"] {
        background: linear-gradient(180deg, #1E1E1E 0%, #171717 100%);
        border-color: #2A2A2A;
    }
    [data-testid="stMetricValue"] {
        color: #F5F5F5 !important;
    }
    h3 {
        color: #F5F5F5;
    }
}
</style>
"""


def apply_theme() -> None:
    """Inject the platform CSS. Call once per page, right after set_page_config."""
    st.markdown(_CSS, unsafe_allow_html=True)
