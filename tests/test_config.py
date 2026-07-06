import unittest

from discord_alert_bridge.config import ConfigError, parse_channel_references


class ParseChannelReferencesTest(unittest.TestCase):
    def test_parses_discord_channel_url(self) -> None:
        selection = parse_channel_references(
            ["https://discord.com/channels/1361029657448808609/1504167299584884952"]
        )

        self.assertEqual(selection.guild_ids, frozenset({1361029657448808609}))
        self.assertEqual(selection.channel_ids, frozenset({1504167299584884952}))

    def test_parses_guild_channel_pair(self) -> None:
        selection = parse_channel_references(["1361029657448808609/1504167299584884952"])

        self.assertEqual(selection.guild_ids, frozenset({1361029657448808609}))
        self.assertEqual(selection.channel_ids, frozenset({1504167299584884952}))

    def test_parses_explicit_channel_ids(self) -> None:
        selection = parse_channel_references([], ["1504167299584884952"])

        self.assertEqual(selection.guild_ids, frozenset())
        self.assertEqual(selection.channel_ids, frozenset({1504167299584884952}))

    def test_rejects_invalid_reference(self) -> None:
        with self.assertRaises(ConfigError):
            parse_channel_references(["not-a-channel"])


if __name__ == "__main__":
    unittest.main()
