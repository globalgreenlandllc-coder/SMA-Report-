"""
transport.py -- Real email / SMS delivery, behind the agent-confirmation gate.

Both functions transmit ONLY when their transport is configured via env; otherwise
they return ``transmitted: False`` with a note (the server records the share as
"simulated"). The server never calls these without the agent's explicit
confirmation -- see web/server.py share_report().

Email:  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM
SMS:    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM
"""
from __future__ import annotations

import base64
import os
import smtplib
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage


def send_email(to: str, subject: str, body: str) -> dict:
    host = os.environ.get("SMTP_HOST")
    if not host:
        return {"transmitted": False, "transport": None,
                "note": "SMTP not configured (set SMTP_* env). Use mode='handoff' "
                        "to send from your own email. Recorded as simulated."}
    msg = EmailMessage()
    msg["From"] = os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER", "noreply@example.com"))
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587")), timeout=15) as s:
            s.starttls()
            if os.environ.get("SMTP_USER"):
                s.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASS", ""))
            s.send_message(msg)
        return {"transmitted": True, "transport": "smtp", "note": None}
    except Exception as e:  # surface failure without crashing the request
        return {"transmitted": False, "transport": "smtp",
                "note": f"SMTP send failed: {e}. Recorded as simulated."}


def send_sms(to: str, body: str) -> dict:
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_ = os.environ.get("TWILIO_FROM")
    if not (sid and token and from_):
        return {"transmitted": False, "transport": None,
                "note": "Twilio not configured (set TWILIO_* env). Use mode='handoff' "
                        "to send from your own phone. Recorded as simulated."}
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    data = urllib.parse.urlencode({"To": to, "From": from_, "Body": body}).encode()
    auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/x-www-form-urlencoded",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
        return {"transmitted": True, "transport": "twilio", "note": None}
    except Exception as e:
        return {"transmitted": False, "transport": "twilio",
                "note": f"Twilio send failed: {e}. Recorded as simulated."}
