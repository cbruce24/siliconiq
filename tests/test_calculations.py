"""
Focused tests for all calculation functions.
Hand-checkable examples are included inline.
"""
import math
import pytest
from siliconiq.calculations import (
    gross_margin, operating_margin, rd_pct_revenue, yoy_growth,
    npv, payback_period, roi_pct,
    deployment_tco, deployment_roi, cost_per_token,
    vendor_model, normalize_weights, score_product, sensitivity_heatmap,
)


# ── Financial ratios ──────────────────────────────────────────────────────────

def test_gross_margin_basic():
    # 70% gross margin: 7000 gross profit on 10000 revenue
    assert gross_margin(7000, 10000) == pytest.approx(70.0)

def test_gross_margin_zero_revenue():
    assert gross_margin(100, 0) is None

def test_gross_margin_negative_revenue():
    assert gross_margin(100, -50) is None

def test_operating_margin_basic():
    # 30% operating margin
    assert operating_margin(3000, 10000) == pytest.approx(30.0)

def test_operating_margin_zero_revenue():
    assert operating_margin(500, 0) is None

def test_rd_pct_revenue_basic():
    # NVDA FY2024: R&D 8675 / revenue 60922 ≈ 14.24%
    result = rd_pct_revenue(8675, 60922)
    assert result == pytest.approx(8675 / 60922 * 100, rel=1e-4)

def test_rd_pct_revenue_zero_revenue():
    assert rd_pct_revenue(1000, 0) is None

def test_yoy_growth_basic():
    # 100% growth: 200 from 100
    assert yoy_growth(200, 100) == pytest.approx(100.0)

def test_yoy_growth_negative():
    # -50% decline
    assert yoy_growth(50, 100) == pytest.approx(-50.0)

def test_yoy_growth_zero_prior():
    assert yoy_growth(100, 0) is None

def test_yoy_growth_negative_prior():
    assert yoy_growth(100, -10) is None


# ── NPV ───────────────────────────────────────────────────────────────────────

def test_npv_simple():
    # Year 0: -1000, Year 1: 1100 at 10% → NPV = -1000 + 1100/1.1 = 0
    result = npv([-1000, 1100], 0.10)
    assert result == pytest.approx(0.0, abs=1e-6)

def test_npv_multi_period():
    # -100 now, +50 year1, +60 year2 at 5%
    # -100 + 50/1.05 + 60/1.1025 = -100 + 47.619 + 54.422 = 2.041
    result = npv([-100, 50, 60], 0.05)
    expected = -100 + 50 / 1.05 + 60 / 1.05 ** 2
    assert result == pytest.approx(expected, rel=1e-6)

def test_npv_zero_rate():
    # At 0% discount, NPV = sum of cash flows
    result = npv([-100, 40, 40, 40], 0.0)
    assert result == pytest.approx(20.0)

def test_npv_invalid_rate():
    with pytest.raises(ValueError):
        npv([-100, 50], -2.0)


# ── Payback period ────────────────────────────────────────────────────────────

def test_payback_basic():
    # 1M investment, 500K annual benefit → 2 years
    assert payback_period(500_000, 1_000_000) == pytest.approx(2.0)

def test_payback_zero_benefit():
    assert payback_period(0, 1_000_000) is None

def test_payback_negative_benefit():
    assert payback_period(-100, 1_000_000) is None

def test_payback_zero_investment():
    assert payback_period(100, 0) is None


# ── ROI % ─────────────────────────────────────────────────────────────────────

def test_roi_pct_basic():
    # Net benefit 50K on 200K investment = 25%
    assert roi_pct(50_000, 200_000) == pytest.approx(25.0)

def test_roi_pct_negative_benefit():
    # -20K net on 100K investment = -20%
    assert roi_pct(-20_000, 100_000) == pytest.approx(-20.0)

def test_roi_pct_zero_investment():
    assert roi_pct(100, 0) is None


# ── Deployment TCO ────────────────────────────────────────────────────────────

