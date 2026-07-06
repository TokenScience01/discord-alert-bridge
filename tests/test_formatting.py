import unittest
from datetime import datetime, timezone

from discord_alert_bridge.formatting import format_discord_message
from discord_alert_bridge.forwarders import build_lark_card
from discord_alert_bridge.models import DiscordAttachment, DiscordEmbed, DiscordMessage


def _build_message(**overrides: object) -> DiscordMessage:
    defaults = {
        "id": 999,
        "channel_id": 456,
        "guild_id": 123,
        "guild_name": "Test Server",
        "channel_name": "alerts",
        "author": DiscordMessage.from_gateway_payload(
            {
                "id": "999",
                "channel_id": "456",
                "guild_id": "123",
                "author": {"id": "789", "username": "alice", "global_name": "Alice"},
                "content": "hello world",
                "timestamp": "2026-07-05T00:00:00+00:00",
            },
            guild_names={123: "Test Server"},
            channel_names={456: "alerts"},
        ).author,
        "content": "hello world",
        "attachments": (),
        "embeds": (),
        "created_at": datetime(2026, 7, 5, tzinfo=timezone.utc),
        "jump_url": "https://discord.com/channels/123/456/999",
    }
    defaults.update(overrides)
    return DiscordMessage(**defaults)  # type: ignore[arg-type]


class FormatDiscordMessageTest(unittest.TestCase):
    def test_formats_channel_sender_and_content(self) -> None:
        alert = format_discord_message(_build_message(), "[Discord]")

        self.assertEqual(alert.subject, "alerts · Alice")
        self.assertEqual(alert.channel, "alerts")
        self.assertEqual(alert.author, "Alice")
        self.assertEqual(alert.message, "hello world")

    def test_builds_lark_card(self) -> None:
        alert = format_discord_message(
            _build_message(
                attachments=(DiscordAttachment(filename="image.png", url="https://cdn.example/image.png"),),
                embeds=(DiscordEmbed(title="公告", url=None, description="今晚维护"),),
            ),
            "[Discord]",
        )
        card = build_lark_card(alert)

        self.assertEqual(card["header"]["title"]["content"], "alerts · Alice")
        self.assertEqual(card["elements"][0]["fields"][0]["text"]["content"], "**频道**\nalerts")
        self.assertEqual(card["elements"][0]["fields"][1]["text"]["content"], "**发送人**\nAlice")
        self.assertIn("📎 image.png", alert.extras[0])


if __name__ == "__main__":
    unittest.main()