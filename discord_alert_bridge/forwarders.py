from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import logging
import smtplib
import time
from email.message import EmailMessage
from urllib.parse import urlencode

import httpx

from .config import AppConfig, GmailConfig, WebhookConfig
from .models import Alert

logger = logging.getLogger(__name__)


class ForwarderError(RuntimeError):
    pass


class CompositeForwarder:
    def __init__(self, forwarders: list[object]) -> None:
        self._forwarders = forwarders

    async def send(self, alert: Alert) -> None:
        results = await asyncio.gather(
            *(forwarder.send(alert) for forwarder in self._forwarders),
            return_exceptions=True,
        )
        failures = [result for result in results if isinstance(result, Exception)]
        if failures:
            for failure in failures:
                logger.error(
                    "Forwarder failed: %s",
                    failure,
                    exc_info=(type(failure), failure, failure.__traceback__),
                )
            raise ForwarderError(f"{len(failures)} forwarder(s) failed")


class GmailForwarder:
    def __init__(self, config: GmailConfig) -> None:
        self._config = config

    async def send(self, alert: Alert) -> None:
        await asyncio.to_thread(self._send_sync, alert)

    def _send_sync(self, alert: Alert) -> None:
        message = EmailMessage()
        message["Subject"] = alert.subject
        message["From"] = self._config.sender
        message["To"] = ", ".join(self._config.recipients)
        message.set_content(alert.body)

        with smtplib.SMTP(self._config.host, self._config.port, timeout=20) as smtp:
            if self._config.starttls:
                smtp.starttls()
            smtp.login(self._config.username, self._config.password)
            smtp.send_message(message)


class LarkForwarder:
    def __init__(self, config: WebhookConfig) -> None:
        self._config = config

    async def send(self, alert: Alert) -> None:
        payload: dict[str, object] = {
            "msg_type": "interactive",
            "card": build_lark_card(alert),
        }
        if self._config.secret:
            timestamp = str(int(time.time()))
            payload["timestamp"] = timestamp
            payload["sign"] = build_lark_sign(timestamp, self._config.secret)

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(self._config.url, json=payload)
            response.raise_for_status()
            data = response.json()
            if data.get("code", 0) not in {0, "0"}:
                raise ForwarderError(f"Lark webhook returned: {data}")


class DingTalkForwarder:
    def __init__(self, config: WebhookConfig) -> None:
        self._config = config

    async def send(self, alert: Alert) -> None:
        url = self._signed_url()
        payload = {
            "msgtype": "text",
            "text": {"content": alert.body},
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            if data.get("errcode", 0) not in {0, "0"}:
                raise ForwarderError(f"DingTalk webhook returned: {data}")

    def _signed_url(self) -> str:
        if not self._config.secret:
            return self._config.url
        timestamp = str(round(time.time() * 1000))
        sign = build_dingtalk_sign(timestamp, self._config.secret)
        separator = "&" if "?" in self._config.url else "?"
        return f"{self._config.url}{separator}{urlencode({'timestamp': timestamp, 'sign': sign})}"


def build_forwarder(config: AppConfig) -> CompositeForwarder:
    forwarders: list[object] = []
    if config.gmail.enabled:
        forwarders.append(GmailForwarder(config.gmail))
    if config.lark.enabled:
        forwarders.append(LarkForwarder(config.lark))
    if config.dingtalk.enabled:
        forwarders.append(DingTalkForwarder(config.dingtalk))
    return CompositeForwarder(forwarders)


def build_lark_card(alert: Alert) -> dict[str, object]:
    title = alert.subject or "Discord 新消息"
    elements: list[dict[str, object]] = []

    fields: list[dict[str, object]] = []
    if alert.channel:
        fields.append(
            {
                "is_short": True,
                "text": {
                    "tag": "lark_md",
                    "content": f"**频道**\n{alert.channel}",
                },
            }
        )
    if alert.author:
        fields.append(
            {
                "is_short": True,
                "text": {
                    "tag": "lark_md",
                    "content": f"**发送人**\n{alert.author}",
                },
            }
        )
    if fields:
        elements.append({"tag": "div", "fields": fields})

    message_text = alert.message or alert.body
    elements.extend(
        [
            {"tag": "hr"},
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": message_text,
                },
            },
        ]
    )

    if alert.extras:
        elements.append({"tag": "hr"})
        elements.append(
            {
                "tag": "note",
                "elements": [
                    {
                        "tag": "plain_text",
                        "content": "\n".join(alert.extras),
                    }
                ],
            }
        )

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "template": "indigo",
        },
        "elements": elements,
    }


def build_lark_sign(timestamp: str, secret: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def build_dingtalk_sign(timestamp: str, secret: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")
