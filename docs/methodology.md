# SiliconIQ Methodology Guide

## 1. Data Provenance

Every financial observation, product specification, and benchmark result stored in the
database carries a `source_id` that links to the `sources` table. That record contains
the source URL, publication date, retrieval date, and source type (`SEC_filing`,
`product_spec`, `benchmark_submission`, `estimate`, or `hypothetical`).

**What is never stored without a source:**
- Financial figures (revenue, margins, R&D)
- Product specifications
- Benchmark results

**What is explicitly user-entered and never sourced:**
- Hardware prices (in the TCO and scoring pages)
- Vendor investment model assumptions

## 2. Financial Data

### Source
NVIDIA and AMD 10-K annual reports filed with the SEC. The SEC EDGAR system provides
machine-readable filings; values in this tool were transcribed from the financial
statements sections.

### Units
All monetary values: USD millions, as reported. No currency conversion was required
(both companies report in USD).

### Fiscal Calendar Differences

| Company | Fiscal Year End | Example: FY2024 |
|---|---|---|
| NVIDIA | Last Sunday of January | Jan 30, 2023 → Jan 28, 2024 |
| AMD | Last Saturday of December | Jan 1, 2023 → Dec 30, 2023 |

**Key implication:** NVIDIA's FY2024 and AMD's FY2023 are the best available pair
for approximate annual comparison — they both cover the majority of calendar year 2023.
However, they are not identical periods. Bar charts use fiscal labels (FY2024, FY2023)
rather than calendar years to avoid implying alignment that does not exist.

### Segment Revenue Caution

NVIDIA's "Data Center" segment includes networking products (Mellanox/Spectrum),
CPUs (Grace), and DPUs in addition to AI accelerators (A100, H100, H200).

AMD's segment structure changed in FY2023: the company introduced separate "Data Center,"
"Client," "Gaming," and "Embedded" segments, replacing the prior "Computing and Graphics"
and "Enterprise, Embedded, and Semi-Custom" structure. AMD's Data Center segment
includes EPYC CPUs and Instinct accelerators.

**Neither company's segment revenue equals AI accelerator revenue.**

## 3. Product Specifications

### Selection Criteria
Products were selected based on:
1. Availability of an official product datasheet or product page
2. Relevance to data-center AI workloads (excludes consumer/workstation GPUs)
3. Meaningful comparability within the dataset (at least two comparable products)

Products included:
- **Current:** NVIDIA H100 SXM5, H100 PCIe, H200 SXM5; AMD MI300X
- **Previous:** NVIDIA A100 SXM4 (80 GB); AMD MI250X

Historical products are retained to show generational improvement. They are labeled
`status = 'previous'` and filtered separately in the UI.

### Compute Figures
All peak TFLOPS/TOPS figures are **non-sparse (dense)** unless explicitly noted.
NVIDIA Tensor Core specifications sometimes cite sparse (2:4 sparsity) figures that
are approximately 2× the dense value. This tool uses dense figures for fair comparison.

FP8 precision is only available on:
- NVIDIA Hopper architecture (H100, H200)
- AMD CDNA3 architecture (MI300X)

Comparing FP8 numbers against FP16/INT8 numbers from other products is **not valid**.

## 4. Benchmark Comparability

### MLPerf Inference
Results are from MLPerf Inference, a standardized benchmark managed by MLCommons.
The benchmark has multiple scenarios (Server, Offline, SingleStream, MultiStream).
This tool uses **Server scenario** results (continuous request stream, latency-constrained)
as the most representative of real production inference workloads.

### Comparability Assessment

A result pair is marked **comparable** when:
- Same benchmark version (e.g., both v4.0)
- Same workload and model (e.g., both Llama2-70B)
- Same numeric precision (e.g., both FP16)
- Same number of accelerators and system scenario
- Same benchmark scenario (Server vs Offline are not comparable)

A result pair is marked **conditional** when:
- Different benchmark versions are compared (optimizer improvements between versions
  can account for 10–30% differences independent of hardware)

A result pair is marked **not comparable** when:
- Different precisions (FP16 vs INT8)
- Different workloads
- Incompatible system configurations

The dashboard never aggregates benchmark results into a single "performance score."
Each result is shown with its full context.

## 5. Scoring Model

### Formula
Score = Σ (w_i × normalized_i) for each criterion i

where normalized_i = min-max normalization across the compared product set:
- Higher-is-better: `(value - min) / (max - min)`
- Lower-is-better (cost): `(max - value) / (max - min)`

Weights are normalized to sum to 1.0 before scoring.

### Missing Data Handling
A product missing a value for criterion i receives 0.0 for that criterion's contribution.
This is a deliberate penalty: missing data is not treated as average.

The coverage ratio (fraction of criteria with available data) is shown alongside the score.
A product with low coverage should be treated with caution regardless of its score.

### Qualitative Criteria
Software ecosystem compatibility is a 0–10 qualitative judgment assigned by the analyst,
based on community size, framework support, enterprise adoption, and published ROCm/CUDA
compatibility assessments as of early 2025. It is not a measured value.

Qualitative factors **not** in the scoring matrix (shown as text instead):
- Vendor support SLAs and enterprise contracts
- Hardware supply availability
- Migration effort from existing stacks
- Regulatory or compliance considerations

## 6. Financial Model Assumptions

### TCO Model
- CapEx = hardware (num_units × price_per_unit) + infrastructure cost
- Annual power cost = num_units × TDP × utilization × (1 + facility_overhead_pct/100) × 8760h × electricity_rate
- Facility overhead models PUE and ancillary losses as a percentage markup on active power
- Annual OpEx = power cost + support/software cost
- Total TCO = CapEx + OpEx × years

### Value Model
Users choose one value type to prevent double-counting:
- **Revenue-generating:** value = annual revenue from the deployment
- **Cost-saving:** value = annual cost reduction vs. the counterfactual

### NPV
Standard discounted cash flow. Year 0 = -CapEx. Years 1–N = annual value − annual OpEx.
Discount rate is user-supplied; it should represent the organization's cost of capital or
hurdle rate. A 10% default is provided but is not a recommendation.

### Cost Per Token
Only calculated when throughput is explicitly provided. Formula:
`cost_per_1M_tokens = (annual_opex / (throughput_tps × utilization × 3600 × 8760)) × 1,000,000`

This uses annual OpEx only. CapEx amortization is not included in this metric
(it is included in the full TCO and ROI calculations).

### Vendor Investment Model
This model is entirely hypothetical. It demonstrates the structure of a product
investment analysis — contribution margin, break-even, NPV — using user-supplied
assumptions. Under no circumstances should its outputs be treated as NVIDIA's or AMD's
actual unit economics, pricing strategy, or demand forecasts.
