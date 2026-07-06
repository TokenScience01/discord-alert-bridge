from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from typing import Mapping

SESSION_COOKIE = "dab_session"
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60


def auth_required() -> bool:
    return bool(admin_password())


def admin_username() -> str:
    value = os.getenv("ADMIN_USERNAME", "admin").strip()
    return value or "admin"


def admin_password() -> str:
    return os.getenv("ADMIN_PASSWORD", "").strip()


def session_secret() -> str:
    explicit = os.getenv("ADMIN_SESSION_SECRET", "").strip()
    if explicit:
        return explicit
    password = admin_password()
    if password:
        return hashlib.sha256(f"discord-alert-bridge:{password}".encode("utf-8")).hexdigest()
    return "discord-alert-bridge-insecure-dev"


def verify_credentials(username: str, password: str) -> bool:
    if not auth_required():
        return True
    return secrets.compare_digest(username.strip(), admin_username()) and secrets.compare_digest(
        password, admin_password()
    )


def issue_session_token(username: str) -> str:
    expires_at = int(time.time()) + SESSION_TTL_SECONDS
    payload = f"{username}:{expires_at}"
    signature = hmac.new(
        session_secret().encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}:{signature}"


def verify_session_token(token: str) -> str | None:
    if not auth_required():
        return admin_username()
    if not token or ":" not in token:
        return None
    payload, signature = token.rsplit(":", 1)
    expected = hmac.new(
        session_secret().encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not secrets.compare_digest(signature, expected):
        return None
    username, expires_raw = payload.split(":", 1)
    try:
        expires_at = int(expires_raw)
    except ValueError:
        return None
    if expires_at < int(time.time()):
        return None
    if not secrets.compare_digest(username, admin_username()):
        return None
    return username


def parse_cookie_header(header: str | None) -> dict[str, str]:
    if not header:
        return {}
    cookies: dict[str, str] = {}
    for part in header.split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        cookies[key.strip()] = value.strip()
    return cookies


def session_cookie_header(token: str) -> str:
    return (
        f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict; "
        f"Max-Age={SESSION_TTL_SECONDS}"
    )


def clear_session_cookie_header() -> str:
    return f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"


def username_from_request(cookies: Mapping[str, str]) -> str | None:
    return verify_session_token(cookies.get(SESSION_COOKIE, ""))