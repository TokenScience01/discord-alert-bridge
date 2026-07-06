from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import random
from dataclasses import replace
from typing import Any

import httpx
import websockets
from websockets.asyncio.client import ClientConnection

from .config import AppConfig
from .formatting import format_discord_message
from .forwarders import CompositeForwarder
from .message_store import record_message
from .models import DiscordMessage
from .paths import MESSAGES_PATH

logger = logging.getLogger(__name__)

GATEWAY_URL = "wss://gateway.discord.gg/?v=10&encoding=json"


class UserGatewayClient:
    def __init__(self, config: AppConfig, forwarder: CompositeForwarder) -> None:
        self._config = config
        self._forwarder = forwarder
        self._session_id: str | None = None
        self._sequence: int | None = None
        self._heartbeat_interval: float | None = None
        self._user_id: int | None = None
        self._guild_names: dict[int, str] = {}
        self._channel_names: dict[int, str] = {}
        self._identified = False

    async def run(self) -> None:
        logger.warning(
            "Using a Discord user token for automation may violate Discord ToS and risk account action. "
            "Use only for local testing."
        )
        backoff = 3.0
        while True:
            try:
                await self._connect_once()
                backoff = 3.0
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Gateway connection failed; reconnecting in %.1fs", backoff)
                await asyncio.sleep(backoff + random.random() * 2)
                backoff = min(backoff * 1.5, 60.0)

    def _resolve_proxy(self) -> str | None:
        proxy_setting = self._config.gateway_proxy
        if proxy_setting == "none":
            return None
        if proxy_setting:
            return proxy_setting
        return True

    async def _connect_once(self) -> None:
        proxy = self._resolve_proxy()
        if proxy not in (None, True):
            logger.info("Connecting to Discord Gateway via proxy %s", proxy)
        elif proxy is None:
            logger.info("Connecting to Discord Gateway without proxy")

        async with websockets.connect(
            GATEWAY_URL,
            max_size=2**24,
            ping_interval=None,
            proxy=proxy,
        ) as websocket:
            heartbeat_task: asyncio.Task[None] | None = None
            try:
                async for raw_message in websocket:
                    payload = json.loads(raw_message)
                    should_reconnect = await self._handle_payload(websocket, payload, heartbeat_task)
                    if should_reconnect:
                        break
                    if heartbeat_task is None and self._heartbeat_interval is not None:
                        heartbeat_task = asyncio.create_task(self._heartbeat_loop(websocket))
            finally:
                if heartbeat_task is not None:
                    heartbeat_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await heartbeat_task

    async def _handle_payload(
        self,
        websocket: ClientConnection,
        payload: dict[str, Any],
        heartbeat_task: asyncio.Task[None] | None,
    ) -> bool:
        sequence = payload.get("s")
        if sequence is not None:
            self._sequence = int(sequence)

        opcode = payload.get("op")
        event_type = payload.get("t")
        data = payload.get("d")

        if opcode == 10 and isinstance(data, dict):
            self._heartbeat_interval = float(data["heartbeat_interval"]) / 1000.0
            if self._session_id and self._sequence is not None:
                await self._send_resume(websocket)
            else:
                await self._send_identify(websocket)
            return False

        if opcode == 11:
            return False

        if opcode == 7:
            logger.info("Gateway requested reconnect")
            return True

        if opcode == 9:
            can_resume = bool(data)
            logger.warning("Invalid session; resume=%s", can_resume)
            if not can_resume:
                self._session_id = None
                self._sequence = None
            return True

        if opcode != 0 or not isinstance(data, dict):
            return False

        if event_type == "READY":
            self._identified = True
            self._session_id = str(data.get("session_id") or "")
            user = data.get("user") or {}
            self._user_id = int(user.get("id") or 0)
            username = user.get("global_name") or user.get("username") or "unknown"
            logger.info("Logged in as %s (%s)", username, self._user_id)
            logger.info(
                "Monitoring channel IDs: %s",
                ", ".join(map(str, sorted(self._config.channel_ids))),
            )
            if self._config.allowed_guild_ids:
                logger.info(
                    "Allowed guild IDs: %s",
                    ", ".join(map(str, sorted(self._config.allowed_guild_ids))),
                )
            self._cache_ready_guilds(data.get("guilds") or [])
            await self._prefetch_monitored_channels()
            return False

        if event_type == "RESUMED":
            logger.info("Gateway session resumed")
            return False

        if event_type == "GUILD_CREATE":
            self._cache_guild(data)
            return False

        if event_type in {"CHANNEL_CREATE", "CHANNEL_UPDATE"}:
            self._cache_channel(data)
            return False

        if event_type == "MESSAGE_CREATE":
            await self._on_message_create(data)
            return False

        if event_type == "MESSAGE_UPDATE":
            logger.debug("Ignored MESSAGE_UPDATE for message %s", data.get("id"))
            return False

        return False

    async def _on_message_create(self, payload: dict[str, Any]) -> None:
        message = DiscordMessage.from_gateway_payload(
            payload,
            guild_names=self._guild_names,
            channel_names=self._channel_names,
        )

        if message.author.bot:
            logger.debug("Skipped message %s: bot author", message.id)
            return
        if message.channel_id not in self._config.channel_ids:
            logger.debug(
                "Skipped message %s: channel %s not in watch list",
                message.id,
                message.channel_id,
            )
            return
        if self._config.allowed_guild_ids and message.guild_id not in self._config.allowed_guild_ids:
            logger.debug(
                "Skipped message %s: guild %s not allowed",
                message.id,
                message.guild_id,
            )
            return

        message = await self._ensure_channel_name(message)

        logger.info(
            "Received message %s in #%s from %s",
            message.id,
            message.channel_name or message.channel_id,
            message.author.display_name(),
        )

        try:
            record_message(MESSAGES_PATH, message)
            logger.info("Stored Discord message %s", message.id)
        except Exception:
            logger.exception("Failed to store Discord message %s", message.id)

        alert = format_discord_message(message, self._config.alert_prefix)
        try:
            await self._forwarder.send(alert)
            logger.info("Forwarded Discord message %s", message.id)
        except Exception:
            logger.exception("Failed to forward Discord message %s", message.id)

    async def _heartbeat_loop(self, websocket: ClientConnection) -> None:
        assert self._heartbeat_interval is not None
        while True:
            await asyncio.sleep(self._heartbeat_interval)
            await websocket.send(json.dumps({"op": 1, "d": self._sequence}))

    async def _send_identify(self, websocket: ClientConnection) -> None:
        await websocket.send(
            json.dumps(
                {
                    "op": 2,
                    "d": {
                        "token": self._config.discord_user_token,
                        "capabilities": 16381,
                        "properties": {
                            "os": "Mac OS X",
                            "browser": "Chrome",
                            "device": "",
                            "system_locale": "en-US",
                            "browser_user_agent": (
                                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/120.0.0.0 Safari/537.36"
                            ),
                            "browser_version": "120.0.0.0",
                            "os_version": "10.15.7",
                            "referrer": "",
                            "referring_domain": "",
                            "referrer_current": "",
                            "referring_domain_current": "",
                            "release_channel": "stable",
                            "client_build_number": 261050,
                            "client_event_source": None,
                        },
                        "presence": {
                            "status": "online",
                            "since": 0,
                            "activities": [],
                            "afk": False,
                        },
                        "compress": False,
                        "client_state": {
                            "guild_versions": {},
                        },
                    },
                }
            )
        )

    async def _send_resume(self, websocket: ClientConnection) -> None:
        await websocket.send(
            json.dumps(
                {
                    "op": 6,
                    "d": {
                        "token": self._config.discord_user_token,
                        "session_id": self._session_id,
                        "seq": self._sequence,
                    },
                }
            )
        )

    def _cache_ready_guilds(self, guilds: list[dict[str, Any]]) -> None:
        for guild in guilds:
            guild_id = guild.get("id")
            name = guild.get("name")
            if guild_id is not None and name:
                self._guild_names[int(guild_id)] = str(name)

    def _cache_guild(self, guild: dict[str, Any]) -> None:
        guild_id = guild.get("id")
        name = guild.get("name")
        if guild_id is not None and name:
            self._guild_names[int(guild_id)] = str(name)
        for channel in guild.get("channels") or []:
            self._cache_channel(channel)

    def _cache_channel(self, channel: dict[str, Any]) -> None:
        channel_id = channel.get("id")
        name = channel.get("name")
        if channel_id is not None and name:
            self._channel_names[int(channel_id)] = str(name)

    async def _prefetch_monitored_channels(self) -> None:
        tasks = [
            self._fetch_channel_name(channel_id)
            for channel_id in self._config.channel_ids
            if channel_id not in self._channel_names
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        resolved = [
            f"{self._channel_names.get(channel_id, channel_id)} ({channel_id})"
            for channel_id in sorted(self._config.channel_ids)
        ]
        logger.info("Resolved channel names: %s", ", ".join(resolved))

    async def _ensure_channel_name(self, message: DiscordMessage) -> DiscordMessage:
        if message.channel_name:
            return message
        name = await self._fetch_channel_name(message.channel_id)
        if not name:
            return message
        return replace(message, channel_name=name)

    async def _fetch_channel_name(self, channel_id: int) -> str | None:
        if channel_id in self._channel_names:
            return self._channel_names[channel_id]

        url = f"https://discord.com/api/v10/channels/{channel_id}"
        headers = {"Authorization": self._config.discord_user_token}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
        except Exception:
            logger.exception("Failed to fetch channel name for %s", channel_id)
            return None

        name = data.get("name")
        if not name:
            return None

        channel_name = str(name)
        self._channel_names[channel_id] = channel_name
        return channel_name