def test_tco_basic():
    """
    8 accelerators × $25K = $200K HW
    Infra = $50K → CapEx = $250K
    TDP = 700W, util = 100% → 5600W active
    Facility overhead 0% → facility = 5600W
    kWh/year = 5600 * 8760 / 1000 = 49056 kWh
    @$0.08/kWh → $3924.48/year
    Support = $0
    Annual OpEx = $3924.48
    Total TCO (3 years) = $250K + 3 * $3924.48 = $261773.44
    """
    t = deployment_tco(8, 25_000, 50_000, 100, 700, 0.08, 0, 0, 3)
    assert t["hw_capex"] == pytest.approx(200_000)
    assert t["total_capex"] == pytest.approx(250_000)
    assert t["active_watts"] == pytest.approx(5600)
    kwh = 5600 * 8760 / 1000
    assert t["kwh_per_year"] == pytest.approx(kwh, rel=1e-4)
    assert t["annual_power_cost"] == pytest.approx(kwh * 0.08, rel=1e-4)

def test_tco_zero_utilization():
    t = deployment_tco(8, 25_000, 0, 0, 700, 0.08, 0, 0, 3)
    assert t["active_watts"] == 0.0
    assert t["annual_power_cost"] == pytest.approx(0.0)

def test_tco_facility_overhead():
    # 10% facility overhead: facility_watts = active * 1.1
    t = deployment_tco(1, 0, 0, 100, 1000, 0.10, 10, 0, 1)
    assert t["facility_watts"] == pytest.approx(1100)

def test_tco_invalid_utilization():
    with pytest.raises(ValueError):
        deployment_tco(8, 25_000, 0, 150, 700, 0.08, 0, 0, 3)

def test_tco_invalid_years():
    with pytest.raises(ValueError):
        deployment_tco(8, 25_000, 0, 50, 700, 0.08, 0, 0, 0)


# ── Deployment ROI ────────────────────────────────────────────────────────────

def test_deployment_roi_basic():
    """
    Simple case: capex=100K, annual_opex=10K, annual_value=50K, 2 years, 0% discount
    Net benefit = 50K*2 - (100K + 10K*2) = 100K - 120K = -20K
    """
    t = {
        "total_capex": 100_000, "annual_opex": 10_000,
        "total_opex": 20_000, "total_tco": 120_000,
        "annual_support_cost": 0, "annual_power_cost": 10_000,
        "hw_capex": 100_000, "infra_cost": 0,
        "active_watts": 0, "facility_watts": 0,
        "kwh_per_year": 0, "deployment_years": 2,
    }
    r = deployment_roi(t, 50_000, 0.0, 2)
    assert r["net_benefit"] == pytest.approx(-20_000)
    assert r["npv"] == pytest.approx(-20_000)   # 0% rate = simple sum

def test_payback_never_occurs():
    """Annual value < annual OpEx → payback never occurs."""
    t = {
        "total_capex": 100_000, "annual_opex": 60_000,
        "total_opex": 300_000, "total_tco": 400_000,
        "annual_support_cost": 0, "annual_power_cost": 60_000,
        "hw_capex": 100_000, "infra_cost": 0,
        "active_watts": 0, "facility_watts": 0, "kwh_per_year": 0, "deployment_years": 5,
    }
    r = deployment_roi(t, 50_000, 0.10, 5)
    assert r["payback_years"] is None


# ── Cost per token ────────────────────────────────────────────────────────────

def test_cost_per_token_basic():
    """
    Annual OpEx = $1M, throughput = 1000 tok/s, utilization = 100%
    tokens/year = 1000 * 3600 * 8760 = 31,536,000,000
    cost per 1M tokens = 1,000,000 / 31,536,000,000 * 1,000,000 = $0.03170
    """
    result = cost_per_token(1_000_000, 1000, 100)
    expected = 1_000_000 / (1000 * 3600 * 8760) * 1_000_000
    assert result == pytest.approx(expected, rel=1e-4)

def test_cost_per_token_zero_utilization():
    assert cost_per_token(1_000_000, 1000, 0) is None

def test_cost_per_token_zero_throughput():
    assert cost_per_token(1_000_000, 0, 50) is None


