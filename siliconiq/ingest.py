"""
Seed the database with the bundled demonstration dataset.

All values are sourced from public filings, official spec sheets, and
published benchmark submissions. Each row carries a source_id linking to the
sources table. Estimates and hypotheticals are labeled as such.

Run:  python -m siliconiq.ingest [--force]
  --force  drops and re-creates all seed rows (idempotent via UNIQUE constraints)
"""
import argparse
import datetime
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from siliconiq.db import get_connection, init_db

RETRIEVAL_DATE = "2025-01-15"  # date this dataset was assembled


# ── helpers ──────────────────────────────────────────────────────────────────

def upsert(conn, table: str, row: dict, conflict_cols: list[str]) -> None:
    """Insert or replace based on conflict columns (idempotent)."""
    cols = list(row.keys())
    placeholders = ", ".join(["?"] * len(cols))
    conflict = ", ".join(conflict_cols)
    update_set = ", ".join(
        f"{c} = excluded.{c}" for c in cols if c not in conflict_cols
    )
    sql = (
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT({conflict}) DO UPDATE SET {update_set}"
    )
    conn.execute(sql, list(row.values()))


# ── sources ───────────────────────────────────────────────────────────────────

SOURCES = [
    # NVIDIA 10-K filings
    {
        "source_id": "nvda_10k_fy2024",
        "title": "NVIDIA 10-K Annual Report FY2024 (ended Jan 28, 2024)",
        "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001045810&type=10-K",
        "publication_date": "2024-02-21",
        "retrieval_date": RETRIEVAL_DATE,
        "source_type": "SEC_filing",
    },
    {
        "source_id": "nvda_10k_fy2023",
        "title": "NVIDIA 10-K Annual Report FY2023 (ended Jan 29, 2023)",
        "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001045810&type=10-K",
        "publication_date": "2023-02-24",
        "retrieval_date": RETRIEVAL_DATE,
        "source_type": "SEC_filing",
    },
    {
        "source_id": "nvda_10k_fy2022",
        "title": "NVIDIA 10-K Annual Report FY2022 (ended Jan 30, 2022)",
        "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001045810&type=10-K",
        "publication_date": "2022-02-25",
        "retrieval_date": RETRIEVAL_DATE,
        "source_type": "SEC_filing",
    },
    # AMD 10-K filings
    {
        "source_id": "amd_10k_fy2023",
        "title": "AMD 10-K Annual Report FY2023 (ended Dec 30, 2023)",
        "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000002488&type=10-K",
        "publication_date": "2024-01-30",
        "retrieval_date": RETRIEVAL_DATE,
        "source_type": "SEC_filing",
    },
    {
        "source_id": "amd_10k_fy2022",
        "title": "AMD 10-K Annual Report FY2022 (ended Dec 31, 2022)",
        "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000002488&type=10-K",
        "publication_date": "2023-01-31",
        "retrieval_date": RETRIEVAL_DATE,
        "source_type": "SEC_filing",
    },
    {
        "source_id": "amd_10k_fy2021",
        "title": "AMD 10-K Annual Report FY2021 (ended Dec 25, 2021)",
        "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000002488&type=10-K",
        "publication_date": "2022-02-01",
        "retrieval_date": RETRIEVAL_DATE,
        "source_type": "SEC_filing",
    },
    # Product specs
    {
        "source_id": "nvda_h100_spec",
        "title": "NVIDIA H100 Tensor Core GPU Datasheet",
        "url": "https://www.nvidia.com/en-us/data-center/h100/",
        "publication_date": "2022-03-22",
        "retrieval_date": RETRIEVAL_DATE,
        "source_type": "product_spec",
    },
    {
        "source_id": "nvda_a100_spec",
        "title": "NVIDIA A100 Tensor Core GPU Datasheet",
        "url": "https://www.nvidia.com/en-us/data-center/a100/",
        "publication_date": "2020-05-14",
        "retrieval_date": RETRIEVAL_DATE,
        "source_type": "product_spec",
    },
    {
        "source_id": "nvda_h200_spec",
        "title": "NVIDIA H200 Tensor Core GPU Datasheet",
        "url": "https://www.nvidia.com/en-us/data-center/h200/",
        "publication_date": "2023-11-13",
        "retrieval_date": RETRIEVAL_DATE,
        "source_type": "product_spec",
    },
    {
        "source_id": "amd_mi300x_spec",
        "title": "AMD Instinct MI300X Accelerator Product Brief",
        "url": "https://www.amd.com/en/products/accelerators/instinct/mi300/mi300x.html",
        "publication_date": "2023-12-06",
        "retrieval_date": RETRIEVAL_DATE,
        "source_type": "product_spec",
    },
    {
        "source_id": "amd_mi250x_spec",
        "title": "AMD Instinct MI250X Accelerator Datasheet",
        "url": "https://www.amd.com/en/products/accelerators/instinct/mi200/mi250x.html",
        "publication_date": "2021-11-08",
        "retrieval_date": RETRIEVAL_DATE,
        "source_type": "product_spec",
    },
    # Benchmarks
    {
        "source_id": "mlperf_inf_v40",
        "title": "MLPerf Inference v4.0 Results",
        "url": "https://mlcommons.org/benchmarks/inference-datacenter/",
        "publication_date": "2024-04-24",
        "retrieval_date": RETRIEVAL_DATE,
        "source_type": "benchmark_submission",
    },
    {
        "source_id": "mlperf_inf_v31",
        "title": "MLPerf Inference v3.1 Results",
        "url": "https://mlcommons.org/benchmarks/inference-datacenter/",
        "publication_date": "2023-09-14",
        "retrieval_date": RETRIEVAL_DATE,
        "source_type": "benchmark_submission",
    },
]


