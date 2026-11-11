"""
Excel workbook export. Sheets mirror dashboard sections.
All callers must use keyword arguments to avoid positional order errors.
"""
from __future__ import annotations
import io
import datetime
import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

HEADER_BG = "1F2937"
HEADER_FG = "FFFFFF"


# ── Cell-level helpers ────────────────────────────────────────────────────────

def _safe_val(v):
    """Return a value safe to write into an openpyxl cell (no lists/dicts)."""
    if v is None:
        return "N/A"
    if isinstance(v, (list, dict, tuple)):
        return f"[{type(v).__name__} — see structured table]"
    if isinstance(v, float):
        return round(v, 4)
    return v


def _style_header(ws, row: int, ncols: int) -> None:
    for col in range(1, ncols + 1):
        cell = ws.cell(row=row, column=col)
        cell.font = Font(bold=True, color=HEADER_FG)
        cell.fill = PatternFill("solid", fgColor=HEADER_BG)
        cell.alignment = Alignment(horizontal="center")


def _autofit(ws) -> None:
    for col in ws.columns:
        max_len = max((len(str(c.value)) for c in col if c.value is not None), default=10)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max_len + 4, 60)


def _write_df(ws, df: pd.DataFrame, start_row: int = 1) -> int:
    """Write a DataFrame starting at start_row; return next free row."""
    headers = list(df.columns)
    for ci, h in enumerate(headers, 1):
        ws.cell(row=start_row, column=ci, value=str(h))
    _style_header(ws, start_row, len(headers))
    for ri, row in enumerate(df.itertuples(index=False), start_row + 1):
        for ci, val in enumerate(row, 1):
            ws.cell(row=ri, column=ci, value=_safe_val(val))
    _autofit(ws)
    return start_row + len(df) + 2


def _write_kv(ws, data: dict, start_row: int, section_label: str) -> int:
    """Write a key-value dict as two columns under a bold section header."""
    ws.cell(row=start_row, column=1, value=section_label).font = Font(bold=True)
    start_row += 1
    for k, v in data.items():
        ws.cell(row=start_row, column=1, value=str(k))
        ws.cell(row=start_row, column=2, value=_safe_val(v))
        start_row += 1
    return start_row + 1


def _write_cash_flow_table(
    ws,
    cash_flows: list[float],
    discount_rate: float,
    start_row: int,
    section_label: str = "Cash Flow Schedule",
) -> int:
    """
    Write a structured cash flow table: Year | Raw CF | Discount Factor |
    Discounted CF | Cumulative Discounted CF.
    Returns next free row.
    """
    ws.cell(row=start_row, column=1, value=section_label).font = Font(bold=True)
    start_row += 1
    headers = ["Year", "Cash Flow ($)", "Discount Factor", "Discounted CF ($)", "Cumulative DCF ($)"]
    for ci, h in enumerate(headers, 1):
        ws.cell(row=start_row, column=ci, value=h)
    _style_header(ws, start_row, len(headers))
    start_row += 1

    cumulative = 0.0
    for t, cf in enumerate(cash_flows):
        df_factor = 1.0 / (1 + discount_rate) ** t if discount_rate > -1 else 0.0
        dcf = cf * df_factor
        cumulative += dcf
        ws.cell(row=start_row + t, column=1, value=t)
        ws.cell(row=start_row + t, column=2, value=round(cf, 2))
        ws.cell(row=start_row + t, column=3, value=round(df_factor, 6))
        ws.cell(row=start_row + t, column=4, value=round(dcf, 2))
        ws.cell(row=start_row + t, column=5, value=round(cumulative, 2))

    _autofit(ws)
    return start_row + len(cash_flows) + 1


# ── Main workbook builder ─────────────────────────────────────────────────────

