"""
store.py -- Minimal JSON-file persistence for shareable reports.

Deliberately dependency-free (no database) so the prototype runs anywhere. The
store holds saved report versions, their share records, and client view events.
Swap this module for a real DB (Postgres, etc.) when multi-tenant accounts land;
the server only depends on the functions exported here.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone

_STORE_DIR = os.path.join(os.path.dirname(__file__), "_store")
_STORE_FILE = os.path.join(_STORE_DIR, "reports.json")
_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read() -> dict:
    if not os.path.exists(_STORE_FILE):
        return {"reports": {}}
    with open(_STORE_FILE, encoding="utf-8") as fh:
        return json.load(fh)


def _write(data: dict) -> None:
    os.makedirs(_STORE_DIR, exist_ok=True)
    tmp = _STORE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)
    os.replace(tmp, _STORE_FILE)


def save_report(token: str, payload: dict) -> dict:
    """Create or overwrite a report version under ``token``."""
    with _lock:
        data = _read()
        existing = data["reports"].get(token, {})
        record = {
            "token": token,
            "created_at": existing.get("created_at", _now()),
            "updated_at": _now(),
            "version": existing.get("version", 0) + 1,
            "client_name": payload.get("client_name", ""),
            "template": payload.get("template", "seller"),
            "branding": payload.get("branding", {}),
            "result": payload.get("result", {}),
            "shares": existing.get("shares", []),
            "views": existing.get("views", []),
        }
        data["reports"][token] = record
        _write(data)
        return record


def get_report(token: str):
    return _read()["reports"].get(token)


def list_reports() -> list:
    data = _read()
    out = []
    for r in data["reports"].values():
        out.append({
            "token": r["token"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
            "version": r["version"],
            "client_name": r.get("client_name", ""),
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
