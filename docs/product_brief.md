# SiliconIQ — Product Brief

## Intended User

An Electrical/Computer Engineering student or early-career engineer interested in
product management, technical sales, or customer-facing roles in the semiconductor
or AI infrastructure space. Also useful for analysts and PMs who need to structure
a hardware evaluation or investment thesis around AI accelerators.

## Problem

Engineers evaluating AI accelerator deployments have to reconcile three different
types of information that are rarely presented together:
1. **Financial context** — How are these companies performing, and what does that
   signal about their product investment and market position?
2. **Technical specifications and benchmarks** — How do products actually compare
   on the workloads that matter to a specific customer?
3. **Economic modeling** — Given real constraints (budget, power, utilization), what
   does deployment actually cost and when does it pay off?

No existing public tool connects all three in a structured, source-referenced,
assumption-transparent way.

## Main Use Cases

| Use Case | User | Key Feature |
|---|---|---|
| Preparing for a hardware vendor evaluation | Enterprise architect | Product catalog, scoring matrix, TCO comparison |
| Structuring an investment thesis for AI infra | Analyst / PM | Financial comparison, segment revenue, ROI model |
| Demonstrating PM and analytical skills | Job applicant / student | Full end-to-end: data → analysis → decision |
| Understanding AI accelerator tradeoffs | Student / newcomer | Benchmark comparability notes, methodology guide |

## MVP Scope (Implemented)

- Financial comparison: NVDA and AMD, 3 fiscal years each, from SEC 10-K filings
- Product catalog: 6 accelerators (4 current, 2 previous) with official specs
- Benchmark data: MLPerf Inference v4.0 and v3.1 (Llama2-70B, ResNet-50)
- Customer scoring: 3 preset profiles, editable weights, transparent scoring formula
- TCO & ROI: full deployment economics with sensitivity heatmap
- Vendor investment model: contribution margin, break-even, NPV, 3 scenarios, heatmap
- Excel export from every major section
- 49 passing tests covering all calculation functions

## Success Criteria

**Functional:**
- All 7 dashboard sections load without errors
- Calculations match hand-verified examples (covered by tests)
- Re-running ingestion produces identical row counts (idempotency tested)
- Excel exports contain the same values shown in the dashboard

**Analytical quality:**
- No fabricated data — every value has a source or is labeled as a user assumption
- Missing data is penalized, not hidden
- Benchmark comparisons show explicit comparability status
- Fiscal calendar differences are explained, not glossed over

## Known Limitations and Data Gaps

| Gap | Impact | Resolution |
|---|---|---|
| No public hardware prices | Cost scoring requires user assumptions | Labeled clearly; test with realistic ranges |
| MLPerf covers only standardized models | Custom workloads not benchmarked | Use as directional signal, not absolute ranking |
| AMD FY2023 segment structure change | Pre-2023 AMD segments don't map 1:1 | Segments labeled with their actual names as reported |
| NVIDIA FY2025 not included | Most recent period missing | Update ingest.py when 10-K is filed |
| No GPU utilization data from customers | TCO utilization is assumption-only | Slide utilization slider to understand sensitivity |
| H100 PCIe has no MLPerf submission in dataset | Benchmark section shows only H100 SXM5 | Noted in product catalog; add if submission found |

## Future Improvements (Prioritized)

1. **Automated filing parser** — Parse XBRL data from SEC EDGAR to auto-update
   financials when new 10-Ks are filed, reducing manual transcription risk.

2. **Workload-specific benchmark filtering** — Let users specify their actual workload
   (e.g., fine-tuning, batch inference, real-time inference) and filter benchmarks
   accordingly, with explicit "no data available" states.

3. **Multi-node scaling model** — Extend the TCO model to support cluster-level
   analysis (inter-node networking costs, NVLink vs InfiniBand tradeoffs).

4. **Competitor expansion** — Add Intel Gaudi 2/3 and Google TPU v5 with the same
   sourcing standards already applied to NVDA and AMD products.

5. **User study metrics to validate** (hypothetical, not measured):
   - Time to reach a defensible hardware recommendation (baseline vs. with tool)
   - Frequency of "I forgot to account for X" discoveries (facility overhead, support cost)
   - Confidence rating before/after using the scoring matrix

## Metrics for Future User Study

The following metrics *could* be measured with a structured user study. They have not
been measured and no claims are made about current user behavior.

- Task completion rate: Can a user configure a scenario and export results in < 15 minutes?
- Assumption awareness: Do users correctly identify which values are assumptions vs. reported?
- Recommendation consistency: Do two users with the same profile reach the same scoring result?
