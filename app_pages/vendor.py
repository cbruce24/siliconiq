import altair as alt
import pandas as pd
import streamlit as st

from siliconiq import analysis, ui
from siliconiq.formatting import fmt_num, fmt_pct, fmt_usd

data = ui.load_data()
ss = st.session_state

ui.page_header(
    "Vendor investment (hypothetical)",
    "Explore how pricing, demand, and cost assumptions shape the return on a hypothetical "
    "accelerator product. A learning exercise, not a forecast.",
    kicker="Supporting analysis",
)
st.warning(
    "Every value here is an assumption you enter. None represent NVIDIA's or AMD's actual "
    "pricing, costs, demand, or internal economics.",
    icon=":material/science:", title="Hypothetical exercise",
)


def _reset() -> None:
    for k, v in ui.VENDOR_DEFAULTS.items():
        ss[k] = v


inputs_col, results_col = st.columns([5, 7], gap="large")

with inputs_col:
    with st.container(horizontal=True, vertical_alignment="center"):
        st.subheader("Assumptions", anchor=False)
        st.button("Reset", icon=":material/restart_alt:", on_click=_reset, key="ven_reset",
                  help="Restore every input on this page to its default.")
    with st.form("ven_form", border=False, enter_to_submit=False):
        with st.container(border=True):
            st.markdown("**:material/sell: Pricing**")
            c1, c2 = st.columns(2)
            c1.number_input("Selling price per unit (USD K)", 1.0, 500.0, step=1.0,
                            key="ven_price_k", persist_state="session")
            c2.number_input("Unit cost (USD K)", 0.5, 400.0, step=0.5, key="ven_cost_k",
                            persist_state="session", help="Manufacturing cost per unit sold.")
        with st.container(border=True):
            st.markdown("**:material/groups: Demand**")
            c1, c2 = st.columns(2)
            c1.number_input("Year 1 unit demand", 100, 1_000_000, step=1000, key="ven_demand",
                            persist_state="session")
            c2.slider("Annual demand growth (%)", -50, 200, key="ven_growth", persist_state="session")
        with st.container(border=True):
            st.markdown("**:material/construction: Development and operating costs**")
            c1, c2 = st.columns(2)
            c1.number_input("Up-front development (USD M)", 0.1, 50_000.0, step=50.0,
                            key="ven_fixed_m", persist_state="session",
                            help="One-time R&D and tape-out investment in year 0.")
            c2.number_input("Annual operating cost (USD M)", 0.0, 10_000.0, step=10.0,
                            key="ven_opex_m", persist_state="session",
                            help="Recurring sales, support, and software cost per year.")
        with st.expander("Advanced financial settings", icon=":material/tune:"):
            st.slider("Model horizon (years)", 1, 10, key="ven_years", persist_state="session")
            st.number_input("Discount rate (%)", 0.0, 50.0, step=1.0, key="ven_discount",
                            persist_state="session")
        st.form_submit_button("Run scenarios", type="primary", icon=":material/play_arrow:",
                              width="stretch")

v = {
    "selling_price": float(ss["ven_price_k"]) * 1000,
    "unit_cost": float(ss["ven_cost_k"]) * 1000,
    "fixed_dev": float(ss["ven_fixed_m"]) * 1e6,
    "annual_opex": float(ss["ven_opex_m"]) * 1e6,
    "base_demand": int(ss["ven_demand"]),
    "demand_growth": float(ss["ven_growth"]),
    "model_years": int(ss["ven_years"]),
    "discount_rate": float(ss["ven_discount"]) / 100.0,
}
results = analysis.run_vendor_scenarios(v)
assumptions = {
    "selling_price_per_unit": v["selling_price"], "unit_cost": v["unit_cost"],
    "fixed_dev_investment_M": v["fixed_dev"] / 1e6, "annual_operating_cost_M": v["annual_opex"] / 1e6,
    "base_demand_year1": v["base_demand"], "demand_growth_pct": v["demand_growth"],
    "model_years": v["model_years"], "discount_rate_pct": v["discount_rate"] * 100,
    "note": "All values are hypothetical user assumptions, not NVIDIA or AMD economics.",
}
ss["ven_result"] = {"base": results["base"], "assumptions": assumptions}
rate_label = fmt_pct(v["discount_rate"] * 100, 0)

