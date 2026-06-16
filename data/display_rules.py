"""
display_rules.py -- Per-MLS display / refresh / retention rule enforcement.

MLS feeds come with rules about how their data may be shown. This module applies
the common ones to a comp set before it is displayed or put in a report:

  * Retention   -- drop closed sales older than the MLS's allowed window.
  * Attribution -- every listing must credit its listing brokerage
                   ("Listing courtesy of ..."); records missing it are labeled.
  * Refresh     -- a per-source cache TTL so we don't query more often than the
                   MLS permits (see CACHE in the server loader).
  * Disclaimer  -- the MLS-required display disclaimer string.

Defaults are sensible placeholders; the admin overrides them per source in
settings. Each MLS's actual policy must be configured to match its license.
"""
from __future__ import annotations

from datetime import date, datetime

# Default rules per source. Admin settings override any of these keys.
DEFAULT_RULES = {
    "sample": {
        "retention_months": None, "refresh_minutes": 0,
        "disclaimer": "Sample data for demonstration only.",
    },
    "simplyrets": {
        "retention_months": 24, "refresh_minutes": 15,
        "disclaimer": "Listing data via SimplyRETS (sandbox). For testing only.",
    },
    "mlsgrid": {
        "retention_months": 36, "refresh_minutes": 60,
        "disclaimer": "Listing information deemed reliable but not guaranteed. "
                      "Provided via MLS Grid. Each listing courtesy of its listing broker.",
    },
    "trestle": {
        "retention_months": 36, "refresh_minutes": 60,
        "disclaimer": "Based on information from the MLS via Trestle/CoreLogic. "
                      "Deemed reliable but not guaranteed.",
    },
}


def rules_for(source: str, overrides: dict = None) -> dict:
    base = dict(DEFAULT_RULES.get(source, DEFAULT_RULES["sample"]))
    if overrides:
        for k in ("retention_months", "refresh_minutes", "disclaimer"):
            v = overrides.get(f"{source}_{k}")
            if v not in (None, ""):
                base[k] = v
    return base


def _months_between(d: date, today: date) -> int:
    return (today.year - d.year) * 12 + (today.month - d.month)


def _close_date(c):
    v = c.get("CloseDate")
    if not v:
        return None
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def apply_rules(comps: list, source: str, overrides: dict = None, today: date = None) -> tuple:
    """
    Enforce display rules on a comp set.

    Returns (kept_comps, meta) where meta = {disclaimer, retention_months,
    dropped_retention, attribution_fixed, as_of}.
    """
    rules = rules_for(source, overrides)
    today = today or date.today()
    retention = rules.get("retention_months")

    kept, dropped, attribution_fixed = [], 0, 0
    for c in comps:
        # Retention: closed sales older than the window may not be displayed.
        cd = _close_date(c)
        if retention and cd and _months_between(cd, today) > int(retention):
            dropped += 1
            continue
        # Attribution: require a listing brokerage credit.
        if not c.get("ListOfficeName"):
            c = {**c, "ListOfficeName": "Listing Brokerage (attribution unavailable)"}
            attribution_fixed += 1
        kept.append(c)

    meta = {
        "source": source,
        "disclaimer": rules.get("disclaimer", ""),
        "retention_months": retention,
        "refresh_minutes": rules.get("refresh_minutes", 0),
        "dropped_retention": dropped,
        "attribution_fixed": attribution_fixed,
        "as_of": today.isoformat(),
        "n": len(kept),
    }
    return kept, meta
