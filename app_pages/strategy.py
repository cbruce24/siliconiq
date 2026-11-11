import pandas as pd
import streamlit as st

from siliconiq import analysis, ui
from siliconiq.formatting import fmt_pct, fmt_usd, vendor_name

data = ui.load_data()
prod = data["products"]
lookup = ui.product_lookup(data)
ss = st.session_state
PROFILES, CRITERIA = analysis.PROFILES, analysis.CRITERIA

ui.page_header(
    "Choose a product for your priorities",
    "Pick a customer profile, adjust what matters, and see which accelerator scores "
    "best, why, and what you give up.",
    step=2,
)

candidates = [p for p in ss["cmp_products"] if p in lookup.index]
if len(candidates) < 2:
    ui.empty_state(
        "Scoring needs at least two accelerators. Your comparison set has "
        f"{len(candidates)}. Add more in step 1.",
        link=(ui.P_COMPARE, "Compare products"), icon=":material/checklist:",
    )
    st.stop()

with st.container(horizontal=True, vertical_alignment="center", gap="small"):
    st.markdown(
        f"Scoring **{len(candidates)} accelerators** from your comparison set: "
        + ", ".join(lookup.loc[candidates, "product_name"])
    )
    st.page_link(ui.P_COMPARE, label="Change selection", icon=":material/edit:")

# ══════════════════════════════════════════════════════════════════════════════
# 1. Profile
# ══════════════════════════════════════════════════════════════════════════════

def _apply_profile_weights() -> None:
    for k, v in PROFILES[ss["str_profile"]].weights.items():
        ss[f"str_w_{k}"] = v


st.subheader("Customer profile", anchor=False)
profile_key = st.segmented_control(
    "Customer profile", list(PROFILES), key="str_profile", persist_state="session",
    format_func=lambda k: PROFILES[k].label, required=True,
    on_change=_apply_profile_weights, label_visibility="collapsed",
) or analysis.DEFAULT_PROFILE
profile = PROFILES[profile_key]
with st.container(border=True):
    st.markdown(f"**{profile.name}.** {profile.description}")
    with st.container(horizontal=True, gap="small"):
        st.markdown(":gray[Typical needs:]")
        for need in profile.needs:
            st.badge(need, color="gray")

# ══════════════════════════════════════════════════════════════════════════════
# 2. Priorities and price assumptions
# ══════════════════════════════════════════════════════════════════════════════
left, right = st.columns([3, 2], gap="large")
with left:
    with st.container(border=True):
        with st.container(horizontal=True, vertical_alignment="center"):
            st.markdown("**Priorities**")
            st.button("Reset to profile defaults", icon=":material/restart_alt:",
                      type="tertiary", on_click=_apply_profile_weights, key="str_reset_w")
        st.markdown(
            "Set each criterion's importance from 0 to 100. Changing the profile resets these."
        )
        weights: dict[str, float] = {}
        for key, crit in CRITERIA.items():
            weights[key] = st.slider(crit.label, 0, 100, key=f"str_w_{key}",
                                     persist_state="session", help=crit.help)

total_w = sum(weights.values())
with right:
    with st.container(border=True, height="stretch"):
        st.markdown("**Share of the final score**")
        if total_w == 0:
            st.error("All priorities are zero. Raise at least one to score the accelerators.",
                     icon=":material/error:")
        else:
            wdf = pd.DataFrame({
                "Criterion": [CRITERIA[k].label for k in weights],
                "Share": [w / total_w for w in weights.values()],
            }).sort_values("Share", ascending=False)
            st.dataframe(
                wdf, hide_index=True, height="content",
                column_config={"Share": st.column_config.ProgressColumn(
                    format="percent", min_value=0.0, max_value=1.0, width="medium")},
                alt="Normalized weight of each criterion",
            )
            st.markdown(":gray[Weights are rescaled to total 100%.]")

with st.container(border=True):
    with st.container(horizontal=True, vertical_alignment="center", gap="small"):
        st.markdown("**Hardware price assumptions**")
        st.badge("Assumed", icon=":material/tune:", color="orange")
    st.markdown(
        "USD thousands per accelerator. These are **your assumptions**, not list prices or "
        "vendor quotes. They feed the cost criterion and carry into deployment economics."
    )
    pcols = st.columns(min(len(candidates), 4), gap="medium")
    prices_usd = {}
    for i, pid in enumerate(candidates):
        prices_usd[pid] = pcols[i % len(pcols)].number_input(
            lookup.loc[pid, "product_name"], min_value=0.0, max_value=1000.0, step=1.0,
            format="%.1f", key=f"str_price_{pid}", persist_state="session",
            help=f"Assumed price per unit for {lookup.loc[pid, 'product_name']}, in USD thousands.",
        ) * 1000

if total_w == 0:
    st.stop()

# ══════════════════════════════════════════════════════════════════════════════
# 3. Results
# ══════════════════════════════════════════════════════════════════════════════
cand_df = prod[prod["product_id"].isin(candidates)]
metrics = analysis.product_metrics(cand_df, prices_usd)
scores = analysis.score_candidates(metrics, weights)
lead = analysis.leader_summary(scores, weights)

ss["str_result"] = {
    "product_id": lead["product_id"], "product_name": lead["product_name"],
    "score": lead["score"], "profile": profile.label,
    "table": scores.assign(profile=profile.name),
}

