import pandas as pd
import streamlit as st

from siliconiq import ui
from siliconiq.formatting import (
    fmt_date, fmt_num, is_missing, status_label, vendor_name, workload_label,
)

data = ui.load_data()
prod, bench = data["products"], data["benchmarks"]
lookup = ui.product_lookup(data)
ss = st.session_state

ui.page_header(
    "Compare accelerators",
    "Pick up to four accelerators to see their published specifications and measured "
    "benchmark results side by side.",
    step=1,
)

MAX_COMPARE = 4


def _option_label(pid: str) -> str:
    r = lookup.loc[pid]
    tag = "" if r["status"] == "current" else f" · {status_label(r['status'])}"
    return f"{r['product_name']}{tag}"


selected = st.multiselect(
    f"Accelerators to compare (up to {MAX_COMPARE})",
    options=prod["product_id"].tolist(),
    format_func=_option_label,
    max_selections=MAX_COMPARE,
    key="cmp_products",
    persist_state="session",
    help="Your selection carries into Choose a product, where these accelerators are scored.",
    placeholder="Choose accelerators",
)

if not selected:
    ui.empty_state(
        "No accelerators selected. Choose at least one above to see specifications and benchmarks.",
    )
    st.stop()

sel = lookup.loc[selected].reset_index()
sel["Vendor"] = sel["ticker"].map(vendor_name)
sel["fp16_per_watt"] = sel["fp16_tflops"] / sel["tdp_watts"]

# ══════════════════════════════════════════════════════════════════════════════
# Theoretical peak specifications
# ══════════════════════════════════════════════════════════════════════════════
with st.container(horizontal=True, vertical_alignment="center", gap="small"):
    st.header("Published specifications", anchor=False)
    st.badge("Theoretical peak", color="gray")
    st.badge("Sourced", icon=":material/verified:", color="blue")
st.markdown(
    f"From official datasheets as of the {ui.SNAPSHOT_LABEL} snapshot. Compute figures are "
    "**dense (non-sparse) peaks**: the hardware's ceiling, not throughput on a real workload."
)

SPEC_ROWS = [
    ("Platform", "Vendor", lambda r: r["Vendor"]),
    ("Platform", "Architecture", lambda r: r["generation"]),
    ("Platform", "Status at snapshot", lambda r: status_label(r["status"])),
    ("Platform", "Form factor", lambda r: r["form_factor"]),
    ("Platform", "Interconnect", lambda r: r["interconnect"]),
    ("Platform", "Release date", lambda r: fmt_date(r["release_date"])),
    ("Memory", "Capacity", lambda r: fmt_num(r["memory_gb"], 0, "GB")),
    ("Memory", "Bandwidth", lambda r: fmt_num(r["memory_bandwidth_tbps"], 2, "TB/s")),
    ("Memory", "Memory type", lambda r: r["memory_type"]),
    ("Peak compute (dense)", "FP16", lambda r: fmt_num(r["fp16_tflops"], 1, "TFLOPS")),
    ("Peak compute (dense)", "BF16", lambda r: fmt_num(r["bf16_tflops"], 1, "TFLOPS")),
    ("Peak compute (dense)", "FP8", lambda r: "Not supported" if is_missing(r["fp8_tflops"])
        else fmt_num(r["fp8_tflops"], 1, "TFLOPS")),
    ("Peak compute (dense)", "INT8", lambda r: fmt_num(r["int8_tops"], 1, "TOPS")),
    ("Power", "TDP", lambda r: fmt_num(r["tdp_watts"], 0, "W")),
    ("Power", "Peak FP16 per watt", lambda r: fmt_num(r["fp16_per_watt"], 2, "TFLOPS/W")),
]
table = pd.DataFrame([
    {"Group": g, "Attribute": a, **{r["product_name"]: f(r) for _, r in sel.iterrows()}}
    for g, a, f in SPEC_ROWS
])
st.dataframe(
    table, hide_index=True, height="content",
    column_config={
        "Group": st.column_config.TextColumn(width=150, pinned=True),
        "Attribute": st.column_config.TextColumn(width=150, pinned=True),
    },
    alt="Specification comparison table, one column per selected accelerator",
)
st.markdown(
    ":material/info: **FP8** is supported only by NVIDIA Hopper (H100, H200) and AMD CDNA 3 "
    "(MI300X). NVIDIA also publishes sparse figures at about 2× these dense values; they're "
    "excluded so all products compare on the same basis."
)

