from __future__ import annotations

import asyncio
import html
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .admin_auth import (
    SESSION_COOKIE,
    admin_password,
    auth_required,
    clear_session_cookie_header,
    issue_session_token,
    parse_cookie_header,
    session_cookie_header,
    username_from_request,
    verify_credentials,
)
from .admin_ui import render_login_page, render_page as render_dashboard_page
from .config import AppConfig, ConfigError, GmailConfig, WebhookConfig, parse_channel_references
from .forwarders import build_forwarder
from .message_store import list_messages
from .models import Alert
from .paths import ENV_EXAMPLE_PATH, ENV_PATH, LOG_PATH, MESSAGES_PATH, PID_PATH, ROOT

SESSION_BANNER_PREFIX = "===== Bridge session started"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

CONFIG_FIELDS = [
    "ADMIN_USERNAME",
    "ADMIN_PASSWORD",
    "DISCORD_USER_TOKEN",
    "DISCORD_CHANNEL_URLS",
    "DISCORD_CHANNEL_IDS",
    "DISCORD_ALLOWED_GUILD_IDS",
    "ALERT_PREFIX",
    "LOG_LEVEL",
    "GMAIL_ENABLED",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_STARTTLS",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "SMTP_FROM",
    "SMTP_TO",
    "LARK_ENABLED",
    "LARK_WEBHOOK_URL",
    "LARK_SECRET",
    "DINGTALK_ENABLED",
    "DINGTALK_WEBHOOK_URL",
    "DINGTALK_SECRET",
]

FIELD_DEFAULTS = {
    "ADMIN_USERNAME": "admin",
    "ADMIN_PASSWORD": "",
    "DISCORD_USER_TOKEN": "",
    "DISCORD_CHANNEL_URLS": "",
    "DISCORD_CHANNEL_IDS": "",
    "DISCORD_ALLOWED_GUILD_IDS": "",
    "ALERT_PREFIX": "[Discord]",
    "LOG_LEVEL": "INFO",
    "GMAIL_ENABLED": "false",
    "SMTP_HOST": "smtp.gmail.com",
    "SMTP_PORT": "587",
    "SMTP_STARTTLS": "true",
    "SMTP_USERNAME": "",
    "SMTP_PASSWORD": "",
    "SMTP_FROM": "",
    "SMTP_TO": "",
    "LARK_ENABLED": "false",
    "LARK_WEBHOOK_URL": "",
    "LARK_SECRET": "",
    "DINGTALK_ENABLED": "false",
    "DINGTALK_WEBHOOK_URL": "",
    "DINGTALK_SECRET": "",
}

SECRET_FIELDS = {
    "ADMIN_PASSWORD",
    "DISCORD_USER_TOKEN",
    "SMTP_PASSWORD",
    "LARK_SECRET",
    "DINGTALK_SECRET",
}


def run() -> None:
    _load_env()
    host = os.getenv("ADMIN_HOST", DEFAULT_HOST)
    port = int(os.getenv("ADMIN_PORT", str(DEFAULT_PORT)))
    try:
        server = ThreadingHTTPServer((host, port), AdminHandler)
    except OSError as exc:
        if exc.errno in {48, 98}:  # macOS / Linux: address already in use
            listener_pid = _find_listener_pid(port)
            if listener_pid is not None:
                print(f"Port {port} is already in use by PID {listener_pid}.")
            else:
                print(f"Port {port} is already in use.")
            print(f"Config page may already be running: http://{host}:{port}")
            print("Stop the existing admin process first, or set ADMIN_PORT to another value.")
            raise SystemExit(1) from exc
        raise
    print(f"Config page: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped admin server.")


def _find_listener_pid(port: int) -> int | None:
    try:
        result = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        return int(result.stdout.strip().splitlines()[0])
    except ValueError:
        return None