with results_col, st.container(key="results"):
    ui.summary_strip([
        ("Price / unit cost", f"{fmt_usd(v['selling_price'])} / {fmt_usd(v['unit_cost'])}"),
        ("Year 1 demand", f"{fmt_num(v['base_demand'])} units"),
        ("Growth", fmt_pct(v["demand_growth"], 0, signed=True) + " / yr"),
        ("Horizon", f"{v['model_years']} years"),
        ("Discount rate", rate_label),
    ], key="ven_summary")

    st.subheader("Scenario comparison", anchor=False)
    st.markdown(
        "Downside and upside scale your year 1 demand and selling price. The base case uses "
        "your inputs as entered. It's a reference point, not a prediction."
    )
    cols = st.columns(3, gap="small")
    for col, s in zip(cols, analysis.VENDOR_SCENARIOS):
        r = results[s.key]
        with col.container(border=True, height="stretch", key=f"scenario_{s.key}"):
            with st.container(horizontal=True, vertical_alignment="center", gap="small"):
                st.markdown(f"**{s.label}**")
                if s.key == "base":
                    st.badge("Your inputs", color="primary")
            st.markdown(f":gray[{s.description}]")
            st.metric(f"NPV at {rate_label}", fmt_usd(r["project_npv"]),
                      help="Discounted value of all cash flows, including year-0 development.")
            st.markdown(
                f"Net profit **{fmt_usd(r['net_profit'])}**  \n"
                f"Revenue **{fmt_usd(r['total_revenue'])}**  \n"
                f"ROI on development **"
                f"{'Undefined' if r['project_roi_pct'] is None else fmt_pct(r['project_roi_pct'], 0)}**  \n"
                f"Contribution margin **{fmt_pct(r['cm_pct'])}**  \n"
                f"Break-even **"
                f"{fmt_num(r['break_even_units']) + ' units' if r['break_even_units'] else 'Never (margin ≤ 0)'}**"
            )

    npv_df = pd.DataFrame([
        {"Scenario": s.label, "NPV": results[s.key]["project_npv"], "key": s.key}
        for s in analysis.VENDOR_SCENARIOS
    ])
    npv_df["Label"] = npv_df["NPV"].map(fmt_usd)
    base = alt.Chart(npv_df).encode(
        x=alt.X("Scenario:N", sort=None, title=None, axis=alt.Axis(labelAngle=0, labelFontSize=13)),
        y=alt.Y("NPV:Q", title=f"NPV at {rate_label} (USD)", axis=ui.money_axis()),
    )
    chart = alt.layer(
        base.mark_bar(cornerRadius=3, width={"band": 0.55}).encode(
            color=alt.Color("Scenario:N", legend=None, scale=alt.Scale(
                domain=[s.label for s in analysis.VENDOR_SCENARIOS],
                range=[ui.NEUTRAL, ui.PRIMARY, "#0D9488"])),
            tooltip=["Scenario", alt.Tooltip("NPV:Q", format="$,.0f")],
        ),
        base.mark_text(dy=-8, fontSize=13, fontWeight=600).encode(
            text="Label:N", y=alt.Y("NPV:Q")),
        alt.Chart(pd.DataFrame({"z": [0]})).mark_rule(color=ui.NEUTRAL).encode(y="z:Q"),
    ).properties(height=260)
    st.altair_chart(chart, alt="NPV by scenario: downside, base case, upside", height=280)

st.divider()

