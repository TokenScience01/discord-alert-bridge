import unittest

from discord_alert_bridge.discord_gateway import UserGatewayClient
from discord_alert_bridge.models import DiscordMessage


class DiscordMessagePayloadTest(unittest.TestCase):
    def test_parses_gateway_payload(self) -> None:
        message = DiscordMessage.from_gateway_payload(
            {
                "id": "999",
                "channel_id": "456",
                "guild_id": "123",
                "author": {
                    "id": "789",
                    "username": "alice",
                    "global_name": "Alice",
                    "bot": False,
                },
                "content": "hello world",
                "attachments": [{"filename": "image.png", "url": "https://cdn.example/image.png"}],
                "embeds": [{"title": "Embed title", "description": "details"}],
                "timestamp": "2026-07-05T12:00:00.000000+00:00",
            },
            guild_names={123: "Test Server"},
            channel_names={456: "alerts"},
        )

        self.assertEqual(message.id, 999)
        self.assertEqual(message.guild_name, "Test Server")
        self.assertEqual(message.channel_name, "alerts")
        self.assertEqual(message.author.display_name(), "Alice")
        self.assertEqual(message.attachments[0].filename, "image.png")
        self.assertEqual(message.embeds[0].title, "Embed title")
        self.assertEqual(message.jump_url, "https://discord.com/channels/123/456/999")


class GatewayProxyTest(unittest.TestCase):
    def test_resolve_proxy_none(self) -> None:
        client = UserGatewayClient.__new__(UserGatewayClient)
        client._config = type("Cfg", (), {"gateway_proxy": "none"})()
        self.assertIsNone(client._resolve_proxy())

    def test_resolve_proxy_explicit(self) -> None:
        client = UserGatewayClient.__new__(UserGatewayClient)
        client._config = type("Cfg", (), {"gateway_proxy": "socks5://127.0.0.1:7890"})()
        self.assertEqual(client._resolve_proxy(), "socks5://127.0.0.1:7890")

    def test_resolve_proxy_system_default(self) -> None:
        client = UserGatewayClient.__new__(UserGatewayClient)
        client._config = type("Cfg", (), {"gateway_proxy": None})()
        self.assertTrue(client._resolve_proxy())


if __name__ == "__main__":
    unittest.main()