class AdminHandler(BaseHTTPRequestHandler):
    server_version = "DiscordAlertBridgeAdmin/0.2"

    def do_HEAD(self) -> None:
        route = urlparse(self.path).path
        if route in {"/", "/login"}:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_GET(self) -> None:
        route = urlparse(self.path).path
        if route == "/login":
            if self._current_user():
                self._redirect("/")
                return
            self._send_html(render_login_page())
            return
        if route == "/":
            if not self._current_user():
                self._redirect("/login")
                return
            self._send_html(render_page())
            return
        if not self._current_user():
            return self._unauthorized()
        if route == "/api/config":
            self._send_json({"config": read_env()})
            return
        if route == "/api/status":
            self._send_json(build_status())
            return
        if route == "/api/messages":
            query = parse_qs(urlparse(self.path).query)
            channel_id = query.get("channel_id", [None])[0]
            self._send_json(list_messages(MESSAGES_PATH, channel_id=channel_id))
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        route = urlparse(self.path).path
        if route == "/api/login":
            data = self._read_json()
            username = str(data.get("username", ""))
            password = str(data.get("password", ""))
            if not verify_credentials(username, password):
                self._send_json(
                    {"ok": False, "message": "账号或密码错误"},
                    status=HTTPStatus.UNAUTHORIZED,
                )
                return
            token = issue_session_token(username)
            self._send_json(
                {"ok": True, "message": "登录成功"},
                extra_headers=[("Set-Cookie", session_cookie_header(token))],
            )
            return
        if route == "/api/logout":
            self._send_json(
                {"ok": True, "message": "已退出"},
                extra_headers=[("Set-Cookie", clear_session_cookie_header())],
            )
            return
        if not self._current_user():
            return self._unauthorized()
        if route == "/api/config":
            data = self._read_json()
            write_env({key: str(data.get(key, "")) for key in CONFIG_FIELDS})
            self._send_json({"ok": True, "status": build_status()})
            return
        if route == "/api/toggle":
            self._send_json(toggle_bridge())
            return
        if route == "/api/start":
            self._send_json(start_bridge())
            return
        if route == "/api/stop":
            self._send_json(stop_bridge())
            return
        if route == "/api/test-alert":
            self._send_json(send_test_alert())
            return
        if route == "/api/clear-log":
            self._send_json(clear_log())
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}")

    def _read_json(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length) if content_length else b"{}"
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _send_html(self, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json(
        self,
        body: dict[str, Any],
        status: HTTPStatus = HTTPStatus.OK,
        extra_headers: list[tuple[str, str]] | None = None,
    ) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        for key, value in extra_headers or []:
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(encoded)

    def _cookies(self) -> dict[str, str]:
        return parse_cookie_header(self.headers.get("Cookie"))

    def _current_user(self) -> str | None:
        return username_from_request(self._cookies())

    def _redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", location)
        self.end_headers()

    def _unauthorized(self) -> None:
        route = urlparse(self.path).path
        if route.startswith("/api/"):
            self._send_json(
                {"ok": False, "message": "未登录"},
                status=HTTPStatus.UNAUTHORIZED,
            )
            return
        self._redirect("/login")


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH, override=True)


def read_env() -> dict[str, str]:
    _load_env()
    values = dict(FIELD_DEFAULTS)
    source = ENV_PATH if ENV_PATH.exists() else ENV_EXAMPLE_PATH
    if not source.exists():
        return values

    for line in source.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if key == "DISCORD_BOT_TOKEN":
            key = "DISCORD_USER_TOKEN"
        if key in values:
            values[key] = _unquote_env(value.strip())
    fill_channel_ids_from_refs(values)
    return values


def write_env(values: dict[str, str]) -> None:
    existing = read_env()
    normalized = dict(FIELD_DEFAULTS)
    for key in CONFIG_FIELDS:
        normalized[key] = values.get(key, normalized[key]).strip()
    if not normalized["ADMIN_PASSWORD"]:
        normalized["ADMIN_PASSWORD"] = existing.get("ADMIN_PASSWORD", "")
    normalized["DISCORD_USER_TOKEN"] = normalize_discord_user_token(normalized["DISCORD_USER_TOKEN"])
    fill_channel_ids_from_refs(normalized)

    lines = [
        "# Managed by discord-alert-bridge admin page.",
        "# Uses a Discord personal user token for local testing only.",
        "",
        "# Admin login",
        f"ADMIN_USERNAME={_quote_env(normalized['ADMIN_USERNAME'])}",
        f"ADMIN_PASSWORD={_quote_env(normalized['ADMIN_PASSWORD'])}",
        "",
        "# Discord",
        f"DISCORD_USER_TOKEN={_quote_env(normalized['DISCORD_USER_TOKEN'])}",
        f"DISCORD_CHANNEL_URLS={_quote_env(normalized['DISCORD_CHANNEL_URLS'])}",
        f"DISCORD_CHANNEL_IDS={_quote_env(normalized['DISCORD_CHANNEL_IDS'])}",
        f"DISCORD_ALLOWED_GUILD_IDS={_quote_env(normalized['DISCORD_ALLOWED_GUILD_IDS'])}",
        f"ALERT_PREFIX={_quote_env(normalized['ALERT_PREFIX'])}",
        f"LOG_LEVEL={_quote_env(normalized['LOG_LEVEL'])}",
        "",
        "# Gmail SMTP",
        f"GMAIL_ENABLED={_bool_text(normalized['GMAIL_ENABLED'])}",
        f"SMTP_HOST={_quote_env(normalized['SMTP_HOST'])}",
        f"SMTP_PORT={_quote_env(normalized['SMTP_PORT'])}",
        f"SMTP_STARTTLS={_bool_text(normalized['SMTP_STARTTLS'], default=True)}",
        f"SMTP_USERNAME={_quote_env(normalized['SMTP_USERNAME'])}",
        f"SMTP_PASSWORD={_quote_env(normalized['SMTP_PASSWORD'])}",
        f"SMTP_FROM={_quote_env(normalized['SMTP_FROM'])}",
        f"SMTP_TO={_quote_env(normalized['SMTP_TO'])}",
        "",
        "# Lark / Feishu",
        f"LARK_ENABLED={_bool_text(normalized['LARK_ENABLED'])}",
        f"LARK_WEBHOOK_URL={_quote_env(normalized['LARK_WEBHOOK_URL'])}",
        f"LARK_SECRET={_quote_env(normalized['LARK_SECRET'])}",
        "",
        "# DingTalk",
        f"DINGTALK_ENABLED={_bool_text(normalized['DINGTALK_ENABLED'])}",
        f"DINGTALK_WEBHOOK_URL={_quote_env(normalized['DINGTALK_WEBHOOK_URL'])}",
        f"DINGTALK_SECRET={_quote_env(normalized['DINGTALK_SECRET'])}",
        "",
    ]
    ENV_PATH.write_text("\n".join(lines), encoding="utf-8")


