# SiliconIQ — Interview Walkthrough

Use this as a guide to walk through the project confidently in a PM or technical
sales interview. Each section answers a standard behavioral or case question using
a concrete artifact from the implementation.

---

## 1. One Customer Problem

**The question an interviewer might ask:**
"Walk me through a customer problem this tool addresses."

**Your answer:**

A research organization wants to train a 70-billion-parameter language model in-house.
They have a budget constraint and a timeline. They receive conflicting claims from NVIDIA
and AMD reps, public benchmarks that compare configurations they'd never actually deploy,
and financial headlines about NVIDIA's dominant market position — none of which directly
answers their question: *which accelerator should we buy, and what will it actually cost?*

The specific friction I designed around: existing comparisons either cherry-pick benchmark
configurations that favor one vendor, or they present raw specs without explaining what
matters for the specific workload. Memory capacity is the binding constraint for
70B+ training (you need to fit the model and optimizer states), but most benchmark tables
lead with TFLOPS — which is secondary when you're memory-bound.

**What to show:** Open the Customer Strategy page, select "Research (Large-Model Training),"
observe that memory capacity weight defaults to 35% and the MI300X (192 GB) scores highest
under those weights. Then drop memory weight to 10% and show how the ranking flips — which
demonstrates the tool is surfacing a real sensitivity, not a predetermined answer.

---

## 2. One Resulting Product Requirement

**The question an interviewer might ask:**
"How did that customer problem turn into a specific product requirement?"

**Your answer:**

The customer problem — "I can't tell what's missing from this comparison" — translated
directly into the requirement: **missing data must be penalized, not hidden.**

An early design instinct would be to impute missing values (use the average, or exclude
the criterion from scoring). Both approaches would silently distort the result. If a
vendor hasn't published FP8 benchmarks for a product, scoring it as "average" would
reward the absence of information.

The implementation requirement: when a product is missing a value for a criterion,
its contribution for that criterion is exactly 0.0, and a coverage ratio is shown
alongside the score. This is documented in `calculations.py:score_product()` and
tested in `test_score_product_missing_penalized`.

**What to show:** In the terminal: `python -m pytest tests/test_calculations.py::test_score_product_missing_penalized -v`

---

## 3. One Analytical Insight

**The question an interviewer might ask:**
"What's the most interesting thing you found in the data?"

**Your answer:**

NVIDIA's gross margin jumped from 56.9% in FY2023 to 72.7% in FY2024 — a 16-point
increase in a single year. That's not typical of a hardware company selling more of
the same product. It reflects a combination of explosive H100 demand (prices were set
before the AI boom became clear), a favorable product mix shift toward the higher-margin
Data Center segment, and operating leverage on a relatively fixed cost structure.

The flip side: AMD's gross margin was 43.5% in FY2023, down from 46.1% in FY2021. AMD
grew revenue faster than NVIDIA in FY2022 (via the Xilinx acquisition), but the
operating margin compression shows the R&D and integration costs of that expansion.
AMD spent 25.9% of revenue on R&D in FY2023 vs. NVIDIA's 14.2% — AMD is investing
aggressively while competing from behind.

**What this means for a product decision:** NVIDIA's margin premium is partly structural
(larger install base → more software stickiness → higher pricing power) and partly
cyclical (AI boom demand). A buyer should ask whether that premium persists when H200
and next-generation AMD products reach the market.

**What to show:** Company Financials page → margin trend chart → point out the FY2024 divergence.

---

## 4. One Engineering Tradeoff

**The question an interviewer might ask:**
"Walk me through a technical decision you made and the tradeoff involved."

**Your answer:**

The most consequential data model decision was how to handle NULL values in the
`financial_observations` table's uniqueness constraint.

The table has a `segment` column — NULL when a row is a company-total (no segment),
and a string like "Data_Center" when it represents a segment breakdown. I wanted
a UNIQUE constraint on `(period_id, metric, segment)` to prevent duplicate rows
on re-ingestion.

The tradeoff: **SQL standard semantics treat NULL ≠ NULL**, so SQLite's standard UNIQUE
constraint does not deduplicate two rows where both have `segment IS NULL`. A second
ingestion run would silently insert duplicate company-total rows.

**The solution:** A partial expression index:
```sql
CREATE UNIQUE INDEX idx_fin_obs_unique
  ON financial_observations(period_id, metric, COALESCE(segment, ''));
```

This maps NULL to an empty string for uniqueness purposes only — the column still
stores NULL semantically. The `ON CONFLICT` clause in the INSERT statement targets
this index explicitly.

**The test:** `test_ingestion_no_duplicates` runs ingestion three times and asserts
row count is identical after each run.

**Why this matters in an interview:** It shows I understand the difference between
"it looks like it works" and "it's provably correct," and that I test the assumption
rather than just asserting it.

---

## 5. One Limitation and How You'd Address It

**The question an interviewer might ask:**
"What's the biggest limitation of this tool, and what would you do next?"

**Your answer:**

The biggest limitation is that the deployment economics model uses a simplified,
single-accelerator-type scenario. Real enterprise deployments are heterogeneous:
some workloads run on H100s, others on A100s that are still in service, some on
cloud instances. The TCO comparison can't currently model a mixed-fleet scenario
or a phased hardware refresh.

**What I'd do next:** Add a multi-scenario comparison view — two side-by-side TCO
models with the same time horizon and discount rate, so a buyer can compare "all H100s
now" vs. "A100s for 18 months, then H200s." The underlying calculation functions
already support this (they're stateless and composable); the work would be in the
UI and in defining a consistent time-horizon normalization.

**The metric I'd track in a user study:** How often do users run only one scenario
vs. modify assumptions to explore alternatives? Low exploration rate would mean either
the UI makes multi-scenario comparison too hard, or users don't realize the model
supports it — both actionable findings.

---

## Résumé Bullets

These are factually supported by the completed implementation:

1. **Built a 7-page interactive analytics dashboard** in Python/Streamlit comparing
   NVIDIA and AMD across 6 fiscal years of SEC 10-K financials, 6 AI accelerator
   product specifications, and MLPerf benchmark submissions, with SQL-backed data
   provenance for every stored value.

2. **Designed and tested a transparent weighted decision matrix** with min-max
   normalization, explicit missing-data penalties, and coverage reporting; validated
   with 49 unit tests covering financial ratios, NPV, TCO, ROI, payback, break-even,
   and ingestion idempotency.

3. **Implemented dual ROI models** — a customer deployment TCO/NPV model and a
   hypothetical vendor investment model — each with two-variable sensitivity heatmaps,
   downloadable Excel exports, and clearly labeled assumptions to prevent misuse
   as vendor-attributed data.
