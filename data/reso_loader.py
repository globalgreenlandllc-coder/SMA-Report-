"""
reso_loader.py -- Live comparable loader via the RESO Web API (SimplyRETS).

This is the production stand-in for ``sample_comps.py``. It hits an aggregator's
RESO Web API and maps each listing into the SAME field shape the sample data uses,
so the engine and report never learn where the data came from -- swapping sample
for live is a single import change.

Build/test:  SimplyRETS sandbox (demo creds ``simplyrets`` / ``simplyrets``).
Production:  point ``BASE_URL`` + credentials at MLSGrid or Trestle and add a
            sibling loader that maps their payload into the same dict shape.

Credentials are read from the environment (never hardcoded for production):
    SIMPLYRETS_API_KEY, SIMPLYRETS_API_SECRET
A local ``.env`` is auto-loaded if present (see .env.example). The sandbox demo
credentials are used as a fallback so the pipeline runs out of the box.

Standard library only -- urllib, no third-party HTTP client.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = os.environ.get("SIMPLYRETS_BASE_URL", "https://api.simplyrets.com")
_DEMO = ("simplyrets", "simplyrets")  # public sandbox credentials


class RESOError(RuntimeError):
    """Raised when the RESO feed cannot be reached or returns an error."""


# ---------------------------------------------------------------------------
# .env loading (no python-dotenv dependency)
# ---------------------------------------------------------------------------

def _load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def _credentials() -> tuple:
    _load_dotenv()
    key = os.environ.get("SIMPLYRETS_API_KEY")
    secret = os.environ.get("SIMPLYRETS_API_SECRET")
    if key and secret:
        return key, secret
    return _DEMO  # fall back to the public sandbox


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def _get(path: str, params: dict, timeout: float = 15.0) -> list:
    user, pw = _credentials()
    # SimplyRETS repeats ?status=Active&status=Closed for multi-value params.
    query = urllib.parse.urlencode(params, doseq=True)
    url = f"{BASE_URL}{path}?{query}" if query else f"{BASE_URL}{path}"
    token = base64.b64encode(f"{user}:{pw}".encode()).decode()
    req = urllib.request.Request(url, headers={
        "Authorization": f"Basic {token}",
        "Accept": "application/json",
        "User-Agent": "SMA-Report/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise RESOError(f"RESO feed HTTP {e.code}: {e.reason}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise RESOError(f"RESO feed unreachable: {e}") from e


# ---------------------------------------------------------------------------
# Mapping  SimplyRETS payload -> our RESO-shaped dict
# ---------------------------------------------------------------------------

def _baths_total(prop: dict):
    if prop.get("bathrooms") is not None:
        return prop["bathrooms"]
    full = prop.get("bathsFull") or 0
    half = prop.get("bathsHalf") or 0
    return full + (1 if half else 0)


def _pool(prop: dict) -> bool:
    val = prop.get("pool")
    if not val:
        return False
    text = str(val).strip().lower()
    return text not in ("", "no", "none", "false")


def _verification_url(p: dict) -> str:
    """
    SimplyRETS' sandbox exposes no public listing page. Per project policy the MLS
    listing is the authoritative source; where the feed provides no URL we emit an
    address-search fallback (Zillow/Redfin/Google are address-search fallbacks
    only). Production feeds (MLSGrid/Trestle) supply a real listing URL to use here.
    """
    direct = p.get("listingURL") or p.get("listingUrl")
    if direct:
        return direct
    addr = (p.get("address") or {})
    q = " ".join(str(addr.get(k, "")) for k in ("full", "city", "state", "postalCode")).strip()
    return "https://www.google.com/search?q=" + urllib.parse.quote(q)


def map_property(p: dict) -> dict:
    """Map one SimplyRETS property to the RESO-shaped dict the engine consumes."""
    prop = p.get("property") or {}
    sales = p.get("sales") or {}
    geo = p.get("geo") or {}
    office = p.get("office") or {}
    addr = p.get("address") or {}

    close_date = sales.get("closeDate")
    if close_date:  # trim ISO timestamp to a plain date
        close_date = str(close_date)[:10]

    return {
        "ListingId": str(p.get("listingId") or p.get("mlsId") or ""),
        "ListingUrl": _verification_url(p),
        "ListOfficeName": office.get("name") or office.get("brokerid") or "Listing Brokerage",
        "StandardStatus": (p.get("mls") or {}).get("status") or "Unknown",
        "ClosePrice": sales.get("closePrice"),
        "ListPrice": p.get("listPrice"),
        "CloseDate": close_date,
        "UnparsedAddress": addr.get("full") or "",
        "LivingArea": prop.get("area"),
        "BedroomsTotal": prop.get("bedrooms"),
        "BathroomsTotalInteger": _baths_total(prop),
        "GarageSpaces": round(prop.get("garageSpaces") or 0),
        "PoolPrivateYN": _pool(prop),
        "YearBuilt": prop.get("yearBuilt"),
        "Latitude": geo.get("lat"),
        "Longitude": geo.get("lng"),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_comps(limit: int = 25, statuses=("Closed", "Active"),
               cities=None, minprice=None, maxprice=None, q=None,
               extra_params=None) -> list:
    """
    Fetch comparables from the RESO feed and return them in our field shape.

    Raises RESOError on network/auth failure (the caller decides whether to fall
    back to sample data).
    """
    params = {"limit": max(1, min(int(limit), 500))}
    if statuses:
        params["status"] = list(statuses)
    if cities:
        params["cities"] = list(cities)
    if minprice is not None:
        params["minprice"] = minprice
    if maxprice is not None:
        params["maxprice"] = maxprice
    if q:
        params["q"] = q
    if extra_params:
        params.update(extra_params)

    raw = _get("/properties", params)
    return [map_property(p) for p in raw]


if __name__ == "__main__":
    # Smoke test against the sandbox.
    comps = load_comps(limit=3)
    print(f"Fetched {len(comps)} comps from {BASE_URL}")
    for c in comps:
        print(f"  {c['ListingId']:>10}  {c['StandardStatus']:<7}  "
              f"{c['LivingArea']} sqft  {c['BedroomsTotal']}bd/{c['BathroomsTotalInteger']}ba  "
              f"close={c['ClosePrice']}  list={c['ListPrice']}")