# ── Vendor model ──────────────────────────────────────────────────────────────

def test_vendor_model_break_even():
    """
    price=$20, cost=$10, fixed_dev=$100, annual_opex=$0, demand=5 units, 1 year, 0% rate
    contribution_margin = $10/unit
    break_even = ($100 + $0) / $10 = 10 units
    """
    r = vendor_model(5, 20, 10, 100, 0, 0, 1, 0.0)
    assert r["contribution_margin"] == pytest.approx(10.0)
    assert r["break_even_units"] == pytest.approx(10.0)

def test_vendor_model_zero_margin():
    """When price == cost, break_even should be None (infinite)."""
    r = vendor_model(1000, 10, 10, 100, 0, 0, 1, 0.1)
    assert r["break_even_units"] is None

def test_vendor_model_negative_margin():
    """Selling below cost — no break-even."""
    r = vendor_model(1000, 5, 10, 100, 0, 0, 1, 0.1)
    assert r["break_even_units"] is None
    assert r["contribution_margin"] < 0

def test_vendor_model_demand_growth():
    """With 100% annual growth: year2 demand = 2× year1."""
    r = vendor_model(100, 10, 5, 0, 0, 100, 2, 0.0)
    # Year1: 100 * 10 = 1000, Year2: 200 * 10 = 2000
    assert r["total_revenue"] == pytest.approx(3000.0)


# ── Normalize weights ─────────────────────────────────────────────────────────

def test_normalize_weights_basic():
    w = normalize_weights({"a": 1, "b": 3})
    assert w["a"] == pytest.approx(0.25)
    assert w["b"] == pytest.approx(0.75)
    assert sum(w.values()) == pytest.approx(1.0)

def test_normalize_weights_zero_total():
    with pytest.raises(ValueError):
        normalize_weights({"a": 0, "b": 0})

def test_normalize_weights_negative_total():
    with pytest.raises(ValueError):
        normalize_weights({"a": -1, "b": -2})


# ── Score product ─────────────────────────────────────────────────────────────

def test_score_product_missing_penalized():
    """Product with missing metric should score lower than product with value."""
    products = [
        {"perf": 100.0, "mem": 80.0},
        {"perf": None,  "mem": 80.0},  # missing perf
    ]
    weights = {"perf": 0.5, "mem": 0.5}
    higher = {"perf": True, "mem": True}
    s0 = score_product(products[0], products, weights, higher)
    s1 = score_product(products[1], products, weights, higher)
    assert s0["score"] > s1["score"]

def test_score_product_all_equal():
    """When all products have the same value, normalized = 1.0 for all."""
    products = [{"perf": 100.0}, {"perf": 100.0}]
    weights = {"perf": 1.0}
    higher = {"perf": True}
    s0 = score_product(products[0], products, weights, higher)
    assert s0["score"] == pytest.approx(1.0)

def test_score_product_coverage():
    """Coverage reflects ratio of non-missing metrics."""
    products = [{"a": 1.0, "b": None, "c": 3.0}]
    weights = {"a": 0.33, "b": 0.33, "c": 0.34}
    higher = {"a": True, "b": True, "c": True}
    s = score_product(products[0], products, weights, higher)
    assert s["coverage"] == pytest.approx(2 / 3, abs=0.01)

def test_score_product_invalid_weights():
    with pytest.raises(ValueError):
        score_product({"a": 1.0}, [{"a": 1.0}], {"a": 0.0}, {"a": True})


# ── Ingestion idempotency ─────────────────────────────────────────────────────

def test_ingestion_no_duplicates(tmp_path):
    """Running ingest twice must not duplicate rows."""
    import pathlib
    db_path = tmp_path / "test.db"
    from siliconiq.ingest import run_ingest
    from siliconiq.db import get_connection
    run_ingest(db_path=db_path)
    run_ingest(db_path=db_path)
    conn = get_connection(db_path)
    count = conn.execute("SELECT COUNT(*) FROM financial_observations").fetchone()[0]
    # Second run must not add extra rows
    run_ingest(db_path=db_path)
    count2 = conn.execute("SELECT COUNT(*) FROM financial_observations").fetchone()[0]
    assert count == count2

