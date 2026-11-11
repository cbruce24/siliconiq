"""
Display formatting helpers. Pure functions (no Streamlit) so they are testable.

Conventions used across the app:
- Currency: whole dollars below $1K, one decimal from $1K to $10K ($2.8K), whole
  thousands up to $1M ($450K), two decimals for millions and billions ($1.25M, $60.92B). Negative values use a true minus sign.
- Percentages: one decimal place.
- Unavailable values render as an em dash. Pages explain why next to the value.
"""
from __future__ import annotations

import math
from datetime import date
from typing import Any

DASH = "—"
MINUS = "−"


def is_missing(v: Any) -> bool:
    if v is None:
        return True
    try:
        return math.isnan(float(v))
    except (TypeError, ValueError):
        return False


def fmt_usd(v: Any, *, scale: float = 1.0) -> str:
    """Format a dollar amount with K/M/B units. `scale` converts the input to dollars
    (e.g. scale=1e6 for values stored in USD millions)."""
    if is_missing(v):
        return DASH
    x = float(v) * scale
    sign = MINUS if x < 0 else ""
    a = abs(x)
    if a >= 1e9:
        body = f"{a / 1e9:,.2f}B"
    elif a >= 1e6:
        body = f"{a / 1e6:,.2f}M"
    elif a >= 1e4:
        body = f"{a / 1e3:,.0f}K"
    elif a >= 1e3:
        body = f"{a / 1e3:,.1f}K"
    else:
        body = f"{a:,.0f}"
    return f"{sign}${body}"


def fmt_pct(v: Any, decimals: int = 1, *, signed: bool = False) -> str:
    if is_missing(v):
        return DASH
    x = float(v)
    s = f"{abs(x):,.{decimals}f}%"
    if x < 0:
        return MINUS + s
    return ("+" + s) if signed and x > 0 else s


def fmt_num(v: Any, decimals: int = 0, unit: str = "") -> str:
    if is_missing(v):
        return DASH
    x = float(v)
    s = f"{abs(x):,.{decimals}f}"
    s = (MINUS + s) if x < 0 else s
    return f"{s} {unit}".strip()


def fmt_years(v: Any) -> str:
    if is_missing(v):
        return DASH
    x = float(v)
    return f"{x:.1f} year" if abs(x - 1.0) < 0.05 else f"{x:.1f} years"


def fmt_date(iso: str | None) -> str:
    """'2025-01-15' -> '15 Jan 2025'."""
    if not iso:
        return DASH
    try:
        d = date.fromisoformat(str(iso)[:10])
    except ValueError:
        return str(iso)
    return f"{d.day} {d.strftime('%b %Y')}"


VENDOR_NAMES = {"NVDA": "NVIDIA", "AMD": "AMD"}


def vendor_name(ticker: str) -> str:
    return VENDOR_NAMES.get(ticker, ticker)


STATUS_LABELS = {
    "current": "Latest generation",
    "previous": "Previous generation",
    "announced": "Announced",
}


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, str(status).title())


def workload_label(workload: str) -> str:
    """'LLM_inference' -> 'LLM inference'."""
    s = str(workload).replace("_", " ")
    return s[:1].upper() + s[1:]
