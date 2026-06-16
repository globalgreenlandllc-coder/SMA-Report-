"""
cma_engine.py -- Comparative Market Analysis pricing engine.

Pure Python, with ZERO dependency on any data source or report format. It takes a
subject property and a list of comparable listings (already mapped to RESO Data
Dictionary field names) and returns a structured valuation: a Low/Likely/High
price range, a 0-100 confidence score with plain-language reasons, and a per-comp
adjustment breakdown the agent can inspect or override.

Why it is "smart"
-----------------
* Adjustment values are DERIVED FROM THE LOCAL COMPS, not hardcoded. The dominant
  driver -- price per square foot -- is the median of ClosePrice / LivingArea
  across the closed comps, so it adapts to each neighborhood. Per-feature dollar
  values (bed, bath, garage, age) are anchored to that local price-per-sqft, and
  pool value is estimated directly from the comp set when there are enough
  pool / non-pool sales to compare.
* Comps are weighted by similarity + recency + distance. Statistical outliers are
  flagged and down-weighted rather than silently dropped, so nothing is hidden.
* The agent can pass ``include`` overrides (toggle comps in/out) and the whole
  valuation recomputes -- never a black box.

RESO field names consumed (Data Dictionary):
    ListingId, ListingUrl, ListOfficeName, StandardStatus, ClosePrice, ListPrice,
    CloseDate, LivingArea, BedroomsTotal, BathroomsTotalInteger, GarageSpaces,
    PoolPrivateYN, YearBuilt, Latitude, Longitude.

TODO (planned "next task"): replace the ppsf-anchored per-feature values with a
regression fit on each market's comps for sharper, fully data-driven adjustments.
"""
from __future__ import annotations

import math
from datetime import date, datetime
from statistics import median
from typing import Optional

from .regression import fit_adjustments


# ---------------------------------------------------------------------------
# Field access helpers (tolerant of missing / None values)
# ---------------------------------------------------------------------------

