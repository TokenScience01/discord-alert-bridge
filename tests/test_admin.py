import tempfile
import unittest
from pathlib import Path

from discord_alert_bridge.admin import (
    SESSION_BANNER_PREFIX,
    build_test_alert_config,
    clear_log,
    fill_channel_ids_from_refs,
    find_latest_session_start,
    is_pid_running,
    normalize_discord_user_token,
    tail_text,
    validate_forwarder_settings,
    validate_discord_user_token,
)


class FillChannelIdsFromRefsTest(unittest.TestCase):
    def test_fills_channel_and_guild_ids_from_url(self) -> None:
        values = {
            "DISCORD_CHANNEL_URLS": "https://discord.com/channels/1361029657448808609/1504167299584884952",
            "DISCORD_CHANNEL_IDS": "",
            "DISCORD_ALLOWED_GUILD_IDS": "",
        }

        fill_channel_ids_from_refs(values)

        self.assertEqual(values["DISCORD_CHANNEL_IDS"], "1504167299584884952")
        self.assertEqual(values["DISCORD_ALLOWED_GUILD_IDS"], "1361029657448808609")


class DiscordTokenValidationTest(unittest.TestCase):
    def test_strips_bearer_prefix(self) -> None:
        self.assertEqual(normalize_discord_user_token("Bearer abc.def.ghi"), "abc.def.ghi")

    def test_rejects_bot_token(self) -> None:
        errors = validate_discord_user_token("Bot abc.def.ghi")
        self.assertTrue(errors)

    def test_accepts_user_token(self) -> None:
        errors = validate_discord_user_token("mfa.example.token")
        self.assertFalse(errors)


class LogHelpersTest(unittest.TestCase):
    def test_tail_text_prefers_current_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bridge.log"
            path.write_text(
                "old noise\n"
                f"{SESSION_BANNER_PREFIX} 2026-07-06 00:00:00 UTC =====\n"
                "new session line\n",
                encoding="utf-8",
            )
            text = tail_text(path, current_session_only=True)
            self.assertIn("new session line", text)
            self.assertNotIn("old noise", text)

    def test_find_latest_session_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bridge.log"
            path.write_text(
                f"{SESSION_BANNER_PREFIX} first =====\n"
                f"{SESSION_BANNER_PREFIX} second =====\n",
                encoding="utf-8",
            )
            self.assertTrue(find_latest_session_start(path).endswith("second ====="))


class TestAlertConfigTest(unittest.TestCase):
    def test_builds_lark_only_config_without_discord_token(self) -> None:
        config = build_test_alert_config(
            {
                "LARK_ENABLED": "true",
                "LARK_WEBHOOK_URL": "https://open.larksuite.com/open-apis/bot/v2/hook/test",
                "LARK_SECRET": "",
            }
        )

        self.assertEqual(config.discord_user_token, "")
        self.assertTrue(config.lark.enabled)

    def test_clear_log_empties_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bridge.log"
            path.write_text("old", encoding="utf-8")
            original = clear_log.__globals__["LOG_PATH"]
            clear_log.__globals__["LOG_PATH"] = path
            try:
                result = clear_log()
            finally:
                clear_log.__globals__["LOG_PATH"] = original
            self.assertTrue(result["ok"])
            self.assertEqual(path.read_text(encoding="utf-8"), "")


if __name__ == "__main__":
    unittest.main()