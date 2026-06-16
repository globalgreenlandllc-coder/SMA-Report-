"""
narrative.py -- Smart, plain-language "why this price" narrative + a pricing
recommendation, generated from the engine result.

This is the editable starting draft the agent tweaks before sending. It reads the
valuation, the market-derived adjustments, the trend signals, and the top comps,
and writes a few sentences a seller can actually understand -- no jargon, no black
box.
"""
from __future__ import annotations


def _money(n) -> str:
    try:
        return "${:,.0f}".format(float(n))
    except (TypeError, ValueError):
        return "n/a"


def build_narrative(result: dict) -> str:
    s = result.get("subject", {}) or {}
    addr = s.get("UnparsedAddress", "the property")
    likely, low, high = result.get("likely"), result.get("low"), result.get("high")
    conf = result.get("confidence", 0)
    adj = result.get("adjustments", {}) or {}
    trends = result.get("trends") or {}
    comps = [c for c in result.get("comps", []) if c.get("included", True)]
    n_closed = result.get("n_closed", 0)

    parts = []

    parts.append(
        f"Based on {len(comps)} comparable {'sale' if n_closed == 1 else 'sales and listings'} "
        f"near {addr}, {addr.split(',')[0]} has an estimated market value of about "
        f"{_money(likely)}, with a likely range of {_money(low)} to {_money(high)}."
    )

    method = adj.get("method")
    ppsf = adj.get("price_per_sqft")
    if method == "regression" and adj.get("regression"):
        r2 = adj["regression"].get("r2")
        parts.append(
            f"The estimate is driven by a pricing model fit to local sales "
            f"(explaining {round((r2 or 0)*100)}% of the variation), anchored on a "
            f"market rate of about {_money(ppsf)} per square foot."
        )
    else:
        parts.append(
            f"The estimate is anchored on a local market rate of about "
            f"{_money(ppsf)} per square foot, with adjustments for differences in "
            f"size, beds, baths, garage, and age."
        )

    # Market context.
    moi = trends.get("months_of_inventory")
    label = trends.get("market_label")
    s2l = trends.get("sold_to_list_pct")
    if moi is not None and label and label != "unknown":
        ctx = f"The neighborhood is currently a {label}"
        if moi is not None:
            ctx += f" ({moi} months of inventory)"
        if s2l is not None:
            ctx += f", and recent homes sold at about {s2l}% of list price"
        parts.append(ctx + ".")

    # Outliers / confidence.
    n_out = sum(1 for c in comps if c.get("is_outlier"))
    if n_out:
        parts.append(
            f"{n_out} non-representative sale{'s' if n_out != 1 else ''} "
            f"{'were' if n_out != 1 else 'was'} flagged and de-emphasized so it "
            f"doesn't distort the estimate."
        )

    conf_word = "high" if conf >= 80 else "moderate" if conf >= 60 else "limited"
    parts.append(
        f"Overall confidence in this estimate is {conf_word} ({conf}/100)."
    )

    return " ".join(parts)


def pricing_recommendation(result: dict) -> dict:
    """A one-line, strategy-aware list-price recommendation."""
    likely = result.get("likely") or 0
    trends = result.get("trends") or {}
    label = trends.get("market_label", "")

    if label.startswith("seller"):
        rec = round(likely * 1.02 / 1000) * 1000
        rationale = ("Low inventory favors sellers — list slightly above the likely "
                     "value to leave room to negotiate.")
        dom = "fast (under ~3 weeks)"
    elif label.startswith("buyer"):
        rec = round(likely * 0.985 / 1000) * 1000
        rationale = ("Higher inventory favors buyers — price at or just below the "
                     "likely value to stand out and avoid sitting on market.")
        dom = "slower (4–8+ weeks)"
    else:
        rec = round(likely / 1000) * 1000
        rationale = "Balanced market — price at the likely value for a timely sale."
        dom = "typical (~3–5 weeks)"

    return {
        "recommended_list_price": rec,
        "rationale": rationale,
        "expected_pace": dom,
    }
