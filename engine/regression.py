"""
regression.py -- Data-driven adjustment values via least-squares regression.

The heuristic model in ``cma_engine`` anchors per-feature values to local
price-per-sqft. This module instead *fits* per-feature dollar values directly to
each market's closed comps, so the contribution of a bedroom, bath, garage space,
pool, or year of age is learned from what actually sold nearby.

Realities of comp sets (small n, collinear features, the occasional luxury
outlier) make a naive OLS fragile, so this uses:

  * **ppsf pre-trim** -- gross outliers are removed before fitting (robust MAD on
    price/sqft), so one mansion can't bend the whole surface.
  * **standardized ridge** -- features are z-scored and a light L2 penalty is
    applied, which stabilizes the fit under collinearity and small samples.
  * **sign/plausibility validation + per-feature fallback** -- any coefficient
    that comes back the wrong sign or an implausible magnitude is discarded and
    the caller keeps the heuristic value for that one feature.

Pure Python / standard library only -- no NumPy.
"""
from __future__ import annotations

import math
from statistics import median, pstdev
from typing import Optional


# Candidate predictors, in priority order, with the sign we expect on the
# coefficient (per-unit marginal dollar contribution to sale price).
#   key -> (subject/comp RESO field, expected_sign)
_FEATURES = [
    ("LivingArea", "LivingArea", +1),
    ("BathroomsTotalInteger", "BathroomsTotalInteger", +1),
    ("BedroomsTotal", "BedroomsTotal", +1),
    ("GarageSpaces", "GarageSpaces", +1),
    ("Age", None, -1),          # derived: ref_year - YearBuilt
    ("PoolPrivateYN", "PoolPrivateYN", +1),
]


def _num(v, default=0.0):
    try:
        return default if v is None else float(v)
    except (TypeError, ValueError):
        return default


def _is_closed(c):
    return str(c.get("StandardStatus", "")).strip().lower() in {"closed", "sold"}


def _row_value(comp, key, field, ref_year):
    if key == "Age":
        yb = _num(comp.get("YearBuilt"))
        return (ref_year - yb) if yb else 0.0
    if key == "PoolPrivateYN":
        return 1.0 if bool(comp.get("PoolPrivateYN")) else 0.0
    return _num(comp.get(field))


# ---------------------------------------------------------------------------
# Tiny linear algebra (small symmetric systems)
# ---------------------------------------------------------------------------

def _solve(A, b):
    """Gaussian elimination with partial pivoting. Returns None if singular."""
    n = len(A)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[piv][col]) < 1e-12:
            return None
        M[col], M[piv] = M[piv], M[col]
        pivot = M[col][col]
        for r in range(n):
            if r == col:
                continue
            factor = M[r][col] / pivot
            if factor:
                for k in range(col, n + 1):
                    M[r][k] -= factor * M[col][k]
    return [M[i][n] / M[i][i] for i in range(n)]


# ---------------------------------------------------------------------------
# Fit
# ---------------------------------------------------------------------------

def _ppsf_trim(rows):
    """Drop rows whose price/sqft is a robust outlier (|MAD z| > 3.5)."""
    ppsf = [r["price"] / r["LivingArea"] for r in rows if r["LivingArea"] > 0]
    if len(ppsf) < 4:
        return rows
    med = median(ppsf)
    mad = median([abs(p - med) for p in ppsf]) or 1.0
    kept = []
    for r in rows:
        if r["LivingArea"] <= 0:
            continue
        z = 0.6745 * ((r["price"] / r["LivingArea"]) - med) / mad
        if abs(z) <= 3.5:
            kept.append(r)
    return kept