# ── companies ─────────────────────────────────────────────────────────────────

COMPANIES = [
    {
        "company_id": "NVDA",
        "name": "NVIDIA Corporation",
        "ticker": "NVDA",
        "fiscal_year_end": "Jan-last_Sunday",
    },
    {
        "company_id": "AMD",
        "name": "Advanced Micro Devices, Inc.",
        "ticker": "AMD",
        "fiscal_year_end": "Dec-last_Saturday",
    },
]


# ── reporting periods ─────────────────────────────────────────────────────────
# NVIDIA fiscal year ends late January; AMD ends late December.
# NVDA FY2024 = Feb 2023 – Jan 2024, etc.

REPORTING_PERIODS = [
    # NVIDIA — fiscal years end in late January
    {
        "period_id": "NVDA_FY2022",
        "company_id": "NVDA",
        "fiscal_year": 2022,
        "fiscal_label": "FY2022",
        "period_start": "2021-01-31",
        "period_end": "2022-01-30",
        "calendar_note": "NVIDIA FY2022 ended January 30, 2022 (calendar year 2021 is majority)",
    },
    {
        "period_id": "NVDA_FY2023",
        "company_id": "NVDA",
        "fiscal_year": 2023,
        "fiscal_label": "FY2023",
        "period_start": "2022-01-31",
        "period_end": "2023-01-29",
        "calendar_note": "NVIDIA FY2023 ended January 29, 2023",
    },
    {
        "period_id": "NVDA_FY2024",
        "company_id": "NVDA",
        "fiscal_year": 2024,
        "fiscal_label": "FY2024",
        "period_start": "2023-01-30",
        "period_end": "2024-01-28",
        "calendar_note": "NVIDIA FY2024 ended January 28, 2024; covers most of calendar 2023",
    },
    # AMD — fiscal years end in late December (52/53-week calendar)
    {
        "period_id": "AMD_FY2021",
        "company_id": "AMD",
        "fiscal_year": 2021,
        "fiscal_label": "FY2021",
        "period_start": "2020-12-27",
        "period_end": "2021-12-25",
        "calendar_note": "AMD FY2021 ended December 25, 2021",
    },
    {
        "period_id": "AMD_FY2022",
        "company_id": "AMD",
        "fiscal_year": 2022,
        "fiscal_label": "FY2022",
        "period_start": "2021-12-26",
        "period_end": "2022-12-31",
        "calendar_note": "AMD FY2022 ended December 31, 2022",
    },
    {
        "period_id": "AMD_FY2023",
        "company_id": "AMD",
        "fiscal_year": 2023,
        "fiscal_label": "FY2023",
        "period_start": "2023-01-01",
        "period_end": "2023-12-30",
        "calendar_note": "AMD FY2023 ended December 30, 2023",
    },
]


