import unittest

from discord_alert_bridge.forwarders import build_lark_card
from discord_alert_bridge.models import Alert


class LarkCardTest(unittest.TestCase):
    def test_builds_interactive_card(self) -> None:
        card = build_lark_card(
            Alert(
                subject="midjourney · Alice",
                body="plain fallback",
                channel="midjourney",
                author="Alice",
                message="a cute cat",
            )
        )

        self.assertEqual(card["config"]["wide_screen_mode"], True)
        self.assertEqual(card["header"]["template"], "indigo")
        self.assertEqual(card["elements"][2]["text"]["content"], "a cute cat")


if __name__ == "__main__":
    unittest.main()