def fill_channel_ids_from_refs(values: dict[str, str]) -> dict[str, str]:
    refs = [part.strip() for part in values.get("DISCORD_CHANNEL_URLS", "").split(",") if part.strip()]
    if not refs:
        return values

    try:
        selection = parse_channel_references(refs)
    except ConfigError:
        return values

    if selection.channel_ids:
        values["DISCORD_CHANNEL_IDS"] = ",".join(map(str, sorted(selection.channel_ids)))
    if selection.guild_ids:
        values["DISCORD_ALLOWED_GUILD_IDS"] = ",".join(map(str, sorted(selection.guild_ids)))
    return values


def start_bridge() -> dict[str, Any]:
    status = build_status()
    if status["running"]:
        return {"ok": True, "message": "Bridge is already running.", "status": status}
    if not status["summary"]["ready"]:
        problems = status["summary"]["missing"] + status["summary"]["errors"]
        return {
            "ok": False,
            "message": "Cannot start: " + ", ".join(problems),
            "status": status,
        }

    if not ENV_PATH.exists():
        write_env(read_env())

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("ab", buffering=0) as log_file:
        log_file.write(_session_banner_bytes())
        process = subprocess.Popen(
            [sys.executable, str(ROOT / "main.py")],
            cwd=ROOT,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        log_file.write(f"Bridge process PID {process.pid}\n".encode("utf-8"))
    PID_PATH.write_text(str(process.pid), encoding="utf-8")
    time.sleep(1.2)
    status = build_status()
    if not status["running"]:
        return {
            "ok": False,
            "message": "Bridge exited right after start. Check the log tab.",
            "status": status,
        }
    return {"ok": True, "message": f"Bridge started with PID {process.pid}.", "status": status}


def send_test_alert() -> dict[str, Any]:
    config = read_env()
    errors = validate_forwarder_settings(config)
    if errors:
        return {
            "ok": False,
            "message": "Cannot send test notification: " + ", ".join(errors),
            "status": build_status(),
        }

    alert_config = build_test_alert_config(config)
    sent_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    alert = Alert(
        subject="测试通知",
        body=f"发送人: 系统\n内容:\n这是一条测试通知\n\n发送时间: {sent_at}",
        channel="测试频道",
        author="系统",
        message="这是一条测试通知。如果你收到了这条消息，说明转发配置正常。",
        extras=(f"发送时间: {sent_at}",),
    )

    try:
        asyncio.run(build_forwarder(alert_config).send(alert))
    except Exception as exc:
        return {
            "ok": False,
            "message": f"Test notification failed: {exc}",
            "status": build_status(),
        }

    return {
        "ok": True,
        "message": "Test notification sent.",
        "status": build_status(),
    }


def clear_log() -> dict[str, Any]:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("", encoding="utf-8")
    return {"ok": True, "message": "日志已清空。", "status": build_status()}


def _session_banner_bytes() -> bytes:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"\n{SESSION_BANNER_PREFIX} {stamp} =====\n".encode("utf-8")


def toggle_bridge() -> dict[str, Any]:
    status = build_status()
    if status["running"]:
        return stop_bridge()
    return start_bridge()


def stop_bridge() -> dict[str, Any]:
    pid = read_pid()
    if pid is None:
        return {"ok": True, "message": "Bridge is not running.", "status": build_status()}

    if is_pid_running(pid):
        os.kill(pid, signal.SIGTERM)
        for _ in range(20):
            time.sleep(0.1)
            if not is_pid_running(pid):
                break
        if is_pid_running(pid):
            os.kill(pid, signal.SIGKILL)

    PID_PATH.unlink(missing_ok=True)
    return {"ok": True, "message": "Bridge stopped.", "status": build_status()}


def build_status() -> dict[str, Any]:
    pid = read_pid()
    running = bool(pid and is_pid_running(pid))
    if pid and not running:
        PID_PATH.unlink(missing_ok=True)
        pid = None
    config = read_env()
    session_started_at = find_latest_session_start(LOG_PATH)
    message_data = list_messages(MESSAGES_PATH)
    return {
        "running": running,
        "pid": pid,
        "log": tail_text(LOG_PATH, limit=12000, current_session_only=True),
        "session_started_at": session_started_at,
        "summary": summarize_config(config),
        "messages": {
            "total": message_data["total"],
            "channels": message_data["channels"],
            "items": message_data["messages"][:40],
        },
    }


def summarize_config(config: dict[str, str]) -> dict[str, Any]:
    enabled = [
        name
        for name, key in (
            ("Gmail", "GMAIL_ENABLED"),
            ("Lark", "LARK_ENABLED"),
            ("DingTalk", "DINGTALK_ENABLED"),
        )
        if _truthy(config.get(key, "false"))
    ]
    missing: list[str] = []
    errors: list[str] = []
    if not _configured(config.get("DISCORD_USER_TOKEN", "")):
        missing.append("Discord User Token")
    else:
        errors.extend(validate_discord_user_token(config.get("DISCORD_USER_TOKEN", "")))
    if not config.get("DISCORD_CHANNEL_URLS") and not config.get("DISCORD_CHANNEL_IDS"):
        missing.append("Discord Channel")
    if not enabled:
        missing.append("Forwarder")
    return {
        "ready": not missing and not errors,
        "missing": missing,
        "errors": errors,
        "enabled_forwarders": enabled,
    }


def validate_forwarder_settings(config: dict[str, str]) -> list[str]:
    errors: list[str] = []
    enabled = [
        _truthy(config.get("GMAIL_ENABLED", "false")),
        _truthy(config.get("LARK_ENABLED", "false")),
        _truthy(config.get("DINGTALK_ENABLED", "false")),
    ]
    if not any(enabled):
        errors.append("Enable Gmail, Lark, or DingTalk first.")

    if _truthy(config.get("GMAIL_ENABLED", "false")):
        if not config.get("SMTP_USERNAME"):
            errors.append("SMTP Username is required.")
        if not config.get("SMTP_PASSWORD"):
            errors.append("SMTP Password is required.")
        if not config.get("SMTP_FROM"):
            errors.append("SMTP From is required.")
        if not _csv_value(config.get("SMTP_TO", "")):
            errors.append("SMTP To is required.")

    if _truthy(config.get("LARK_ENABLED", "false")) and not _configured_webhook(config.get("LARK_WEBHOOK_URL", "")):
        errors.append("Lark Webhook URL is required.")
    if _truthy(config.get("DINGTALK_ENABLED", "false")) and not _configured_webhook(
        config.get("DINGTALK_WEBHOOK_URL", "")
    ):
        errors.append("DingTalk Webhook URL is required.")
    return errors


def build_test_alert_config(config: dict[str, str]) -> AppConfig:
    return AppConfig(
        discord_user_token="",
        gateway_proxy=None,
        channel_ids=frozenset(),
        allowed_guild_ids=frozenset(),
        alert_prefix=config.get("ALERT_PREFIX", "[Discord]"),
        log_level=config.get("LOG_LEVEL", "INFO"),
        gmail=GmailConfig(
            enabled=_truthy(config.get("GMAIL_ENABLED", "false")),
            host=config.get("SMTP_HOST", "smtp.gmail.com"),
            port=_int_value(config.get("SMTP_PORT", "587"), default=587),
            starttls=_truthy(config.get("SMTP_STARTTLS", "true")),
            username=config.get("SMTP_USERNAME", ""),
            password=config.get("SMTP_PASSWORD", ""),
            sender=config.get("SMTP_FROM", ""),
            recipients=tuple(_csv_value(config.get("SMTP_TO", ""))),
        ),
        lark=WebhookConfig(
            enabled=_truthy(config.get("LARK_ENABLED", "false")),
            url=config.get("LARK_WEBHOOK_URL", ""),
            secret=config.get("LARK_SECRET", ""),
        ),
        dingtalk=WebhookConfig(
            enabled=_truthy(config.get("DINGTALK_ENABLED", "false")),
            url=config.get("DINGTALK_WEBHOOK_URL", ""),
            secret=config.get("DINGTALK_SECRET", ""),
        ),
    )


def read_pid() -> int | None:
    if not PID_PATH.exists():
        return None
    try:
        return int(PID_PATH.read_text(encoding="utf-8").strip())
    except ValueError:
        PID_PATH.unlink(missing_ok=True)
        return None


def is_pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    state = process_state(pid)
    if state and "Z" in state:
        return False
    return True


def process_state(pid: int) -> str:
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "stat="],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return ""
    return result.stdout.strip()


