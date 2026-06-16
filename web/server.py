"""
server.py -- Backend API + send-to-client flow for SMA-Report.

Exposes the engine over HTTP for the React agent UI, persists shareable report
versions, serves a branded client-facing web report at /r/<token>, tracks when
the client views it, and handles sharing.

SEND-TO-CLIENT SAFETY (do not weaken):
  * Nothing is ever auto-sent to a client. An email/text is only dispatched when
    the request carries ``confirmed: true`` -- the agent's explicit confirmation.
  * Without confirmation the endpoint returns a *draft* for the agent to review.
  * "handoff" mode returns a mailto:/sms: link so the message goes out from the
    agent's OWN email/phone (their address, their sender reputation).
  * "app" mode only actually transmits if SMTP is configured; otherwise it is
    clearly reported as simulated. It still requires confirmation.

Run:  python web/server.py     (defaults to http://localhost:8000)
"""
from __future__ import annotations

import os
import secrets
import smtplib
import sys
import urllib.parse
from email.message import EmailMessage

from flask import Flask, jsonify, request, Response
from flask_cors import CORS

# Make the project root importable when run as `python web/server.py`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import run_cma                       # noqa: E402
from report import render_html                    # noqa: E402
from data import SUBJECT, COMPS, AGENT_BRANDING   # noqa: E402
from web import store                             # noqa: E402

app = Flask(__name__)
CORS(app)  # allow the Vite dev server (localhost:5173) to call the API

PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_from_body(body: dict) -> dict:
    """Run the engine from a request body: {subject, comps, include|exclude, method}."""
    subject = body.get("subject") or SUBJECT
    comps = body.get("comps") or COMPS
    include = body.get("include")
    if include is None and body.get("exclude"):
        include = {lid: False for lid in body["exclude"]}
    method = body.get("method", "auto")
    return run_cma(subject, comps, include=include or {}, method=method)


def _share_url(token: str) -> str:
    return f"{PUBLIC_BASE_URL}/r/{token}"


