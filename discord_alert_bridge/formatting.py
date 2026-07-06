from __future__ import annotations

from .models import Alert, DiscordAttachment, DiscordEmbed, DiscordMessage


def format_discord_message(message: DiscordMessage, prefix: str) -> Alert:
    author_name = message.author.display_name()
    channel_name = message.channel_name
    content = _format_content(message)

    preview = content.splitlines()[0] if content else "（无文字内容）"
    if channel_name:
        subject = _truncate(f"{channel_name} · {author_name}", 150)
    else:
        subject = _truncate(author_name, 150)

    extras: list[str] = []
    extras.extend(_format_attachment_lines(message.attachments))
    extras.extend(_format_embed_lines(message.embeds))

    body_lines: list[str] = []
    if channel_name:
        body_lines.append(f"频道: {channel_name}")
    body_lines.extend(
        [
            f"发送人: {author_name}",
            "内容:",
            content or "（无文字内容）",
        ]
    )
    if extras:
        body_lines.extend(["", *extras])

    return Alert(
        subject=subject,
        body="\n".join(body_lines),
        channel=channel_name,
        author=author_name,
        message=content or "（无文字内容）",
        extras=tuple(extras),
    )


def _format_content(message: DiscordMessage) -> str:
    return message.content.strip()


def _format_attachment_lines(attachments: tuple[DiscordAttachment, ...]) -> list[str]:
    return [f"📎 {item.filename}" for item in attachments]


def _format_embed_lines(embeds: tuple[DiscordEmbed, ...]) -> list[str]:
    lines: list[str] = []
    for embed in embeds:
        parts: list[str] = []
        if embed.title:
            parts.append(str(embed.title))
        if embed.description:
            parts.append(_truncate(str(embed.description).replace("\n", " "), 180))
        if parts:
            lines.append("📌 " + " · ".join(parts))
    return lines


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."