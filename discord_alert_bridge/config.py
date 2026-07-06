from __future__ import annotations

import os
import re
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - lets lightweight tests run before install
    def load_dotenv(*_args: object, **_kwargs: object) -> bool:
        return False


_DISCORD_URL_RE = re.compile(
    r"(?:https?://)?(?:canary\.|ptb\.)?discord(?:app)?\.com/channels/"
    r"(?P<guild>\d+|@me)/(?P<channel>\d+)(?:/(?P<message>\d+))?"
)
_DISCORD_PAIR_RE = re.compile(r"^(?P<guild>\d{15,25})/(?P<channel>\d{15,25})$")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class ChannelSelection:
    channel_ids: frozenset[int]
    guild_ids: frozenset[int]


@dataclass(frozen=True)
class GmailConfig:
    enabled: bool
    host: str
    port: int
    starttls: bool
    username: str
    password: str
    sender: str
    recipients: tuple[str, ...]


@dataclass(frozen=True)
class WebhookConfig:
    enabled: bool
    url: str
    secret: str


@dataclass(frozen=True)
class AppConfig:
    discord_user_token: str
    gateway_proxy: str | None
    channel_ids: frozenset[int]
    allowed_guild_ids: frozenset[int]
    alert_prefix: str
    log_level: str
    gmail: GmailConfig
    lark: WebhookConfig
    dingtalk: WebhookConfig


def load_config() -> AppConfig:
    load_dotenv()

    channel_selection = parse_channel_references(
        refs=_csv("DISCORD_CHANNEL_URLS"),
        explicit_channel_ids=_csv("DISCORD_CHANNEL_IDS"),
    )
    explicit_guild_ids = _int_set(_csv("DISCORD_ALLOWED_GUILD_IDS"), "DISCORD_ALLOWED_GUILD_IDS")
    allowed_guild_ids = explicit_guild_ids or channel_selection.guild_ids

    config = AppConfig(
        discord_user_token=_discord_user_token(),
        gateway_proxy=_gateway_proxy(),
        channel_ids=channel_selection.channel_ids,
        allowed_guild_ids=allowed_guild_ids,
        alert_prefix=os.getenv("ALERT_PREFIX", "[Discord]").strip() or "[Discord]",
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        gmail=GmailConfig(
            enabled=_bool("GMAIL_ENABLED"),
            host=os.getenv("SMTP_HOST", "smtp.gmail.com").strip(),
            port=_int_env("SMTP_PORT", 587),
            starttls=_bool("SMTP_STARTTLS", default=True),
            username=os.getenv("SMTP_USERNAME", "").strip(),
            password=os.getenv("SMTP_PASSWORD", "").strip(),
            sender=os.getenv("SMTP_FROM", "").strip(),
            recipients=tuple(_csv("SMTP_TO")),
        ),
        lark=WebhookConfig(
            enabled=_bool("LARK_ENABLED"),
            url=os.getenv("LARK_WEBHOOK_URL", "").strip(),
            secret=os.getenv("LARK_SECRET", "").strip(),
        ),
        dingtalk=WebhookConfig(
            enabled=_bool("DINGTALK_ENABLED"),
            url=os.getenv("DINGTALK_WEBHOOK_URL", "").strip(),
            secret=os.getenv("DINGTALK_SECRET", "").strip(),
        ),
    )
    validate_config(config)
    return config


def validate_config(config: AppConfig) -> None:
    errors: list[str] = []

    if not config.discord_user_token:
        errors.append("DISCORD_USER_TOKEN is required.")
    if not config.channel_ids:
        errors.append("Set DISCORD_CHANNEL_URLS or DISCORD_CHANNEL_IDS.")

    enabled_forwarders = [
        config.gmail.enabled,
        config.lark.enabled,
        config.dingtalk.enabled,
    ]
    if not any(enabled_forwarders):
        errors.append("Enable at least one forwarder: GMAIL_ENABLED, LARK_ENABLED, or DINGTALK_ENABLED.")

    if config.gmail.enabled:
        if not config.gmail.username:
            errors.append("SMTP_USERNAME is required when GMAIL_ENABLED=true.")
        if not config.gmail.password:
            errors.append("SMTP_PASSWORD is required when GMAIL_ENABLED=true.")
        if not config.gmail.sender:
            errors.append("SMTP_FROM is required when GMAIL_ENABLED=true.")
        if not config.gmail.recipients:
            errors.append("SMTP_TO is required when GMAIL_ENABLED=true.")

    if config.lark.enabled and not config.lark.url:
        errors.append("LARK_WEBHOOK_URL is required when LARK_ENABLED=true.")
    if config.dingtalk.enabled and not config.dingtalk.url:
        errors.append("DINGTALK_WEBHOOK_URL is required when DINGTALK_ENABLED=true.")

    if errors:
        raise ConfigError("\n".join(errors))


def parse_channel_references(
    refs: list[str],
    explicit_channel_ids: list[str] | None = None,
) -> ChannelSelection:
    channel_ids: set[int] = set()
    guild_ids: set[int] = set()

    for raw_ref in refs:
        ref = raw_ref.strip()
        if not ref:
            continue

        url_match = _DISCORD_URL_RE.search(ref)
        pair_match = _DISCORD_PAIR_RE.match(ref)

        if url_match:
            guild = url_match.group("guild")
            if guild != "@me":
                guild_ids.add(int(guild))
            channel_ids.add(int(url_match.group("channel")))
            continue

        if pair_match:
            guild_ids.add(int(pair_match.group("guild")))
            channel_ids.add(int(pair_match.group("channel")))
            continue

        if ref.isdigit():
            channel_ids.add(int(ref))
            continue

        raise ConfigError(f"Invalid Discord channel reference: {raw_ref}")

    if explicit_channel_ids:
        channel_ids.update(_int_set(explicit_channel_ids, "DISCORD_CHANNEL_IDS"))

    return ChannelSelection(frozenset(channel_ids), frozenset(guild_ids))


def _csv(name: str) -> list[str]:
    value = os.getenv(name, "")
    return [part.strip() for part in value.split(",") if part.strip()]


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer.") from exc


def _gateway_proxy() -> str | None:
    value = os.getenv("DISCORD_GATEWAY_PROXY", "").strip()
    if not value:
        return None
    lowered = value.lower()
    if lowered in {"none", "direct", "false", "off", "0"}:
        return "none"
    return value


def _discord_user_token() -> str:
    token = os.getenv("DISCORD_USER_TOKEN", "").strip()
    if token:
        return token
    legacy = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    if legacy.lower().startswith("bot "):
        legacy = legacy[4:].strip()
    return legacy


def _int_set(values: list[str], name: str) -> frozenset[int]:
    output: set[int] = set()
    for value in values:
        if not value.isdigit():
            raise ConfigError(f"{name} must contain numeric IDs only: {value}")
        output.add(int(value))
    return frozenset(output)
