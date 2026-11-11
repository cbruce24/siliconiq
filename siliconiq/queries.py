"""
Reusable SQL queries returning pandas DataFrames.
Each function documents its join logic and what it returns.
"""
from __future__ import annotations
import pandas as pd
from siliconiq.db import get_connection


def _df(conn, sql: str, params=()) -> pd.DataFrame:
    return pd.read_sql_query(sql, conn, params=params)


# ── Financial ─────────────────────────────────────────────────────────────────

def get_financials(conn) -> pd.DataFrame:
    """Company-level financials with calculated ratios, all periods."""
    sql = """
    WITH base AS (
        SELECT
            c.ticker,
            rp.fiscal_label,
            rp.period_end,
            MAX(CASE WHEN fo.metric='total_revenue'    THEN fo.value END) AS revenue,
            MAX(CASE WHEN fo.metric='gross_profit'     THEN fo.value END) AS gross_profit,
            MAX(CASE WHEN fo.metric='operating_income' THEN fo.value END) AS operating_income,
            MAX(CASE WHEN fo.metric='rd_expense'       THEN fo.value END) AS rd_expense
        FROM financial_observations fo
        JOIN reporting_periods rp ON fo.period_id = rp.period_id
        JOIN companies c          ON rp.company_id = c.company_id
        WHERE fo.segment IS NULL
        GROUP BY c.ticker, rp.fiscal_label, rp.period_end
    )
    SELECT *,
        ROUND(gross_profit    / NULLIF(revenue, 0) * 100, 2) AS gross_margin_pct,
        ROUND(operating_income/ NULLIF(revenue, 0) * 100, 2) AS operating_margin_pct,
        ROUND(rd_expense      / NULLIF(revenue, 0) * 100, 2) AS rd_pct_revenue
    FROM base
    ORDER BY ticker, period_end
    """
    return _df(conn, sql)


def get_revenue_growth(conn) -> pd.DataFrame:
    """YoY revenue growth using the v_revenue_growth view."""
    return _df(conn, "SELECT * FROM v_revenue_growth ORDER BY ticker, period_end")


def get_segment_revenue(conn, company: str | None = None) -> pd.DataFrame:
    sql = """
    SELECT
        c.ticker,
        rp.fiscal_label,
        rp.period_end,
        fo.segment,
        fo.value AS segment_revenue_usd_m,
        s.url AS source_url
    FROM financial_observations fo
    JOIN reporting_periods rp ON fo.period_id = rp.period_id
    JOIN companies c          ON rp.company_id = c.company_id
    LEFT JOIN sources s       ON fo.source_id = s.source_id
    WHERE fo.metric = 'segment_revenue'
      AND fo.segment IS NOT NULL
    """
    params: list = []
    if company:
        sql += " AND c.ticker = ?"
        params.append(company)
    sql += " ORDER BY c.ticker, rp.period_end"
    return _df(conn, sql, params)


def get_rd_comparison(conn) -> pd.DataFrame:
    """R&D spend and intensity comparison across companies and periods."""
    sql = """
    SELECT
        c.ticker,
        rp.fiscal_label,
        rp.period_end,
        MAX(CASE WHEN fo.metric='rd_expense'    THEN fo.value END) AS rd_expense_usd_m,
        MAX(CASE WHEN fo.metric='total_revenue' THEN fo.value END) AS revenue_usd_m,
        ROUND(
            MAX(CASE WHEN fo.metric='rd_expense' THEN fo.value END) /
            NULLIF(MAX(CASE WHEN fo.metric='total_revenue' THEN fo.value END), 0)
            * 100, 2
        ) AS rd_pct_revenue
    FROM financial_observations fo
    JOIN reporting_periods rp ON fo.period_id = rp.period_id
    JOIN companies c          ON rp.company_id = c.company_id
    WHERE fo.segment IS NULL
    GROUP BY c.ticker, rp.fiscal_label, rp.period_end
    ORDER BY c.ticker, rp.period_end
    """
    return _df(conn, sql)


# ── Products ──────────────────────────────────────────────────────────────────

def get_products(conn, status: str | None = None) -> pd.DataFrame:
    sql = "SELECT * FROM v_product_catalog"
    params: list = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY ticker, release_date"
    return _df(conn, sql, params)


def get_benchmarks(conn, workload: str | None = None,
                   version: str | None = None) -> pd.DataFrame:
    sql = """
    SELECT
        p.name        AS product_name,
        c.ticker,
        bo.workload,
        bo.model_name,
        bo.precision,
        bo.num_accelerators,
        bo.system_config,
        bo.software_stack,
        bo.benchmark_suite,
        bo.benchmark_version,
        bo.result,
        bo.result_unit,
        bo.comparability,
        bo.comparability_note,
        s.url AS source_url,
        bo.submission_date
    FROM benchmark_observations bo
    JOIN products p  ON bo.product_id = p.product_id
    JOIN companies c ON p.company_id = c.company_id
    LEFT JOIN sources s ON bo.source_id = s.source_id
    WHERE 1=1
    """
    params: list = []
    if workload:
        sql += " AND bo.workload = ?"
        params.append(workload)
    if version:
        sql += " AND bo.benchmark_version = ?"
        params.append(version)
    sql += " ORDER BY bo.workload, bo.benchmark_version DESC, bo.result DESC"
    return _df(conn, sql, params)


def get_sources(conn) -> pd.DataFrame:
    return _df(conn, "SELECT * FROM sources ORDER BY source_type, publication_date")
