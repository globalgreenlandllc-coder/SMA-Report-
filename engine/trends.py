"""
trends.py -- Neighborhood market trends derived from the comp set.

Computes, from the closed + active comps:
  * price-per-sqft over time (monthly)
  * months of inventory (active supply vs. recent absorption)
  * sold-to-list ratio (are homes selling over/under ask?)

Pure Python / standard library. Returns plain dicts ready for SVG sparklines in
the UI and the report.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from statistics import median


def _num(v, default=0.0):
    try:
        return default if v is None else float(v)
    except (TypeError, ValueError):
        return default


def _is_closed(c):
    return str(c.get("StandardStatus", "")).strip().lower() in {"closed", "sold"}


def _month(value):
    if not value:
        return None
    text = str(value)[:10]
    try:
        d = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None
    return f"{d.year:04d}-{d.month:02d}"


def market_trends(comps: list) -> dict:
    closed = [c for c in comps if _is_closed(c)]
    active = [c for c in comps if not _is_closed(c)]

    # ---- price per sqft over time (monthly median) ----
    by_month = defaultdict(list)
    for c in closed:
        m = _month(c.get("CloseDate"))
        area = _num(c.get("LivingArea"))
        price = _num(c.get("ClosePrice")) or _num(c.get("ListPrice"))
        if m and area > 0 and price > 0:
            by_month[m].append(price / area)
    ppsf_series = [{"month": m, "ppsf": round(median(v), 2), "n": len(v)}
                   for m, v in sorted(by_month.items())]

    # ---- sold-to-list ratio ----
    ratios = []
    for c in closed:
        cp = _num(c.get("ClosePrice"))
        lp = _num(c.get("ListPrice"))
        if cp > 0 and lp > 0:
            ratios.append(cp / lp)
    sold_to_list = round(median(ratios), 4) if ratios else None

    # ---- months of inventory ----
    # active supply / average closed sales per month over the observed window.
    n_months = max(1, len(by_month))
    absorption = len(closed) / n_months if closed else 0
    months_of_inventory = round(len(active) / absorption, 1) if absorption else None

    return {
        "ppsf_series": ppsf_series,
        "sold_to_list": sold_to_list,
        "sold_to_list_pct": round(sold_to_list * 100, 1) if sold_to_list else None,
        "months_of_inventory": months_of_inventory,
        "n_closed": len(closed),
        "n_active": len(active),
        "market_label": _market_label(months_of_inventory),
    }


def _market_label(moi):
    if moi is None:
        return "unknown"
    if moi < 4:
        return "seller's market"
    if moi <= 6:
        return "balanced market"
    return "buyer's market"
