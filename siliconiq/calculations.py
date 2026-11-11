"""
Core financial, scoring, and ROI calculations.
All functions are pure (no side effects) and independently testable.
"""
from __future__ import annotations
import math
from typing import Optional


# ── Financial ratios ──────────────────────────────────────────────────────────

def gross_margin(gross_profit: float, revenue: float) -> Optional[float]:
    """Gross margin as a percentage. Returns None on zero/negative revenue."""
    if revenue <= 0:
        return None
    return gross_profit / revenue * 100.0


def operating_margin(operating_income: float, revenue: float) -> Optional[float]:
    if revenue <= 0:
        return None
    return operating_income / revenue * 100.0


def rd_pct_revenue(rd_expense: float, revenue: float) -> Optional[float]:
    if revenue <= 0:
        return None
    return rd_expense / revenue * 100.0


def yoy_growth(current: float, prior: float) -> Optional[float]:
    """Year-over-year growth as a percentage."""
    if prior <= 0:
        return None
    return (current - prior) / prior * 100.0


# ── NPV / ROI / payback ───────────────────────────────────────────────────────

def npv(cash_flows: list[float], discount_rate: float) -> float:
    """
    NPV of a series of cash flows.
    cash_flows[0] is period 0 (initial outlay, typically negative).
    discount_rate is annual as a decimal (e.g. 0.10 for 10%).
    """
    if discount_rate < -1:
        raise ValueError("discount_rate must be > -1")
    return sum(cf / (1 + discount_rate) ** t for t, cf in enumerate(cash_flows))


def irr(cash_flows: list[float], guess: float = 0.1, max_iter: int = 1000) -> Optional[float]:
    """Newton-Raphson IRR. Returns None if it fails to converge."""
    rate = guess
    for _ in range(max_iter):
        f = sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))
        df = sum(-t * cf / (1 + rate) ** (t + 1) for t, cf in enumerate(cash_flows))
        if df == 0:
            return None
        new_rate = rate - f / df
        if abs(new_rate - rate) < 1e-9:
            return new_rate
        rate = new_rate
    return None


def payback_period(annual_net_benefit: float, initial_investment: float) -> Optional[float]:
    """
    Simple payback in years.
    Returns None if annual_net_benefit <= 0 (payback never occurs).
    """
    if annual_net_benefit <= 0 or initial_investment <= 0:
        return None
    return initial_investment / annual_net_benefit


def roi_pct(net_benefit: float, total_investment: float) -> Optional[float]:
    """ROI as a percentage = net_benefit / total_investment * 100."""
    if total_investment <= 0:
        return None
    return net_benefit / total_investment * 100.0


# ── Customer deployment TCO ───────────────────────────────────────────────────

def deployment_tco(
    num_accelerators: int,
    hw_price_per_unit: float,         # user-entered assumption
    infra_cost: float,                 # supporting infra (networking, servers)
    utilization_pct: float,           # 0-100
    tdp_watts: float,
    electricity_price_kwh: float,
    facility_overhead_pct: float,     # 0-100 of electricity cost
    annual_support_cost: float,
    deployment_years: int,
) -> dict:
    """
    Returns a dict with TCO components and totals.
    Power model: active_watts = tdp_watts * utilization / 100
    PUE is modeled as: total_facility_power = active_power * (1 + facility_overhead_pct/100)
    """
    if utilization_pct < 0 or utilization_pct > 100:
        raise ValueError("utilization_pct must be 0-100")
    if deployment_years <= 0:
        raise ValueError("deployment_years must be > 0")

    hw_capex = num_accelerators * hw_price_per_unit
    total_capex = hw_capex + infra_cost

    # Annual power cost
    active_watts = num_accelerators * tdp_watts * (utilization_pct / 100.0)
    facility_watts = active_watts * (1 + facility_overhead_pct / 100.0)
    kwh_per_year = facility_watts * 8760 / 1000.0
    annual_power_cost = kwh_per_year * electricity_price_kwh

    annual_opex = annual_power_cost + annual_support_cost
    total_opex = annual_opex * deployment_years
    total_tco = total_capex + total_opex

    return {
        "hw_capex": hw_capex,
        "infra_cost": infra_cost,
        "total_capex": total_capex,
        "active_watts": active_watts,
        "facility_watts": facility_watts,
        "kwh_per_year": kwh_per_year,
        "annual_power_cost": annual_power_cost,
        "annual_support_cost": annual_support_cost,
        "annual_opex": annual_opex,
        "total_opex": total_opex,
        "total_tco": total_tco,
        "deployment_years": deployment_years,
    }


def deployment_roi(
    tco: dict,
    annual_value: float,              # revenue OR cost savings (not both)
    discount_rate: float,
    deployment_years: int,
) -> dict:
    """
    Annual value: revenue generated OR cost savings — not both.
    Returns net_benefit, ROI%, payback, NPV.
    """
    # Build yearly cash flows: year 0 = -capex, years 1..N = value - opex
    annual_opex = tco["annual_opex"]
    flows = [-tco["total_capex"]]
    for _ in range(deployment_years):
        flows.append(annual_value - annual_opex)

    total_value = annual_value * deployment_years
    net_benefit = total_value - tco["total_tco"]
    roi = roi_pct(net_benefit, tco["total_tco"])
    payback = payback_period(annual_value - annual_opex, tco["total_capex"])
    project_npv = npv(flows, discount_rate)

    return {
        "cash_flows": flows,
        "total_value": total_value,
        "net_benefit": net_benefit,
        "roi_pct": roi,
        "payback_years": payback,
        "npv": project_npv,
        "discount_rate": discount_rate,
    }