def test_ingestion_no_null_zero_confusion(tmp_path):
    """Missing data should be NULL, not 0.0."""
    db_path = tmp_path / "test.db"
    from siliconiq.ingest import run_ingest
    from siliconiq.db import get_connection
    run_ingest(db_path=db_path)
    conn = get_connection(db_path)
    # FP8 for NVDA A100 should be NULL (not supported)
    row = conn.execute(
        "SELECT fp8_tflops FROM products WHERE product_id = 'NVDA_A100_SXM4_80'"
    ).fetchone()
    assert row is not None
    assert row["fp8_tflops"] is None


# ── Fiscal label checks ───────────────────────────────────────────────────────

def test_fiscal_labels_present(tmp_path):
    db_path = tmp_path / "test.db"
    from siliconiq.ingest import run_ingest
    from siliconiq.db import get_connection
    run_ingest(db_path=db_path)
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT fiscal_label FROM reporting_periods ORDER BY fiscal_label"
    ).fetchall()
    labels = [r["fiscal_label"] for r in rows]
    for expected in ["FY2022", "FY2023", "FY2024", "FY2021"]:
        assert any(expected in l for l in labels)

def test_nvda_period_end_in_january(tmp_path):
    """NVIDIA fiscal year ends in January."""
    db_path = tmp_path / "test.db"
    from siliconiq.ingest import run_ingest
    from siliconiq.db import get_connection
    run_ingest(db_path=db_path)
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT period_end FROM reporting_periods WHERE company_id='NVDA'"
    ).fetchall()
    for r in rows:
        month = int(r["period_end"].split("-")[1])
        assert month == 1, f"Expected January, got month {month} for {r['period_end']}"


# ── Sensitivity heatmap ───────────────────────────────────────────────────────

def test_sensitivity_heatmap_shape():
    base = {"x": 1.0, "y": 1.0}
    x_vals = [1, 2, 3]
    y_vals = [10, 20]
    result = sensitivity_heatmap(base, "x", "y", x_vals, y_vals, lambda p: p["x"] * p["y"])
    assert len(result) == 2       # rows = y_vals
    assert len(result[0]) == 3   # cols = x_vals

def test_sensitivity_heatmap_values():
    base = {"x": 0.0, "y": 0.0}
    result = sensitivity_heatmap(base, "x", "y", [2.0, 4.0], [3.0, 6.0],
                                  lambda p: p["x"] + p["y"])
    # row0 (y=3): [2+3=5, 4+3=7]
    # row1 (y=6): [2+6=8, 4+6=10]
    assert result[0][0] == pytest.approx(5.0)
    assert result[1][1] == pytest.approx(10.0)


# ── Export regression tests ───────────────────────────────────────────────────
# Generate each workbook, reopen it with openpyxl, and verify structure/values.

def _make_minimal_export_inputs(tmp_path):
    """Build the minimal valid inputs for build_workbook and return them as a dict."""
    import pandas as pd
    from siliconiq.ingest import run_ingest
    from siliconiq.db import get_connection
    from siliconiq import queries

    db_path = tmp_path / "export_test.db"
    run_ingest(db_path=db_path)
    conn = get_connection(db_path)

    fin_df   = queries.get_financials(conn)
    seg_df   = queries.get_segment_revenue(conn)
    prod_df  = queries.get_products(conn, status="current")
    bench_df = queries.get_benchmarks(conn)
    src_df   = queries.get_sources(conn)
    conn.close()

    scoring_df = pd.DataFrame({
        "Product": ["Widget A", "Widget B"],
        "Score": [0.75, 0.60],
        "Coverage": ["100%", "80%"],
    })
    return {
        "financials_df": fin_df,
        "segment_df": seg_df,
        "products_df": prod_df,
        "benchmarks_df": bench_df,
        "scoring_df": scoring_df,
        "sources_df": src_df,
    }