st.subheader("Sensitivity and cash flow", anchor=False)
tab_sens, tab_cf = st.tabs(["Price × demand sensitivity", "Cash flow by scenario"])
with tab_sens:
    grid = analysis.vendor_npv_grid(v)
    grid["Selling price"] = grid.apply(lambda r: f"{fmt_usd(r['selling_price'])}", axis=1)
    grid["Year 1 demand"] = grid.apply(
        lambda r: f"{fmt_num(r['unit_demand'])} ({r['demand_mult']:.0%})", axis=1)
    grid["NPV label"] = grid["npv"].map(fmt_usd)
    st.altair_chart(
        ui.heatmap(grid, x="Selling price", y="Year 1 demand", z="npv",
                   x_title="Selling price per unit", y_title="Year 1 demand (vs your input)",
                   z_title=f"NPV at {rate_label}", text_col="NPV label",
                   x_order=grid.drop_duplicates("price_mult")["Selling price"].tolist(),
                   y_order=grid.drop_duplicates("demand_mult")["Year 1 demand"].tolist()[::-1]),
        alt="NPV across selling price and demand; outlined cell is the base case",
    )
    st.markdown(
        "Base-case NPV across selling price (60–120% of your input) and year 1 demand "
        "(50–150%). The **outlined cell** is the base case. Blue is positive, orange negative."
    )
with tab_cf:
    rows = []
    for s in analysis.VENDOR_SCENARIOS:
        for t, cf in enumerate(results[s.key]["cash_flows"]):
            rows.append({"Year": t, "Cash flow": cf, "Scenario": s.label})
    cf = pd.DataFrame(rows)
    chart = alt.Chart(cf).mark_line(point=True, strokeWidth=2.5).encode(
        x=alt.X("Year:O", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("Cash flow:Q", title="Annual cash flow (USD)", axis=ui.money_axis()),
        color=alt.Color("Scenario:N", sort=None, scale=alt.Scale(
            domain=[s.label for s in analysis.VENDOR_SCENARIOS],
            range=[ui.NEUTRAL, ui.PRIMARY, "#0D9488"]), legend=alt.Legend(orient="top", title=None)),
        tooltip=["Scenario", "Year", alt.Tooltip("Cash flow:Q", format="$,.0f")],
    ).properties(height=300)
    st.altair_chart(chart, alt="Annual cash flow by scenario", height=320)
    st.markdown("Year 0 is development spend. Later years are revenue minus unit costs and operating cost.")

with st.expander("Scenario detail table", icon=":material/table_chart:"):
    tbl = pd.DataFrame([{
        "Scenario": s.label,
        "Assumption": s.description,
        "Total revenue": fmt_usd(results[s.key]["total_revenue"]),
        "Contribution margin": fmt_pct(results[s.key]["cm_pct"]),
        "Net profit": fmt_usd(results[s.key]["net_profit"]),
        "ROI on development": "Undefined" if results[s.key]["project_roi_pct"] is None
            else fmt_pct(results[s.key]["project_roi_pct"]),
        f"NPV at {rate_label}": fmt_usd(results[s.key]["project_npv"]),
        "Break-even units": fmt_num(results[s.key]["break_even_units"])
            if results[s.key]["break_even_units"] else "Never (margin ≤ 0)",
    } for s in analysis.VENDOR_SCENARIOS])
    st.dataframe(tbl, hide_index=True, alt="Scenario results table")


def _workbook() -> bytes:
    scoring = ss["str_result"]["table"] if ss.get("str_result") else None
    dep = ss.get("dep_result")
    return analysis.build_session_workbook(
        data, scoring_df=scoring, deployment=(dep["tco"], dep["roi"]) if dep else None,
        vendor=(results["base"], assumptions),
    )


st.download_button(
    "Download Excel workbook", data=_workbook, file_name="siliconiq_analysis.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    icon=":material/download:", on_click="ignore",
    help="Includes the dataset, the base-case vendor scenario, and any other analysis you've "
         "run this session. Built when you click.",
)
