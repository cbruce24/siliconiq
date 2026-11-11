import altair as alt
import pandas as pd
import streamlit as st

from siliconiq import analysis, ui
from siliconiq.formatting import fmt_pct, fmt_usd, vendor_name

data = ui.load_data()
prod, bench, fin, src = data["products"], data["benchmarks"], data["financials"], data["sources"]
ss = st.session_state

st.title("Find the right AI accelerator, then test the economics")
st.markdown(
    "SiliconIQ compares NVIDIA and AMD data-center accelerators using official "
    "specifications and MLPerf results, scores them against your priorities, and "
    "models whether a deployment pays off **under your assumptions**."
)

with st.container(horizontal=True, gap="small", key="ov_status"):
    st.badge(f"Data snapshot {ui.SNAPSHOT_LABEL}", icon=":material/event:", color="gray")
    st.badge(f"{len(prod)} accelerators", icon=":material/memory:", color="gray")
    st.badge(f"{len(bench)} MLPerf results", icon=":material/speed:", color="gray")
    st.badge(f"{len(src)} source documents", icon=":material/description:", color="gray")

st.space("small")

# ── Three entry points ───────────────────────────────────────────────────────
STEP_COPY = {
    1: ("Compare specifications and measured benchmark results side by side.",
        "Compare products"),
    2: ("Weight cost, performance, memory, power, and software for your use case.",
        "Choose a product"),
    3: ("Model TCO, ROI, NPV, and payback for a deployment of your chosen accelerator.",
        "Review deployment economics"),
}
cols = st.columns(3, gap="medium")
for col, (n, label, path, icon) in zip(cols, ui.STEPS):
    body, action = STEP_COPY[n]
    with col.container(border=True, height="stretch", key=f"step_card_{n}"):
        st.markdown(f":gray[Step {n}]")
        st.subheader(label, anchor=False)
        st.markdown(body)
        st.page_link(path, label=action, icon=":material/arrow_forward:")

st.space("medium")

# ── Sourced findings vs your scenario ─────────────────────────────────────────
left, right = st.columns([3, 2], gap="large")

with left:
    with st.container(horizontal=True, vertical_alignment="center", gap="small"):
        st.subheader("What the data shows", anchor=False)
        st.badge("Sourced", icon=":material/verified:", color="blue")
    st.markdown(
        f"Historical observations from the {ui.SNAPSHOT_LABEL} snapshot. "
        "Each finding notes its source and limits."
    )
    for i, t in enumerate(analysis.key_takeaways(prod, bench, fin)):
        with st.container(border=True, key=f"takeaway_{i}"):
            st.markdown(f"**{t['headline']}**")
            st.markdown(t["detail"])
            st.markdown(f":gray[{t['qualifier']}]")
            st.markdown(f":gray[:material/source: {t['source']}]")

with right:
    with st.container(horizontal=True, vertical_alignment="center", gap="small"):
        st.subheader("Your scenario", anchor=False)
        st.badge("Hypothetical", icon=":material/tune:", color="orange")
    st.markdown("Outputs that depend on your selections and assumptions. They carry across pages.")

    names = ui.product_lookup(data)["product_name"]
    chosen = [names[p] for p in ss["cmp_products"] if p in names.index]
    with st.container(border=True):
        st.markdown("**Comparison set**")
        st.markdown(", ".join(chosen) if chosen else "No accelerators selected.")

    with st.container(border=True):
        st.markdown("**Leading option**")
        res = ss.get("str_result")
        if res:
            st.markdown(
                f"{res['product_name']}, score {res['score']:.3f} for the "
                f"*{res['profile']}* profile."
            )
        else:
            st.markdown(":gray[Not scored yet.]")
            st.page_link(ui.P_STRATEGY, label="Choose a product", icon=":material/arrow_forward:")

    with st.container(border=True):
        st.markdown("**Deployment result**")
        dep = ss.get("dep_result")
        if dep:
            st.markdown(
                f"{dep['qty']} × {dep['product_name']} over {dep['years']} years: "
                f"NPV **{fmt_usd(dep['npv'])}**, ROI **{fmt_pct(dep['roi_pct'])}**."
            )
        else:
            st.markdown(":gray[Not evaluated yet.]")
            st.page_link(ui.P_DEPLOY, label="Review deployment economics",
                         icon=":material/arrow_forward:")

st.divider()

# ── Supporting: company trends and coverage ──────────────────────────────────
with st.container(horizontal=True, vertical_alignment="center"):
    st.subheader("Company financial trends", anchor=False)
    st.page_link(ui.P_FIN, label="Open company financials", icon=":material/arrow_forward:")
st.markdown(
    "Company-wide revenue and gross margin from 10-K filings. NVIDIA's fiscal year ends "
    "in late January and AMD's in late December, so the same label covers different months."
)

f = fin.assign(Company=fin["ticker"].map(vendor_name), revenue_usd=fin["revenue"] * 1e6)
c1, c2 = st.columns(2, gap="large")
with c1:
    chart = alt.Chart(f).mark_bar(cornerRadiusEnd=2).encode(
        x=alt.X("fiscal_label:N", title="Fiscal year", axis=alt.Axis(labelAngle=0)),
        xOffset="Company:N",
        y=alt.Y("revenue_usd:Q", title="Revenue (USD)", axis=ui.money_axis()),
        color=alt.Color("Company:N", scale=ui.vendor_scale(), legend=alt.Legend(orient="top", title=None)),
        tooltip=[alt.Tooltip("Company:N"), alt.Tooltip("fiscal_label:N", title="Fiscal year"),
                 alt.Tooltip("revenue_usd:Q", title="Revenue", format="$,.0f")],
    ).properties(title="Annual revenue", height=280)
    st.altair_chart(chart, alt="Annual revenue by company and fiscal year; NVIDIA rises sharply in FY2024")
with c2:
    chart = alt.Chart(f).mark_line(point=True, strokeWidth=2.5).encode(
        x=alt.X("fiscal_label:N", title="Fiscal year", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("gross_margin_pct:Q", title="Gross margin (%)", scale=alt.Scale(zero=False)),
        color=alt.Color("Company:N", scale=ui.vendor_scale(), legend=alt.Legend(orient="top", title=None)),
        tooltip=[alt.Tooltip("Company:N"), alt.Tooltip("fiscal_label:N", title="Fiscal year"),
                 alt.Tooltip("gross_margin_pct:Q", title="Gross margin (%)", format=".1f")],
    ).properties(title="Gross margin", height=280)
    st.altair_chart(chart, alt="Gross margin by company and fiscal year")

with st.expander("Dataset coverage", icon=":material/dataset:"):
    m = st.columns(4)
    m[0].metric("Source documents", len(src), border=True)
    m[1].metric("Accelerators in catalog", len(prod), border=True)
    m[2].metric("MLPerf results", len(bench), border=True)
    m[3].metric("Company fiscal years", len(fin), border=True)
    counts = src["source_type"].value_counts()
    by_type = pd.DataFrame({"source_type": counts.index, "Documents": counts.to_numpy()})
    by_type["Source type"] = by_type["source_type"].map({
        "SEC_filing": "SEC 10-K filings", "product_spec": "Official spec sheets",
        "benchmark_submission": "MLPerf submissions",
    }).fillna(by_type["source_type"])
    st.dataframe(by_type[["Source type", "Documents"]], hide_index=True, width="content",
                 alt="Number of source documents by type")
    st.markdown(
        "**Prices are not in the dataset.** Every price in SiliconIQ is an assumption you "
        "enter. None are list prices, quotes, or figures reported by NVIDIA or AMD."
    )
