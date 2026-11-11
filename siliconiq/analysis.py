"""
Scenario assembly and derived findings for the dashboard.

This module wires user inputs into the unchanged formulas in `calculations.py`
and derives sourced findings from the dataset. It has no Streamlit dependency,
so every function here is unit-testable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from siliconiq import calculations
from siliconiq.formatting import (
    fmt_num, fmt_pct, fmt_usd, is_missing, vendor_name, workload_label,
)

# ══════════════════════════════════════════════════════════════════════════════
# Customer strategy: profiles, criteria, scoring
# ══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Profile:
    key: str
    label: str            # short label for the selector
    name: str             # full name
    description: str
    needs: tuple[str, ...]
    weights: dict


PROFILES: dict[str, Profile] = {
    "startup": Profile(
        key="startup",
        label="Startup inference",
        name="Startup (Inference, Budget-Constrained)",
        description=(
            "A small team deploying LLM inference on a constrained budget. "
            "Has CUDA experience but is open to ROCm."
        ),
        needs=("Low purchase price", "Good inference throughput", "Power efficiency"),
        weights={"cost": 35, "performance_fp16": 25, "memory_gb": 15,
                 "power_efficiency": 15, "software_compat": 10},
    ),
    "enterprise": Profile(
        key="enterprise",
        label="Enterprise production",
        name="Enterprise (Production AI)",
        description=(
            "A large organization scaling production AI services. Software ecosystem "
            "maturity and vendor support matter as much as raw performance."
        ),
        needs=("Peak throughput", "Mature software ecosystem", "Balanced cost"),
        weights={"cost": 20, "performance_fp16": 30, "memory_gb": 15,
                 "power_efficiency": 15, "software_compat": 20},
    ),
    "research": Profile(
        key="research",
        label="Research training",
        name="Research (Large-Model Training)",
        description=(
            "A research lab training models with 70B+ parameters. Memory capacity and "
            "bandwidth are the binding constraint; cost is secondary."
        ),
        needs=("Memory capacity", "Software ecosystem", "Compute throughput"),
        weights={"cost": 10, "performance_fp16": 20, "memory_gb": 35,
                 "power_efficiency": 10, "software_compat": 25},
    ),
}
DEFAULT_PROFILE = "startup"


@dataclass(frozen=True)
class Criterion:
    key: str
    label: str
    help: str
    higher_is_better: bool


CRITERIA: dict[str, Criterion] = {
    "cost": Criterion(
        "cost", "Purchase price",
        "Your assumed price per accelerator. Lower is better.", False),
    "performance_fp16": Criterion(
        "performance_fp16", "Peak FP16 compute",
        "Dense (non-sparse) FP16 TFLOPS from official spec sheets. Higher is better.", True),
    "memory_gb": Criterion(
        "memory_gb", "Memory capacity",
        "On-package HBM capacity in GB. Higher is better.", True),
    "power_efficiency": Criterion(
        "power_efficiency", "Power efficiency",
        "Peak FP16 TFLOPS per watt of TDP. Higher is better.", True),
    "software_compat": Criterion(
        "software_compat", "Software ecosystem",
        "Analyst estimate on a 0–10 scale (early 2025), not a measured value. Higher is better.", True),
}
HIGHER_IS_BETTER = {k: c.higher_is_better for k, c in CRITERIA.items()}

# Software compatibility scores (qualitative, 0–10 scale).
# Rationale: published framework support lists, community metrics, and enterprise
# deployment maturity as of early 2025. Products without an entry are scored as
# missing data (coverage penalty), consistent with the scoring model.
SW_SCORES = {
    "NVDA_H100_SXM5": 10,  # CUDA: dominant; largest optimized library ecosystem
    "NVDA_H100_PCIE": 10,  # Same CUDA ecosystem as SXM5
    "NVDA_H200_SXM5": 10,  # Same CUDA ecosystem, newer HBM3e variant
    "AMD_MI300X":      7,  # ROCm: improved significantly; PyTorch/vLLM support growing
}


def default_price_k(ticker: str) -> float:
    """Default assumed price per unit, USD thousands. A placeholder, not a list price."""
    return 25.0 if ticker == "AMD" else 30.0


def product_metrics(prod_df: pd.DataFrame, prices_usd: dict[str, float]) -> list[dict]:
    """Build the per-product metric dicts consumed by calculations.score_product."""
    out = []
    for _, row in prod_df.iterrows():
        pid = row["product_id"]
        fp16 = None if is_missing(row["fp16_tflops"]) or not row["fp16_tflops"] else float(row["fp16_tflops"])
        tdp = None if is_missing(row["tdp_watts"]) or not row["tdp_watts"] else float(row["tdp_watts"])
        power_eff = (fp16 / tdp) if (fp16 and tdp and tdp > 0) else None
        mem = None if is_missing(row["memory_gb"]) else float(row["memory_gb"])
        out.append({
            "product_id": pid,
            "product_name": row["product_name"],
            "ticker": row["ticker"],
            "tdp_watts": tdp,
            "cost": prices_usd.get(pid),
            "performance_fp16": fp16,
            "memory_gb": mem,
            "power_efficiency": power_eff,
            "software_compat": SW_SCORES.get(pid),
        })
    return out


def score_candidates(metrics: list[dict], weights: dict[str, float]) -> pd.DataFrame:
    """Score every candidate. Returns one row per product, best first.

    Columns: product_id, product_name, ticker, score, coverage, and for each
    criterion `n_<criterion>` (normalized 0–1 or None) and `raw_<criterion>`.
    """
    rows = []
    for pm in metrics:
        res = calculations.score_product(pm, metrics, weights, HIGHER_IS_BETTER)
        row = {
            "product_id": pm["product_id"],
            "product_name": pm["product_name"],
            "ticker": pm["ticker"],
            "score": res["score"],
            "coverage": res["coverage"],
        }
        for crit in weights:
            bd = res["breakdown"].get(crit, {})
            row[f"n_{crit}"] = bd.get("normalized")
            row[f"w_{crit}"] = bd.get("weighted")
            row[f"raw_{crit}"] = pm.get(crit)
        rows.append(row)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values("score", ascending=False, kind="stable").reset_index(drop=True)


def fmt_criterion_value(crit: str, v) -> str:
    if is_missing(v):
        return "Unavailable"
    if crit == "cost":
        return fmt_usd(v)
    if crit == "performance_fp16":
        return fmt_num(v, 1, "TFLOPS")
    if crit == "memory_gb":
        return fmt_num(v, 0, "GB")
    if crit == "power_efficiency":
        return fmt_num(v, 2, "TFLOPS/W")
    if crit == "software_compat":
        return f"{fmt_num(v, 0)}/10"
    return str(v)


def leader_summary(scores: pd.DataFrame, weights: dict[str, float]) -> dict:
    """Explain the top-ranked option: strengths, main tradeoff, and margin to #2."""
    best = scores.iloc[0]
    active = [c for c, w in weights.items() if w > 0]

    def rank_of(crit: str) -> Optional[int]:
        col = scores[f"n_{crit}"]
        if is_missing(best[f"n_{crit}"]):
            return None
        return int((col.dropna() > best[f"n_{crit}"]).sum()) + 1

    scored = [c for c in active if not is_missing(best[f"n_{c}"])]
    by_contrib = sorted(scored, key=lambda c: best[f"w_{c}"], reverse=True)
    strengths = []
    for c in by_contrib:
        if best[f"n_{c}"] >= 0.5 and len(strengths) < 2:
            strengths.append({
                "criterion": c, "label": CRITERIA[c].label,
                "value": fmt_criterion_value(c, best[f"raw_{c}"]),
                "rank": rank_of(c),
            })

    missing = [c for c in active if is_missing(best[f"n_{c}"])]
    tradeoff = None
    if missing:
        c = missing[0]
        tradeoff = {"criterion": c, "label": CRITERIA[c].label, "value": "Unavailable",
                    "rank": None, "missing": True}
    elif scored:
        c = min(scored, key=lambda c: best[f"n_{c}"])
        if best[f"n_{c}"] < 0.8:
            tradeoff = {"criterion": c, "label": CRITERIA[c].label,
                        "value": fmt_criterion_value(c, best[f"raw_{c}"]),
                        "rank": rank_of(c), "missing": False}

    gap = None
    runner_up = None
    if len(scores) > 1:
        runner_up = scores.iloc[1]["product_name"]
        gap = float(best["score"] - scores.iloc[1]["score"])

    return {
        "product_id": best["product_id"],
        "product_name": best["product_name"],
        "ticker": best["ticker"],
        "score": float(best["score"]),
        "coverage": float(best["coverage"]),
        "strengths": strengths,
        "tradeoff": tradeoff,
        "runner_up": runner_up,
        "gap": gap,
        "close_call": gap is not None and gap < 0.05,
        "n_candidates": len(scores),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Deployment economics
# ══════════════════════════════════════════════════════════════════════════════

def run_deployment(p: dict) -> tuple[dict, dict]:
    """p uses dollars and a decimal discount rate. Returns (tco, roi)."""
    tco = calculations.deployment_tco(
        p["num_acc"], p["hw_price"], p["infra_cost"], p["utilization"], p["tdp"],
        p["elec_price"], p["facility_oh"], p["annual_support"], p["deploy_years"],
    )
    roi = calculations.deployment_roi(tco, p["annual_value"], p["discount_rate"], p["deploy_years"])
    return tco, roi


VALUE_MULTIPLIERS = [0.5, 0.75, 1.0, 1.25, 1.5]


def deployment_npv_grid(p: dict) -> pd.DataFrame:
    """NPV across utilization × annual value, same formulas as the headline results.
    The current utilization is always included as a column."""
    utils = sorted(set(range(20, 101, 20)) | {int(p["utilization"])})
    values = [p["annual_value"] * m for m in VALUE_MULTIPLIERS]

    def cell(params):
        return run_deployment(params)[1]["npv"]

    grid = calculations.sensitivity_heatmap(
        p, "utilization", "annual_value", [float(u) for u in utils], values, cell)
    rows = []
    for yi, m in enumerate(VALUE_MULTIPLIERS):
        for xi, u in enumerate(utils):
            rows.append({
                "utilization": u, "value_mult": m, "annual_value": values[yi],
                "npv": grid[yi][xi],
                "is_current": (u == int(p["utilization"]) and m == 1.0),
            })
    return pd.DataFrame(rows)


def deployment_cash_flow_table(roi: dict, tco: dict, annual_value: float) -> pd.DataFrame:
    flows = roi["cash_flows"]
    r = roi["discount_rate"]
    rows, cum, cum_disc = [], 0.0, 0.0
    for t, cf in enumerate(flows):
        disc = cf / (1 + r) ** t
        cum += cf
        cum_disc += disc
        rows.append({
            "Year": t,
            "Business value": 0.0 if t == 0 else annual_value,
            "Capital cost": tco["total_capex"] if t == 0 else 0.0,
            "Operating cost": 0.0 if t == 0 else tco["annual_opex"],
            "Net cash flow": cf,
            "Cumulative cash flow": cum,
            "Discounted cash flow": disc,
            "Cumulative discounted": cum_disc,
        })
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
# Vendor investment
# ══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Scenario:
    key: str
    label: str
    demand_mult: float
    price_mult: float

    @property
    def description(self) -> str:
        return f"{self.demand_mult:g}× demand · {self.price_mult:g}× price"


VENDOR_SCENARIOS = (
    Scenario("downside", "Downside", 0.6, 0.9),
    Scenario("base", "Base case", 1.0, 1.0),
    Scenario("upside", "Upside", 1.4, 1.1),
)


def run_vendor_scenarios(v: dict) -> dict[str, dict]:
    """v uses dollars and a decimal discount rate."""
    out = {}
    for s in VENDOR_SCENARIOS:
        out[s.key] = calculations.vendor_model(
            unit_demand=v["base_demand"] * s.demand_mult,
            selling_price=v["selling_price"] * s.price_mult,
            unit_cost=v["unit_cost"],
            fixed_dev_investment=v["fixed_dev"],
            annual_operating_cost=v["annual_opex"],
            demand_growth_pct=v["demand_growth"],
            years=v["model_years"],
            discount_rate=v["discount_rate"],
        )
    return out


PRICE_MULTIPLIERS = [0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2]
DEMAND_MULTIPLIERS = [0.5, 0.75, 1.0, 1.25, 1.5]


def vendor_npv_grid(v: dict) -> pd.DataFrame:
    prices = [v["selling_price"] * m for m in PRICE_MULTIPLIERS]
    demands = [v["base_demand"] * m for m in DEMAND_MULTIPLIERS]

    def cell(p):
        return calculations.vendor_model(
            unit_demand=p["unit_demand"], selling_price=p["selling_price"],
            unit_cost=v["unit_cost"], fixed_dev_investment=v["fixed_dev"],
            annual_operating_cost=v["annual_opex"], demand_growth_pct=v["demand_growth"],
            years=v["model_years"], discount_rate=v["discount_rate"],
        )["project_npv"]

    grid = calculations.sensitivity_heatmap(
        {"unit_demand": v["base_demand"], "selling_price": v["selling_price"]},
        "selling_price", "unit_demand", prices, demands, cell,
    )
    rows = []
    for yi, dm in enumerate(DEMAND_MULTIPLIERS):
        for xi, pm in enumerate(PRICE_MULTIPLIERS):
            rows.append({
                "price_mult": pm, "selling_price": prices[xi],
                "demand_mult": dm, "unit_demand": demands[yi],
                "npv": grid[yi][xi], "is_current": pm == 1.0 and dm == 1.0,
            })
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
# Sourced findings for the overview
# ══════════════════════════════════════════════════════════════════════════════

def latest_fiscal_years(fin: pd.DataFrame) -> pd.DataFrame:
    """Latest fiscal year per company with YoY revenue growth."""
    rows = []
    for ticker, g in fin.sort_values("period_end").groupby("ticker"):
        last = g.iloc[-1]
        prior = g.iloc[-2] if len(g) > 1 else None
        growth = (calculations.yoy_growth(last["revenue"], prior["revenue"])
                  if prior is not None else None)
        rows.append({**last.to_dict(), "yoy_growth_pct": growth})
    return pd.DataFrame(rows)


def key_takeaways(prod: pd.DataFrame, bench: pd.DataFrame, fin: pd.DataFrame) -> list[dict]:
    """Derive a few qualified findings from sourced data. Each has a headline,
    a supporting detail, a qualifier, and a source label."""
    out: list[dict] = []

    # 1) Measured vs peak — comparable MLPerf results across vendors
    comp = bench[bench["comparability"] == "comparable"]
    if not comp.empty:
        groups = comp.groupby(["workload", "model_name", "precision", "benchmark_version"])
        cands = [(k, g) for k, g in groups if g["ticker"].nunique() >= 2]
        if cands:
            cands.sort(key=lambda kg: (kg[0][0] != "LLM_inference", str(kg[0][3])), reverse=False)
            (wl, model, prec, ver), g = cands[0]
            g = g.sort_values("result", ascending=False)
            top, nxt = g.iloc[0], g.iloc[1]
            lead = (top["result"] / nxt["result"] - 1) * 100 if nxt["result"] else None
            detail = (
                f"{top['product_name']} reached {fmt_num(top['result'])} {top['result_unit']} vs "
                f"{fmt_num(nxt['result'])} for {nxt['product_name']}, "
                f"in {int(top['num_accelerators'])}-accelerator systems."
            )
            peak = prod.set_index("product_name")["fp16_tflops"]
            qualifier = "Vendor-optimized submissions. Results depend on the software stack and system configuration."
            if (top["product_name"] in peak and nxt["product_name"] in peak
                    and peak[nxt["product_name"]] > peak[top["product_name"]]):
                qualifier = (
                    f"{nxt['product_name']} has the higher peak FP16 spec "
                    f"({fmt_num(peak[nxt['product_name']], 0)} vs {fmt_num(peak[top['product_name']], 0)} TFLOPS), "
                    "so peak specifications alone don't predict measured throughput. " + qualifier
                )
            out.append({
                "headline": (
                    f"{vendor_name(top['ticker'])} leads measured {model} throughput by "
                    f"{fmt_pct(lead, 0)}" if lead is not None else f"{model} results"
                ),
                "detail": detail,
                "qualifier": qualifier,
                "source": f"MLPerf Inference v{ver} · {workload_label(wl)} · {prec}",
            })

    # 2) Memory capacity among latest-generation products
    cur = prod[prod["status"] == "current"].dropna(subset=["memory_gb"])
    if len(cur) >= 2:
        cur = cur.sort_values(["memory_gb", "memory_bandwidth_tbps"], ascending=False)
        a, b = cur.iloc[0], cur.iloc[1]
        out.append({
            "headline": f"{a['product_name']} has the most memory per accelerator",
            "detail": (
                f"{fmt_num(a['memory_gb'])} GB at {fmt_num(a['memory_bandwidth_tbps'], 2)} TB/s, vs "
                f"{fmt_num(b['memory_gb'])} GB at {fmt_num(b['memory_bandwidth_tbps'], 2)} TB/s for {b['product_name']}."
            ),
            "qualifier": "Among latest-generation products in the dataset. Capacity matters most when a model doesn't fit on fewer devices.",
            "source": "Official product specification sheets",
        })

    # 3) Financial scale
    if not fin.empty:
        lf = latest_fiscal_years(fin).set_index("ticker")
        if {"NVDA", "AMD"} <= set(lf.index):
            n, a = lf.loc["NVDA"], lf.loc["AMD"]
            out.append({
                "headline": (
                    f"NVIDIA revenue grew {fmt_pct(n['yoy_growth_pct'], 0)} in {n['fiscal_label']}"
                ),
                "detail": (
                    f"NVIDIA {n['fiscal_label']}: {fmt_usd(n['revenue'], scale=1e6)} revenue, "
                    f"{fmt_pct(n['gross_margin_pct'])} gross margin. AMD {a['fiscal_label']}: "
                    f"{fmt_usd(a['revenue'], scale=1e6)} revenue "
                    f"({fmt_pct(a['yoy_growth_pct'], 0, signed=True)} YoY), "
                    f"{fmt_pct(a['gross_margin_pct'])} gross margin."
                ),
                "qualifier": "Company-wide figures, not AI accelerator revenue. Fiscal years end in late January (NVIDIA) and late December (AMD).",
                "source": "SEC Form 10-K filings",
            })
    return out


# ══════════════════════════════════════════════════════════════════════════════
# Export
# ══════════════════════════════════════════════════════════════════════════════

TCO_KEYS = [
    "hw_capex", "infra_cost", "total_capex", "active_watts", "facility_watts",
    "kwh_per_year", "annual_power_cost", "annual_support_cost", "annual_opex",
    "total_opex", "total_tco", "deployment_years",
]


def build_session_workbook(
    data: dict[str, pd.DataFrame],
    *,
    scoring_df: pd.DataFrame | None = None,
    deployment: tuple[dict, dict] | None = None,
    vendor: tuple[dict, dict] | None = None,
) -> bytes:
    """Build one workbook from whatever analyses the user has run this session.
    Sections that haven't been run are filled with clearly labeled placeholders."""
    from siliconiq import export

    if deployment is not None:
        tco, roi = deployment
    else:
        tco = {k: 0.0 for k in TCO_KEYS}
        roi = {"cash_flows": [], "total_value": 0.0, "net_benefit": 0.0,
               "roi_pct": None, "payback_years": None, "npv": 0.0, "discount_rate": 0.0}
    if vendor is not None:
        vres, vassume = vendor
    else:
        vres = {"total_revenue": 0.0, "total_cogs": 0.0, "net_profit": 0.0,
                "project_roi_pct": None, "project_npv": 0.0, "contribution_margin": 0.0,
                "cm_pct": None, "break_even_units": None, "discount_rate": 0.0,
                "cash_flows": []}
        vassume = {"note": "No vendor model run — use the Vendor investment page."}
    if scoring_df is None:
        scoring_df = pd.DataFrame({"note": ["Visit Choose a product to generate scores"]})

    return export.build_workbook(
        financials_df=data["financials"],
        segment_df=data["segments"],
        products_df=data["products"],
        benchmarks_df=data["benchmarks"],
        scoring_df=scoring_df,
        tco_dict=tco,
        roi_dict=roi,
        vendor_model_result=vres,
        vendor_assumptions=vassume,
        sources_df=data["sources"],
    )
