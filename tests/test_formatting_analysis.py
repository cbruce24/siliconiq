"""Tests for display formatting and scenario assembly (siliconiq.formatting / siliconiq.analysis)."""
import pandas as pd
import pytest

from siliconiq import analysis, calculations
from siliconiq.formatting import (
    DASH, fmt_date, fmt_num, fmt_pct, fmt_usd, fmt_years, status_label, workload_label,
)


# ── Formatting ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value,expected", [
    (950, "$950"),
    (2806, "$2.8K"),
    (25_000, "$25K"),
    (408_400, "$408K"),
    (1_090_000, "$1.09M"),
    (60_922_000_000, "$60.92B"),
    (-366_000, "−$366K"),
    (0, "$0"),
])
def test_fmt_usd_units(value, expected):
    assert fmt_usd(value) == expected


def test_fmt_usd_scale_from_millions():
    assert fmt_usd(60922, scale=1e6) == "$60.92B"


@pytest.mark.parametrize("missing", [None, float("nan")])
def test_missing_values_render_as_dash(missing):
    assert fmt_usd(missing) == DASH
    assert fmt_pct(missing) == DASH
    assert fmt_num(missing) == DASH
    assert fmt_years(missing) == DASH


def test_fmt_pct_sign_and_precision():
    assert fmt_pct(72.71) == "72.7%"
    assert fmt_pct(-4.0, 0) == "−4%"
    assert fmt_pct(126.0, 0, signed=True) == "+126%"


def test_fmt_num_separators_and_unit():
    assert fmt_num(51705) == "51,705"
    assert fmt_num(1307.4, 1, "TFLOPS") == "1,307.4 TFLOPS"


def test_fmt_years_singular():
    assert fmt_years(1.0) == "1.0 year"
    assert fmt_years(2.68) == "2.7 years"


def test_labels():
    assert fmt_date("2025-01-15") == "15 Jan 2025"
    assert status_label("current") == "Latest generation"
    assert workload_label("LLM_inference") == "LLM inference"


# ── Scoring assembly ──────────────────────────────────────────────────────────

def _products():
    return pd.DataFrame([
        {"product_id": "A", "product_name": "Alpha", "ticker": "NVDA",
         "fp16_tflops": 1000.0, "tdp_watts": 700.0, "memory_gb": 80.0},
        {"product_id": "B", "product_name": "Beta", "ticker": "AMD",
         "fp16_tflops": 1300.0, "tdp_watts": 750.0, "memory_gb": 192.0},
        {"product_id": "C", "product_name": "Gamma", "ticker": "NVDA",
         "fp16_tflops": 750.0, "tdp_watts": 350.0, "memory_gb": float("nan")},
    ])


def test_product_metrics_derives_power_efficiency_and_missing_memory():
    m = {d["product_id"]: d for d in analysis.product_metrics(_products(), {"A": 30e3, "B": 25e3})}
    assert m["A"]["power_efficiency"] == pytest.approx(1000 / 700)
    assert m["C"]["memory_gb"] is None
    assert m["C"]["cost"] is None


def test_score_candidates_matches_calculations_and_sorts():
    weights = {"cost": 35, "performance_fp16": 25, "memory_gb": 15,
               "power_efficiency": 15, "software_compat": 10}
    metrics = analysis.product_metrics(_products(), {"A": 30e3, "B": 25e3, "C": 20e3})
    scores = analysis.score_candidates(metrics, weights)
    assert list(scores["score"]) == sorted(scores["score"], reverse=True)
    for _, row in scores.iterrows():
        pm = next(p for p in metrics if p["product_id"] == row["product_id"])
        direct = calculations.score_product(pm, metrics, weights, analysis.HIGHER_IS_BETTER)
        assert row["score"] == direct["score"]
        assert row["coverage"] == direct["coverage"]


