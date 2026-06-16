"""
store.py -- SQLite-backed persistence for SMA-Report.

A real database (stdlib sqlite3) replaces the earlier JSON file, while keeping the
exact same function API the server depends on. Rich/nested values (branding,
engine result, history, shares, views) are stored as JSON in a column; the columns
that need querying (email, owner, agent_id, created_at) are promoted to real
columns and indexed.

On first run it auto-imports any legacy ``_store/data.json`` so existing prototype
data carries over.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone

_DIR = os.path.join(os.path.dirname(__file__), "_store")
_DB = os.path.join(_DIR, "sma.db")
_lock = threading.Lock()
_conn = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        os.makedirs(_DIR, exist_ok=True)
        _conn = sqlite3.connect(_DB, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _init(_conn)
        _maybe_import_legacy(_conn)
    return _conn


def _init(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE,
            created_at TEXT,
            json TEXT
        );
        CREATE TABLE IF NOT EXISTS reports (
            token TEXT PRIMARY KEY,
            owner TEXT,
            created_at TEXT,
            updated_at TEXT,
            json TEXT
        );
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT,
            at TEXT,
            json TEXT
        );
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            json TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_reports_owner ON reports(owner);
        CREATE INDEX IF NOT EXISTS idx_leads_agent ON leads(agent_id);
        """
    )
    conn.commit()


