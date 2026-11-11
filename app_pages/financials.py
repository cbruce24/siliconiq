import altair as alt
import pandas as pd
import streamlit as st

from siliconiq import analysis, ui
from siliconiq.formatting import fmt_date, fmt_pct, fmt_usd, vendor_name

data = ui.load_data()
ss = st.session_state

ui.page_header(
    "Company financials",
    "Compare NVIDIA's and AMD's revenue, margins, R&D investment, and segments, as reported "
    "in their 10-K filings.",
    kicker="Supporting analysis",
)

with st.container(horizontal=True, vertical_alignment="bottom", gap="medium"):
    companies = st.pills(
        "Companies", ["NVDA", "AMD"], selection_mode="multi", key="fin_companies",
        persist_state="session", format_func=vendor_name,
    )
    ui.provenance_legend()

st.info(
    "**NVIDIA's** fiscal year ends in late January (FY2024 = 30 Jan 2023 to 28 Jan 2024). "
    "**AMD's** ends in late December (FY2023 = 1 Jan to 30 Dec 2023). Charts use fiscal labels, "
    "so the same label covers different months.",
    icon=":material/calendar_month:",
)

if not companies:
    ui.empty_state("No company selected. Choose NVIDIA, AMD, or both above.")
    st.stop()

fin = data["financials"]
fin = fin[fin["ticker"].isin(companies)].assign(Company=lambda d: d["ticker"].map(vendor_name))
grw = data["growth"]
grw = grw[grw["ticker"].isin(companies)].dropna(subset=["yoy_growth_pct"]).assign(
    Company=lambda d: d["ticker"].map(vendor_name))
seg = data["segments"]
seg = seg[seg["ticker"].isin(companies)].assign(Company=lambda d: d["ticker"].map(vendor_name))

# ── Latest fiscal year per company ───────────────────────────────────────────
st.subheader("Latest fiscal year in the dataset", anchor=False)
latest = analysis.latest_fiscal_years(fin)
latest = latest.sort_values("ticker", key=lambda s: s.map({"NVDA": 0, "AMD": 1}))
for _, r in latest.iterrows():
    with st.container(border=True):
        with st.container(horizontal=True, vertical_alignment="center", gap="small"):
            st.markdown(f"**{vendor_name(r['ticker'])} {r['fiscal_label']}**")
            yoy = ("" if r["yoy_growth_pct"] is None
                   else f" · revenue {fmt_pct(r['yoy_growth_pct'], 0, signed=True)} year over year")
            st.markdown(f":gray[ended {fmt_date(r['period_end'])}{yoy}]")
        m = st.columns(4)
        m[0].metric("Revenue", fmt_usd(r["revenue"], scale=1e6))
        m[1].metric("Gross margin", fmt_pct(r["gross_margin_pct"]))
        m[2].metric("Operating margin", fmt_pct(r["operating_margin_pct"]))
        m[3].metric("R&D share of revenue", fmt_pct(r["rd_pct_revenue"]))


def _xaxis():
    return alt.X("fiscal_label:N", title="Fiscal year", axis=alt.Axis(labelAngle=0))


def _color():
    return alt.Color("Company:N", scale=ui.vendor_scale(), legend=alt.Legend(orient="top", title=None))


def grouped_bars(df, y, y_title, fmt, title):
    return alt.Chart(df).mark_bar(cornerRadiusEnd=2).encode(
        x=_xaxis(), xOffset="Company:N", color=_color(),
        y=alt.Y(f"{y}:Q", title=y_title,
                axis=ui.money_axis() if fmt == "$~s" else alt.Axis(format=fmt)),
        tooltip=["Company", alt.Tooltip("fiscal_label:N", title="Fiscal year"),
                 alt.Tooltip(f"{y}:Q", title=y_title, format=fmt.replace("~s", ",.0f"))],
    ).properties(title=title, height=280)


def lines(df, y, y_title, title):
    return alt.Chart(df).mark_line(point=True, strokeWidth=2.5).encode(
        x=_xaxis(), color=_color(),
        y=alt.Y(f"{y}:Q", title=y_title, scale=alt.Scale(zero=False)),
        tooltip=["Company", alt.Tooltip("fiscal_label:N", title="Fiscal year"),
                 alt.Tooltip(f"{y}:Q", title=y_title, format=".1f")],
    ).properties(title=title, height=260)


tab_rev, tab_margin, tab_rd, tab_seg = st.tabs(["Revenue and growth", "Margins", "R&D", "Segments"])

