import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from discord_alert_bridge.message_store import list_messages, record_message
from discord_alert_bridge.models import DiscordMessage


def _message(**overrides: object) -> DiscordMessage:
    defaults = {
        "id": 1001,
        "channel_id": 2002,
        "guild_id": 3003,
        "guild_name": "Server",
        "channel_name": "alerts",
        "author": DiscordMessage.from_gateway_payload(
            {
                "id": "1001",
                "channel_id": "2002",
                "guild_id": "3003",
                "author": {"id": "9", "username": "alice", "global_name": "Alice"},
                "content": "hello",
            },
            guild_names={3003: "Server"},
            channel_names={2002: "alerts"},
        ).author,
        "content": "hello",
        "attachments": (),
        "embeds": (),
        "created_at": datetime(2026, 7, 6, tzinfo=timezone.utc),
        "jump_url": "https://discord.com/channels/3003/2002/1001",
    }
    defaults.update(overrides)
    return DiscordMessage(**defaults)  # type: ignore[arg-type]


class MessageStoreTest(unittest.TestCase):
    def test_records_and_lists_by_channel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "messages.json"
            record_message(path, _message())
            record_message(path, _message(id=1002, content="second"))  # type: ignore[arg-type]

            all_messages = list_messages(path)
            self.assertEqual(all_messages["total"], 2)
            self.assertEqual(all_messages["channels"][0]["channel_name"], "alerts")

            filtered = list_messages(path, channel_id="2002")
            self.assertEqual(filtered["total"], 2)
            self.assertEqual(filtered["messages"][0]["content"], "second")


if __name__ == "__main__":
    unittest.main()