-- SiliconIQ SQLite Schema
-- Separates companies, reporting periods, financial observations,
-- products, benchmark observations, and sources.

PRAGMA foreign_keys = ON;

-- ── Sources ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sources (
    source_id       TEXT PRIMARY KEY,          -- e.g. "nvda_10k_fy2024"
    title           TEXT NOT NULL,
    url             TEXT,
    publication_date TEXT,                      -- ISO-8601 date
    retrieval_date  TEXT,                      -- ISO-8601 date
    source_type     TEXT CHECK(source_type IN (
                        'SEC_filing','IR_page','product_spec',
                        'benchmark_submission','estimate','hypothetical'))
                    NOT NULL
);

-- ── Companies ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS companies (
    company_id      TEXT PRIMARY KEY,          -- "NVDA" / "AMD"
    name            TEXT NOT NULL,
    ticker          TEXT,
    fiscal_year_end TEXT                       -- e.g. "Jan-31" (month-day)
);

-- ── Reporting periods ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reporting_periods (
    period_id       TEXT PRIMARY KEY,          -- "NVDA_FY2024"
    company_id      TEXT REFERENCES companies(company_id),
    fiscal_year     INTEGER NOT NULL,
    fiscal_label    TEXT NOT NULL,             -- "FY2024"
    period_start    TEXT NOT NULL,             -- ISO-8601
    period_end      TEXT NOT NULL,             -- ISO-8601
    calendar_note   TEXT                       -- e.g. "ends Jan 28, 2024"
);

-- ── Financial observations ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS financial_observations (
    obs_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    period_id       TEXT REFERENCES reporting_periods(period_id),
    metric          TEXT NOT NULL,             -- e.g. "total_revenue"
    segment         TEXT,                      -- NULL = company total
    value           REAL NOT NULL,
    unit            TEXT NOT NULL DEFAULT 'USD_millions',
    obs_type        TEXT CHECK(obs_type IN ('reported','calculated','estimated'))
                    NOT NULL DEFAULT 'reported',
    source_id       TEXT REFERENCES sources(source_id),
    notes           TEXT
    -- uniqueness enforced via idx_fin_obs_unique below (handles NULL segment)
);

-- ── Products ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS products (
    product_id              TEXT PRIMARY KEY,
    company_id              TEXT REFERENCES companies(company_id),
    name                    TEXT NOT NULL,
    generation              TEXT,
    announcement_date       TEXT,
    release_date            TEXT,
    status                  TEXT CHECK(status IN ('current','previous','announced'))
                            NOT NULL DEFAULT 'current',
    form_factor             TEXT,
    tdp_watts               REAL,
    memory_gb               REAL,
    memory_bandwidth_tbps   REAL,
    memory_type             TEXT,
    interconnect            TEXT,
    fp16_tflops             REAL,
    fp8_tflops              REAL,
    int8_tops               REAL,
    bf16_tflops             REAL,
    spec_source_id          TEXT REFERENCES sources(source_id),
    notes                   TEXT
);

-- ── Benchmark observations ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS benchmark_observations (
    bench_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id          TEXT REFERENCES products(product_id),
    workload            TEXT NOT NULL,         -- e.g. "LLM_inference"
    model_name          TEXT,
    precision           TEXT,                  -- "FP16","INT8","FP8","BF16"
    batch_size          INTEGER,
    num_accelerators    INTEGER,
    system_config       TEXT,
    software_stack      TEXT,
    benchmark_suite     TEXT,
    benchmark_version   TEXT,
    result              REAL,
    result_unit         TEXT,
    comparability       TEXT CHECK(comparability IN
                            ('comparable','conditional','not_comparable'))
                        NOT NULL DEFAULT 'conditional',
    comparability_note  TEXT,
    source_id           TEXT REFERENCES sources(source_id),
    submission_date     TEXT
);

-- ── Scenarios (user-entered, not source data) ─────────────────────────────
CREATE TABLE IF NOT EXISTS scenarios (
    scenario_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_name   TEXT NOT NULL,
    scenario_type   TEXT CHECK(scenario_type IN ('customer_deployment','vendor_investment'))
                    NOT NULL,
    created_at      TEXT DEFAULT (datetime('now')),
    assumptions_json TEXT   -- JSON blob of all input parameters
);

-- ── Views ──────────────────────────────────────────────────────────────────

-- Expression index to enforce uniqueness on (period_id, metric, segment)
-- treating NULL segment as '' (company total).
CREATE UNIQUE INDEX IF NOT EXISTS idx_fin_obs_unique
    ON financial_observations(period_id, metric, COALESCE(segment, ''));

CREATE VIEW IF NOT EXISTS v_financial_summary AS
SELECT
    c.ticker,
    c.name         AS company_name,
    rp.fiscal_label,
    rp.period_end,
    fo.metric,
    fo.segment,
    fo.value,
    fo.unit,
    fo.obs_type,
    s.url          AS source_url
FROM financial_observations fo
JOIN reporting_periods rp ON fo.period_id = rp.period_id
JOIN companies c          ON rp.company_id = c.company_id
LEFT JOIN sources s       ON fo.source_id = s.source_id;

CREATE VIEW IF NOT EXISTS v_revenue_growth AS
SELECT
    curr.ticker,
    curr.fiscal_label,
    curr.period_end,
    curr.value       AS revenue,
    prev.value       AS prev_revenue,
    CASE
        WHEN prev.value > 0
        THEN ROUND((curr.value - prev.value) / prev.value * 100.0, 2)
        ELSE NULL
    END              AS yoy_growth_pct
FROM v_financial_summary curr
LEFT JOIN v_financial_summary prev
    ON  curr.ticker      = prev.ticker
    AND curr.metric      = prev.metric
    AND prev.metric      = 'total_revenue'
    AND CAST(SUBSTR(curr.fiscal_label,3) AS INTEGER)
        = CAST(SUBSTR(prev.fiscal_label,3) AS INTEGER) + 1
WHERE curr.metric = 'total_revenue'
  AND curr.segment IS NULL;

CREATE VIEW IF NOT EXISTS v_product_catalog AS
SELECT
    p.product_id,
    c.ticker,
    c.name         AS company_name,
    p.name         AS product_name,
    p.generation,
    p.status,
    p.form_factor,
    p.tdp_watts,
    p.memory_gb,
    p.memory_bandwidth_tbps,
    p.memory_type,
    p.fp16_tflops,
    p.fp8_tflops,
    p.int8_tops,
    p.bf16_tflops,
    p.interconnect,
    p.release_date,
    s.url          AS spec_source_url
FROM products p
JOIN companies c    ON p.company_id = c.company_id
LEFT JOIN sources s ON p.spec_source_id = s.source_id;