def _num(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_date(value) -> Optional[date]:
    """Parse an ISO-ish date string or pass through a date/datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text[: len(fmt) + 4], fmt).date()
        except ValueError:
            continue
    # Last resort: take the leading YYYY-MM-DD.
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _is_closed(comp: dict) -> bool:
    return str(comp.get("StandardStatus", "")).strip().lower() in {"closed", "sold"}


def _base_price(comp: dict) -> float:
    """Sale price for closed comps, list price for active listings."""
    if _is_closed(comp):
        return _num(comp.get("ClosePrice")) or _num(comp.get("ListPrice"))
    return _num(comp.get("ListPrice")) or _num(comp.get("ClosePrice"))


# ---------------------------------------------------------------------------
# Geo
# ---------------------------------------------------------------------------

def haversine_miles(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance between two lat/lon points, in statute miles."""
    if None in (lat1, lon1, lat2, lon2):
        return 0.0
    r = 3958.7613  # earth radius, miles
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


# ---------------------------------------------------------------------------
# Market-derived adjustment values
# ---------------------------------------------------------------------------

def derive_adjustments(comps: list, method: str = "auto", ref_year: Optional[int] = None) -> dict:
    """
    Derive dollar adjustment values from the local comp set.

    method:
        "auto"       -- fit a regression when the data supports it, otherwise use
                        the ppsf-anchored heuristics; any regression coefficient
                        that fails validation falls back to its heuristic value.
        "regression" -- same as auto (regression is always validated/fallback-backed).
        "heuristic"  -- force the ppsf-anchored heuristics only.

    The heuristic baseline: price_per_sqft is the median ClosePrice/LivingArea
    across closed comps (neighborhood-aware); per-feature values are anchored to
    that local ppsf; pool value is measured from the comps when the data supports it.
    """
    closed = [c for c in comps if _is_closed(c) and _num(c.get("LivingArea")) > 0]
    ppsf_samples = [
        _base_price(c) / _num(c.get("LivingArea"))
        for c in closed
        if _base_price(c) > 0
    ]
    # Fall back to all comps if there are no usable closed sales.
    if not ppsf_samples:
        ppsf_samples = [
            _base_price(c) / _num(c.get("LivingArea"))
            for c in comps
            if _num(c.get("LivingArea")) > 0 and _base_price(c) > 0
        ]
    ppsf = median(ppsf_samples) if ppsf_samples else 0.0

    # Sqft-equivalents: how much extra living area a feature is "worth" locally.
    # Anchored to ppsf so the dollar value scales with the neighborhood.
    bed_value = round(ppsf * 110)          # ~110 sqft of value per bedroom
    bath_value = round(ppsf * 55)          # ~55 sqft per full bath
    garage_value = round(ppsf * 70)        # ~70 sqft per garage space
    age_value_per_year = round(ppsf * 0.5)  # mild depreciation per year of age

    pool_value = _derive_pool_value(closed, ppsf)

    adj = {
        "price_per_sqft": round(ppsf, 2),
        "bed_value": bed_value,
        "bath_value": bath_value,
        "garage_value": garage_value,
        "age_value_per_year": age_value_per_year,
        "pool_value": pool_value,
        "pool_value_source": "comps" if _pool_derivable(closed) else "ppsf-fallback",
        "n_ppsf_samples": len(ppsf_samples),
        "method": "heuristic",
        "regression": None,
    }

    if method in ("auto", "regression"):
        if ref_year is None:
            years = [int(_num(c.get("YearBuilt"))) for c in comps if c.get("YearBuilt")]
            ref_year = (max(years) if years else date.today().year)
        fit = fit_adjustments(comps, ref_year)
        if fit:
            # Override only the features the regression validated; keep heuristic
            # values (and pool source) for the rest. Never a silent black box.
            for key in ("price_per_sqft", "bed_value", "bath_value",
                        "garage_value", "pool_value", "age_value_per_year"):
                if key in fit:
                    adj[key] = fit[key]
                    if key == "pool_value":
                        adj["pool_value_source"] = "regression"
            adj["method"] = "regression"
            adj["regression"] = {
                "n": fit["n"], "r2": fit["r2"],
                "features_used": fit["features_used"],
                "dropped_features": fit["dropped_features"],
            }

    return adj


def _pool_derivable(closed: list) -> bool:
    with_pool = [c for c in closed if bool(c.get("PoolPrivateYN"))]
    without = [c for c in closed if not bool(c.get("PoolPrivateYN"))]
    return len(with_pool) >= 2 and len(without) >= 2


def _derive_pool_value(closed: list, ppsf: float) -> int:
    """
    Estimate pool value from the comp set: compare size-normalized prices of
    pooled vs non-pooled sales. Falls back to a ppsf multiple when there are too
    few of either to compare. Clamped to a sane non-negative range.
    """
    if _pool_derivable(closed):
        def adj_ppsf(group):
            vals = [
                _base_price(c) / _num(c.get("LivingArea"))
                for c in group
                if _num(c.get("LivingArea")) > 0 and _base_price(c) > 0
            ]
            return median(vals) if vals else 0.0

        with_pool = [c for c in closed if bool(c.get("PoolPrivateYN"))]
        without = [c for c in closed if not bool(c.get("PoolPrivateYN"))]
        med_sqft = median([_num(c.get("LivingArea")) for c in closed if _num(c.get("LivingArea")) > 0])
        delta_ppsf = adj_ppsf(with_pool) - adj_ppsf(without)
        estimate = delta_ppsf * med_sqft
        # Clamp: a pool rarely adds < 0 or more than ~12% of median ppsf-value.
        ceiling = ppsf * med_sqft * 0.12
        return int(max(0, min(estimate, ceiling)))
    # Fallback: a pool is worth roughly a small fixed multiple of local ppsf.
    return int(round(ppsf * 60))


# ---------------------------------------------------------------------------
# Per-comp adjustment
# ---------------------------------------------------------------------------

def adjust_comp(subject: dict, comp: dict, adj: dict, ref_date: date) -> dict:
    """
    Adjust one comp's base price toward the subject and compute its weight.

    Returns a dict with the adjusted price, a line-item breakdown (for the
    side-by-side view), distance, recency, and the composite weight.
    """
    base = _base_price(comp)
    ppsf = adj["price_per_sqft"]

    d_sqft = _num(subject.get("LivingArea")) - _num(comp.get("LivingArea"))
    d_bed = _num(subject.get("BedroomsTotal")) - _num(comp.get("BedroomsTotal"))
    d_bath = _num(subject.get("BathroomsTotalInteger")) - _num(comp.get("BathroomsTotalInteger"))
    d_garage = _num(subject.get("GarageSpaces")) - _num(comp.get("GarageSpaces"))
    subj_pool = 1 if bool(subject.get("PoolPrivateYN")) else 0
    comp_pool = 1 if bool(comp.get("PoolPrivateYN")) else 0
    d_pool = subj_pool - comp_pool
    # Age difference: a NEWER subject (higher YearBuilt) is worth more.
    d_age_years = _num(subject.get("YearBuilt")) - _num(comp.get("YearBuilt"))

    breakdown = {
        "sqft": round(d_sqft * ppsf),
        "beds": round(d_bed * adj["bed_value"]),
        "baths": round(d_bath * adj["bath_value"]),
        "garage": round(d_garage * adj["garage_value"]),
        "pool": round(d_pool * adj["pool_value"]),
        "age": round(d_age_years * adj["age_value_per_year"]),
    }
    total_adjustment = sum(breakdown.values())
    adjusted = base + total_adjustment

    distance = haversine_miles(
        subject.get("Latitude"), subject.get("Longitude"),
        comp.get("Latitude"), comp.get("Longitude"),
    )

    close_d = _to_date(comp.get("CloseDate"))
    months_old = ((ref_date - close_d).days / 30.4) if close_d else 12.0
    months_old = max(0.0, months_old)

    weight = _composite_weight(subject, comp, distance, months_old)

    return {
        "ListingId": comp.get("ListingId"),
        "ListingUrl": comp.get("ListingUrl"),
        "ListOfficeName": comp.get("ListOfficeName"),
        "StandardStatus": comp.get("StandardStatus"),
        "address": comp.get("UnparsedAddress") or comp.get("address"),
        "is_closed": _is_closed(comp),
        "base_price": round(base),
        "adjusted_price": round(adjusted),
        "total_adjustment": round(total_adjustment),
        "breakdown": breakdown,
        "distance_mi": round(distance, 2),
        "months_old": round(months_old, 1),
        "weight": round(weight, 4),
        # carry raw features through for the side-by-side comparison view
        "LivingArea": _num(comp.get("LivingArea")),
        "BedroomsTotal": _num(comp.get("BedroomsTotal")),
        "BathroomsTotalInteger": _num(comp.get("BathroomsTotalInteger")),
        "GarageSpaces": _num(comp.get("GarageSpaces")),
        "PoolPrivateYN": bool(comp.get("PoolPrivateYN")),
        "YearBuilt": int(_num(comp.get("YearBuilt"))) if comp.get("YearBuilt") else None,
    }


def _composite_weight(subject, comp, distance_mi, months_old) -> float:
    """Similarity x recency x distance x listing-status, each in (0, 1]."""
    # Recency: ~6-month soft half-life.
    w_recency = math.exp(-months_old / 6.0)

    # Distance: 0.5-mile scale; falls off smoothly.
    w_distance = 1.0 / (1.0 + (distance_mi / 0.5) ** 2)

    # Similarity from size + room counts.
    subj_sqft = _num(subject.get("LivingArea")) or 1.0
    sqft_pct = abs(_num(subject.get("LivingArea")) - _num(comp.get("LivingArea"))) / subj_sqft
    bed_diff = abs(_num(subject.get("BedroomsTotal")) - _num(comp.get("BedroomsTotal")))
    bath_diff = abs(_num(subject.get("BathroomsTotalInteger")) - _num(comp.get("BathroomsTotalInteger")))
    dissimilarity = sqft_pct + 0.10 * bed_diff + 0.08 * bath_diff
    w_similarity = math.exp(-dissimilarity)

    # Active listings are evidence of asking price, not realized value: down-weight.
    w_status = 1.0 if _is_closed(comp) else 0.6

    return w_recency * w_distance * w_similarity * w_status


# ---------------------------------------------------------------------------
# Outlier handling
# ---------------------------------------------------------------------------

def _flag_outliers(comp_results: list) -> None:
    """Robust (median/MAD) outlier flagging on adjusted prices; mutates in place."""
    prices = [c["adjusted_price"] for c in comp_results]
    if len(prices) < 4:
        for c in comp_results:
            c["is_outlier"] = False
        return
    med = median(prices)
    abs_dev = [abs(p - med) for p in prices]
    mad = median(abs_dev) or 1.0
    for c in comp_results:
        # 0.6745 scales MAD to a std-equivalent; |z| > 3 is a strong outlier.
        z = 0.6745 * (c["adjusted_price"] - med) / mad
        c["is_outlier"] = abs(z) > 3.0
        if c["is_outlier"]:
            c["weight"] *= 0.25  # down-weight, don't drop


# ---------------------------------------------------------------------------
# Weighted statistics
# ---------------------------------------------------------------------------

def _weighted_mean(values, weights) -> float:
    tw = sum(weights)
    if tw <= 0:
        return sum(values) / len(values) if values else 0.0
    return sum(v * w for v, w in zip(values, weights)) / tw


def _weighted_std(values, weights, mean) -> float:
    tw = sum(weights)
    if tw <= 0 or len(values) < 2:
        return 0.0
    var = sum(w * (v - mean) ** 2 for v, w in zip(values, weights)) / tw
    return math.sqrt(max(0.0, var))


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

def _confidence(comp_results, n_closed, mean, std) -> tuple:
    """Return (score 0-100, list of plain-language reason strings)."""
    score = 100.0
    reasons = []

    n = len(comp_results)
    if n < 3:
        score -= 35
        reasons.append(f"Only {n} comparable(s) available -- thin data.")
    elif n < 5:
        score -= 12
        reasons.append(f"{n} comparables used; more would tighten the estimate.")
    else:
        reasons.append(f"{n} comparables used.")

    if n_closed < 3:
        score -= 15
        reasons.append(f"Only {n_closed} closed sale(s); active listings carry less weight.")

    # Dispersion: coefficient of variation of adjusted prices.
    cov = (std / mean) if mean else 0.0
    if cov > 0.15:
        score -= 25
        reasons.append(f"Wide spread in adjusted prices (+/-{cov*100:.0f}%).")
    elif cov > 0.08:
        score -= 10
        reasons.append(f"Moderate spread in adjusted prices (+/-{cov*100:.0f}%).")
    else:
        reasons.append("Adjusted comp prices cluster tightly.")

    # Recency.
    avg_months = sum(c["months_old"] for c in comp_results) / n if n else 12
    if avg_months > 9:
        score -= 12
        reasons.append(f"Comps average {avg_months:.0f} months old.")
    elif avg_months <= 4:
        reasons.append("Comps are recent (< 4 months on average).")

    # Distance.
    avg_dist = sum(c["distance_mi"] for c in comp_results) / n if n else 0
    if avg_dist > 1.0:
        score -= 10
        reasons.append(f"Comps average {avg_dist:.1f} mi away.")
    elif avg_dist <= 0.5:
        reasons.append("Comps are close by (< 0.5 mi on average).")

    n_out = sum(1 for c in comp_results if c.get("is_outlier"))
    if n_out:
        reasons.append(f"{n_out} outlier(s) detected and down-weighted.")

    return max(0, min(100, round(score))), reasons


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_cma(
    subject: dict,
    comps: list,
    include: Optional[dict] = None,
    ref_date: Optional[date] = None,
    method: str = "auto",
) -> dict:
    """
    Run a full CMA.

    Parameters
    ----------
    subject : dict
        Subject property in RESO field names.
    comps : list[dict]
        Candidate comparables in RESO field names.
    include : dict[ListingId -> bool], optional
        Agent toggles. Comps mapped to False are excluded from the valuation but
        still returned (marked ``included=False``) so the UI can show them greyed.
    ref_date : date, optional
        "As of" date for recency weighting. Defaults to the most recent CloseDate
        in the comp set, or today if none is present.

    Returns
    -------
    dict with keys: likely, low, high, confidence, reasons, adjustments,
    price_per_sqft, comps (list, sorted by weight desc), n_comps, n_closed,
    subject, ref_date.
    """
    include = include or {}

    if ref_date is None:
        close_dates = [d for d in (_to_date(c.get("CloseDate")) for c in comps) if d]
        ref_date = max(close_dates) if close_dates else date.today()

    adj = derive_adjustments(comps, method=method, ref_year=ref_date.year)

    all_results = [adjust_comp(subject, c, adj, ref_date) for c in comps]
    for r in all_results:
        r["included"] = include.get(r["ListingId"], True)

    active_results = [r for r in all_results if r["included"]]
    _flag_outliers(active_results)

    values = [r["adjusted_price"] for r in active_results]
    weights = [r["weight"] for r in active_results]

    likely = _weighted_mean(values, weights)
    std = _weighted_std(values, weights, likely)
    # Range: one weighted std out, with a floor so it never collapses to a point.
    spread = max(std, likely * 0.03)
    low = likely - spread
    high = likely + spread

    n_closed = sum(1 for r in active_results if r["is_closed"])
    confidence, reasons = _confidence(active_results, n_closed, likely, std)

    all_results.sort(key=lambda r: r["weight"], reverse=True)

    return {
        "subject": subject,
        "ref_date": ref_date.isoformat(),
        "price_per_sqft": adj["price_per_sqft"],
        "adjustments": adj,
        "likely": round(likely),
        "low": round(low),
        "high": round(high),
        "confidence": confidence,
        "reasons": reasons,
        "comps": all_results,
        "n_comps": len(active_results),
        "n_closed": n_closed,
    }
