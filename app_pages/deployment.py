import altair as alt
import pandas as pd
import streamlit as st

from siliconiq import analysis, calculations, ui
from siliconiq.formatting import fmt_num, fmt_pct, fmt_usd, fmt_years

data = ui.load_data()
prod = data["products"]
lookup = ui.product_lookup(data)
ss = st.session_state

ui.page_header(
    "Evaluate deployment economics",
    "Does this deployment make economic sense under your assumptions? Set the hardware, "
    "operating costs, and expected value, then review TCO, ROI, NPV, and payback.",
    step=3,
)


def _sync_product() -> None:
    """When the accelerator changes, load its catalog TDP and your assumed price."""
    pid = ss["dep_product_id"]
    row = lookup.loc[pid]
    ss["dep_tdp"] = float(row["tdp_watts"])
    ss["dep_hw_price_k"] = float(ss.get(f"str_price_{pid}", analysis.default_price_k(row["ticker"])))
    ss["dep_carried"] = None


def _reset() -> None:
    for k, v in ui.DEPLOY_DEFAULTS.items():
        ss[k] = v
    ss["dep_carried"] = None


carried = ss.get("dep_carried")
if carried:
    st.info(
        f"**{carried['product_name']}** carried over from {carried['source']}, with its catalog "
        f"TDP ({carried['tdp_watts']:.0f} W) and your assumed price "
        f"({fmt_usd(carried['price_k'] * 1000)} per unit).",
        icon=":material/input:",
    )

inputs_col, results_col = st.columns([5, 7], gap="large")

# ══════════════════════════════════════════════════════════════════════════════
# Inputs
# ══════════════════════════════════════════════════════════════════════════════
with inputs_col:
    with st.container(horizontal=True, vertical_alignment="bottom"):
        st.selectbox(
            "Accelerator", prod["product_id"].tolist(), key="dep_product_id",
            persist_state="session", format_func=lambda p: lookup.loc[p, "product_name"],
            on_change=_sync_product,
            help="Changing this loads the catalog TDP and your price assumption from Choose a product.",
        )
        st.button("Reset", icon=":material/restart_alt:", on_click=_reset, key="dep_reset",
                  help="Restore every input on this page to its default.")

    product = lookup.loc[ss["dep_product_id"]]
    catalog_tdp = float(product["tdp_watts"])

    with st.form("dep_form", border=False, enter_to_submit=False):
        with st.container(border=True):
            st.markdown("**:material/memory: Hardware and infrastructure**")
            c1, c2 = st.columns(2)
            c1.number_input("Number of accelerators", 1, 10_000, step=1, key="dep_num_acc",
                            persist_state="session")
            c2.number_input("Price per accelerator (USD K)", 0.0, 500.0, step=1.0,
                            key="dep_hw_price_k", persist_state="session",
                            help="Your assumption, not a list price or quote.")
            c1.number_input("Supporting infrastructure (USD K)", 0.0, 10_000.0, step=10.0,
                            key="dep_infra_k", persist_state="session",
                            help="One-time cost for servers, networking, and installation.")
            c2.number_input("TDP per accelerator (W)", 100.0, 1500.0, step=50.0, key="dep_tdp",
                            persist_state="session",
                            help=f"Catalog value for {product['product_name']}: {catalog_tdp:.0f} W.")

        with st.container(border=True):
            st.markdown("**:material/bolt: Operating costs**")
            st.slider("Average utilization (%)", 0, 100, key="dep_utilization",
                      persist_state="session",
                      help="Share of time accelerators run at full power. Drives power cost only.")
            c1, c2 = st.columns(2)
            c1.number_input("Electricity (USD per kWh)", 0.01, 0.50, step=0.01, format="%.2f",
                            key="dep_elec", persist_state="session")
            c2.number_input("Support and software (USD K per year)", 0.0, 1000.0, step=5.0,
                            key="dep_support_k", persist_state="session")
            st.slider("Facility overhead (% of active power)", 0, 100, key="dep_facility_oh",
                      persist_state="session",
                      help="Cooling, power distribution, and other losses. A PUE of 1.1 is about 10%.")

        with st.container(border=True):
            st.markdown("**:material/trending_up: Expected business value**")
            st.segmented_control(
                "Value type", ["Revenue", "Cost savings"], key="dep_value_type",
                persist_state="session", required=True,
                help="Choose one. Counting both revenue and savings would double-count value.",
            )
            c1, c2 = st.columns(2)
            c1.number_input("Annual value (USD K per year)", 0.0, 100_000.0, step=50.0,
                            key="dep_value_k", persist_state="session")
            c2.slider("Evaluation horizon (years)", 1, 10, key="dep_years", persist_state="session")
            st.markdown(
                ":material/info: Annual value is **fixed**: it doesn't change with utilization. "
                "Only power cost scales with utilization."
            )

        with st.expander("Advanced financial settings", icon=":material/tune:"):
            st.number_input("Discount rate (%)", 0.0, 50.0, step=1.0, key="dep_discount",
                            persist_state="session",
                            help="Used for NPV. The 10% default is a placeholder, not a recommendation.")
            st.toggle("Show cost per million tokens", key="dep_cpt_enabled", persist_state="session")
            st.number_input("System throughput (tokens/sec at 100% utilization)", 0.0, 1e7,
                            step=1000.0, key="dep_cpt_tps", persist_state="session",
                            help="Used only when cost per million tokens is on.")

        st.form_submit_button("Run analysis", type="primary", icon=":material/play_arrow:",
                              width="stretch")