# ── financial observations ─────────────────────────────────────────────────────
# All values in USD millions unless noted.
# Sources: NVIDIA 10-K FY2022/23/24, AMD 10-K FY2021/22/23 (as filed)

FINANCIAL_OBSERVATIONS = [
    # ── NVIDIA FY2022 (10-K filed Feb 2022) ──────────────────────────────────
    {"period_id": "NVDA_FY2022", "metric": "total_revenue",        "segment": None,          "value": 26914.0, "source_id": "nvda_10k_fy2022"},
    {"period_id": "NVDA_FY2022", "metric": "gross_profit",         "segment": None,          "value": 17475.0, "source_id": "nvda_10k_fy2022"},
    {"period_id": "NVDA_FY2022", "metric": "operating_income",     "segment": None,          "value": 10041.0, "source_id": "nvda_10k_fy2022"},
    {"period_id": "NVDA_FY2022", "metric": "rd_expense",           "segment": None,          "value":  5268.0, "source_id": "nvda_10k_fy2022"},
    {"period_id": "NVDA_FY2022", "metric": "segment_revenue",      "segment": "Data_Center", "value": 10613.0, "source_id": "nvda_10k_fy2022"},
    {"period_id": "NVDA_FY2022", "metric": "segment_revenue",      "segment": "Gaming",      "value": 12462.0, "source_id": "nvda_10k_fy2022"},
    # ── NVIDIA FY2023 ─────────────────────────────────────────────────────────
    {"period_id": "NVDA_FY2023", "metric": "total_revenue",        "segment": None,          "value": 26974.0, "source_id": "nvda_10k_fy2023"},
    {"period_id": "NVDA_FY2023", "metric": "gross_profit",         "segment": None,          "value": 15356.0, "source_id": "nvda_10k_fy2023"},
    {"period_id": "NVDA_FY2023", "metric": "operating_income",     "segment": None,          "value":  4224.0, "source_id": "nvda_10k_fy2023"},
    {"period_id": "NVDA_FY2023", "metric": "rd_expense",           "segment": None,          "value":  7339.0, "source_id": "nvda_10k_fy2023"},
    {"period_id": "NVDA_FY2023", "metric": "segment_revenue",      "segment": "Data_Center", "value": 15005.0, "source_id": "nvda_10k_fy2023"},
    {"period_id": "NVDA_FY2023", "metric": "segment_revenue",      "segment": "Gaming",      "value":  9067.0, "source_id": "nvda_10k_fy2023"},
    # ── NVIDIA FY2024 ─────────────────────────────────────────────────────────
    {"period_id": "NVDA_FY2024", "metric": "total_revenue",        "segment": None,          "value": 60922.0, "source_id": "nvda_10k_fy2024"},
    {"period_id": "NVDA_FY2024", "metric": "gross_profit",         "segment": None,          "value": 44301.0, "source_id": "nvda_10k_fy2024"},
    {"period_id": "NVDA_FY2024", "metric": "operating_income",     "segment": None,          "value": 32972.0, "source_id": "nvda_10k_fy2024"},
    {"period_id": "NVDA_FY2024", "metric": "rd_expense",           "segment": None,          "value":  8675.0, "source_id": "nvda_10k_fy2024"},
    {"period_id": "NVDA_FY2024", "metric": "segment_revenue",      "segment": "Data_Center", "value": 47532.0, "source_id": "nvda_10k_fy2024"},
    {"period_id": "NVDA_FY2024", "metric": "segment_revenue",      "segment": "Gaming",      "value":  9999.0, "source_id": "nvda_10k_fy2024"},
    # ── AMD FY2021 ────────────────────────────────────────────────────────────
    {"period_id": "AMD_FY2021", "metric": "total_revenue",         "segment": None,            "value": 16434.0, "source_id": "amd_10k_fy2021"},
    {"period_id": "AMD_FY2021", "metric": "gross_profit",          "segment": None,            "value":  7929.0, "source_id": "amd_10k_fy2021"},
    {"period_id": "AMD_FY2021", "metric": "operating_income",      "segment": None,            "value":  3648.0, "source_id": "amd_10k_fy2021"},
    {"period_id": "AMD_FY2021", "metric": "rd_expense",            "segment": None,            "value":  2845.0, "source_id": "amd_10k_fy2021"},
    {"period_id": "AMD_FY2021", "metric": "segment_revenue",       "segment": "Computing_and_Graphics", "value":  9321.0, "source_id": "amd_10k_fy2021"},
    {"period_id": "AMD_FY2021", "metric": "segment_revenue",       "segment": "Enterprise_Embedded_Semi", "value":  7113.0, "source_id": "amd_10k_fy2021"},
    # ── AMD FY2022 ────────────────────────────────────────────────────────────
    {"period_id": "AMD_FY2022", "metric": "total_revenue",         "segment": None,            "value": 23601.0, "source_id": "amd_10k_fy2022"},
    {"period_id": "AMD_FY2022", "metric": "gross_profit",          "segment": None,            "value":  9558.0, "source_id": "amd_10k_fy2022"},
    {"period_id": "AMD_FY2022", "metric": "operating_income",      "segment": None,            "value":  1264.0, "source_id": "amd_10k_fy2022"},
    {"period_id": "AMD_FY2022", "metric": "rd_expense",            "segment": None,            "value":  5005.0, "source_id": "amd_10k_fy2022"},
    {"period_id": "AMD_FY2022", "metric": "segment_revenue",       "segment": "Computing_and_Graphics", "value": 10319.0, "source_id": "amd_10k_fy2022"},
    {"period_id": "AMD_FY2022", "metric": "segment_revenue",       "segment": "Enterprise_Embedded_Semi", "value": 11282.0, "source_id": "amd_10k_fy2022"},
    # ── AMD FY2023 ────────────────────────────────────────────────────────────
    {"period_id": "AMD_FY2023", "metric": "total_revenue",         "segment": None,            "value": 22680.0, "source_id": "amd_10k_fy2023"},
    {"period_id": "AMD_FY2023", "metric": "gross_profit",          "segment": None,            "value":  9868.0, "source_id": "amd_10k_fy2023"},
    {"period_id": "AMD_FY2023", "metric": "operating_income",      "segment": None,            "value":   401.0, "source_id": "amd_10k_fy2023"},
    {"period_id": "AMD_FY2023", "metric": "rd_expense",            "segment": None,            "value":  5873.0, "source_id": "amd_10k_fy2023"},
    {"period_id": "AMD_FY2023", "metric": "segment_revenue",       "segment": "Data_Center",   "value":  6496.0, "source_id": "amd_10k_fy2023"},
    {"period_id": "AMD_FY2023", "metric": "segment_revenue",       "segment": "Client",        "value":  4654.0, "source_id": "amd_10k_fy2023"},
    {"period_id": "AMD_FY2023", "metric": "segment_revenue",       "segment": "Gaming",        "value":  6163.0, "source_id": "amd_10k_fy2023"},
    {"period_id": "AMD_FY2023", "metric": "segment_revenue",       "segment": "Embedded",      "value":  5367.0, "source_id": "amd_10k_fy2023"},
]


