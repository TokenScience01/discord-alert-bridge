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
from urllib.parse import urlparse

from .config import AppConfig, ConfigError, GmailConfig, WebhookConfig, parse_channel_references
from .forwarders import build_forwarder
from .models import Alert


ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
ENV_EXAMPLE_PATH = ROOT / ".env.example"
PID_PATH = ROOT / ".bridge.pid"
LOG_PATH = ROOT / "bridge.log"
SESSION_BANNER_PREFIX = "===== Bridge session started"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

CONFIG_FIELDS = [
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
    "DISCORD_USER_TOKEN",
    "SMTP_PASSWORD",
    "LARK_SECRET",
    "DINGTALK_SECRET",
}


def run() -> None:
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
    server_version = "DiscordAlertBridgeAdmin/0.1"

    def do_HEAD(self) -> None:
        route = urlparse(self.path).path
        if route == "/":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_GET(self) -> None:
        route = urlparse(self.path).path
        if route == "/":
            self._send_html(render_page())
            return
        if route == "/api/config":
            self._send_json({"config": read_env()})
            return
        if route == "/api/status":
            self._send_json(build_status())
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        route = urlparse(self.path).path
        if route == "/api/config":
            data = self._read_json()
            write_env({key: str(data.get(key, "")) for key in CONFIG_FIELDS})
            self._send_json({"ok": True, "status": build_status()})
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

    def _send_json(self, body: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def read_env() -> dict[str, str]:
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
    normalized = dict(FIELD_DEFAULTS)
    for key in CONFIG_FIELDS:
        normalized[key] = values.get(key, normalized[key]).strip()
    normalized["DISCORD_USER_TOKEN"] = normalize_discord_user_token(normalized["DISCORD_USER_TOKEN"])
    fill_channel_ids_from_refs(normalized)

    lines = [
        "# Managed by discord-alert-bridge admin page.",
        "# Uses a Discord personal user token for local testing only.",
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
            "message": "Bridge exited right after start. Check the log on the right.",
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
    return {
        "running": running,
        "pid": pid,
        "log": tail_text(LOG_PATH, limit=12000, current_session_only=True),
        "session_started_at": session_started_at,
        "summary": summarize_config(config),
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
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Discord Alert Bridge</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0b0d12;
      --bg-accent: radial-gradient(ellipse 80% 60% at 10% -10%, rgba(88, 101, 242, 0.28), transparent 55%),
        radial-gradient(ellipse 60% 50% at 100% 0%, rgba(35, 165, 89, 0.12), transparent 50%),
        #0b0d12;
      --panel: rgba(22, 25, 34, 0.92);
      --panel-soft: rgba(255, 255, 255, 0.03);
      --text: #f2f3f5;
      --muted: #949ba4;
      --line: rgba(255, 255, 255, 0.08);
      --accent: #5865f2;
      --accent-hover: #4752c4;
      --ok: #23a559;
      --danger: #f23f43;
      --warn: #f0b232;
      --shadow: 0 24px 60px rgba(0, 0, 0, 0.35);
      --radius: 14px;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font: 14px/1.5 "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg-accent);
      color: var(--text);
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 20;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 20px;
      padding: 16px 28px;
      border-bottom: 1px solid var(--line);
      background: rgba(11, 13, 18, 0.82);
      backdrop-filter: blur(16px);
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 14px;
      min-width: 0;
    }}
    .brand-mark {{
      width: 42px;
      height: 42px;
      border-radius: 12px;
      background: linear-gradient(135deg, #5865f2 0%, #7289da 100%);
      box-shadow: 0 10px 24px rgba(88, 101, 242, 0.35);
      display: grid;
      place-items: center;
      font-weight: 800;
      font-size: 18px;
      color: #fff;
      flex-shrink: 0;
    }}
    .brand h1 {{
      margin: 0;
      font-size: 18px;
      font-weight: 700;
      letter-spacing: -0.02em;
    }}
    .brand p {{
      margin: 2px 0 0;
      color: var(--muted);
      font-size: 12px;
    }}
    main {{
      width: min(1240px, calc(100vw - 40px));
      margin: 24px auto 48px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) 380px;
      gap: 20px;
    }}
    section, aside {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
    }}
    section {{
      display: grid;
      grid-template-columns: 180px minmax(0, 1fr);
      overflow: hidden;
      min-height: 620px;
    }}
    aside {{
      padding: 20px;
      align-self: start;
      position: sticky;
      top: 92px;
    }}
    .tabs {{
      display: flex;
      flex-direction: column;
      gap: 6px;
      padding: 18px 12px;
      border-right: 1px solid var(--line);
      background: rgba(0, 0, 0, 0.18);
    }}
    .tab {{
      display: flex;
      align-items: center;
      gap: 10px;
      width: 100%;
      min-height: 42px;
      padding: 10px 12px;
      border: 1px solid transparent;
      border-radius: 10px;
      background: transparent;
      color: var(--muted);
      text-align: left;
      transition: 0.18s ease;
    }}
    .tab:hover {{
      background: var(--panel-soft);
      color: var(--text);
    }}
    .tab.active {{
      background: rgba(88, 101, 242, 0.16);
      border-color: rgba(88, 101, 242, 0.28);
      color: #fff;
      box-shadow: inset 0 0 0 1px rgba(88, 101, 242, 0.08);
    }}
    .tab-icon {{
      width: 22px;
      text-align: center;
      flex-shrink: 0;
    }}
    .config-body {{
      padding: 24px 26px 28px;
    }}
    .panel-head {{
      margin-bottom: 20px;
    }}
    .panel-head h2 {{
      margin: 0 0 6px;
      font-size: 20px;
      font-weight: 700;
      letter-spacing: -0.02em;
    }}
    .panel-head p {{
      margin: 0;
      color: var(--muted);
      font-size: 13px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
    }}
    .field {{
      display: flex;
      flex-direction: column;
      gap: 8px;
      min-width: 0;
    }}
    .field.full {{ grid-column: 1 / -1; }}
    label {{
      font-weight: 600;
      font-size: 12px;
      color: #b5bac1;
      letter-spacing: 0.02em;
    }}
    input, select {{
      width: 100%;
      min-height: 42px;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px 12px;
      background: rgba(0, 0, 0, 0.22);
      color: var(--text);
      font: inherit;
      transition: border-color 0.18s ease, box-shadow 0.18s ease;
    }}
    input:focus, select:focus {{
      outline: none;
      border-color: rgba(88, 101, 242, 0.65);
      box-shadow: 0 0 0 3px rgba(88, 101, 242, 0.18);
    }}
    .switch {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      min-height: 42px;
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: rgba(0, 0, 0, 0.18);
      cursor: pointer;
    }}
    .switch input {{
      width: 18px;
      min-height: 18px;
      accent-color: var(--accent);
    }}
    .toolbar {{
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}
    button {{
      min-height: 40px;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 9px 14px;
      font: inherit;
      font-weight: 600;
      cursor: pointer;
      background: rgba(255, 255, 255, 0.04);
      color: var(--text);
      transition: 0.18s ease;
    }}
    button:hover:not(:disabled) {{
      transform: translateY(-1px);
      background: rgba(255, 255, 255, 0.07);
    }}
    button.primary {{
      background: linear-gradient(180deg, #5865f2 0%, #4752c4 100%);
      border-color: rgba(88, 101, 242, 0.5);
      color: #fff;
      box-shadow: 0 10px 24px rgba(88, 101, 242, 0.28);
    }}
    button.primary:hover:not(:disabled) {{
      background: linear-gradient(180deg, #6873ff 0%, #5865f2 100%);
    }}
    button.danger {{
      background: rgba(242, 63, 67, 0.12);
      border-color: rgba(242, 63, 67, 0.35);
      color: #ffb4b6;
    }}
    button:disabled {{ opacity: 0.5; cursor: wait; transform: none; }}
    .status {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--line);
      font-weight: 600;
      white-space: nowrap;
    }}
    .dot {{
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: var(--muted);
      box-shadow: 0 0 10px transparent;
    }}
    .status.running .dot {{
      background: var(--ok);
      box-shadow: 0 0 10px rgba(35, 165, 89, 0.8);
    }}
    .status.stopped .dot {{
      background: var(--danger);
      box-shadow: 0 0 10px rgba(242, 63, 67, 0.55);
    }}
    .tab-panel {{ display: none; }}
    .tab-panel.active {{ display: block; }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 16px;
    }}
    .stat-card {{
      padding: 12px 14px;
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid var(--line);
    }}
    .stat-card span {{
      display: block;
      color: var(--muted);
      font-size: 11px;
      margin-bottom: 6px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}
    .stat-card strong {{
      display: block;
      font-size: 14px;
      line-height: 1.35;
      word-break: break-word;
    }}
    .stat-card.wide {{ grid-column: 1 / -1; }}
    .log-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 10px;
    }}
    .log-head h2 {{
      margin: 0;
      font-size: 16px;
      font-weight: 700;
    }}
    .log-box {{
      min-height: 320px;
      max-height: 56vh;
      overflow: auto;
      margin: 0;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: #090b10;
      font: 12px/1.6 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    .log-line {{ display: block; }}
    .log-error {{ color: #ff8e90; }}
    .log-warn {{ color: #ffd56a; }}
    .log-info {{ color: #8fd3ff; }}
    .log-ok {{ color: #7ddea2; }}
    .log-banner {{ color: #c9cdff; font-weight: 700; }}
    .log-muted {{ color: #6d7685; }}
    .toast {{
      min-height: 22px;
      margin-bottom: 12px;
      padding: 10px 12px;
      border-radius: 10px;
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid var(--line);
      color: var(--muted);
    }}
    .toast.error {{
      color: #ffb4b6;
      border-color: rgba(242, 63, 67, 0.35);
      background: rgba(242, 63, 67, 0.08);
    }}
    .toast.ok {{
      color: #9ae6b0;
      border-color: rgba(35, 165, 89, 0.35);
      background: rgba(35, 165, 89, 0.08);
    }}
    @media (max-width: 980px) {{
      header {{ align-items: flex-start; flex-direction: column; }}
      main {{ grid-template-columns: 1fr; }}
      section {{ grid-template-columns: 1fr; }}
      .tabs {{
        flex-direction: row;
        overflow-x: auto;
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }}
      aside {{ position: static; }}
      .grid {{ grid-template-columns: 1fr; }}
      .summary {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="brand-mark">D</div>
      <div>
        <h1>Discord Alert Bridge</h1>
        <p>监听 Discord 频道，转发到 Lark / Gmail / 钉钉</p>
      </div>
    </div>
    <div class="toolbar">
      <span id="statusPill" class="status stopped"><span class="dot"></span><span id="statusText">已停止</span></span>
      <button class="primary" id="saveBtn">保存配置</button>
      <button id="startBtn">启动监听</button>
      <button id="testBtn">测试通知</button>
      <button class="danger" id="stopBtn">停止</button>
      <button id="clearLogBtn">清空日志</button>
    </div>
  </header>

  <main>
    <section>
      <div class="tabs" role="tablist">
        <button class="tab active" data-tab="discord"><span class="tab-icon">💬</span>Discord</button>
        <button class="tab" data-tab="gmail"><span class="tab-icon">✉️</span>Gmail</button>
        <button class="tab" data-tab="lark"><span class="tab-icon">🐦</span>Lark</button>
        <button class="tab" data-tab="dingtalk"><span class="tab-icon">📣</span>钉钉</button>
      </div>

      <div class="config-body">
      <form id="configForm">
        <div class="tab-panel active" id="tab-discord">
          <div class="panel-head">
            <h2>Discord 监听</h2>
            <p>使用你的用户 Token 监听指定频道的新消息。</p>
          </div>
          <div class="grid">
            {field("DISCORD_USER_TOKEN", "User Token", config, secret=True, full=True)}
            {field("DISCORD_CHANNEL_URLS", "频道链接", config, full=True)}
            {field("DISCORD_CHANNEL_IDS", "频道 ID", config)}
            {field("DISCORD_ALLOWED_GUILD_IDS", "服务器 ID", config)}
            {field("ALERT_PREFIX", "通知前缀", config)}
            {select("LOG_LEVEL", "日志级别", config, ["DEBUG", "INFO", "WARNING", "ERROR"])}
          </div>
        </div>

        <div class="tab-panel" id="tab-gmail">
          <div class="panel-head">
            <h2>Gmail 转发</h2>
            <p>通过 SMTP 把消息发到邮箱。</p>
          </div>
          <div class="grid">
            {toggle("GMAIL_ENABLED", "启用 Gmail", config)}
            {toggle("SMTP_STARTTLS", "启用 STARTTLS", config)}
            {field("SMTP_HOST", "SMTP Host", config)}
            {field("SMTP_PORT", "SMTP Port", config)}
            {field("SMTP_USERNAME", "SMTP Username", config)}
            {field("SMTP_PASSWORD", "SMTP Password", config, secret=True)}
            {field("SMTP_FROM", "发件人", config)}
            {field("SMTP_TO", "收件人", config)}
          </div>
        </div>

        <div class="tab-panel" id="tab-lark">
          <div class="panel-head">
            <h2>Lark / 飞书</h2>
            <p>使用自定义机器人 Webhook 发送卡片通知。</p>
          </div>
          <div class="grid">
            {toggle("LARK_ENABLED", "启用 Lark", config)}
            {field("LARK_WEBHOOK_URL", "Webhook URL", config, full=True)}
            {field("LARK_SECRET", "签名 Secret", config, secret=True, full=True)}
          </div>
        </div>

        <div class="tab-panel" id="tab-dingtalk">
          <div class="panel-head">
            <h2>钉钉</h2>
            <p>使用自定义机器人 Webhook 推送文本消息。</p>
          </div>
          <div class="grid">
            {toggle("DINGTALK_ENABLED", "启用钉钉", config)}
            {field("DINGTALK_WEBHOOK_URL", "Webhook URL", config, full=True)}
            {field("DINGTALK_SECRET", "签名 Secret", config, secret=True, full=True)}
          </div>
        </div>
      </form>
      </div>
    </section>

    <aside>
      <div class="summary">
        <div class="stat-card"><span>进程 PID</span><strong id="pidValue">-</strong></div>
        <div class="stat-card"><span>转发出口</span><strong id="forwardersValue">-</strong></div>
        <div class="stat-card"><span>配置状态</span><strong id="readyValue">-</strong></div>
        <div class="stat-card wide"><span>本次会话</span><strong id="sessionValue">-</strong></div>
      </div>
      <p id="toast" class="toast">准备就绪</p>
      <div class="log-head"><h2>运行日志</h2></div>
      <div id="logBox" class="log-box"></div>
    </aside>
  </main>

  <script>
    const fields = {json.dumps(CONFIG_FIELDS)};
    const secretFields = new Set({json.dumps(sorted(SECRET_FIELDS))});
    const form = document.querySelector("#configForm");
    const toast = document.querySelector("#toast");
    const statusPill = document.querySelector("#statusPill");
    const statusText = document.querySelector("#statusText");
    const logBox = document.querySelector("#logBox");
    const saveBtn = document.querySelector("#saveBtn");
    const startBtn = document.querySelector("#startBtn");
    const testBtn = document.querySelector("#testBtn");
    const stopBtn = document.querySelector("#stopBtn");
    const clearLogBtn = document.querySelector("#clearLogBtn");

    document.querySelectorAll(".tab").forEach((tab) => {{
      tab.addEventListener("click", () => {{
        document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
        document.querySelectorAll(".tab-panel").forEach((item) => item.classList.remove("active"));
        tab.classList.add("active");
        document.querySelector("#tab-" + tab.dataset.tab).classList.add("active");
      }});
    }});

    async function request(path, options = {{}}) {{
      const response = await fetch(path, {{
        headers: {{ "Content-Type": "application/json" }},
        ...options,
      }});
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    }}

    function collectConfig() {{
      const values = {{}};
      fields.forEach((name) => {{
        const input = form.elements[name];
        if (!input) return;
        values[name] = input.type === "checkbox" ? String(input.checked) : input.value;
      }});
      return values;
    }}

    function applyConfig(config) {{
      fields.forEach((name) => {{
        const input = form.elements[name];
        if (!input) return;
        if (input.type === "checkbox") {{
          input.checked = ["1", "true", "yes", "on"].includes(String(config[name] || "").toLowerCase());
        }} else {{
          input.value = config[name] || "";
        }}
      }});
      autofillDiscordIds();
    }}

    function parseDiscordChannelRefs(value) {{
      const channelIds = new Set();
      const guildIds = new Set();
      const refs = String(value || "").split(",").map((item) => item.trim()).filter(Boolean);
      refs.forEach((ref) => {{
        const urlMatch = ref.match(/(?:https?:\\/\\/)?(?:canary\\.|ptb\\.)?discord(?:app)?\\.com\\/channels\\/(\\d+|@me)\\/(\\d+)(?:\\/\\d+)?/i);
        const pairMatch = ref.match(/^(\\d{{15,25}})\\/(\\d{{15,25}})$/);
        if (urlMatch) {{
          if (urlMatch[1] !== "@me") guildIds.add(urlMatch[1]);
          channelIds.add(urlMatch[2]);
        }} else if (pairMatch) {{
          guildIds.add(pairMatch[1]);
          channelIds.add(pairMatch[2]);
        }}
      }});
      return {{
        channelIds: Array.from(channelIds).sort(),
        guildIds: Array.from(guildIds).sort(),
      }};
    }}

    function autofillDiscordIds() {{
      const channelUrlInput = form.elements.DISCORD_CHANNEL_URLS;
      const channelIdInput = form.elements.DISCORD_CHANNEL_IDS;
      const guildIdInput = form.elements.DISCORD_ALLOWED_GUILD_IDS;
      if (!channelUrlInput || !channelIdInput || !guildIdInput) return;
      const parsed = parseDiscordChannelRefs(channelUrlInput.value);
      if (parsed.channelIds.length) channelIdInput.value = parsed.channelIds.join(",");
      if (parsed.guildIds.length) guildIdInput.value = parsed.guildIds.join(",");
    }}

    function escapeHtml(value) {{
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
    }}

    function formatLogLine(line) {{
      const safe = escapeHtml(line);
      if (!line.trim()) return `<span class="log-line log-muted">${{safe}}</span>`;
      if (line.includes("Bridge session started")) return `<span class="log-line log-banner">${{safe}}</span>`;
      if (/\\bERROR\\b/.test(line)) return `<span class="log-line log-error">${{safe}}</span>`;
      if (/\\bWARNING\\b/.test(line)) return `<span class="log-line log-warn">${{safe}}</span>`;
      if (/Forwarded Discord message/.test(line)) return `<span class="log-line log-ok">${{safe}}</span>`;
      if (/\\bINFO\\b/.test(line)) return `<span class="log-line log-info">${{safe}}</span>`;
      return `<span class="log-line">${{safe}}</span>`;
    }}

    function renderLog(text) {{
      const content = text && text.trim() ? text : "（暂无日志）";
      logBox.innerHTML = content.split("\\n").map(formatLogLine).join("");
      logBox.scrollTop = logBox.scrollHeight;
    }}

    function renderStatus(status) {{
      const running = Boolean(status.running);
      statusPill.classList.toggle("running", running);
      statusPill.classList.toggle("stopped", !running);
      statusText.textContent = running ? "运行中" : "已停止";
      document.querySelector("#pidValue").textContent = status.pid || "-";
      document.querySelector("#forwardersValue").textContent =
        status.summary.enabled_forwarders.length ? status.summary.enabled_forwarders.join(", ") : "-";
      document.querySelector("#readyValue").textContent =
        status.summary.ready ? "已就绪" : status.summary.missing.concat(status.summary.errors || []).join(", ");
      document.querySelector("#sessionValue").textContent = status.session_started_at || "未启动";
      renderLog(status.log || "");
    }}

    function setToast(message, type = "") {{
      toast.textContent = message;
      toast.className = "toast " + type;
    }}

    async function saveConfig() {{
      saveBtn.disabled = true;
      try {{
        const data = await request("/api/config", {{
          method: "POST",
          body: JSON.stringify(collectConfig()),
        }});
        renderStatus(data.status);
        setToast("配置已保存", "ok");
      }} catch (error) {{
        setToast("保存失败: " + error.message, "error");
      }} finally {{
        saveBtn.disabled = false;
      }}
    }}

    async function startBridge() {{
      startBtn.disabled = true;
      try {{
        await saveConfig();
        const data = await request("/api/start", {{ method: "POST", body: "{{}}" }});
        renderStatus(data.status);
        setToast(data.message, data.ok ? "ok" : "error");
      }} catch (error) {{
        setToast("启动失败: " + error.message, "error");
      }} finally {{
        startBtn.disabled = false;
      }}
    }}

    async function sendTestAlert() {{
      testBtn.disabled = true;
      try {{
        await saveConfig();
        const data = await request("/api/test-alert", {{ method: "POST", body: "{{}}" }});
        renderStatus(data.status);
        setToast(data.message, data.ok ? "ok" : "error");
      }} catch (error) {{
        setToast("测试失败: " + error.message, "error");
      }} finally {{
        testBtn.disabled = false;
      }}
    }}

    async function stopBridge() {{
      stopBtn.disabled = true;
      try {{
        const data = await request("/api/stop", {{ method: "POST", body: "{{}}" }});
        renderStatus(data.status);
        setToast(data.message, "ok");
      }} catch (error) {{
        setToast("停止失败: " + error.message, "error");
      }} finally {{
        stopBtn.disabled = false;
      }}
    }}

    async function clearLog() {{
      clearLogBtn.disabled = true;
      try {{
        const data = await request("/api/clear-log", {{ method: "POST", body: "{{}}" }});
        renderStatus(data.status);
        setToast(data.message, data.ok ? "ok" : "error");
      }} catch (error) {{
        setToast("清空日志失败: " + error.message, "error");
      }} finally {{
        clearLogBtn.disabled = false;
      }}
    }}

    async function refresh() {{
      try {{
        const data = await request("/api/status");
        renderStatus(data);
      }} catch (error) {{
        setToast("状态刷新失败: " + error.message, "error");
      }}
    }}

    saveBtn.addEventListener("click", saveConfig);
    startBtn.addEventListener("click", startBridge);
    testBtn.addEventListener("click", sendTestAlert);
    stopBtn.addEventListener("click", stopBridge);
    clearLogBtn.addEventListener("click", clearLog);
    form.elements.DISCORD_CHANNEL_URLS.addEventListener("input", autofillDiscordIds);
    form.elements.DISCORD_CHANNEL_URLS.addEventListener("paste", () => setTimeout(autofillDiscordIds, 0));
    form.elements.DISCORD_CHANNEL_URLS.addEventListener("change", autofillDiscordIds);

    request("/api/config").then((data) => applyConfig(data.config)).then(refresh);
    setInterval(refresh, 2500);
  </script>
</body>
</html>"""


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
