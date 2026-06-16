"""
reso_odata_loader.py -- Production comp loader for RESO Web API (OData) feeds.

Targets MLSGrid and Trestle, which both serve the RESO Data Dictionary over OData.
Because our engine already uses RESO field names, mapping is nearly 1:1 -- this
loader mostly coerces types, respects display permissions, and carries attribution
through. It yields the SAME dict shape as ``sample_comps`` / ``reso_loader`` so it
is a drop-in swap.

Compliance:
  * Honors per-record display flags (MLSGrid's ``MlgCanView``); records the agent
    isn't permitted to display are dropped.
  * Carries ``ListOfficeName`` for "Listing courtesy of ..." attribution.

Config via env:
  RESO_PROVIDER = mlsgrid | trestle
  MLSGrid : MLSGRID_API_TOKEN [, MLSGRID_BASE_URL]
  Trestle : TRESTLE_CLIENT_ID, TRESTLE_CLIENT_SECRET [, TRESTLE_BASE_URL, TRESTLE_TOKEN_URL]

Standard library only (urllib). Live calls need real credentials; the field
mapping is independently unit-tested via the __main__ fixture below.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request


class RESOError(RuntimeError):
    pass


def _num(v):
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _can_display(p: dict) -> bool:
    # MLSGrid gates display with MlgCanView; default True when the field is absent.
    flag = p.get("MlgCanView")
    return True if flag is None else bool(flag)


def map_property(p: dict) -> dict:
    """Map one RESO OData Property record into our engine's dict shape."""
    close_date = p.get("CloseDate")
    if close_date:
        close_date = str(close_date)[:10]

    listing_url = (
        p.get("ListingURL") or p.get("ListingUrl")
        or _address_search_fallback(p)
    )
    return {
        "ListingId": str(p.get("ListingId") or p.get("ListingKey") or ""),
        "ListingUrl": listing_url,
        "ListOfficeName": p.get("ListOfficeName") or "Listing Brokerage",
        "StandardStatus": p.get("StandardStatus") or "Unknown",
        "ClosePrice": _num(p.get("ClosePrice")),
        "ListPrice": _num(p.get("ListPrice")),
        "CloseDate": close_date,
        "UnparsedAddress": p.get("UnparsedAddress") or "",
        "LivingArea": _num(p.get("LivingArea")),
        "BedroomsTotal": _num(p.get("BedroomsTotal")),
        "BathroomsTotalInteger": _num(p.get("BathroomsTotalInteger")),
        "GarageSpaces": round(_num(p.get("GarageSpaces")) or 0),
        "PoolPrivateYN": bool(p.get("PoolPrivateYN")),
        "YearBuilt": p.get("YearBuilt"),
        "Latitude": _num(p.get("Latitude")),
        "Longitude": _num(p.get("Longitude")),
    }


def _address_search_fallback(p: dict) -> str:
    q = " ".join(str(p.get(k, "")) for k in ("UnparsedAddress", "City", "StateOrProvince")).strip()
    return "https://www.google.com/search?q=" + urllib.parse.quote(q)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

class ODataRESOLoader:
    def __init__(self, base_url: str, bearer_token: str):
        self.base_url = base_url.rstrip("/")
        self.token = bearer_token

    def _get(self, path: str, params: dict, timeout: float = 20.0) -> dict:
        url = f"{self.base_url}/{path}?" + urllib.parse.urlencode(params, safe="$(),' =")
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "User-Agent": "SMA-Report/1.0",
        })
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raise RESOError(f"RESO OData HTTP {e.code}: {e.reason}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise RESOError(f"RESO OData unreachable: {e}") from e

    def load_comps(self, odata_filter: str = None, top: int = 50) -> list:
        params = {"$top": min(int(top), 200)}
        if odata_filter:
            params["$filter"] = odata_filter
        data = self._get("Property", params)
        records = data.get("value", data if isinstance(data, list) else [])
        return [map_property(p) for p in records if _can_display(p)]


# ---------------------------------------------------------------------------
# Factory (reads env / provider)
# ---------------------------------------------------------------------------

def _trestle_token(client_id: str, client_secret: str, token_url: str) -> str:
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id, "client_secret": client_secret,
        "scope": "api",
    }).encode()
    req = urllib.request.Request(token_url, data=data,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())["access_token"]
    except Exception as e:
        raise RESOError(f"Trestle OAuth failed: {e}") from e


def make_loader() -> ODataRESOLoader:
    """Build a loader from environment configuration."""
    provider = (os.environ.get("RESO_PROVIDER") or "").lower()
    if provider == "mlsgrid":
        tok = os.environ.get("MLSGRID_API_TOKEN")
        if not tok:
            raise RESOError("MLSGRID_API_TOKEN not set")
        base = os.environ.get("MLSGRID_BASE_URL", "https://api.mlsgrid.com/v2")
        return ODataRESOLoader(base, tok)
    if provider == "trestle":
        cid = os.environ.get("TRESTLE_CLIENT_ID")
        sec = os.environ.get("TRESTLE_CLIENT_SECRET")
        if not (cid and sec):
            raise RESOError("TRESTLE_CLIENT_ID / TRESTLE_CLIENT_SECRET not set")
        token_url = os.environ.get("TRESTLE_TOKEN_URL", "https://api-trestle.corelogic.com/trestle/oidc/connect/token")
        base = os.environ.get("TRESTLE_BASE_URL", "https://api-trestle.corelogic.com/trestle/odata")
        return ODataRESOLoader(base, _trestle_token(cid, sec, token_url))
    raise RESOError("Set RESO_PROVIDER=mlsgrid|trestle and the matching credentials.")


if __name__ == "__main__":
    # Mapping unit test against a representative RESO OData record (no network).
    fixture = {
        "value": [{
            "ListingId": "TX-998877", "ListingKey": "abc123",
            "ListOfficeName": "Capitol City Properties",
            "StandardStatus": "Closed", "ClosePrice": 575000, "ListPrice": 580000,
            "CloseDate": "2026-05-01T00:00:00Z", "UnparsedAddress": "12 Elm St, Austin, TX 78745",
            "LivingArea": 2200, "BedroomsTotal": 4, "BathroomsTotalInteger": 3,
            "GarageSpaces": 2.0, "PoolPrivateYN": True, "YearBuilt": 2009,
            "Latitude": 30.21, "Longitude": -97.80, "MlgCanView": True,
        }, {
            "ListingId": "HIDDEN-1", "StandardStatus": "Closed", "ClosePrice": 1, "MlgCanView": False,
        }]
    }
    mapped = [map_property(p) for p in fixture["value"] if _can_display(p)]
    assert len(mapped) == 1, "MlgCanView=False record should be dropped"
    m = mapped[0]
    assert m["ListingId"] == "TX-998877" and m["ClosePrice"] == 575000.0
    assert m["CloseDate"] == "2026-05-01" and m["GarageSpaces"] == 2 and m["PoolPrivateYN"] is True
    print("OK: mapped", len(mapped), "record(s); display-gated record dropped.")
    print(json.dumps(m, indent=2))