def _build_draft(channel: str, report: dict, to: str, custom_msg: str) -> dict:
    branding = report.get("branding", {})
    result = report.get("result", {})
    addr = (result.get("subject", {}) or {}).get("UnparsedAddress", "your property")
    agent = branding.get("agent_name", "Your agent")
    brokerage = branding.get("brokerage", "")
    link = _share_url(report["token"])
    client = report.get("client_name", "").strip()
    greeting = f"Hi {client}," if client else "Hi,"

    body_lines = [
        greeting,
        "",
        custom_msg.strip() if custom_msg else
        f"I put together a market analysis for {addr}. You can view the full "
        f"report here -- every comparable links to its MLS listing so you can "
        f"verify the numbers yourself:",
        "",
        link,
        "",
        "Happy to walk through it whenever works for you.",
        "",
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


def _smtp_send(to: str, subject: str, body: str) -> bool:
    """Send via SMTP only if configured. Returns True if actually transmitted."""
    host = os.environ.get("SMTP_HOST")
    if not host:
        return False
    msg = EmailMessage()
    msg["From"] = os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER", "noreply@example.com"))
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587"))) as s:
        s.starttls()
        if os.environ.get("SMTP_USER"):
            s.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASS", ""))
        s.send_message(msg)
    return True


# ---------------------------------------------------------------------------
# API: engine + sample data
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.get("/api/sample")
def sample():
    """Default subject / comps / branding so the UI can load something instantly."""
    return jsonify({"subject": SUBJECT, "comps": COMPS, "branding": AGENT_BRANDING})


@app.post("/api/cma")
def cma():
    """Run the engine. Body: {subject, comps, include|exclude, method}."""
    return jsonify(_run_from_body(request.get_json(force=True) or {}))


# ---------------------------------------------------------------------------
# API: shareable reports + view tracking
# ---------------------------------------------------------------------------

@app.post("/api/reports")
def create_report():
    """
    Persist a shareable report version.
    Body: {result?|subject,comps,include,method, branding, client_name, template, token?}
    Returns {token, url, version}.
    """
    body = request.get_json(force=True) or {}
    result = body.get("result") or _run_from_body(body)
    token = body.get("token") or secrets.token_urlsafe(9)
    record = store.save_report(token, {
        "result": result,
        "branding": body.get("branding") or AGENT_BRANDING,
        "client_name": body.get("client_name", ""),
        "template": body.get("template", "seller"),
    })
    return jsonify({"token": token, "url": _share_url(token), "version": record["version"]})


@app.get("/api/reports")
def reports_index():
    return jsonify({"reports": store.list_reports()})


@app.get("/api/reports/<token>")
def report_json(token):
    r = store.get_report(token)
    if not r:
        return jsonify({"error": "not found"}), 404
    return jsonify(r)


@app.get("/api/reports/<token>/views")
def report_views(token):
    r = store.get_report(token)
    if not r:
        return jsonify({"error": "not found"}), 404
    views = r.get("views", [])
    return jsonify({
        "token": token,
        "view_count": len(views),
        "first_viewed_at": views[0]["at"] if views else None,
        "last_viewed_at": views[-1]["at"] if views else None,
        "viewed": bool(views),
        "views": views,
    })


@app.get("/r/<token>")
def client_report(token):
    """Branded, client-facing web report. Records a view event."""
    r = store.get_report(token)
    if not r:
        return Response("Report not found.", status=404)
    store.record_view(token, ip=request.remote_addr or "",
                      user_agent=request.headers.get("User-Agent", ""))
    html = render_html(r["result"], r.get("branding", {}))
    return Response(html, mimetype="text/html")


# ---------------------------------------------------------------------------
# API: send-to-client (confirmation required)
# ---------------------------------------------------------------------------

@app.post("/api/reports/<token>/share")
def share_report(token):
    """
    Prepare or send a share.
    Body: {channel: link|email|sms, to, message?, confirmed: bool, mode: app|handoff}

    Returns a DRAFT unless confirmed=true. Never auto-sends.
    """
    r = store.get_report(token)
    if not r:
        return jsonify({"error": "not found"}), 404

    body = request.get_json(force=True) or {}
    channel = body.get("channel", "link")
    to = (body.get("to") or "").strip()
    confirmed = bool(body.get("confirmed"))
    mode = body.get("mode", "handoff")
    custom_msg = body.get("message", "")

    # Sharing a private link is just generating a URL for the agent to send.
    if channel == "link":
        url = _share_url(token)
        store.record_share(token, {"channel": "link", "status": "link_generated"})
        return jsonify({"status": "link_generated", "url": url})

    if channel not in ("email", "sms"):
        return jsonify({"error": f"unknown channel '{channel}'"}), 400
    if not to:
        return jsonify({"error": "recipient 'to' is required"}), 400

    draft = _build_draft(channel, r, to, custom_msg)

    # No confirmation -> return the draft for the agent to review. Nothing sent.
    if not confirmed:
        return jsonify({"status": "draft", "requires_confirmation": True, "draft": draft})

    # Confirmed. Handoff = open the agent's own client (sends from their address).
    if mode == "handoff":
        store.record_share(token, {"channel": channel, "to": to,
                                   "status": "handoff", "confirmed": True})
        return jsonify({"status": "handoff", "handoff_url": draft["handoff_url"], "draft": draft})

    # Confirmed app-mode send. Only truly transmits if a transport is configured.
    sent = False
    if channel == "email":
        sent = _smtp_send(to, draft.get("subject", ""), draft["body"])
    # (SMS app-mode would call a provider like Twilio here; simulated by default.)
    store.record_share(token, {"channel": channel, "to": to, "confirmed": True,
                               "status": "sent" if sent else "simulated", "mode": "app"})
    return jsonify({
        "status": "sent" if sent else "simulated",
        "transmitted": sent,
        "note": None if sent else
                "No transport configured (set SMTP_* env to actually send email, "
                "or use mode='handoff'). Share recorded as simulated.",
        "draft": draft,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print(f"SMA-Report API on http://localhost:{port}  (public base: {PUBLIC_BASE_URL})")
    app.run(host="0.0.0.0", port=port, debug=True)