st.space("small")
with st.container(key="results"):
    st.header("Recommendation", anchor=False)
    st.markdown(
        "Scores are **relative**: each criterion is rescaled across the accelerators you're "
        "comparing, then weighted by your priorities. Changing priorities, prices, or the "
        "comparison set can change the ranking."
    )

    with st.container(border=True, key="leader_card"):
        st.markdown(":gray[Leading option]")
        with st.container(horizontal=True, vertical_alignment="center", gap="small"):
            st.subheader(lead["product_name"], anchor=False)
            ui.vendor_badge(lead["ticker"])
        m1, m2, m3 = st.columns(3)
        m1.metric("Weighted score", f"{lead['score']:.3f}",
                  help="0 to 1. Sum of each normalized criterion times its share of the score.")
        m2.metric("Data coverage", fmt_pct(lead["coverage"] * 100, 0),
                  help="Share of criteria with data for this product. Missing data scores zero.")
        m3.metric("Lead over next option",
                  f"{lead['gap']:.3f}" if lead["gap"] is not None else "—",
                  help=f"Score difference versus {lead['runner_up']}." if lead["runner_up"] else None)

        s_col, t_col = st.columns(2, gap="large")
        with s_col:
            st.markdown("**Main strengths**")
            if lead["strengths"]:
                for s in lead["strengths"]:
                    rank = f" (best of {lead['n_candidates']})" if s["rank"] == 1 else (
                        f" (#{s['rank']} of {lead['n_candidates']})" if s["rank"] else "")
                    st.markdown(f":material/check: **{s['label']}**: {s['value']}{rank}")
            else:
                st.markdown("No single criterion stands out; it leads on balance.")
        with t_col:
            st.markdown("**Main tradeoff**")
            t = lead["tradeoff"]
            if t is None:
                st.markdown("No significant weakness on the criteria you weighted.")
            elif t.get("missing"):
                st.markdown(f":material/remove: **{t['label']}**: no data, so it scores zero here.")
            else:
                rank = f" (#{t['rank']} of {lead['n_candidates']})" if t["rank"] else ""
                st.markdown(f":material/remove: **{t['label']}**: {t['value']}{rank}")

        if lead["close_call"]:
            st.warning(
                f"Only {lead['gap']:.3f} points ahead of {lead['runner_up']}. Small changes to "
                "priorities or prices could flip the result.",
                icon=":material/balance:", title="Close call",
            )

        with st.container(horizontal=True, gap="small"):
            if st.button(f"Evaluate {lead['product_name']}", type="primary",
                         icon=":material/payments:", key="str_eval_lead"):
                ui.carry_to_deployment(lead["product_id"], "Choose a product", prod)
                st.switch_page(ui.P_DEPLOY)

    # Alternatives
    st.subheader("All options", anchor=False)
    alt_df = pd.DataFrame({
        "Rank": range(1, len(scores) + 1),
        "Accelerator": scores["product_name"],
        "Vendor": scores["ticker"].map(vendor_name),
        "Score": scores["score"],
        "Data coverage": scores["coverage"],
        "Assumed price": scores["raw_cost"].map(fmt_usd),
    })
    st.dataframe(
        alt_df, hide_index=True, height="content",
        column_config={
            "Rank": st.column_config.NumberColumn(width="small"),
            "Score": st.column_config.ProgressColumn(format="%.3f", min_value=0.0, max_value=1.0),
            "Data coverage": st.column_config.NumberColumn(format="percent"),
        },
        alt="Weighted scores for every accelerator in the comparison set",
    )

    with st.container(horizontal=True, vertical_alignment="bottom"):
        other = st.selectbox(
            "Evaluate a different option", scores["product_id"].tolist(),
            format_func=lambda p: lookup.loc[p, "product_name"], key="str_eval_pick",
        )
        if st.button("Evaluate this accelerator", icon=":material/arrow_forward:",
                     key="str_eval_other"):
            ui.carry_to_deployment(other, "Choose a product", prod)
            st.switch_page(ui.P_DEPLOY)

st.divider()

with st.expander("Score breakdown by criterion", icon=":material/table_chart:"):
    st.markdown(
        "Each value is the product's position between the worst (0) and best (1) of the "
        "compared accelerators on that criterion. **Unavailable** means no data, which scores zero."
    )
    bd = pd.DataFrame({"Accelerator": scores["product_name"]})
    for k, c in CRITERIA.items():
        bd[c.label] = scores[f"n_{k}"]
    st.dataframe(
        bd, hide_index=True,
        column_config={c.label: st.column_config.NumberColumn(format="%.2f") for c in CRITERIA.values()},
        alt="Normalized criterion values per accelerator",
    )

with st.expander("Factors the score doesn't capture", icon=":material/psychology:"):
    st.markdown("""
- **Software ecosystem depth:** CUDA's library advantage (TensorRT, cuBLAS, Triton) is large and
  not fully captured by a 0–10 score. Teams without ROCm experience should budget validation
  time. Software scores are an analyst estimate from early 2025: NVIDIA 10/10, AMD MI300X 7/10.
- **Vendor support contracts:** enterprise SLAs differ significantly.
- **Supply availability:** H100 and H200 availability has historically been constrained.
- **Migration cost:** moving from CUDA to ROCm requires workload validation.

**What tends to change the result:** your price assumptions; a memory weight of about 35% or more
favors the MI300X (192 GB vs 80 or 141 GB); a software weight of about 25% or more favors NVIDIA.
""")

with st.expander("Scoring methodology", icon=":material/functions:"):
    st.markdown("""
**Formula:** `Score = Σ (normalized_metric_i × normalized_weight_i)` across criteria.

**Normalization** is min-max across the compared accelerators:
- Higher is better: `(value − min) / (max − min)`
- Lower is better (price): `(max − value) / (max − min)`
- When every product has the same value, all score 1.0 on that criterion.

**Missing data** contributes 0 for that criterion. It is not averaged or treated as neutral.
Data coverage shows the share of criteria with data.

**Software ecosystem** is a qualitative 0–10 judgment, not a measurement. Products without a
rating (previous generations) are treated as missing.
""")
