from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Alert:
    subject: str
    body: str
    channel: str | None = None
    author: str | None = None
    message: str | None = None
    extras: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiscordAuthor:
    id: int
    username: str
    global_name: str | None
    bot: bool

    def display_name(self) -> str:
        if self.global_name:
            return self.global_name
        return self.username


@dataclass(frozen=True)
class DiscordAttachment:
    filename: str
    url: str


@dataclass(frozen=True)
class DiscordEmbed:
    title: str | None
    url: str | None
    description: str | None


@dataclass(frozen=True)
class DiscordMessage:
    id: int
    channel_id: int
    guild_id: int | None
    guild_name: str | None
    channel_name: str | None
    author: DiscordAuthor
    content: str
    attachments: tuple[DiscordAttachment, ...]
    embeds: tuple[DiscordEmbed, ...]
    created_at: datetime | None
    jump_url: str

    @classmethod
    def from_gateway_payload(
        cls,
        payload: dict[str, Any],
        *,
        guild_names: dict[int, str],
        channel_names: dict[int, str],
    ) -> DiscordMessage:
        author_data = payload.get("author") or {}
        guild_id = _optional_int(payload.get("guild_id"))
        channel_id = int(payload["channel_id"])
        message_id = int(payload["id"])

        attachments = tuple(
            DiscordAttachment(
                filename=str(item.get("filename") or "attachment"),
                url=str(item.get("url") or ""),
            )
            for item in payload.get("attachments") or []
        )
        embeds = tuple(
            DiscordEmbed(
                title=item.get("title"),
                url=item.get("url"),
                description=item.get("description"),
            )
            for item in payload.get("embeds") or []
        )

        if guild_id is None:
            jump_url = f"https://discord.com/channels/@me/{channel_id}/{message_id}"
        else:
            jump_url = f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"

        created_at = _parse_timestamp(payload.get("timestamp"))

        return cls(
            id=message_id,
            channel_id=channel_id,
            guild_id=guild_id,
            guild_name=guild_names.get(guild_id) if guild_id is not None else None,
            channel_name=channel_names.get(channel_id),
            author=DiscordAuthor(
                id=int(author_data.get("id") or 0),
                username=str(author_data.get("username") or "unknown"),
                global_name=author_data.get("global_name"),
                bot=bool(author_data.get("bot")),
            ),
            content=str(payload.get("content") or ""),
            attachments=attachments,
            embeds=embeds,
            created_at=created_at,
            jump_url=jump_url,
        )


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None