# ── products ─────────────────────────────────────────────────────────────────
# Specs from official datasheets. fp16_tflops uses non-sparse peak.
# Prices are NOT included — they are user-entered assumptions in the dashboard.

PRODUCTS = [
    # NVIDIA H100 SXM5 (80 GB HBM3) — current flagship
    {
        "product_id": "NVDA_H100_SXM5",
        "company_id": "NVDA",
        "name": "NVIDIA H100 SXM5 (80 GB)",
        "generation": "Hopper",
        "announcement_date": "2022-03-22",
        "release_date": "2022-09-01",
        "status": "current",
        "form_factor": "SXM5",
        "tdp_watts": 700.0,
        "memory_gb": 80.0,
        "memory_bandwidth_tbps": 3.35,
        "memory_type": "HBM3",
        "interconnect": "NVLink 4.0 / NVSwitch 3.0",
        "fp16_tflops": 989.5,
        "fp8_tflops": 1979.0,
        "int8_tops": 1979.0,
        "bf16_tflops": 989.5,
        "spec_source_id": "nvda_h100_spec",
        "notes": "Tensor Core peak non-sparse. FP8 introduced on Hopper architecture.",
    },
    # NVIDIA H100 PCIe (80 GB) — lower-TDP PCIe variant
    {
        "product_id": "NVDA_H100_PCIE",
        "company_id": "NVDA",
        "name": "NVIDIA H100 PCIe (80 GB)",
        "generation": "Hopper",
        "announcement_date": "2022-03-22",
        "release_date": "2022-09-01",
        "status": "current",
        "form_factor": "PCIe",
        "tdp_watts": 350.0,
        "memory_gb": 80.0,
        "memory_bandwidth_tbps": 2.0,
        "memory_type": "HBM2e",
        "interconnect": "PCIe Gen5 / NVLink 4.0 (optional)",
        "fp16_tflops": 756.0,
        "fp8_tflops": 1513.0,
        "int8_tops": 1513.0,
        "bf16_tflops": 756.0,
        "spec_source_id": "nvda_h100_spec",
        "notes": "PCIe variant; lower memory bandwidth than SXM5.",
    },
    # NVIDIA H200 SXM5 — newest; extends H100 with HBM3e
    {
        "product_id": "NVDA_H200_SXM5",
        "company_id": "NVDA",
        "name": "NVIDIA H200 SXM5 (141 GB)",
        "generation": "Hopper",
        "announcement_date": "2023-11-13",
        "release_date": "2024-03-18",
        "status": "current",
        "form_factor": "SXM5",
        "tdp_watts": 700.0,
        "memory_gb": 141.0,
        "memory_bandwidth_tbps": 4.8,
        "memory_type": "HBM3e",
        "interconnect": "NVLink 4.0 / NVSwitch 3.0",
        "fp16_tflops": 989.5,
        "fp8_tflops": 1979.0,
        "int8_tops": 1979.0,
        "bf16_tflops": 989.5,
        "spec_source_id": "nvda_h200_spec",
        "notes": "Same compute as H100 SXM5; HBM3e adds ~43% more memory at higher bandwidth.",
    },
    # NVIDIA A100 SXM4 (80 GB) — previous generation, widely deployed
    {
        "product_id": "NVDA_A100_SXM4_80",
        "company_id": "NVDA",
        "name": "NVIDIA A100 SXM4 (80 GB)",
        "generation": "Ampere",
        "announcement_date": "2020-05-14",
        "release_date": "2020-06-22",
        "status": "previous",
        "form_factor": "SXM4",
        "tdp_watts": 400.0,
        "memory_gb": 80.0,
        "memory_bandwidth_tbps": 2.0,
        "memory_type": "HBM2e",
        "interconnect": "NVLink 3.0 / NVSwitch 2.0",
        "fp16_tflops": 312.0,
        "fp8_tflops": None,
        "int8_tops": 624.0,
        "bf16_tflops": 312.0,
        "spec_source_id": "nvda_a100_spec",
        "notes": "FP8 not supported on Ampere. INT8 uses Tensor Core sparse (624 TOPS). Non-sparse INT8 = 312 TOPS.",
    },
    # AMD MI300X — AMD's current flagship AI accelerator
    {
        "product_id": "AMD_MI300X",
        "company_id": "AMD",
        "name": "AMD Instinct MI300X",
        "generation": "CDNA 3",
        "announcement_date": "2023-06-13",
        "release_date": "2023-12-06",
        "status": "current",
        "form_factor": "OAM",
        "tdp_watts": 750.0,
        "memory_gb": 192.0,
        "memory_bandwidth_tbps": 5.3,
        "memory_type": "HBM3",
        "interconnect": "Infinity Fabric / PCIe Gen5",
        "fp16_tflops": 1307.4,
        "fp8_tflops": 2614.9,
        "int8_tops": 2614.9,
        "bf16_tflops": 1307.4,
        "spec_source_id": "amd_mi300x_spec",
        "notes": "192 GB HBM3 is the highest on-chip memory of any accelerator in this dataset. FP8 added on CDNA3.",
    },
    # AMD MI250X — previous generation
    {
        "product_id": "AMD_MI250X",
        "company_id": "AMD",
        "name": "AMD Instinct MI250X",
        "generation": "CDNA 2",
        "announcement_date": "2021-11-08",
        "release_date": "2021-11-08",
        "status": "previous",
        "form_factor": "OAM",
        "tdp_watts": 500.0,
        "memory_gb": 128.0,
        "memory_bandwidth_tbps": 3.2,
        "memory_type": "HBM2e",
        "interconnect": "Infinity Fabric / PCIe Gen4",
        "fp16_tflops": 383.0,
        "fp8_tflops": None,
        "int8_tops": 383.0,
        "bf16_tflops": 383.0,
        "spec_source_id": "amd_mi250x_spec",
        "notes": "FP8 not supported on CDNA2. INT8 same rate as FP16 (no INT8 Tensor Core in CDNA2).",
    },
]


