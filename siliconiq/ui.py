"""
Shared Streamlit UI: data loading, session defaults, page scaffolding, and charts.

Pages import from here so headers, status, colors, and number formats stay
consistent across the app.
"""
from __future__ import annotations

from typing import Iterable

import altair as alt
import pandas as pd
import streamlit as st

from siliconiq import analysis, queries
from siliconiq.db import DB_PATH, get_connection
from siliconiq.formatting import fmt_date, fmt_usd, vendor_name

DATASET_DATE = "2025-01-15"
SNAPSHOT_LABEL = fmt_date(DATASET_DATE)

# ── Color system ──────────────────────────────────────────────────────────────
# One action color (theme primary), fixed vendor colors, neutral support colors.
PRIMARY = "#2563EB"
VENDOR_COLORS = {"NVIDIA": "#76B900", "AMD": "#ED1C24"}
POSITIVE = "#2563EB"      # gains: primary blue (avoids clashing with NVIDIA green)
NEGATIVE = "#EA580C"      # losses: orange (avoids clashing with AMD red)
NEUTRAL = "#94A3B8"

# ── Page registry (paths relative to the entrypoint) ─────────────────────────
P_OVERVIEW = "app_pages/overview.py"
P_COMPARE = "app_pages/compare.py"
P_STRATEGY = "app_pages/strategy.py"
P_DEPLOY = "app_pages/deployment.py"
P_FIN = "app_pages/financials.py"
P_VENDOR = "app_pages/vendor.py"
P_SOURCES = "app_pages/sources.py"

STEPS = [
    (1, "Compare accelerators", P_COMPARE, ":material/compare_arrows:"),
    (2, "Choose a product", P_STRATEGY, ":material/checklist:"),
    (3, "Evaluate deployment economics", P_DEPLOY, ":material/payments:"),
]


# ══════════════════════════════════════════════════════════════════════════════
# Data
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(show_spinner="Loading dataset…")
def load_data() -> dict[str, pd.DataFrame]:
    """Load every table the app uses once. Cleared by the dataset reload action."""
    conn = get_connection(DB_PATH)
    try:
        return {
            "financials": queries.get_financials(conn),
            "growth": queries.get_revenue_growth(conn),
            "segments": queries.get_segment_revenue(conn),
            "rd": queries.get_rd_comparison(conn),
            "products": queries.get_products(conn),
            "benchmarks": queries.get_benchmarks(conn),
            "sources": queries.get_sources(conn),
        }
    finally:
        conn.close()


def product_lookup(data: dict) -> pd.DataFrame:
    return data["products"].set_index("product_id")


# ══════════════════════════════════════════════════════════════════════════════
# Session state
# ══════════════════════════════════════════════════════════════════════════════

DEPLOY_DEFAULTS = {
    "dep_product_id":  "NVDA_H100_SXM5",
    "dep_num_acc":     8,
    "dep_hw_price_k":  30.0,
    "dep_infra_k":     100.0,
    "dep_utilization": 65,
    "dep_tdp":         700.0,
    "dep_elec":        0.08,
    "dep_facility_oh": 10,
    "dep_years":       3,
    "dep_support_k":   20.0,
    "dep_discount":    10.0,
    "dep_value_k":     500.0,
    "dep_value_type":  "Revenue",
    "dep_cpt_enabled": False,
    "dep_cpt_tps":     50000.0,
}
VENDOR_DEFAULTS = {
    "ven_price_k":  25.0,
    "ven_cost_k":   10.0,
    "ven_fixed_m":  500.0,
    "ven_opex_m":   50.0,
    "ven_demand":   50_000,
    "ven_growth":   20,
    "ven_years":    5,
    "ven_discount": 12.0,
}