with tab_rev:
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.altair_chart(grouped_bars(fin.assign(rev=fin["revenue"] * 1e6), "rev", "Revenue (USD)",
                                     "$~s", "Total revenue"),
                        alt="Total revenue by company and fiscal year")
    with c2:
        if grw.empty:
            ui.empty_state("Growth needs at least two consecutive fiscal years per company.")
        else:
            chart = grouped_bars(grw, "yoy_growth_pct", "YoY growth (%)", ".0f",
                                 "Revenue growth year over year (%)")
            rule = alt.Chart(pd.DataFrame({"z": [0]})).mark_rule(color=ui.NEUTRAL).encode(y="z:Q")
            st.altair_chart(chart + rule, alt="Year-over-year revenue growth by company")

with tab_margin:
    c = st.columns(3, gap="medium")
    for col, (metric, label) in zip(c, [("gross_margin_pct", "Gross margin (%)"),
                                         ("operating_margin_pct", "Operating margin (%)"),
                                         ("rd_pct_revenue", "R&D share of revenue (%)")]):
        with col:
            st.altair_chart(lines(fin, metric, label, label), alt=f"{label} by company and year")

with tab_rd:
    rd = data["rd"]
    rd = rd[rd["ticker"].isin(companies)].assign(Company=lambda d: d["ticker"].map(vendor_name))
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.altair_chart(grouped_bars(rd.assign(rdu=rd["rd_expense_usd_m"] * 1e6), "rdu",
                                     "R&D expense (USD)", "$~s", "Annual R&D expense"),
                        alt="Annual R&D expense by company")
    with c2:
        st.altair_chart(lines(rd, "rd_pct_revenue", "R&D share of revenue (%)", "R&D intensity"),
                        alt="R&D as a share of revenue by company")
    st.markdown(
        "R&D intensity falls when revenue grows faster than R&D. In NVIDIA FY2024, revenue rose "
        "126% while R&D rose 18%, so intensity fell even as R&D reached a record $8.7B."
    )

with tab_seg:
    if seg.empty:
        ui.empty_state("No segment data for the selected companies.")
    else:
        cols = st.columns(len(companies), gap="large")
        for col, t in zip(cols, companies):
            s = seg[seg["ticker"] == t].assign(v=lambda d: d["segment_revenue_usd_m"] * 1e6)
            if s.empty:
                col.markdown(f":gray[No segment data for {vendor_name(t)}.]")
                continue
            chart = alt.Chart(s).mark_bar(cornerRadiusEnd=2).encode(
                x=_xaxis(), xOffset="segment:N",
                y=alt.Y("v:Q", title="Segment revenue (USD)", axis=ui.money_axis()),
                color=alt.Color("segment:N", title=None, legend=alt.Legend(orient="top")),
                tooltip=[alt.Tooltip("segment:N", title="Segment"),
                         alt.Tooltip("fiscal_label:N", title="Fiscal year"),
                         alt.Tooltip("v:Q", title="Revenue", format="$,.0f")],
            ).properties(title=f"{vendor_name(t)} segment revenue", height=300)
            col.altair_chart(chart, alt=f"{vendor_name(t)} revenue by reported segment")
        st.warning(
            "Data center segments include more than AI accelerators (networking, CPUs, and more), "
            "so segment revenue isn't AI accelerator revenue. AMD restructured its segments in "
            "FY2023, so earlier years aren't directly comparable.",
            icon=":material/warning:", title="Read segments with care",
        )

with st.expander("Financial data table", icon=":material/table_chart:"):
    tbl = pd.DataFrame({
        "Company": fin["Company"],
        "Fiscal year": fin["fiscal_label"],
        "Period end": fin["period_end"].map(fmt_date),
        "Revenue": fin["revenue"].map(lambda x: fmt_usd(x, scale=1e6)),
        "Gross profit": fin["gross_profit"].map(lambda x: fmt_usd(x, scale=1e6)),
        "Operating income": fin["operating_income"].map(lambda x: fmt_usd(x, scale=1e6)),
        "R&D expense": fin["rd_expense"].map(lambda x: fmt_usd(x, scale=1e6)),
        "Gross margin": fin["gross_margin_pct"].map(fmt_pct),
        "Operating margin": fin["operating_margin_pct"].map(fmt_pct),
        "R&D share": fin["rd_pct_revenue"].map(fmt_pct),
    })
    st.dataframe(tbl, hide_index=True, alt="Financial data by company and fiscal year")