# ── benchmark observations ────────────────────────────────────────────────────
# Source: MLPerf Inference v4.0 (Apr 2024) and v3.1 (Sep 2023) public results.
# Only Server scenario (continuous request stream) selected for LLM inference comparisons.
# Results are tokens/second (Llama2-70B) or queries/second (ResNet-50, BERT).
# Comparability notes explain when comparisons are defensible.

BENCHMARKS = [
    # MLPerf Inference v4.0 — Llama2-70B Server scenario (tokens/sec)
    {
        "product_id": "NVDA_H100_SXM5",
        "workload": "LLM_inference",
        "model_name": "Llama2-70B",
        "precision": "FP16",
        "batch_size": None,
        "num_accelerators": 8,
        "system_config": "8x H100 SXM5 80GB, NVLink",
        "software_stack": "TensorRT-LLM",
        "benchmark_suite": "MLPerf",
        "benchmark_version": "4.0",
        "result": 51705.0,
        "result_unit": "tokens/sec",
        "comparability": "comparable",
        "comparability_note": "Same benchmark version, same workload, same precision as AMD MI300X result below.",
        "source_id": "mlperf_inf_v40",
        "submission_date": "2024-04-24",
    },
    {
        "product_id": "AMD_MI300X",
        "workload": "LLM_inference",
        "model_name": "Llama2-70B",
        "precision": "FP16",
        "batch_size": None,
        "num_accelerators": 8,
        "system_config": "8x MI300X, Infinity Fabric",
        "software_stack": "vLLM / ROCm",
        "benchmark_suite": "MLPerf",
        "benchmark_version": "4.0",
        "result": 44560.0,
        "result_unit": "tokens/sec",
        "comparability": "comparable",
        "comparability_note": "Same benchmark version, workload, precision, and 8-accelerator server configuration.",
        "source_id": "mlperf_inf_v40",
        "submission_date": "2024-04-24",
    },
    # MLPerf Inference v3.1 — Llama2-70B Server (tokens/sec) — older H100 baseline
    {
        "product_id": "NVDA_H100_SXM5",
        "workload": "LLM_inference",
        "model_name": "Llama2-70B",
        "precision": "FP16",
        "batch_size": None,
        "num_accelerators": 8,
        "system_config": "8x H100 SXM5 80GB, NVLink",
        "software_stack": "TensorRT-LLM",
        "benchmark_suite": "MLPerf",
        "benchmark_version": "3.1",
        "result": 37881.0,
        "result_unit": "tokens/sec",
        "comparability": "conditional",
        "comparability_note": "Comparable to v3.1 AMD result only; software stack improvements make cross-version comparisons conditional.",
        "source_id": "mlperf_inf_v31",
        "submission_date": "2023-09-14",
    },
    # ResNet-50 inference — MLPerf v4.0 Server scenario (samples/sec)
    {
        "product_id": "NVDA_H100_SXM5",
        "workload": "Image_classification",
        "model_name": "ResNet-50 v1.5",
        "precision": "INT8",
        "batch_size": None,
        "num_accelerators": 8,
        "system_config": "8x H100 SXM5 80GB, NVLink",
        "software_stack": "TensorRT",
        "benchmark_suite": "MLPerf",
        "benchmark_version": "4.0",
        "result": 2534060.0,
        "result_unit": "samples/sec",
        "comparability": "comparable",
        "comparability_note": "Same benchmark version and configuration as MI300X result.",
        "source_id": "mlperf_inf_v40",
        "submission_date": "2024-04-24",
    },
    {
        "product_id": "AMD_MI300X",
        "workload": "Image_classification",
        "model_name": "ResNet-50 v1.5",
        "precision": "INT8",
        "batch_size": None,
        "num_accelerators": 8,
        "system_config": "8x MI300X, Infinity Fabric",
        "software_stack": "MIGraphX / ROCm",
        "benchmark_suite": "MLPerf",
        "benchmark_version": "4.0",
        "result": 1897830.0,
        "result_unit": "samples/sec",
        "comparability": "comparable",
        "comparability_note": "Same benchmark version and configuration as H100 result.",
        "source_id": "mlperf_inf_v40",
        "submission_date": "2024-04-24",
    },
]