# ══════════════════════════════════════════════════════════════════════════════
# Compute (from applied values)
# ══════════════════════════════════════════════════════════════════════════════
p = {
    "num_acc": int(ss["dep_num_acc"]),
    "hw_price": float(ss["dep_hw_price_k"]) * 1000,
    "infra_cost": float(ss["dep_infra_k"]) * 1000,
    "utilization": int(ss["dep_utilization"]),
    "tdp": float(ss["dep_tdp"]),
    "elec_price": float(ss["dep_elec"]),
    "facility_oh": float(ss["dep_facility_oh"]),
    "annual_support": float(ss["dep_support_k"]) * 1000,
    "deploy_years": int(ss["dep_years"]),
    "discount_rate": float(ss["dep_discount"]) / 100.0,
    "annual_value": float(ss["dep_value_k"]) * 1000,
}
try:
    tco, roi = analysis.run_deployment(p)
except ValueError as e:
    results_col.error(f"Check your inputs: {e}", icon=":material/error:")
    st.stop()

pb = roi["payback_years"]
ss["dep_result"] = {
    "product_name": product["product_name"], "qty": p["num_acc"], "years": p["deploy_years"],
    "npv": roi["npv"], "roi_pct": roi["roi_pct"], "tco": tco, "roi": roi,
}
annual_net = p["annual_value"] - tco["annual_opex"]