def test_leader_summary_flags_missing_data_as_tradeoff():
    weights = {"cost": 0, "performance_fp16": 0, "memory_gb": 50,
               "power_efficiency": 50, "software_compat": 0}
    metrics = analysis.product_metrics(_products(), {})
    scores = analysis.score_candidates(metrics, weights)
    lead = analysis.leader_summary(scores, weights)
    assert lead["product_name"] == scores.iloc[0]["product_name"]
    assert lead["gap"] == pytest.approx(scores.iloc[0]["score"] - scores.iloc[1]["score"])
    gamma = analysis.leader_summary(scores[scores["product_id"] == "C"].reset_index(drop=True), weights)
    assert gamma["tradeoff"]["missing"] is True


def test_profiles_use_known_criteria():
    for p in analysis.PROFILES.values():
        assert set(p.weights) == set(analysis.CRITERIA)


# ── Deployment and vendor wiring ──────────────────────────────────────────────

BASE = {
    "num_acc": 8, "hw_price": 30_000.0, "infra_cost": 100_000.0, "utilization": 65,
    "tdp": 700.0, "elec_price": 0.08, "facility_oh": 10.0, "annual_support": 20_000.0,
    "deploy_years": 3, "discount_rate": 0.10, "annual_value": 500_000.0,
}


def test_run_deployment_matches_calculations():
    tco, roi = analysis.run_deployment(BASE)
    direct = calculations.deployment_tco(8, 30_000.0, 100_000.0, 65, 700.0, 0.08, 10.0, 20_000.0, 3)
    assert tco == direct
    assert roi["npv"] == pytest.approx(
        calculations.deployment_roi(direct, 500_000.0, 0.10, 3)["npv"])


def test_npv_grid_includes_current_utilization_and_matches_headline():
    p = {**BASE, "utilization": 65}
    grid = analysis.deployment_npv_grid(p)
    cur = grid[grid["is_current"]]
    assert len(cur) == 1
    assert cur.iloc[0]["npv"] == pytest.approx(analysis.run_deployment(p)[1]["npv"])


def test_cash_flow_table_cumulative_matches_flows():
    tco, roi = analysis.run_deployment(BASE)
    t = analysis.deployment_cash_flow_table(roi, tco, BASE["annual_value"])
    assert len(t) == BASE["deploy_years"] + 1
    assert t["Cumulative cash flow"].iloc[-1] == pytest.approx(sum(roi["cash_flows"]))


def test_vendor_scenarios_base_equals_direct_model():
    v = {"selling_price": 25e3, "unit_cost": 10e3, "fixed_dev": 500e6, "annual_opex": 50e6,
         "base_demand": 50_000, "demand_growth": 20.0, "model_years": 5, "discount_rate": 0.12}
    res = analysis.run_vendor_scenarios(v)
    direct = calculations.vendor_model(50_000, 25e3, 10e3, 500e6, 50e6, 20.0, 5, 0.12)
    assert res["base"]["project_npv"] == pytest.approx(direct["project_npv"])
    assert res["downside"]["project_npv"] < res["base"]["project_npv"] < res["upside"]["project_npv"]
    grid = analysis.vendor_npv_grid(v)
    assert grid[grid["is_current"]]["npv"].iloc[0] == pytest.approx(direct["project_npv"])


# ── Sourced findings ──────────────────────────────────────────────────────────

def test_key_takeaways_against_bundled_dataset(tmp_path):
    from siliconiq import queries
    from siliconiq.db import get_connection
    from siliconiq.ingest import run_ingest
    db = tmp_path / "siliconiq.db"
    run_ingest(db_path=db)
    conn = get_connection(db)
    try:
        t = analysis.key_takeaways(queries.get_products(conn), queries.get_benchmarks(conn),
                                   queries.get_financials(conn))
    finally:
        conn.close()
    assert len(t) == 3
    for item in t:
        assert {"headline", "detail", "qualifier", "source"} <= set(item)
    assert "Llama2-70B" in t[0]["headline"]