def test_export_deployment_workbook(tmp_path):
    """
    Deployment export must succeed, produce a valid workbook with all 8 sheets,
    and contain no list values in any cell.
    """
    from openpyxl import load_workbook
    from siliconiq import export
    from siliconiq.calculations import deployment_tco, deployment_roi

    inputs = _make_minimal_export_inputs(tmp_path)

    tco = deployment_tco(8, 25_000, 50_000, 65, 700, 0.08, 10, 20_000, 3)
    roi = deployment_roi(tco, 500_000, 0.10, 3)

    xls = export.build_workbook(
        financials_df=inputs["financials_df"],
        segment_df=inputs["segment_df"],
        products_df=inputs["products_df"],
        benchmarks_df=inputs["benchmarks_df"],
        scoring_df=inputs["scoring_df"],
        tco_dict=tco,
        roi_dict=roi,
        vendor_model_result={
            "total_revenue": 0.0, "total_cogs": 0.0, "net_profit": 0.0,
            "project_roi_pct": None, "project_npv": 0.0,
            "contribution_margin": 0.0, "cm_pct": None,
            "break_even_units": None, "discount_rate": 0.10, "cash_flows": [],
        },
        vendor_assumptions={"note": "placeholder"},
        sources_df=inputs["sources_df"],
    )

    # Must return bytes
    assert isinstance(xls, bytes)
    assert len(xls) > 1000

    # Save and reopen
    out = tmp_path / "deployment.xlsx"
    out.write_bytes(xls)
    wb = load_workbook(out)

    # All 8 sheets present
    expected_sheets = [
        "Financial Summary", "Segment Revenue", "Product Catalog",
        "Benchmarks", "Decision Matrix", "Deployment Economics",
        "Vendor Investment", "Sources",
    ]
    assert set(wb.sheetnames) == set(expected_sheets), f"Sheets: {wb.sheetnames}"

    # No cell in any sheet contains a list or dict
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                assert not isinstance(cell.value, (list, dict, tuple)), (
                    f"Sheet '{ws.title}' cell {cell.coordinate} contains "
                    f"unsupported type {type(cell.value).__name__}: {cell.value!r}"
                )

    # Deployment sheet must contain TCO total
    dep_ws = wb["Deployment Economics"]
    all_values = [cell.value for row in dep_ws.iter_rows() for cell in row]
    assert any(v == "total_tco" for v in all_values), "total_tco missing from Deployment Economics sheet"

    # Cash flow schedule must have Year 0
    assert any(v == 0 for v in all_values), "Year 0 cash flow row missing"


def test_export_vendor_workbook(tmp_path):
    """
    Vendor export must succeed, place vendor_model_result in vendor sheet,
    place vendor_assumptions (not cash flows) in assumptions section,
    and contain no list values in any cell.
    """
    from openpyxl import load_workbook
    from siliconiq import export
    from siliconiq.calculations import vendor_model

    inputs = _make_minimal_export_inputs(tmp_path)

    base_res = vendor_model(
        unit_demand=50_000,
        selling_price=25_000,
        unit_cost=10_000,
        fixed_dev_investment=500_000_000,
        annual_operating_cost=50_000_000,
        demand_growth_pct=20,
        years=5,
        discount_rate=0.12,
    )
    assumptions = {
        "selling_price": 25_000,
        "unit_cost": 10_000,
        "fixed_dev_M": 500.0,
        "annual_opex_M": 50.0,
        "base_demand": 50_000,
        "growth_pct": 20,
        "years": 5,
        "discount_rate_pct": 12.0,
    }

    xls = export.build_workbook(
        financials_df=inputs["financials_df"],
        segment_df=inputs["segment_df"],
        products_df=inputs["products_df"],
        benchmarks_df=inputs["benchmarks_df"],
        scoring_df=inputs["scoring_df"],
        tco_dict={k: 0.0 for k in [
            "hw_capex","infra_cost","total_capex","active_watts","facility_watts",
            "kwh_per_year","annual_power_cost","annual_support_cost","annual_opex",
            "total_opex","total_tco","deployment_years",
        ]},
        roi_dict={
            "cash_flows": [], "total_value": 0.0, "net_benefit": 0.0,
            "roi_pct": None, "payback_years": None, "npv": 0.0, "discount_rate": 0.0,
        },
        vendor_model_result=base_res,
        vendor_assumptions=assumptions,
        sources_df=inputs["sources_df"],
    )

    assert isinstance(xls, bytes)
    out = tmp_path / "vendor.xlsx"
    out.write_bytes(xls)
    wb = load_workbook(out)

    # No lists or dicts in any cell
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                assert not isinstance(cell.value, (list, dict, tuple)), (
                    f"Sheet '{ws.title}' cell {cell.coordinate} has "
                    f"{type(cell.value).__name__}: {cell.value!r}"
                )

    # Vendor sheet must contain scalar assumption keys
    ven_ws = wb["Vendor Investment"]
    all_values = [cell.value for row in ven_ws.iter_rows() for cell in row]
    assert "selling_price" in all_values, "selling_price assumption missing from vendor sheet"

    # Vendor sheet must contain computed results
    assert "total_revenue" in all_values, "total_revenue missing from vendor sheet"

    # Cash flow schedule must have Year 0 header and discount factor column
    assert 0 in all_values, "Year 0 missing from vendor cash flow table"
    assert "Discount Factor" in all_values, "Discount Factor column missing"