tab_compute, tab_mem, tab_power = st.tabs(["Peak compute", "Memory", "Power"])

with tab_compute:
    PRECISIONS = {"FP16": ("fp16_tflops", "TFLOPS"), "BF16": ("bf16_tflops", "TFLOPS"),
                  "FP8": ("fp8_tflops", "TFLOPS"), "INT8": ("int8_tops", "TOPS")}
    ss.setdefault("cmp_precision", "FP16")
    prec = st.segmented_control("Precision", list(PRECISIONS), key="cmp_precision",
                                persist_state="session", required=True) or "FP16"
    col, unit = PRECISIONS[prec]
    d = sel.dropna(subset=[col])
    missing = sel.loc[sel[col].isna(), "product_name"].tolist()
    if d.empty:
        ui.empty_state(f"None of the selected accelerators support {prec}.")
    else:
        st.altair_chart(
            ui.hbar(d, label="product_name", value=col, value_title=f"Peak {prec} ({unit}, dense)",
                    text_fmt=",.1f", title=f"Peak {prec} compute ({unit}, dense)"),
            alt=f"Peak {prec} compute by accelerator",
        )
    if missing:
        st.markdown(f":gray[Not shown, no {prec} support: {', '.join(missing)}.]")

with tab_mem:
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.altair_chart(
            ui.hbar(sel, label="product_name", value="memory_gb", value_title="GB",
                    text_fmt=",.0f", title="Memory capacity (GB)"),
            alt="Memory capacity by accelerator",
        )
    with c2:
        st.altair_chart(
            ui.hbar(sel, label="product_name", value="memory_bandwidth_tbps", value_title="TB/s",
                    text_fmt=",.2f", title="Memory bandwidth (TB/s)"),
            alt="Memory bandwidth by accelerator",
        )
    st.markdown(
        "Capacity sets the largest model that fits per accelerator; bandwidth usually limits "
        "LLM inference speed more than peak compute."
    )

with tab_power:
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.altair_chart(
            ui.hbar(sel, label="product_name", value="tdp_watts", value_title="Watts",
                    text_fmt=",.0f", title="Thermal design power (W)"),
            alt="TDP by accelerator",
        )
    with c2:
        st.altair_chart(
            ui.hbar(sel.dropna(subset=["fp16_per_watt"]), label="product_name",
                    value="fp16_per_watt", value_title="TFLOPS per watt", text_fmt=",.2f",
                    title="Peak FP16 per watt"),
            alt="Peak FP16 TFLOPS per watt by accelerator",
        )
    st.markdown(
        "Higher TDP means more power and cooling cost. Per-watt figures use peak compute, "
        "so treat them as an upper bound."
    )

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# Measured workload results
# ══════════════════════════════════════════════════════════════════════════════
with st.container(horizontal=True, vertical_alignment="center", gap="small"):
    st.header("Measured benchmark results", anchor=False)
    st.badge("Measured", color="gray")
    st.badge("Sourced", icon=":material/verified:", color="blue")
st.markdown(
    "Throughput from public MLPerf Inference submissions (MLCommons). Compare results only "
    "when workload, precision, system configuration, and benchmark version match."
)

if bench.empty:
    ui.empty_state("No benchmark results in the dataset.", icon=":material/speed:")
    st.stop()

wl_models = (bench[["workload", "model_name"]].drop_duplicates()
             .set_index("workload")["model_name"].to_dict())
workloads = sorted(wl_models, key=lambda w: (w != "LLM_inference", w))
if ss.get("bench_workload") not in workloads:
    ss["bench_workload"] = workloads[0]
c1, c2 = st.columns([3, 2], gap="medium")
with c1:
    wl = st.segmented_control(
        "Workload", workloads, key="bench_workload", persist_state="session", required=True,
        format_func=lambda w: f"{workload_label(w)} · {wl_models[w]}",
    )
bw = bench[bench["workload"] == wl]
versions = sorted(bw["benchmark_version"].unique().tolist(), reverse=True)
if ss.get("bench_version") not in versions:
    ss["bench_version"] = versions[0]