def _maybe_import_legacy(conn: sqlite3.Connection) -> None:
    legacy = os.path.join(_DIR, "data.json")
    already = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    if already or not os.path.exists(legacy):
        return
    try:
        with open(legacy, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return
    for a in data.get("accounts", {}).values():
        conn.execute("INSERT OR IGNORE INTO accounts(id,email,created_at,json) VALUES (?,?,?,?)",
                     (a["id"], a.get("email"), a.get("created_at"), json.dumps(a, default=str)))
    for r in data.get("reports", {}).values():
        conn.execute("INSERT OR IGNORE INTO reports(token,owner,created_at,updated_at,json) VALUES (?,?,?,?,?)",
                     (r["token"], r.get("owner"), r.get("created_at"), r.get("updated_at"), json.dumps(r, default=str)))
    for l in data.get("leads", []):
        conn.execute("INSERT INTO leads(agent_id,at,json) VALUES (?,?,?)",
                     (l.get("agent_id"), l.get("at"), json.dumps(l, default=str)))
    if data.get("settings"):
        conn.execute("INSERT OR REPLACE INTO settings(id,json) VALUES (1,?)",
                     (json.dumps(data["settings"], default=str),))
    conn.commit()


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

def create_account(account: dict) -> dict:
    with _lock:
        c = _db()
        c.execute("INSERT INTO accounts(id,email,created_at,json) VALUES (?,?,?,?)",
                  (account["id"], account["email"], account.get("created_at", _now()),
                   json.dumps(account, default=str)))
        c.commit()
        return account


def get_account(agent_id: str):
    row = _db().execute("SELECT json FROM accounts WHERE id=?", (agent_id,)).fetchone()
    return json.loads(row["json"]) if row else None


def find_account_by_email(email: str):
    email = (email or "").strip().lower()
    row = _db().execute("SELECT json FROM accounts WHERE lower(email)=?", (email,)).fetchone()
    return json.loads(row["json"]) if row else None


def update_account(agent_id: str, patch: dict):
    with _lock:
        c = _db()
        row = c.execute("SELECT json FROM accounts WHERE id=?", (agent_id,)).fetchone()
        if not row:
            return None
        a = json.loads(row["json"])
        a.update(patch)
        a["updated_at"] = _now()
        c.execute("UPDATE accounts SET email=?, json=? WHERE id=?",
                  (a.get("email"), json.dumps(a, default=str), agent_id))
        c.commit()
        return a


def list_accounts() -> list:
    rows = _db().execute("SELECT json FROM accounts ORDER BY created_at DESC").fetchall()
    return [json.loads(r["json"]) for r in rows]


def count_accounts() -> int:
    return _db().execute("SELECT COUNT(*) FROM accounts").fetchone()[0]


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def get_settings() -> dict:
    row = _db().execute("SELECT json FROM settings WHERE id=1").fetchone()
    return json.loads(row["json"]) if row else {}


def save_settings(patch: dict) -> dict:
    with _lock:
        c = _db()
        s = get_settings()
        s.update(patch)
        s["updated_at"] = _now()
        c.execute("INSERT OR REPLACE INTO settings(id,json) VALUES (1,?)", (json.dumps(s, default=str),))
        c.commit()
        return s


# ---------------------------------------------------------------------------
# Reports (owner-scoped, versioned)
# ---------------------------------------------------------------------------

def save_report(token: str, payload: dict) -> dict:
    with _lock:
        c = _db()
        row = c.execute("SELECT json FROM reports WHERE token=?", (token,)).fetchone()
        existing = json.loads(row["json"]) if row else {}
        version = existing.get("version", 0) + 1
        result = payload.get("result", existing.get("result", {}))

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
        c.execute("INSERT OR REPLACE INTO reports(token,owner,created_at,updated_at,json) VALUES (?,?,?,?,?)",
                  (token, record["owner"], record["created_at"], record["updated_at"],
                   json.dumps(record, default=str)))
        c.commit()
        return record


def get_report(token: str):
    row = _db().execute("SELECT json FROM reports WHERE token=?", (token,)).fetchone()
    return json.loads(row["json"]) if row else None


def list_reports(owner: str = None) -> list:
    if owner is None:
        rows = _db().execute("SELECT json FROM reports").fetchall()
    else:
        rows = _db().execute("SELECT json FROM reports WHERE owner=?", (owner,)).fetchall()
    out = []
    for row in rows:
        r = json.loads(row["json"])
        out.append({
            "token": r["token"], "created_at": r["created_at"], "updated_at": r["updated_at"],
            "version": r["version"], "client_name": r.get("client_name", ""),
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


def count_reports_this_month(owner: str) -> int:
    """Distinct reports first created in the current calendar month (UTC)."""
    prefix = datetime.now(timezone.utc).strftime("%Y-%m")
    rows = _db().execute(
        "SELECT created_at FROM reports WHERE owner=? AND substr(created_at,1,7)=?",
        (owner, prefix)).fetchall()
    return len(rows)


def _mutate_report(token: str, fn):
    with _lock:
        c = _db()
        row = c.execute("SELECT json FROM reports WHERE token=?", (token,)).fetchone()
        if not row:
            return None
        r = json.loads(row["json"])
        out = fn(r)
        c.execute("UPDATE reports SET updated_at=?, json=? WHERE token=?",
                  (r.get("updated_at"), json.dumps(r, default=str), token))
        c.commit()
        return out


def record_view(token: str, ip: str = "", user_agent: str = "") -> bool:
    def fn(r):
        r.setdefault("views", []).append({"at": _now(), "ip": ip, "ua": user_agent})
        return True
    return bool(_mutate_report(token, fn))


def record_share(token: str, share: dict):
    def fn(r):
        entry = {"at": _now(), **share}
        r.setdefault("shares", []).append(entry)
        return entry
    return _mutate_report(token, fn)


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------

def add_lead(lead: dict) -> dict:
    with _lock:
        c = _db()
        entry = {"at": _now(), **lead}
        c.execute("INSERT INTO leads(agent_id,at,json) VALUES (?,?,?)",
                  (entry.get("agent_id"), entry["at"], json.dumps(entry, default=str)))
        c.commit()
        return entry


def list_leads(agent_id: str = None) -> list:
    if agent_id is None:
        rows = _db().execute("SELECT json FROM leads ORDER BY at DESC").fetchall()
    else:
        rows = _db().execute("SELECT json FROM leads WHERE agent_id=? ORDER BY at DESC",
                             (agent_id,)).fetchall()
    return [json.loads(r["json"]) for r in rows]