# ══════════════════════════════════════════════════════════════════════════════
# Results
# ══════════════════════════════════════════════════════════════════════════════
with results_col, st.container(key="results"):
    tdp_note = "" if abs(p["tdp"] - catalog_tdp) < 0.5 else f" (catalog {catalog_tdp:.0f} W)"
    ui.summary_strip([
        ("Accelerator", product["product_name"]),
        ("Quantity", fmt_num(p["num_acc"])),
        ("Assumed price", f"{fmt_usd(p['hw_price'])} / unit"),
        ("Utilization", f"{p['utilization']}%"),
        ("Horizon", f"{p['deploy_years']} years"),
        ("TDP", f"{p['tdp']:.0f} W{tdp_note}"),
    ], key="dep_summary")

    # Verdict
    if roi["npv"] > 0 and pb is not None and pb <= p["deploy_years"]:
        st.success(
            f"NPV is {fmt_usd(roi['npv'])} at a {fmt_pct(p['discount_rate'] * 100, 0)} discount "
            f"rate, and the up-front cost is recovered in {fmt_years(pb)}.",
            icon=":material/check_circle:", title="Yes, under these assumptions",
        )
    elif roi["npv"] > 0:
        st.warning(
            f"NPV is positive ({fmt_usd(roi['npv'])}), but payback takes longer than the "
            f"{p['deploy_years']}-year horizon.",
            icon=":material/warning:", title="Marginal",
        )
    else:
        reason = (
            f"annual value ({fmt_usd(p['annual_value'])}) doesn't cover annual operating cost "
            f"({fmt_usd(tco['annual_opex'])})" if annual_net <= 0 else
            f"net cash flow of {fmt_usd(annual_net)} per year doesn't recover "
            f"{fmt_usd(tco['total_capex'])} of capital cost in {p['deploy_years']} years at this discount rate"
        )
        st.error(f"NPV is {fmt_usd(roi['npv'])}: {reason}.", icon=":material/cancel:",
                 title="No, under these assumptions")

    r1 = st.columns(3)
    r1[0].metric("Total cost (TCO)", fmt_usd(tco["total_tco"]), border=True,
                 help=f"Capital cost plus {p['deploy_years']} years of power and support.")
    r1[1].metric("Net benefit", fmt_usd(roi["net_benefit"]), border=True,
                 help="Total business value over the horizon minus TCO. Undiscounted.")
    r1[2].metric("ROI", "Undefined" if roi["roi_pct"] is None else fmt_pct(roi["roi_pct"]),
                 border=True,
                 help="Net benefit ÷ TCO. Undefined when TCO is zero.")
    r2 = st.columns(3)
    r2[0].metric(f"NPV at {fmt_pct(p['discount_rate'] * 100, 0)}", fmt_usd(roi["npv"]), border=True,
                 help="Today's value of all cash flows, discounted at your rate. Positive means "
                      "the deployment beats your required return.")
    if pb is None:
        pb_val, pb_help = "Never", (
            "Annual value doesn't exceed annual operating cost, so the up-front cost is never recovered.")
    else:
        pb_val = fmt_years(pb)
        pb_help = "Up-front cost ÷ annual net cash flow. Undiscounted."
        if pb > p["deploy_years"]:
            pb_help += f" Beyond your {p['deploy_years']}-year horizon."
    r2[1].metric("Payback", pb_val, border=True, help=pb_help)
    r2[2].metric("Annual power cost", fmt_usd(tco["annual_power_cost"]), border=True,
                 help=f"At {p['utilization']}% utilization, including facility overhead.")

    if ss["dep_cpt_enabled"] and ss["dep_cpt_tps"] > 0:
        cpt = calculations.cost_per_token(tco["annual_opex"], ss["dep_cpt_tps"], p["utilization"])
        st.metric("Operating cost per million tokens",
                  "Undefined" if cpt is None else f"${cpt:,.4f}", border=True,
                  help=f"{ss['dep_cpt_tps']:,.0f} tokens/sec × {p['utilization']}% utilization. "
                       "Excludes capital cost amortization.")

    if p["utilization"] == 0 and p["annual_value"] > 0:
        st.warning(
            "Utilization is 0%, yet annual value is still counted in full because value is fixed. "
            "Power cost is zero here, but real hardware draws roughly 15–25% of TDP at idle.",
            icon=":material/warning:",
        )
    elif p["utilization"] < 20 and p["annual_value"] > 0:
        st.info(
            f"At {p['utilization']}% utilization, power cost is low but annual value "
            f"({fmt_usd(p['annual_value'])}) is still counted in full. Check this matches your workload.",
            icon=":material/info:",
        )

    tab_cost, tab_cf, tab_sens = st.tabs(["Cost breakdown", "Cash flow", "Sensitivity"])
    with tab_cost:
        n = p["deploy_years"]
        comp = pd.DataFrame([
            ("Accelerators", tco["hw_capex"], "Capital"),
            ("Infrastructure", tco["infra_cost"], "Capital"),
            (f"Power ({n} yrs)", tco["annual_power_cost"] * n, "Operating"),
            (f"Support ({n} yrs)", tco["annual_support_cost"] * n, "Operating"),
        ], columns=["Component", "Cost", "Type"])
        total = comp["Cost"].sum() or 1.0
        comp["Label"] = comp.apply(lambda r: f"{fmt_usd(r['Cost'])} · {r['Cost'] / total:.0%}", axis=1)
        base = alt.Chart(comp).encode(
            y=alt.Y("Component:N", sort=None, title=None,
                    scale=alt.Scale(paddingInner=0.28, paddingOuter=0.15), axis=alt.Axis(labelFontSize=13, labelLimit=200)),
            x=alt.X("Cost:Q", title="USD", axis=ui.money_axis(),
                    scale=alt.Scale(domain=[0, float(comp["Cost"].max()) * 1.3], nice=False)),
        )
        chart = (base.mark_bar(cornerRadiusEnd=3).encode(
            color=alt.Color("Type:N", scale=alt.Scale(domain=["Capital", "Operating"],
                                                      range=[ui.PRIMARY, ui.NEUTRAL]),
                            legend=alt.Legend(orient="top", title=None)),
            tooltip=["Component", alt.Tooltip("Cost:Q", format="$,.0f"), "Type"],
        ) + base.mark_text(align="left", dx=6, fontSize=13).encode(text="Label:N")
        ).properties(height=alt.Step(44), title=f"Where the {fmt_usd(tco['total_tco'])} goes")
        st.altair_chart(chart, alt="TCO by component: accelerators, infrastructure, power, support")

    cf_table = analysis.deployment_cash_flow_table(roi, tco, p["annual_value"])
    with tab_cf:
        st.altair_chart(
            ui.cash_flow_chart(cf_table, x="Year", y="Net cash flow", cum="Cumulative cash flow",
                               y_title="USD"),
            alt="Net cash flow by year with cumulative line", height=320,
        )
        st.markdown(
            "Year 0 is the capital outlay. Each later year is annual value minus operating cost. "
            "The dashed line is the cumulative position; payback is where it crosses zero."
        )

    with tab_sens:
        grid = analysis.deployment_npv_grid(p)
        grid["Utilization"] = grid["utilization"].map(lambda u: f"{u}%")
        grid["Annual value"] = grid.apply(
            lambda r: f"{fmt_usd(r['annual_value'])} ({r['value_mult']:.0%})", axis=1)
        grid["NPV label"] = grid["npv"].map(fmt_usd)
        st.altair_chart(
            ui.heatmap(grid, x="Utilization", y="Annual value", z="npv",
                       x_title="Utilization", y_title="Annual value (vs your input)",
                       z_title="NPV", text_col="NPV label",
                       x_order=grid.drop_duplicates("utilization")["Utilization"].tolist(),
                       y_order=grid.drop_duplicates("value_mult")["Annual value"].tolist()[::-1]),
            alt="NPV across utilization and annual value; outlined cell is your current input",
        )
        st.markdown(
            "Same formulas as the results above, varying only utilization and annual value. "
            "The **outlined cell** is your current input. Blue is positive NPV, orange negative. "
            "Utilization changes NPV only through power cost, because value is fixed."
        )

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# Details and export
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("Details and export", anchor=False)
c1, c2 = st.columns([3, 2], gap="large")
with c1:
    st.markdown("**Year-by-year cash flow**")
    money_cols = [c for c in cf_table.columns if c != "Year"]
    st.dataframe(
        cf_table.assign(**{c: cf_table[c].map(fmt_usd) for c in money_cols}),
        hide_index=True, height="content",
        column_config={c: st.column_config.TextColumn(alignment="right") for c in money_cols},
        alt="Annual cash flow table",
    )
