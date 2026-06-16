"""
auth.py -- Lightweight account auth, standard library only.

* Passwords are hashed with PBKDF2-HMAC-SHA256 (never stored in plaintext).
* Sessions are stateless, hmac-signed bearer tokens: "<agent_id>.<expiry>.<sig>".

The signing secret comes from SMA_SECRET. A random dev secret is generated if it
is unset (tokens then reset on restart -- fine for local dev, set SMA_SECRET in
production).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time

_PBKDF2_ROUNDS = 120_000
_TOKEN_TTL = 60 * 60 * 24 * 14  # 14 days

_SECRET = os.environ.get("SMA_SECRET") or ("dev-" + secrets.token_hex(16))


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------

def hash_password(password: str) -> dict:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _PBKDF2_ROUNDS)
    return {"salt": salt, "hash": digest.hex()}


def verify_password(password: str, salt: str, expected_hex: str) -> bool:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _PBKDF2_ROUNDS)
    return hmac.compare_digest(digest.hex(), expected_hex)


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

def _sign(msg: str) -> str:
    sig = hmac.new(_SECRET.encode(), msg.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode().rstrip("=")


def make_token(agent_id: str, ttl: int = _TOKEN_TTL) -> str:
    expiry = str(int(time.time()) + ttl)
    body = f"{agent_id}.{expiry}"
    return f"{body}.{_sign(body)}"


def parse_token(token: str):
    """Return agent_id if the token is valid and unexpired, else None."""
    if not token:
        return None
    try:
        agent_id, expiry, sig = token.rsplit(".", 2)
    except ValueError:
        return None
    body = f"{agent_id}.{expiry}"
    if not hmac.compare_digest(sig, _sign(body)):
        return None
    try:
        if int(expiry) < int(time.time()):
            return None
    except ValueError:
        return None
    return agent_id


def bearer_from_header(header_value: str):
    if not header_value:
        return None
    parts = header_value.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return header_value.strip() or None
