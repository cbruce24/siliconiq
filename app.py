"""
SiliconIQ: compare AI accelerators, choose one for your priorities, and
evaluate deployment economics.

Launch:  streamlit run app.py
Ingest:  python -m siliconiq.ingest
Tests:   python -m pytest tests/

This entrypoint sets up shared state and navigation. Each page lives in
app_pages/, and shared UI helpers live in siliconiq/ui.py.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT))

import streamlit as st

from siliconiq import ui
from siliconiq.db import DB_PATH
from siliconiq.ingest import run_ingest

st.set_page_config(
    page_title="SiliconIQ",
    page_icon=":material/memory:",
    layout="wide",
    initial_sidebar_state="auto",
)
st.logo(str(ROOT / "assets" / "logo.svg"), size="large")

if not DB_PATH.exists():
    with st.spinner("Building the database from the bundled dataset…"):
        run_ingest()

data = ui.load_data()
ui.init_state(data["products"])
ui.inject_css()

pages = {
    "": [
        st.Page(ui.P_OVERVIEW, title="Overview", icon=":material/home:", default=True,
                help="What SiliconIQ does, key findings from the dataset, and where to start."),
    ],
    "Decision workflow": [
        st.Page(ui.P_COMPARE, title="1 · Compare accelerators", icon=":material/compare_arrows:",
                help="Side-by-side specifications and measured MLPerf results for the accelerators you pick."),
        st.Page(ui.P_STRATEGY, title="2 · Choose a product", icon=":material/checklist:",
                help="Score accelerators against a customer profile and your priorities and price assumptions."),
        st.Page(ui.P_DEPLOY, title="3 · Deployment economics", icon=":material/payments:",
                help="TCO, ROI, NPV, and payback for deploying the accelerator you chose."),
    ],
    "Supporting analysis": [
        st.Page(ui.P_FIN, title="Company financials", icon=":material/account_balance:",
                help="NVIDIA and AMD revenue, margins, R&D, and segments from 10-K filings."),
        st.Page(ui.P_VENDOR, title="Vendor investment", icon=":material/science:",
                help="A hypothetical product-investment exercise. All inputs are assumptions."),
        st.Page(ui.P_SOURCES, title="Sources & methodology", icon=":material/menu_book:",
                help="Every source document, comparability rules, and model formulas."),
    ],
}

nav = st.navigation(pages, position="sidebar", expanded=True)
ui.sidebar_status(data)
nav.run()