with c2:
    st.markdown("**Cost components**")
    comp_tbl = pd.DataFrame([
        ("Accelerator hardware", fmt_usd(tco["hw_capex"])),
        ("Infrastructure", fmt_usd(tco["infra_cost"])),
        ("Total capital cost", fmt_usd(tco["total_capex"])),
        ("Annual power", fmt_usd(tco["annual_power_cost"])),
        ("Annual support and software", fmt_usd(tco["annual_support_cost"])),
        ("Annual operating cost", fmt_usd(tco["annual_opex"])),
        ("Facility power draw", fmt_num(tco["facility_watts"], 0, "W")),
        ("Energy per year", fmt_num(tco["kwh_per_year"], 0, "kWh")),
    ], columns=["Item", "Value"])
    st.dataframe(comp_tbl, hide_index=True, height="content", alt="TCO component values")

with st.expander("Power model", icon=":material/bolt:"):
    st.markdown(f"""
- **Active power:** {p['num_acc']} accelerators × {p['tdp']:.0f} W × {p['utilization']}% =
  **{fmt_num(tco['active_watts'], 0, 'W')}**
- **Facility power:** active × (1 + {p['facility_oh']:.0f}%) = **{fmt_num(tco['facility_watts'], 0, 'W')}**
- **Energy per year:** facility watts × 8,760 hours ÷ 1,000 = **{fmt_num(tco['kwh_per_year'], 0, 'kWh')}**

**Idle power:** this model uses TDP × utilization, so 0% utilization means zero power. Real
hardware draws about 15–25% of TDP at idle. For lightly used systems, set utilization to at
least 15–20%, or add idle power to infrastructure cost.
""")


def _workbook() -> bytes:
    scoring = ss["str_result"]["table"] if ss.get("str_result") else None
    vendor = ss.get("ven_result")
    return analysis.build_session_workbook(
        data, scoring_df=scoring, deployment=(tco, roi),
        vendor=(vendor["base"], vendor["assumptions"]) if vendor else None,
    )


st.download_button(
    "Download Excel workbook", data=_workbook, file_name="siliconiq_analysis.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    icon=":material/download:", on_click="ignore",
    help="Includes the dataset, this deployment scenario, and any scoring or vendor analysis "
         "you've run this session. Built when you click.",
)