def build_workbook(
    *,
    financials_df: pd.DataFrame,
    segment_df: pd.DataFrame,
    products_df: pd.DataFrame,
    benchmarks_df: pd.DataFrame,
    scoring_df: pd.DataFrame,
    tco_dict: dict,
    roi_dict: dict,
    vendor_model_result: dict,
    vendor_assumptions: dict,
    sources_df: pd.DataFrame,
) -> bytes:
    """
    Build and return an .xlsx workbook as bytes.

    All parameters are keyword-only to prevent positional order mistakes.

    vendor_model_result  — output of calculations.vendor_model() or a placeholder dict
    vendor_assumptions   — user-entered scalar assumptions for the vendor model
    tco_dict             — output of calculations.deployment_tco()
    roi_dict             — output of calculations.deployment_roi()
    """
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)

    generated = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    disclaimer = (
        "Dataset snapshot: 2025-01-15 | "
        "Hardware prices are user-entered assumptions, not public list prices."
    )

    # ── Sheet 1: Financial Summary ────────────────────────────────────────────
    ws1 = wb.create_sheet("Financial Summary")
    ws1["A1"] = "SiliconIQ — Financial Summary"
    ws1["A1"].font = Font(bold=True, size=14)
    ws1["A2"] = f"Generated: {generated}"
    ws1["A3"] = disclaimer
    ws1["A3"].font = Font(italic=True)
    _write_df(ws1, financials_df, start_row=5)

    # ── Sheet 2: Segment Revenue ──────────────────────────────────────────────
    ws2 = wb.create_sheet("Segment Revenue")
    ws2["A1"] = "Segment Revenue by Company and Period"
    ws2["A1"].font = Font(bold=True, size=14)
    ws2["A2"] = (
        "NOTE: NVIDIA Data Center and AMD Data Center segments include "
        "products beyond AI accelerators. Segment ≠ AI accelerator revenue."
    )
    ws2["A2"].font = Font(italic=True, color="CC0000")
    _write_df(ws2, segment_df, start_row=4)

    # ── Sheet 3: Product Catalog ──────────────────────────────────────────────
    ws3 = wb.create_sheet("Product Catalog")
    ws3["A1"] = "AI Accelerator Catalog"
    ws3["A1"].font = Font(bold=True, size=14)
    ws3["A2"] = "Prices are user-entered assumptions — not public list prices or quotes."
    ws3["A2"].font = Font(italic=True, color="CC0000")
    _write_df(ws3, products_df, start_row=4)

    # ── Sheet 4: Benchmarks ───────────────────────────────────────────────────
    ws4 = wb.create_sheet("Benchmarks")
    ws4["A1"] = "Benchmark Observations (MLPerf)"
    ws4["A1"].font = Font(bold=True, size=14)
    ws4["A2"] = (
        "Only results marked 'comparable' (same version, workload, precision, config) "
        "support direct head-to-head comparison."
    )
    ws4["A2"].font = Font(italic=True)
    _write_df(ws4, benchmarks_df, start_row=4)

    # ── Sheet 5: Decision Matrix ──────────────────────────────────────────────
    ws5 = wb.create_sheet("Decision Matrix")
    ws5["A1"] = "Customer Scoring Results"
    ws5["A1"].font = Font(bold=True, size=14)
    ws5["A2"] = (
        "Score = weighted sum of min-max normalized metrics (0-1). "
        "Missing values score 0.0 — absence of data is a penalty, not neutral."
    )
    ws5["A2"].font = Font(italic=True)
    _write_df(ws5, scoring_df, start_row=4)

    # ── Sheet 6: Deployment Economics ────────────────────────────────────────
    ws6 = wb.create_sheet("Deployment Economics")
    ws6["A1"] = "TCO and ROI — Customer Deployment Model"
    ws6["A1"].font = Font(bold=True, size=14)
    ws6["A2"] = "All hardware prices are user-entered assumptions."
    ws6["A2"].font = Font(italic=True, color="CC0000")

    row = 4
    # TCO components
    tco_display = {k: v for k, v in tco_dict.items()}
    row = _write_kv(ws6, tco_display, row, "TCO Components")

    # ROI scalars (skip cash_flows list)
    roi_scalars = {k: v for k, v in roi_dict.items() if k != "cash_flows"}
    row = _write_kv(ws6, roi_scalars, row, "ROI Summary")

    # Cash flow table with discounting
    cfs = roi_dict.get("cash_flows", [])
    dr = roi_dict.get("discount_rate", 0.0) or 0.0
    if cfs:
        row = _write_cash_flow_table(ws6, cfs, dr, row, "Deployment Cash Flow Schedule")

    # ── Sheet 7: Vendor Investment ────────────────────────────────────────────
    ws7 = wb.create_sheet("Vendor Investment")
    ws7["A1"] = "Hypothetical Vendor Investment Model"
    ws7["A1"].font = Font(bold=True, size=14)
    ws7["A2"] = (
        "ALL values are user-entered hypothetical assumptions. "
        "They do NOT represent NVIDIA or AMD internal economics."
    )
    ws7["A2"].font = Font(italic=True, color="CC0000")

    row = 4
    # User-entered assumptions (all scalars)
    row = _write_kv(ws7, vendor_assumptions, row, "Input Assumptions")

    # Computed results (scalars only)
    vendor_scalars = {k: v for k, v in vendor_model_result.items() if k != "cash_flows"}
    row = _write_kv(ws7, vendor_scalars, row, "Computed Results")

    # Cash flow table
    vcfs = vendor_model_result.get("cash_flows", [])
    vdr = vendor_model_result.get("discount_rate", 0.0) or 0.0
    if vcfs:
        row = _write_cash_flow_table(ws7, vcfs, vdr, row, "Vendor Cash Flow Schedule")

    # ── Sheet 8: Sources ──────────────────────────────────────────────────────
    ws8 = wb.create_sheet("Sources")
    ws8["A1"] = "Data Sources and Provenance"
    ws8["A1"].font = Font(bold=True, size=14)
    ws8["A2"] = f"Dataset snapshot date: 2025-01-15 | Retrieval date per source listed below."
    _write_df(ws8, sources_df, start_row=4)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