def test_export_cash_flow_table_values(tmp_path):
    """
    Cash flow table in deployment sheet must match hand-calculated NPV.
    Year 0: -100, Year 1: +50, Year 2: +60, rate 10%
    Discounted: -100, 50/1.1=45.455, 60/1.21=49.587 → NPV=−4.958
    """
    from openpyxl import load_workbook
    from siliconiq import export
    import pandas as pd

    inputs = _make_minimal_export_inputs(tmp_path)

    tco_stub = {k: 0.0 for k in [
        "hw_capex","infra_cost","total_capex","active_watts","facility_watts",
        "kwh_per_year","annual_power_cost","annual_support_cost","annual_opex",
        "total_opex","total_tco","deployment_years",
    ]}
    roi_stub = {
        "cash_flows": [-100.0, 50.0, 60.0],
        "total_value": 110.0,
        "net_benefit": 10.0,
        "roi_pct": 10.0,
        "payback_years": 2.0,
        "npv": -4.958,
        "discount_rate": 0.10,
    }

    xls = export.build_workbook(
        financials_df=inputs["financials_df"],
        segment_df=inputs["segment_df"],
        products_df=inputs["products_df"],
        benchmarks_df=inputs["benchmarks_df"],
        scoring_df=pd.DataFrame({"note": ["test"]}),
        tco_dict=tco_stub,
        roi_dict=roi_stub,
        vendor_model_result={"cash_flows": [], "discount_rate": 0.10},
        vendor_assumptions={"note": "test"},
        sources_df=inputs["sources_df"],
    )

    out = tmp_path / "cf_test.xlsx"
    out.write_bytes(xls)
    wb = load_workbook(out)
    dep_ws = wb["Deployment Economics"]

    all_vals = [cell.value for row in dep_ws.iter_rows() for cell in row]

    # Year 0 raw CF = -100.0 must appear
    assert -100.0 in all_vals, "Year 0 cash flow −100 not found in deployment sheet"
    # Year 1 discounted CF ≈ 45.4545
    assert any(
        isinstance(v, (int, float)) and abs(v - 45.4545) < 0.01
        for v in all_vals
    ), "Year 1 discounted CF (~45.45) not found"


def test_export_no_positional_arg_error(tmp_path):
    """
    build_workbook uses keyword-only args; calling it without keywords raises TypeError.
    This guards against callers accidentally reverting to positional style.
    """
    from siliconiq import export
    import pandas as pd

    empty_df = pd.DataFrame()
    # Python says "takes 0 positional arguments but N were given" for keyword-only functions
    with pytest.raises(TypeError, match="positional"):
        export.build_workbook(
            empty_df, empty_df, empty_df, empty_df, empty_df,
            {}, {}, {}, {}, empty_df,
        )