def find_latest_session_start(path: Path) -> str | None:
    if not path.exists():
        return None
    latest: str | None = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if SESSION_BANNER_PREFIX in line:
            latest = line.strip()
    return latest


def tail_text(path: Path, limit: int = 8000, current_session_only: bool = False) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    if current_session_only:
        marker_index = text.rfind(SESSION_BANNER_PREFIX)
        if marker_index >= 0:
            text = text[marker_index:]
    if len(text) <= limit:
        return text
    return text[-limit:]


def _quote_env(value: str) -> str:
    if value == "":
        return ""
    if any(char.isspace() for char in value) or any(char in value for char in "\"'#"):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _unquote_env(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value.replace('\\"', '"').replace("\\\\", "\\")


def _bool_text(value: str, default: bool = False) -> str:
    if value.strip() == "":
        return "true" if default else "false"
    return "true" if _truthy(value) else "false"


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _csv_value(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _int_value(value: str, default: int) -> int:
    try:
        return int(value)
    except ValueError:
        return default


def _configured(value: str) -> bool:
    normalized = value.strip().lower()
    return bool(normalized) and not normalized.startswith(("replace_", "your_"))


def _configured_webhook(value: str) -> bool:
    normalized = value.strip().lower()
    return bool(normalized) and "replace_me" not in normalized


def normalize_discord_user_token(value: str) -> str:
    value = value.strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return value


def validate_discord_user_token(value: str) -> list[str]:
    token = value.strip()
    lowered = token.lower()
    errors: list[str] = []
    if re.search(r"\s|;", token) or lowered.startswith(("__dcf", "__sdcf", "locale=", "cf_clearance=")):
        errors.append("Discord User Token looks like a browser cookie/header, not a user token.")
    if lowered.startswith("bot "):
        errors.append("Bot tokens are not supported here. Use your personal Discord user token.")
    if lowered.startswith("oauth2 "):
        errors.append("Discord OAuth access tokens are not supported. Use your user token.")
    return errors


def render_page() -> str:
    config = read_env()
    return render_dashboard_page(
        config,
        field=field,
        select=select,
        toggle=toggle,
        config_fields=CONFIG_FIELDS,
        secret_fields=SECRET_FIELDS,
    )

def field(
    name: str,
    label: str,
    config: dict[str, str],
    *,
    secret: bool = False,
    full: bool = False,
) -> str:
    input_type = "password" if secret else "text"
    klass = "field full" if full else "field"
    value = html.escape(config.get(name, ""), quote=True)
    return (
        f'<div class="{klass}">'
        f'<label for="{name}">{html.escape(label)}</label>'
        f'<input id="{name}" name="{name}" type="{input_type}" value="{value}" autocomplete="off">'
        "</div>"
    )


def select(name: str, label: str, config: dict[str, str], options: list[str]) -> str:
    selected = config.get(name, "")
    option_html = "".join(
        f'<option value="{html.escape(option)}"{" selected" if option == selected else ""}>{html.escape(option)}</option>'
        for option in options
    )
    return (
        '<div class="field">'
        f'<label for="{name}">{html.escape(label)}</label>'
        f'<select id="{name}" name="{name}">{option_html}</select>'
        "</div>"
    )


def toggle(name: str, label: str, config: dict[str, str]) -> str:
    checked = " checked" if _truthy(config.get(name, "false")) else ""
    return (
        '<div class="field">'
        f'<label class="switch"><input id="{name}" name="{name}" type="checkbox"{checked}>'
        f"<span>{html.escape(label)}</span></label>"
        "</div>"
    )