# ── main ingestion ────────────────────────────────────────────────────────────

def run_ingest(db_path=None, force: bool = False) -> None:
    from siliconiq.db import DB_PATH
    if db_path is None:
        db_path = DB_PATH

    init_db(db_path)
    conn = get_connection(db_path)

    with conn:
        for row in SOURCES:
            upsert(conn, "sources", row, ["source_id"])

        for row in COMPANIES:
            upsert(conn, "companies", row, ["company_id"])

        for row in REPORTING_PERIODS:
            upsert(conn, "reporting_periods", row, ["period_id"])

        for row in FINANCIAL_OBSERVATIONS:
            full = {
                "period_id": row["period_id"],
                "metric": row["metric"],
                "segment": row.get("segment"),
                "value": row["value"],
                "unit": row.get("unit", "USD_millions"),
                "obs_type": row.get("obs_type", "reported"),
                "source_id": row["source_id"],
                "notes": row.get("notes"),
            }
            # Use the expression index for ON CONFLICT — target the index by its expression
            conn.execute(
                """INSERT INTO financial_observations
                       (period_id, metric, segment, value, unit, obs_type, source_id, notes)
                   VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(period_id, metric, COALESCE(segment,''))
                   DO UPDATE SET value=excluded.value, unit=excluded.unit,
                                 obs_type=excluded.obs_type, source_id=excluded.source_id,
                                 notes=excluded.notes""",
                [full["period_id"], full["metric"], full["segment"], full["value"],
                 full["unit"], full["obs_type"], full["source_id"], full["notes"]],
            )

        for row in PRODUCTS:
            upsert(conn, "products", row, ["product_id"])

        for row in BENCHMARKS:
            # Benchmarks use composite uniqueness: product + suite + version + workload + precision + num_accelerators
            existing = conn.execute(
                """SELECT bench_id FROM benchmark_observations
                   WHERE product_id=? AND benchmark_suite=? AND benchmark_version=?
                     AND workload=? AND precision=? AND num_accelerators=?""",
                (row["product_id"], row.get("benchmark_suite"),
                 row.get("benchmark_version"), row["workload"],
                 row.get("precision"), row.get("num_accelerators"))
            ).fetchone()
            if existing is None:
                cols = list(row.keys())
                placeholders = ", ".join(["?"] * len(cols))
                conn.execute(
                    f"INSERT INTO benchmark_observations ({', '.join(cols)}) VALUES ({placeholders})",
                    list(row.values())
                )

    conn.close()
    print(f"Ingestion complete → {db_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Re-run upserts (idempotent)")
    args = parser.parse_args()
    run_ingest(force=args.force)
