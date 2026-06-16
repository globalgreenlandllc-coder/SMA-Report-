"""
server.py -- Backend API for SMA-Report (multi-tenant).

Exposes the engine over HTTP for the React agent UI, with agent accounts,
per-agent branding, owner-scoped + versioned shareable reports, a branded
client-facing web report with view tracking, market trends, a public lead-capture
widget, and a confirmation-gated send-to-client flow.

SEND-TO-CLIENT SAFETY (do not weaken):
  * Nothing is ever auto-sent. Email/text only goes out with ``confirmed: true``.
  * Without confirmation the endpoint returns a *draft* for the agent to review.
  * "handoff" mode returns a mailto:/sms: link so the message sends from the
    agent's OWN client. "app" mode transmits only if SMTP/Twilio is configured,
    otherwise it is clearly reported as simulated.

Run:  python web/server.py     (defaults to http://localhost:8000)
"""
from __future__ import annotations

import functools
import os
import secrets
import sys
import urllib.parse

from flask import Flask, jsonify, request, Response, g
from flask_cors import CORS

# Make the project root importable when run as `python web/server.py`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import run_cma                       # noqa: E402
from engine.trends import market_trends           # noqa: E402
from report import render_html                    # noqa: E402
from report.report import generate_pdf_bytes       # noqa: E402
from report.templates import TEMPLATES            # noqa: E402
from report.narrative import build_narrative, pricing_recommendation  # noqa: E402
from data import SUBJECT, COMPS, AGENT_BRANDING   # noqa: E402
from web import store, auth                        # noqa: E402
from web.transport import send_email, send_sms     # noqa: E402

app = Flask(__name__)
CORS(app)  # allow the Vite dev server (localhost:5173) to call the API

PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000")


# ---------------------------------------------------------------------------
# Auth plumbing
# ---------------------------------------------------------------------------

def _current_agent():
    token = auth.bearer_from_header(request.headers.get("Authorization", ""))
    agent_id = auth.parse_token(token)
    return store.get_account(agent_id) if agent_id else None