with c2:
    ver = st.segmented_control(
        "MLPerf Inference version", versions, key="bench_version", persist_state="session",
        required=True, format_func=lambda v: f"v{v}" + (" (latest)" if v == versions[0] else ""),
    )
bv = bw[bw["benchmark_version"] == ver].copy()
bv["Vendor"] = bv["ticker"].map(vendor_name)
selected_names = set(sel["product_name"])
shown = bv[bv["product_name"].isin(selected_names)]
others = sorted(set(bv["product_name"]) - selected_names)

if shown.empty:
    msg = "None of your selected accelerators have results for this workload and version."
    if others:
        msg += f" Results exist for: **{', '.join(others)}**. Add them to your comparison above."
    ui.empty_state(msg, icon=":material/speed:")
else:
    unit = shown["result_unit"].iloc[0]
    precs = ", ".join(sorted(shown["precision"].unique()))
    n_acc = ", ".join(str(int(n)) for n in sorted(shown["num_accelerators"].unique()))
    all_comparable = bool((shown["comparability"] == "comparable").all())
    ui.summary_strip([
        ("Model", wl_models[wl]),
        ("Precision", precs),
        ("Accelerators per system", n_acc),
        ("Unit", unit),
        ("Suite", f"MLPerf Inference v{ver}"),
    ], key="bench_context")

    chart_col, note_col = st.columns([3, 2], gap="large")
    with chart_col:
        st.altair_chart(
            ui.hbar(shown, label="product_name", value="result", value_title=unit,
                    text_fmt=",.0f", title=f"{wl_models[wl]} throughput ({unit}, higher is better)"),
            alt=f"Measured {wl_models[wl]} throughput by accelerator",
        )
    with note_col:
        if all_comparable:
            st.success(
                "Same benchmark version, workload, precision, and system size, so a "
                "direct comparison is defensible.",
                icon=":material/check_circle:", title="Comparable",
            )
        else:
            st.warning(
                "At least one result differs in version or configuration. Read the notes "
                "below before drawing conclusions.",
                icon=":material/warning:", title="Use with caution",
            )
        if others:
            st.markdown(f":gray[Also available, not in your selection: {', '.join(others)}.]")
        st.markdown(
            "Results reflect each vendor's tuned software stack at submission time, not "
            "only the silicon."
        )

    with st.expander("System configuration, comparability notes, and sources",
                     icon=":material/fact_check:"):
        det = shown.rename(columns={
            "product_name": "Accelerator", "precision": "Precision",
            "num_accelerators": "Accelerators", "system_config": "System",
            "software_stack": "Software stack", "result": "Result", "result_unit": "Unit",
            "comparability": "Comparability", "comparability_note": "Note",
            "source_url": "Source", "submission_date": "Submitted",
        })
        det["Comparability"] = det["Comparability"].str.capitalize()
        st.dataframe(
            det[["Accelerator", "Result", "Unit", "Precision", "Accelerators", "System",
                 "Software stack", "Comparability", "Note", "Submitted", "Source"]],
            hide_index=True,
            column_config={
                "Result": st.column_config.NumberColumn(format="localized"),
                "Source": st.column_config.LinkColumn(display_text="MLCommons"),
                "Note": st.column_config.TextColumn(width="large"),
            },
            alt="Benchmark configuration and comparability details",
        )

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# Next steps
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("Next step", anchor=False)
c1, c2 = st.columns(2, gap="large")
with c1.container(border=True, height="stretch"):
    st.markdown("**Choose based on your priorities**")
    st.markdown(f"Score your {len(selected)} selected accelerators against a customer profile.")
    st.page_link(ui.P_STRATEGY, label="Choose a product", icon=":material/arrow_forward:")
with c2.container(border=True, height="stretch"):
    st.markdown("**Already know which one?**")
    with st.container(horizontal=True, vertical_alignment="bottom"):
        pick = st.selectbox("Accelerator", selected, format_func=lambda p: lookup.loc[p, "product_name"],
                            key="cmp_eval_pick")
        if st.button("Evaluate this accelerator", type="primary", icon=":material/payments:",
                     key="cmp_eval_btn"):
            ui.carry_to_deployment(pick, "Compare accelerators", prod)
            st.switch_page(ui.P_DEPLOY)
