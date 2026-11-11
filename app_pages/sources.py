import streamlit as st

from siliconiq import ui
from siliconiq.db import SCHEMA_PATH
from siliconiq.formatting import fmt_date

data = ui.load_data()
src = data["sources"]

ui.page_header(
    "Sources and methodology",
    "See where every number comes from, when it was published, and how the models turn "
    "sourced data and your assumptions into results.",
    kicker="Supporting analysis",
)

TYPE_LABELS = {"SEC_filing": "SEC 10-K filing", "product_spec": "Official spec sheet",
               "benchmark_submission": "MLPerf submission"}

tab_src, tab_prov, tab_bench, tab_score, tab_fin, tab_schema = st.tabs([
    "Sources", "Data provenance", "Benchmark comparability", "Scoring model",
    "Financial models", "Database schema",
])

with tab_src:
    tbl = src.assign(
        Type=src["source_type"].map(TYPE_LABELS).fillna(src["source_type"]),
        Published=src["publication_date"].map(fmt_date),
        Retrieved=src["retrieval_date"].map(fmt_date),
    ).rename(columns={"title": "Document", "url": "Link"})
    st.dataframe(
        tbl[["Document", "Type", "Published", "Retrieved", "Link"]], hide_index=True,
        column_config={"Link": st.column_config.LinkColumn(display_text="Open"),
                       "Document": st.column_config.TextColumn(width="large")},
        alt="All source documents with publication and retrieval dates",
    )
    st.markdown(f"""
Three dates matter, and they're distinct:
- **Snapshot date ({ui.SNAPSHOT_LABEL}):** when this demonstration dataset was assembled.
  Labels like "latest generation" describe products as of this date, not today.
- **Published:** when the company or organization released the document.
- **Retrieved:** when the data was collected for the dataset.
""")

with tab_prov:
    st.markdown(f"""
**Financial data** comes only from NVIDIA and AMD 10-K filings with the SEC, as filed, with no
adjustments. Stored in USD millions and shown with K, M, or B units.

**Fiscal calendars differ:**
- NVIDIA's fiscal year ends on the last Sunday of January. FY2024 ran 30 Jan 2023 to 28 Jan 2024,
  mostly calendar 2023.
- AMD's fiscal year ends on the last Saturday of December. FY2023 ran 1 Jan to 30 Dec 2023.
- NVIDIA FY2024 and AMD FY2023 are the closest pair for an annual comparison, about one month apart.

**Product specifications** come from official NVIDIA and AMD datasheets. All peak compute figures
are **dense (non-sparse)**; NVIDIA sparse figures are about 2× higher. FP8 applies only to Hopper
(H100, H200) and CDNA 3 (MI300X).

**Benchmark data** comes from public MLPerf Inference submissions (MLCommons).

**Prices** aren't stored in the database. Every price is an assumption you enter. Never read
them as list prices or vendor quotes.
""")

with tab_bench:
    st.markdown("""
**Comparable:** direct head-to-head is defensible when results share:
- the same benchmark suite and version
- the same workload and model (for example, Llama2-70B)
- the same numeric precision (FP16 vs FP16, not FP16 vs INT8)
- the same number of accelerators and scenario (Server and Offline aren't comparable)

**Conditional:** use with caution. Typically a different benchmark version, where software
improvements alone can account for 10–30% differences.

**Not comparable:** different precisions, workloads, models, or system configurations.
""")

with tab_score:
    st.markdown("""
**Formula:** `Score = Σ (normalized_i × weight_i)`, with weights rescaled to total 1.0.

**Normalization:** min-max across the compared accelerators, so adding or removing a product
changes everyone's score. Scores are relative, not absolute.

**Missing data:** contributes 0 for that criterion, a deliberate penalty. Data coverage shows
how complete each product's data is.

**Software ecosystem:** a qualitative 0–10 judgment, not a measurement. NVIDIA = 10 (dominant
CUDA ecosystem, largest optimized library); AMD MI300X = 7 (strong PyTorch and vLLM support as
of early 2025, smaller enterprise adoption). Re-evaluate for your workloads and team.
""")

with tab_fin:
    st.markdown("""
**Total cost of ownership:** capital cost = accelerators + infrastructure. Annual power cost =
units × TDP × utilization × (1 + facility overhead) × 8,760 hours × electricity rate.
Operating cost = power + support.

**Value:** annual value is fixed and doesn't depend on utilization. If your value scales with
throughput, enter peak value × utilization.

**NPV:** standard discounted cash flow. Year 0 = −capital cost; years 1 to N = annual value −
operating cost. The discount rate is yours; the 10% default is a placeholder.

**ROI:** net benefit ÷ TCO, undiscounted. **Payback:** capital cost ÷ annual net cash flow;
"Never" when annual value doesn't exceed operating cost.

**Vendor investment model:** every input is a hypothetical assumption. It shows the structure of
a product investment analysis; it doesn't forecast real economics.
""")

with tab_schema:
    st.code(SCHEMA_PATH.read_text(), language="sql")
