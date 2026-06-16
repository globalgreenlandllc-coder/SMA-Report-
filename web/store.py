"""
store.py -- Minimal JSON-file persistence for SMA-Report.

Dependency-free (no database) so the prototype runs anywhere. Holds agent
accounts, saved report versions (with history for diffs), share + view events,
and captured leads. Swap for a real DB (Postgres, etc.) at production scale; the
server only depends on the functions exported here.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone

_STORE_DIR = os.path.join(os.path.dirname(__file__), "_store")
_STORE_FILE = os.path.join(_STORE_DIR, "data.json")
_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read() -> dict:
    if not os.path.exists(_STORE_FILE):
        return {"accounts": {}, "reports": {}, "leads": []}
    with open(_STORE_FILE, encoding="utf-8") as fh:
        data = json.load(fh)
    data.setdefault("accounts", {})
    data.setdefault("reports", {})
    data.setdefault("leads", [])
    return data


def _write(data: dict) -> None:
    os.makedirs(_STORE_DIR, exist_ok=True)
    tmp = _STORE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)
    os.replace(tmp, _STORE_FILE)


# ---------------------------------------------------------------------------
# Accounts (agents)
# ---------------------------------------------------------------------------

def create_account(account: dict) -> dict:
    with _lock:
        data = _read()
        data["accounts"][account["id"]] = account
        _write(data)
        return account


def get_account(agent_id: str):
    return _read()["accounts"].get(agent_id)


def find_account_by_email(email: str):
    email = (email or "").strip().lower()
    for a in _read()["accounts"].values():
        if a.get("email", "").lower() == email:
            return a
    return None


def update_account(agent_id: str, patch: dict):
    with _lock:
        data = _read()
        a = data["accounts"].get(agent_id)
        if not a:
            return None
        a.update(patch)
        a["updated_at"] = _now()
        _write(data)
        return a


# ---------------------------------------------------------------------------
# Reports (owner-scoped, versioned)
# ---------------------------------------------------------------------------

def save_report(token: str, payload: dict) -> dict:
    """Create or update a report version under ``token``, retaining history."""
    with _lock:
        data = _read()
        existing = data["reports"].get(token, {})
        version = existing.get("version", 0) + 1
        result = payload.get("result", existing.get("result", {}))

        # Snapshot prior version into history for diffs.
        history = existing.get("history", [])
        if existing:
            history = history + [{
                "version": existing.get("version"),
                "saved_at": existing.get("updated_at"),
                "likely": existing.get("result", {}).get("likely"),
                "low": existing.get("result", {}).get("low"),
                "high": existing.get("result", {}).get("high"),
                "confidence": existing.get("result", {}).get("confidence"),
                "n_comps": existing.get("result", {}).get("n_comps"),
            }]

        record = {
            "token": token,
            "owner": payload.get("owner", existing.get("owner")),
            "created_at": existing.get("created_at", _now()),
            "updated_at": _now(),
            "version": version,
            "client_name": payload.get("client_name", existing.get("client_name", "")),
            "template": payload.get("template", existing.get("template", "seller")),
            "branding": payload.get("branding", existing.get("branding", {})),
            "result": result,
            "shares": existing.get("shares", []),
            "views": existing.get("views", []),
            "history": history,
        }
        data["reports"][token] = record
        _write(data)
        return record


def get_report(token: str):
    return _read()["reports"].get(token)


def list_reports(owner: str = None) -> list:
    data = _read()
    out = []
    for r in data["reports"].values():
        if owner is not None and r.get("owner") != owner:
            continue
        out.append({
            "token": r["token"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
            "version": r["version"],
            "client_name": r.get("client_name", ""),
            "template": r.get("template", "seller"),
            "address": (r.get("result", {}).get("subject", {}) or {}).get("UnparsedAddress", ""),
            "likely": r.get("result", {}).get("likely"),
            "view_count": len(r.get("views", [])),
            "first_viewed_at": (r["views"][0]["at"] if r.get("views") else None),
            "last_viewed_at": (r["views"][-1]["at"] if r.get("views") else None),
            "share_count": len(r.get("shares", [])),
        })
    out.sort(key=lambda x: x["updated_at"], reverse=True)
    return out


def record_view(token: str, ip: str = "", user_agent: str = "") -> bool:
    with _lock:
        data = _read()
        r = data["reports"].get(token)
        if not r:
            return False
        r.setdefault("views", []).append({"at": _now(), "ip": ip, "ua": user_agent})
        _write(data)
        return True


def record_share(token: str, share: dict):
    with _lock:
        data = _read()
        r = data["reports"].get(token)
        if not r:
            return None
        entry = {"at": _now(), **share}
        r.setdefault("shares", []).append(entry)
        _write(data)
        return entry


# ---------------------------------------------------------------------------
# Leads (from the public widget)
# ---------------------------------------------------------------------------

def add_lead(lead: dict) -> dict:
    with _lock:
        data = _read()
        entry = {"at": _now(), **lead}
        data["leads"].append(entry)
        _write(data)
        return entry


def list_leads(agent_id: str = None) -> list:
    leads = _read()["leads"]
    if agent_id is not None:
        leads = [l for l in leads if l.get("agent_id") == agent_id]
    return sorted(leads, key=lambda x: x["at"], reverse=True)
