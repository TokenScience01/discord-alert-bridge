from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import DiscordMessage

logger = logging.getLogger(__name__)

_MAX_PER_CHANNEL = 100
_MAX_CHANNELS = 50

_lock = threading.Lock()


def record_message(path: Path, message: DiscordMessage) -> None:
    entry = {
        "id": str(message.id),
        "channel_id": str(message.channel_id),
        "channel_name": message.channel_name or str(message.channel_id),
        "author": message.author.display_name(),
        "content": message.content.strip() or "（无文字内容）",
        "created_at": _iso(message.created_at),
        "forwarded_at": datetime.now(timezone.utc).isoformat(),
    }
    with _lock:
        data = _load(path)
        channels: dict[str, Any] = data.setdefault("channels", {})
        channel_key = str(message.channel_id)
        bucket = channels.setdefault(
            channel_key,
            {
                "channel_id": channel_key,
                "channel_name": entry["channel_name"],
                "messages": [],
            },
        )
        if entry["channel_name"]:
            bucket["channel_name"] = entry["channel_name"]
        messages: list[dict[str, Any]] = bucket.setdefault("messages", [])
        if any(item.get("id") == entry["id"] for item in messages):
            return
        messages.insert(0, entry)
        bucket["messages"] = messages[:_MAX_PER_CHANNEL]
        if len(channels) > _MAX_CHANNELS:
            oldest_key = min(
                channels,
                key=lambda key: channels[key].get("messages", [{}])[0].get("forwarded_at", ""),
            )
            channels.pop(oldest_key, None)
        _save(path, data)
    logger.debug("Recorded message %s to %s", entry["id"], path)


def list_messages(path: Path, channel_id: str | None = None, limit: int = 80) -> dict[str, Any]:
    with _lock:
        data = _load(path)
    channels = data.get("channels", {})
    items: list[dict[str, Any]] = []
    for bucket in channels.values():
        channel_key = str(bucket.get("channel_id", ""))
        if channel_id and channel_key != str(channel_id):
            continue
        for message in bucket.get("messages", []):
            items.append(
                {
                    **message,
                    "channel_id": channel_key,
                    "channel_name": bucket.get("channel_name") or channel_key,
                }
            )
    items.sort(key=lambda item: item.get("forwarded_at", ""), reverse=True)
    summary = [
        {
            "channel_id": str(bucket.get("channel_id", "")),
            "channel_name": bucket.get("channel_name") or str(bucket.get("channel_id", "")),
            "message_count": len(bucket.get("messages", [])),
        }
        for bucket in sorted(
            channels.values(),
            key=lambda value: value.get("messages", [{}])[0].get("forwarded_at", "")
            if value.get("messages")
            else "",
            reverse=True,
        )
    ]
    return {
        "channels": summary,
        "messages": items[:limit],
        "total": len(items),
    }


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"channels": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"channels": {}}


def _save(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _iso(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(timezone.utc).isoformat()