def fit_adjustments(comps: list, ref_year: int, ridge: float = 1.0) -> Optional[dict]:
    """
    Fit per-feature dollar values from the closed comps.

    Returns a dict with the fitted values plus diagnostics, or None if there is
    not enough usable data to fit anything (caller should fall back to heuristics).

    Result keys:
        price_per_sqft, bed_value, bath_value, garage_value, pool_value,
        age_value_per_year   -- only present for features that passed validation
        method='regression', n, r2, features_used, dropped_features
    """
    closed = [c for c in comps if _is_closed(c) and _num(c.get("LivingArea")) > 0]
    rows = []
    for c in closed:
        price = _num(c.get("ClosePrice")) or _num(c.get("ListPrice"))
        if price <= 0:
            continue
        rows.append({"comp": c, "price": price, "LivingArea": _num(c.get("LivingArea"))})

    rows = _ppsf_trim(rows)
    n = len(rows)
    if n < 5:
        return None  # too few to fit responsibly; use heuristics

    # Choose predictors that actually vary, capped so we keep degrees of freedom.
    max_k = max(1, n - 3)
    chosen = []
    for key, field, sign in _FEATURES:
        col = [_row_value(r["comp"], key, field, ref_year) for r in rows]
        if max(col) - min(col) > 1e-9:  # has variation
            chosen.append((key, field, sign, col))
        if len(chosen) >= max_k:
            break
    if not chosen:
        return None

    y = [r["price"] for r in rows]
    y_mean = sum(y) / n
    yc = [v - y_mean for v in y]

    # Standardize each chosen column.
    stds, means, Z = [], [], []
    for _, _, _, col in chosen:
        m = sum(col) / n
        sd = pstdev(col) or 1.0
        means.append(m)
        stds.append(sd)
        Z.append([(v - m) / sd for v in col])  # Z[j] is column j

    k = len(chosen)
    # Normal equations with ridge on standardized features: (Z'Z + ridge*I) b = Z'yc
    ZtZ = [[sum(Z[i][t] * Z[j][t] for t in range(n)) for j in range(k)] for i in range(k)]
    for i in range(k):
        ZtZ[i][i] += ridge
    Zty = [sum(Z[i][t] * yc[t] for t in range(n)) for i in range(k)]
    b_std = _solve(ZtZ, Zty)
    if b_std is None:
        return None

    # Un-standardize: raw slope_j = b_std_j / std_j
    raw = {chosen[j][0]: b_std[j] / stds[j] for j in range(k)}

    # R^2 on the (trimmed) training rows.
    fitted = []
    for t in range(n):
        pred = y_mean + sum(b_std[j] * Z[j][t] for j in range(k))
        fitted.append(pred)
    ss_res = sum((y[t] - fitted[t]) ** 2 for t in range(n))
    ss_tot = sum((y[t] - y_mean) ** 2 for t in range(n)) or 1.0
    r2 = 1.0 - ss_res / ss_tot

    # Validate each coefficient; keep only the plausible ones.
    out = {"method": "regression", "n": n, "r2": round(r2, 3),
           "features_used": [], "dropped_features": []}
    ppsf_seen = median([r["price"] / r["LivingArea"] for r in rows])

    for key, field, sign, _ in chosen:
        coef = raw[key]
        ok, value, out_key = _validate(key, coef, sign, ppsf_seen)
        if ok:
            out[out_key] = value
            out["features_used"].append(key)
        else:
            out["dropped_features"].append(key)

    # A regression with no usable price/sqft is not worth trusting.
    if "price_per_sqft" not in out:
        return None
    return out


def _validate(key, coef, sign, ppsf_seen):
    """Return (ok, value, out_key). Rejects wrong-sign / implausible coefficients."""
    if key == "LivingArea":
        ppsf = coef
        ok = 30.0 <= ppsf <= 3000.0
        return ok, round(ppsf, 2), "price_per_sqft"
    if key == "Age":
        # coef is $ per year of AGE (expected negative). Value of being newer:
        age_val = -coef
        ok = 0.0 <= age_val <= 0.5 * ppsf_seen * 50  # generous upper bound
        return ok, int(round(max(0.0, age_val))), "age_value_per_year"

    out_key = {
        "BedroomsTotal": "bed_value",
        "BathroomsTotalInteger": "bath_value",
        "GarageSpaces": "garage_value",
        "PoolPrivateYN": "pool_value",
    }[key]
    # Expected positive; reject negatives and absurd magnitudes.
    if coef <= 0:
        return False, None, out_key
    ceiling = ppsf_seen * 1200  # no single feature worth > ~1200 sqft of value
    if coef > ceiling:
        return False, None, out_key
    return True, int(round(coef)), out_key