def auth_required(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        agent = _current_agent()
        if not agent:
            return jsonify({"error": "authentication required"}), 401
        g.agent = agent
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        agent = _current_agent()
        if not agent:
            return jsonify({"error": "authentication required"}), 401
        if agent.get("role") != "admin":
            return jsonify({"error": "admin only"}), 403
        g.agent = agent
        return fn(*args, **kwargs)
    return wrapper


def _public_account(a: dict) -> dict:
    """Account without secrets, safe to return to the client."""
    return {k: v for k, v in a.items() if k not in ("pw_hash", "pw_salt")}


# Which settings keys are secret (masked on read, only updated when re-sent).
_SECRET_KEYS = {"simplyrets_secret", "mlsgrid_token", "trestle_client_secret",
                "smtp_pass", "twilio_auth_token"}


def _masked_settings(s: dict) -> dict:
    out = {}
    for k, v in s.items():
        out[k] = ("••••••" if (k in _SECRET_KEYS and v) else v)
    return out


def _apply_source_env(s: dict) -> None:
    """Push stored data-source credentials into the process env for the loaders."""
    mapping = {
        "simplyrets_key": "SIMPLYRETS_API_KEY", "simplyrets_secret": "SIMPLYRETS_API_SECRET",
        "mlsgrid_token": "MLSGRID_API_TOKEN", "mlsgrid_base_url": "MLSGRID_BASE_URL",
        "trestle_client_id": "TRESTLE_CLIENT_ID", "trestle_client_secret": "TRESTLE_CLIENT_SECRET",
        "smtp_host": "SMTP_HOST", "smtp_port": "SMTP_PORT", "smtp_user": "SMTP_USER",
        "smtp_pass": "SMTP_PASS", "smtp_from": "SMTP_FROM",
        "twilio_account_sid": "TWILIO_ACCOUNT_SID", "twilio_auth_token": "TWILIO_AUTH_TOKEN",
        "twilio_from": "TWILIO_FROM",
    }
    for k, env_key in mapping.items():
        if s.get(k):
            os.environ[env_key] = str(s[k])


def _load_source_comps(limit: int = 25):
    """Pull comps from the admin-configured source; fall back to sample data."""
    settings = store.get_settings()
    _apply_source_env(settings)
    source = (settings.get("data_source") or "sample").lower()
    try:
        if source == "simplyrets":
            from data.reso_loader import load_comps
            return load_comps(limit=limit), "simplyrets", None
        if source in ("mlsgrid", "trestle"):
            from data.reso_odata_loader import make_loader
            os.environ["RESO_PROVIDER"] = source
            return make_loader().load_comps(top=limit), source, None
    except Exception as exc:
        return COMPS, "sample", f"{source} unavailable ({exc}); using sample data."
    return COMPS, "sample", None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_from_body(body: dict) -> dict:
    subject = body.get("subject") or SUBJECT
    comps = body.get("comps") or COMPS
    include = body.get("include")
    if include is None and body.get("exclude"):
        include = {lid: False for lid in body["exclude"]}
    method = body.get("method", "auto")
    result = run_cma(subject, comps, include=include or {}, method=method)
    result["trends"] = market_trends(comps)
    result["narrative"] = body.get("narrative") or build_narrative(result)
    result["recommendation"] = pricing_recommendation(result)
    return result


def _share_url(token: str) -> str:
    return f"{PUBLIC_BASE_URL}/r/{token}"


# ---------------------------------------------------------------------------
# Auth + account
# ---------------------------------------------------------------------------

@app.post("/api/auth/register")
def register():
    body = request.get_json(force=True) or {}
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    if not email or len(password) < 6:
        return jsonify({"error": "email and a 6+ char password are required"}), 400
    if store.find_account_by_email(email):
        return jsonify({"error": "an account with that email already exists"}), 409

    pw = auth.hash_password(password)
    agent_id = secrets.token_urlsafe(8)
    branding = dict(AGENT_BRANDING)
    branding.update({
        "agent_name": body.get("agent_name", branding["agent_name"]),
        "brokerage": body.get("brokerage", branding["brokerage"]),
        "email": email,
    })
    # The first account to register becomes the admin (manages API/data sources).
    role = "admin" if store.count_accounts() == 0 else "agent"
    account = {
        "id": agent_id, "email": email, "role": role,
        "pw_hash": pw["hash"], "pw_salt": pw["salt"],
        "branding": branding, "created_at": store._now(),
    }
    store.create_account(account)
    return jsonify({"token": auth.make_token(agent_id), "agent": _public_account(account)})


@app.post("/api/auth/login")
def login():
    body = request.get_json(force=True) or {}
    account = store.find_account_by_email(body.get("email", ""))
    if not account or not auth.verify_password(
        body.get("password", ""), account["pw_salt"], account["pw_hash"]
    ):
        return jsonify({"error": "invalid email or password"}), 401
    return jsonify({"token": auth.make_token(account["id"]), "agent": _public_account(account)})


@app.get("/api/auth/me")
@auth_required
def me():
    return jsonify({"agent": _public_account(g.agent)})


@app.put("/api/account/branding")
@auth_required
def update_branding():
    body = request.get_json(force=True) or {}
    branding = dict(g.agent.get("branding", {}))
    for k in ("agent_name", "title", "brokerage", "phone", "email", "license",
              "logo_url", "headshot_url", "primary_color", "accent_color"):
        if k in body:
            branding[k] = body[k]
    store.update_account(g.agent["id"], {"branding": branding})
    return jsonify({"branding": branding})


# ---------------------------------------------------------------------------
# Engine + sample data (public)
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.get("/api/sample")
def sample():
    return jsonify({"subject": SUBJECT, "comps": COMPS, "branding": AGENT_BRANDING})


@app.post("/api/cma")
def cma():
    body = request.get_json(force=True) or {}
    return jsonify(_run_from_body(body))


@app.get("/api/comps")
def comps_from_source():
    """Pull comps from the admin-configured data source (fallback: sample)."""
    comps, source, note = _load_source_comps(limit=int(request.args.get("limit", 25)))
    return jsonify({"comps": comps, "source": source, "note": note})


@app.get("/api/templates")
def templates():
    return jsonify({"templates": [{"key": k, **v} for k, v in TEMPLATES.items()]})


# ---------------------------------------------------------------------------
# Reports (owner-scoped + versioned)
# ---------------------------------------------------------------------------

@app.post("/api/reports")
@auth_required
def create_report():
    body = request.get_json(force=True) or {}
    result = body.get("result") or _run_from_body(body)
    result.setdefault("trends", market_trends(body.get("comps") or COMPS))
    if body.get("narrative"):
        result["narrative"] = body["narrative"]
    result.setdefault("narrative", build_narrative(result))
    result.setdefault("recommendation", pricing_recommendation(result))
    token = body.get("token") or secrets.token_urlsafe(9)

    # ownership check on update
    existing = store.get_report(token)
    if existing and existing.get("owner") not in (None, g.agent["id"]):
        return jsonify({"error": "forbidden"}), 403

    record = store.save_report(token, {
        "result": result,
        "owner": g.agent["id"],
        "branding": body.get("branding") or g.agent.get("branding") or AGENT_BRANDING,
        "client_name": body.get("client_name", ""),
        "template": body.get("template", "seller"),
    })
    return jsonify({"token": token, "url": _share_url(token), "version": record["version"]})


@app.get("/api/reports")
@auth_required
def reports_index():
    return jsonify({"reports": store.list_reports(owner=g.agent["id"])})


@app.get("/api/reports/<token>")
@auth_required
def report_json(token):
    r = store.get_report(token)
    if not r or r.get("owner") != g.agent["id"]:
        return jsonify({"error": "not found"}), 404
    return jsonify(r)


@app.get("/api/reports/<token>/history")
@auth_required
def report_history(token):
    r = store.get_report(token)
    if not r or r.get("owner") != g.agent["id"]:
        return jsonify({"error": "not found"}), 404
    current = {
        "version": r["version"], "saved_at": r["updated_at"],
        "likely": r["result"].get("likely"), "low": r["result"].get("low"),
        "high": r["result"].get("high"), "confidence": r["result"].get("confidence"),
        "n_comps": r["result"].get("n_comps"),
    }
    versions = r.get("history", []) + [current]
    # diff vs first version
    first = versions[0]
    delta = (current["likely"] or 0) - (first["likely"] or 0)
    return jsonify({
        "token": token, "versions": versions,
        "delta_likely": delta,
        "delta_pct": (delta / first["likely"] * 100) if first.get("likely") else 0,
    })


@app.get("/api/reports/<token>/views")
@auth_required
def report_views(token):
    r = store.get_report(token)
    if not r or r.get("owner") != g.agent["id"]:
        return jsonify({"error": "not found"}), 404
    views = r.get("views", [])
    return jsonify({
        "token": token, "view_count": len(views),
        "first_viewed_at": views[0]["at"] if views else None,
        "last_viewed_at": views[-1]["at"] if views else None,
        "viewed": bool(views), "views": views,
    })


@app.get("/r/<token>")
def client_report(token):
    """Branded, public client-facing web report. Records a view event."""
    r = store.get_report(token)
    if not r:
        return Response("Report not found.", status=404)
    store.record_view(token, ip=request.remote_addr or "",
                      user_agent=request.headers.get("User-Agent", ""))
    html = render_html(r["result"], r.get("branding", {}), template=r.get("template", "seller"))
    return Response(html, mimetype="text/html")


# ---------------------------------------------------------------------------
# Send-to-client (auth + ownership + confirmation)
# ---------------------------------------------------------------------------

def _build_draft(channel: str, report: dict, to: str, custom_msg: str) -> dict:
    branding = report.get("branding", {})
    result = report.get("result", {})
    addr = (result.get("subject", {}) or {}).get("UnparsedAddress", "your property")
    agent = branding.get("agent_name", "Your agent")
    brokerage = branding.get("brokerage", "")
    link = _share_url(report["token"])
    client = (report.get("client_name", "") or "").strip()
    greeting = f"Hi {client}," if client else "Hi,"

    body_lines = [
        greeting, "",
        custom_msg.strip() if custom_msg else
        f"I put together a market analysis for {addr}. You can view the full "
        f"report here -- every comparable links to its MLS listing so you can "
        f"verify the numbers yourself:",
        "", link, "",
        "Happy to walk through it whenever works for you.", "",
        agent + (f"\n{brokerage}" if brokerage else ""),
        branding.get("phone", ""),
    ]
    body = "\n".join(l for l in body_lines if l is not None)
    subject = f"Your home value analysis -- {addr}"
    draft = {"channel": channel, "to": to, "body": body, "link": link}
    if channel == "email":
        draft["subject"] = subject
        draft["handoff_url"] = "mailto:" + urllib.parse.quote(to) + "?" + urllib.parse.urlencode(
            {"subject": subject, "body": body})
    elif channel == "sms":
        sms_body = f"{greeting} here's the home value report for {addr}: {link} -- {agent}"
        draft["body"] = sms_body
        draft["handoff_url"] = "sms:" + urllib.parse.quote(to) + "?" + urllib.parse.urlencode({"body": sms_body})
    return draft


@app.post("/api/reports/<token>/share")
@auth_required
def share_report(token):
    r = store.get_report(token)
    if not r or r.get("owner") != g.agent["id"]:
        return jsonify({"error": "not found"}), 404

    body = request.get_json(force=True) or {}
    channel = body.get("channel", "link")
    to = (body.get("to") or "").strip()
    confirmed = bool(body.get("confirmed"))
    mode = body.get("mode", "handoff")
    custom_msg = body.get("message", "")

    if channel == "link":
        store.record_share(token, {"channel": "link", "status": "link_generated"})
        return jsonify({"status": "link_generated", "url": _share_url(token)})

    if channel not in ("email", "sms"):
        return jsonify({"error": f"unknown channel '{channel}'"}), 400
    if not to:
        return jsonify({"error": "recipient 'to' is required"}), 400

    draft = _build_draft(channel, r, to, custom_msg)

    if not confirmed:
        return jsonify({"status": "draft", "requires_confirmation": True, "draft": draft})

    if mode == "handoff":
        store.record_share(token, {"channel": channel, "to": to, "status": "handoff", "confirmed": True})
        return jsonify({"status": "handoff", "handoff_url": draft["handoff_url"], "draft": draft})

    # Confirmed app-mode send via configured transport (else simulated).
    if channel == "email":
        res = send_email(to, draft.get("subject", ""), draft["body"])
    else:
        res = send_sms(to, draft["body"])
    store.record_share(token, {"channel": channel, "to": to, "confirmed": True,
                               "status": "sent" if res["transmitted"] else "simulated",
                               "mode": "app", "transport": res.get("transport")})
    return jsonify({
        "status": "sent" if res["transmitted"] else "simulated",
        "transmitted": res["transmitted"], "note": res.get("note"), "draft": draft,
    })


# ---------------------------------------------------------------------------
# Leads (public capture + agent dashboard)
# ---------------------------------------------------------------------------

@app.post("/api/leads")
def create_lead():
    body = request.get_json(force=True) or {}
    if not body.get("agent_id") or not (body.get("address") or body.get("email")):
        return jsonify({"error": "agent_id and address/email required"}), 400
    lead = store.add_lead({
        "agent_id": body["agent_id"],
        "name": body.get("name", ""), "address": body.get("address", ""),
        "email": body.get("email", ""), "phone": body.get("phone", ""),
        "message": body.get("message", ""), "source": "widget",
    })
    return jsonify({"ok": True, "lead": lead})


@app.get("/api/leads")
@auth_required
def leads_index():
    return jsonify({"leads": store.list_leads(agent_id=g.agent["id"])})


@app.get("/widget/<agent_id>")
def lead_widget(agent_id):
    """Embeddable 'what's my home worth' lead-capture widget."""
    account = store.get_account(agent_id)
    if not account:
        return Response("Unknown agent.", status=404)
    from web.widget import render_widget
    return Response(render_widget(account, PUBLIC_BASE_URL), mimetype="text/html")


# ---------------------------------------------------------------------------
# PDF export
# ---------------------------------------------------------------------------

@app.post("/api/report/pdf")
@auth_required
def report_pdf():
    """Render the branded PDF from the current state and return it for download."""
    body = request.get_json(force=True) or {}
    result = body.get("result") or _run_from_body(body)
    branding = body.get("branding") or g.agent.get("branding") or AGENT_BRANDING
    template = body.get("template", "seller")
    try:
        pdf = generate_pdf_bytes(result, branding, template=template)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503
    addr = (result.get("subject", {}) or {}).get("UnparsedAddress", "report")
    fname = "CMA - " + "".join(c for c in addr.split(",")[0] if c.isalnum() or c in " -") + ".pdf"
    return Response(pdf, mimetype="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


# ---------------------------------------------------------------------------
# Admin: data-source / API management
# ---------------------------------------------------------------------------

@app.get("/api/admin/settings")
@admin_required
def admin_get_settings():
    return jsonify({"settings": _masked_settings(store.get_settings())})


@app.put("/api/admin/settings")
@admin_required
def admin_put_settings():
    body = request.get_json(force=True) or {}
    patch = {}
    for k, v in body.items():
        # Ignore masked secrets that were sent back unchanged.
        if k in _SECRET_KEYS and v == "••••••":
            continue
        patch[k] = v
    s = store.save_settings(patch)
    _apply_source_env(s)
    return jsonify({"settings": _masked_settings(s)})


@app.get("/api/admin/agents")
@admin_required
def admin_agents():
    agents = [_public_account(a) for a in store._read()["accounts"].values()]
    agents.sort(key=lambda a: a.get("created_at", ""), reverse=True)
    # attach report + lead counts
    for a in agents:
        a["report_count"] = len(store.list_reports(owner=a["id"]))
        a["lead_count"] = len(store.list_leads(agent_id=a["id"]))
    return jsonify({"agents": agents})


@app.post("/api/admin/test-source")
@admin_required
def admin_test_source():
    comps, source, note = _load_source_comps(limit=3)
    return jsonify({"source": source, "ok": note is None, "note": note,
                    "sample_count": len(comps)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print(f"SMA-Report API on http://localhost:{port}  (public base: {PUBLIC_BASE_URL})")
    app.run(host="0.0.0.0", port=port, debug=True)