def init_state(products: pd.DataFrame) -> None:
    """Set defaults once per session. Widgets use `persist_state="session"`, so
    user edits survive page switches and are never silently reset."""
    ss = st.session_state
    for k, v in {**DEPLOY_DEFAULTS, **VENDOR_DEFAULTS}.items():
        ss.setdefault(k, v)

    current_ids = products.loc[products["status"] == "current", "product_id"].tolist()
    ss.setdefault("cmp_products", current_ids)
    ss.setdefault("fin_companies", ["NVDA", "AMD"])

    ss.setdefault("str_profile", analysis.DEFAULT_PROFILE)
    for k, v in analysis.PROFILES[ss["str_profile"]].weights.items():
        ss.setdefault(f"str_w_{k}", v)
    for pid, ticker in zip(products["product_id"], products["ticker"]):
        ss.setdefault(f"str_price_{pid}", analysis.default_price_k(ticker))

    # Cross-page results (not widget-bound)
    ss.setdefault("dep_carried", None)     # accelerator handed over from another page
    ss.setdefault("str_result", None)      # latest scoring summary
    ss.setdefault("dep_result", None)      # latest deployment outputs
    ss.setdefault("ven_result", None)      # latest vendor outputs
    ss.setdefault("refresh_msg", None)


def carry_to_deployment(product_id: str, source: str, products: pd.DataFrame) -> None:
    """Hand an accelerator to Deployment Economics, with its catalog TDP and the
    price assumption the user set in Choose a product."""
    row = products.set_index("product_id").loc[product_id]
    price_k = float(st.session_state.get(f"str_price_{product_id}",
                                         analysis.default_price_k(row["ticker"])))
    st.session_state["dep_product_id"] = product_id
    st.session_state["dep_tdp"] = float(row["tdp_watts"])
    st.session_state["dep_hw_price_k"] = price_k
    st.session_state["dep_carried"] = {
        "product_id": product_id, "product_name": row["product_name"],
        "tdp_watts": float(row["tdp_watts"]), "price_k": price_k, "source": source,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Page scaffolding
# ══════════════════════════════════════════════════════════════════════════════

_CSS = f"""
<style>
/* Scoped to containers this app keys explicitly (.st-key-*). No generated class names. */
[class*="st-key-step_card_"], [class*="st-key-takeaway_"], .st-key-leader_card,
[class*="st-key-scenario_"] {{
  transition: transform 140ms ease-out, box-shadow 140ms ease-out, border-color 140ms ease-out;
}}
[class*="st-key-step_card_"]:hover, [class*="st-key-step_card_"]:focus-within {{
  transform: translateY(-2px);
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.10);
  border-color: {PRIMARY} !important;
}}
.st-key-leader_card, .st-key-scenario_base {{
  border-color: {PRIMARY} !important;
  box-shadow: inset 4px 0 0 {PRIMARY};
}}
.st-key-results {{ animation: siq-fade 180ms ease-out; }}
@keyframes siq-fade {{ from {{ opacity: 0.6; }} to {{ opacity: 1; }} }}
[class*="st-key-"] a:focus-visible, [class*="st-key-"] button:focus-visible {{
  outline: 2px solid {PRIMARY};
  outline-offset: 2px;
}}
@media (prefers-reduced-motion: reduce) {{
  [class*="st-key-"] {{ transition: none !important; animation: none !important; transform: none !important; }}
}}
</style>
"""


def inject_css() -> None:
    st.html(_CSS)


def step_indicator(current: int) -> None:
    with st.container(horizontal=True, gap="small", vertical_alignment="center", key="step_nav"):
        for i, (n, label, path, icon) in enumerate(STEPS):
            if n == current:
                st.badge(f"Step {n} · {label}", icon=":material/radio_button_checked:", color="primary")
            else:
                st.page_link(path, label=f"Step {n} · {label}", icon=icon)
            if i < len(STEPS) - 1:
                st.markdown(":gray[:material/chevron_right:]")


def page_header(title: str, description: str, *, step: int | None = None,
                kicker: str | None = None) -> None:
    if step is not None:
        step_indicator(step)
    elif kicker:
        st.badge(kicker, color="gray", icon=":material/library_books:")
    st.title(title)
    st.markdown(description)


def summary_strip(items: Iterable[tuple[str, str]], *, key: str) -> None:
    """Compact row of 'value / label' pairs summarizing active selections."""
    with st.container(border=True, horizontal=True, gap="medium", key=key):
        for label, value in items:
            with st.container(gap=None, width="content"):
                st.markdown(f":gray[{label}]")
                st.markdown(f"**{value}**")


def empty_state(message: str, *, link: tuple[str, str] | None = None,
                icon: str = ":material/filter_alt_off:") -> None:
    with st.container(border=True):
        st.markdown(f"{icon} {message}")
        if link:
            st.page_link(link[0], label=link[1], icon=":material/arrow_forward:")


def vendor_badge(ticker: str) -> None:
    st.badge(vendor_name(ticker), color="green" if ticker == "NVDA" else "red")


def provenance_legend() -> None:
    with st.container(horizontal=True, gap="small"):
        st.badge("Sourced", icon=":material/verified:", color="blue",
                 help="Values from SEC filings, official spec sheets, or MLPerf submissions.")
        st.badge("Assumed", icon=":material/tune:", color="orange",
                 help="Values you enter or that the model assumes. Not reported by NVIDIA or AMD.")


def sidebar_status(data: dict) -> None:
    """Small, consistent dataset-status block plus the reload action."""
    prod, bench, fin, src = (data["products"], data["benchmarks"],
                             data["financials"], data["sources"])
    with st.sidebar:
        st.markdown("**Dataset status**")
        fy = []
        for t, g in fin.groupby("ticker"):
            fy.append(f"{vendor_name(t)} {g['fiscal_label'].iloc[0]}–{g['fiscal_label'].iloc[-1]}")
        st.markdown(
            f":material/event: Snapshot **{SNAPSHOT_LABEL}**  \n"
            f":material/memory: {len(prod)} accelerators · {len(bench)} MLPerf results  \n"
            f":material/account_balance: {'; '.join(fy)}  \n"
            f":material/description: {len(src)} source documents"
        )
        provenance_legend()

        msg = st.session_state.pop("refresh_msg", None)  # shown once, after the reload rerun
        if msg:
            (st.success if msg["ok"] else st.error)(msg["text"], icon=msg["icon"])

        with st.expander("Reload bundled dataset", icon=":material/refresh:"):
            st.markdown(
                "Rewrites the local SQLite database from the demonstration dataset "
                "bundled with the app, then reloads every page. It **does not** fetch "
                "live data. Your scenario inputs are kept."
            )
            if st.button("Reload dataset", icon=":material/refresh:", key="reload_dataset",
                         width="stretch"):
                from siliconiq.ingest import run_ingest
                try:
                    with st.spinner("Rebuilding database from bundled data…"):
                        run_ingest()
                        load_data.clear()
                    st.session_state["refresh_msg"] = {
                        "ok": True, "icon": ":material/check_circle:",
                        "text": f"Dataset reloaded (snapshot {SNAPSHOT_LABEL}).",
                    }
                except Exception as e:  # surface the failure, keep the app usable
                    st.session_state["refresh_msg"] = {
                        "ok": False, "icon": ":material/error:",
                        "text": f"Reload failed: {e}. The previous data is still loaded.",
                    }
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# Charts (Altair; follows the app theme in light and dark mode)
# ══════════════════════════════════════════════════════════════════════════════

def money_axis(**kw) -> alt.Axis:
    """Currency axis with K/M/B suffixes (d3's SI format would print G for billions)."""
    return alt.Axis(labelExpr="replace(replace(format(datum.value, '$~s'), 'G', 'B'), 'k', 'K')", **kw)


def vendor_scale(domain: Iterable[str] | None = None) -> alt.Scale:
    dom = list(domain) if domain is not None else list(VENDOR_COLORS)
    return alt.Scale(domain=dom, range=[VENDOR_COLORS.get(d, NEUTRAL) for d in dom])


def hbar(df: pd.DataFrame, *, label: str, value: str, value_title: str,
         text_fmt: str = ",.0f", color: str = "Vendor", title: str | None = None,
         sort_desc: bool = True) -> alt.LayerChart:
    """Aligned horizontal bars with value labels; one bar per row in `df`."""
    order = df.sort_values(value, ascending=not sort_desc)[label].tolist()
    vmax = float(df[value].max()) if len(df) else 1.0
    base = alt.Chart(df).encode(
        y=alt.Y(f"{label}:N", sort=order, title=None,
                scale=alt.Scale(paddingInner=0.28, paddingOuter=0.15),
                axis=alt.Axis(labelLimit=320, labelFontSize=13, labelPadding=8, ticks=False)),
        x=alt.X(f"{value}:Q", title=value_title,
                axis=alt.Axis(format="~s") if vmax >= 1e5 else alt.Axis(),
                scale=alt.Scale(domain=[0, vmax * 1.15], nice=False)),
        tooltip=[alt.Tooltip(f"{label}:N", title="Product"),
                 alt.Tooltip(f"{value}:Q", title=value_title, format=text_fmt)],
    )
    bars = base.mark_bar(cornerRadiusEnd=3).encode(
        color=alt.Color(f"{color}:N", scale=vendor_scale(), legend=alt.Legend(orient="top", title=None)),
    )
    text = base.mark_text(align="left", dx=6, fontSize=13, fontWeight=600).encode(
        text=alt.Text(f"{value}:Q", format=text_fmt),
    )
    # Size by band (step) so each bar keeps a readable height regardless of container.
    chart = (bars + text).properties(height=alt.Step(44))
    if title:
        chart = chart.properties(title=title)
    return chart


def heatmap(df: pd.DataFrame, *, x: str, y: str, z: str, x_title: str, y_title: str,
            z_title: str, x_order: list, y_order: list, z_fmt: str = "$,.0f",
            text_col: str | None = None) -> alt.LayerChart:
    """Diverging heatmap centered on zero: orange = negative, blue = positive.
    Cells where df['is_current'] is True get an outline marking current inputs."""
    zmax = float(df[z].abs().max()) or 1.0
    d = df.copy()
    d["_strong"] = d[z].abs() > 0.55 * zmax
    base = alt.Chart(d).encode(
        x=alt.X(f"{x}:O", sort=x_order, title=x_title, axis=alt.Axis(labelAngle=0)),
        y=alt.Y(f"{y}:O", sort=y_order, title=y_title),
    )
    rect = base.mark_rect().encode(
        color=alt.Color(f"{z}:Q", title=z_title,
                        legend=alt.Legend(labelExpr="replace(replace(format(datum.value, '$~s'), 'G', 'B'), 'k', 'K')"),
                        scale=alt.Scale(scheme="blueorange", reverse=True, domainMid=0,
                                        domain=[-zmax, zmax])),
        tooltip=[alt.Tooltip(f"{x}:O", title=x_title), alt.Tooltip(f"{y}:O", title=y_title),
                 alt.Tooltip(f"{z}:Q", title=z_title, format=z_fmt)],
    )
    text = base.mark_text(fontSize=12).encode(
        text=f"{text_col or z}:N",
        color=alt.condition("datum._strong", alt.value("white"), alt.value("#0F172A")),
    )
    outline = base.transform_filter("datum.is_current").mark_rect(
        fill=None, stroke="#0F172A", strokeWidth=2.5)
    return (rect + text + outline).properties(height=alt.Step(40))


def cash_flow_chart(df: pd.DataFrame, *, x: str, y: str, cum: str | None, y_title: str) -> alt.LayerChart:
    d = df.copy()
    d["Direction"] = d[y].apply(lambda v: "Inflow" if v >= 0 else "Outflow")
    base = alt.Chart(d).encode(x=alt.X(f"{x}:O", title="Year", axis=alt.Axis(labelAngle=0)))
    bars = base.mark_bar(cornerRadius=2, width={"band": 0.6}).encode(
        y=alt.Y(f"{y}:Q", title=y_title, axis=money_axis()),
        color=alt.Color("Direction:N", scale=alt.Scale(domain=["Inflow", "Outflow"],
                                                       range=[POSITIVE, NEGATIVE]),
                        legend=alt.Legend(orient="top", title=None)),
        tooltip=[alt.Tooltip(f"{x}:O", title="Year"),
                 alt.Tooltip(f"{y}:Q", title="Net cash flow", format="$,.0f")],
    )
    rule = alt.Chart(pd.DataFrame({"z": [0]})).mark_rule(color=NEUTRAL).encode(y="z:Q")
    layers = [bars, rule]
    if cum:
        line = base.mark_line(point=True, color="#64748B", strokeDash=[4, 3]).encode(
            y=alt.Y(f"{cum}:Q"),
            tooltip=[alt.Tooltip(f"{x}:O", title="Year"),
                     alt.Tooltip(f"{cum}:Q", title="Cumulative", format="$,.0f")],
        )
        layers.append(line)
    return alt.layer(*layers).properties(height=300)


def money_axis_values(values: Iterable[float]) -> list[str]:
    return [fmt_usd(v) for v in values]