def cost_per_token(
    annual_tco_cost: float,
    tokens_per_second: float,
    utilization_pct: float,
) -> Optional[float]:
    """
    Cost per 1M tokens. Returns None when utilization or throughput is 0.
    tokens_per_second: system throughput at 100% utilization.
    """
    if utilization_pct <= 0 or tokens_per_second <= 0:
        return None
    effective_tps = tokens_per_second * (utilization_pct / 100.0)
    tokens_per_year = effective_tps * 3600 * 8760
    return (annual_tco_cost / tokens_per_year) * 1_000_000


# ── Vendor investment model ───────────────────────────────────────────────────

def vendor_model(
    unit_demand: float,
    selling_price: float,
    unit_cost: float,
    fixed_dev_investment: float,
    annual_operating_cost: float,
    demand_growth_pct: float,         # annual % growth
    years: int,
    discount_rate: float,
) -> dict:
    """
    Hypothetical vendor economics. All inputs are user assumptions.
    Returns revenue, contribution margin, break-even, project ROI, NPV.
    """
    contribution_margin = selling_price - unit_cost
    if selling_price > 0:
        cm_pct = contribution_margin / selling_price * 100.0
    else:
        cm_pct = None

    if contribution_margin > 0:
        break_even_units = (fixed_dev_investment + annual_operating_cost) / contribution_margin
    else:
        break_even_units = None

    flows = [-(fixed_dev_investment)]
    total_revenue = 0.0
    total_cogs = 0.0
    year_demand = unit_demand
    for y in range(1, years + 1):
        if y > 1:
            year_demand *= (1 + demand_growth_pct / 100.0)
        yr_rev = year_demand * selling_price
        yr_cogs = year_demand * unit_cost
        yr_operating_contribution = yr_rev - yr_cogs - annual_operating_cost
        flows.append(yr_operating_contribution)
        total_revenue += yr_rev
        total_cogs += yr_cogs

    total_investment = fixed_dev_investment + annual_operating_cost * years
    net_profit = sum(flows)
    project_roi = roi_pct(net_profit, fixed_dev_investment) if fixed_dev_investment > 0 else None
    project_npv = npv(flows, discount_rate)

    return {
        "cash_flows": flows,
        "contribution_margin": contribution_margin,
        "cm_pct": cm_pct,
        "break_even_units": break_even_units,
        "total_revenue": total_revenue,
        "total_cogs": total_cogs,
        "net_profit": net_profit,
        "project_roi_pct": project_roi,
        "project_npv": project_npv,
        "discount_rate": discount_rate,
    }


# ── Weighted decision matrix ──────────────────────────────────────────────────

def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    """Normalize a dict of weights to sum to 1.0. Raises on zero/negative totals."""
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("Sum of weights must be positive")
    return {k: v / total for k, v in weights.items()}


def score_product(
    product_metrics: dict[str, Optional[float]],
    all_products_metrics: list[dict[str, Optional[float]]],
    weights: dict[str, float],
    higher_is_better: dict[str, bool],
) -> dict:
    """
    Normalize each metric across all products (min-max), apply weights.
    Missing values receive a coverage penalty (scored as 0.0 for the metric,
    and the coverage ratio is returned explicitly).

    Returns: {'score': float, 'coverage': float, 'breakdown': dict}
    """
    norm_weights = normalize_weights(weights)
    total_weight = 0.0
    weighted_score = 0.0
    covered = 0
    total_criteria = len(weights)
    breakdown = {}

    for criterion, weight in norm_weights.items():
        raw = product_metrics.get(criterion)
        all_vals = [
            p.get(criterion) for p in all_products_metrics
            if p.get(criterion) is not None
        ]

        if raw is None or len(all_vals) == 0:
            breakdown[criterion] = {
                "raw": None,
                "normalized": None,
                "weighted": 0.0,
                "missing": True,
            }
            # Weight contributes 0 to score — missing data is a penalty
            continue

        covered += 1
        min_val = min(all_vals)
        max_val = max(all_vals)

        if max_val == min_val:
            normalized = 1.0
        else:
            if higher_is_better.get(criterion, True):
                normalized = (raw - min_val) / (max_val - min_val)
            else:
                normalized = (max_val - raw) / (max_val - min_val)

        weighted_contrib = normalized * weight
        weighted_score += weighted_contrib
        breakdown[criterion] = {
            "raw": raw,
            "normalized": round(normalized, 4),
            "weighted": round(weighted_contrib, 4),
            "missing": False,
        }

    coverage = covered / total_criteria if total_criteria > 0 else 0.0

    return {
        "score": round(weighted_score, 4),
        "coverage": round(coverage, 4),
        "breakdown": breakdown,
    }


# ── Sensitivity analysis ──────────────────────────────────────────────────────

def sensitivity_heatmap(
    base_params: dict,
    param_x: str,
    param_y: str,
    x_values: list[float],
    y_values: list[float],
    model_fn,          # callable(params) -> scalar metric
) -> list[list[float]]:
    """
    Returns a 2D list [len(y_values)][len(x_values)] of model outputs.
    model_fn receives a copy of base_params with param_x and param_y swapped in.
    """
    import copy
    result = []
    for y_val in y_values:
        row = []
        for x_val in x_values:
            params = copy.deepcopy(base_params)
            params[param_x] = x_val
            params[param_y] = y_val
            row.append(model_fn(params))
        result.append(row)
    return result
