import os
import unittest
from unittest import mock

from discord_alert_bridge.admin_auth import (
    issue_session_token,
    verify_credentials,
    verify_session_token,
)


class AdminAuthTest(unittest.TestCase):
    def test_verify_credentials(self) -> None:
        env = {"ADMIN_USERNAME": "admin", "ADMIN_PASSWORD": "secret"}
        with mock.patch.dict(os.environ, env, clear=False):
            self.assertTrue(verify_credentials("admin", "secret"))
            self.assertFalse(verify_credentials("admin", "wrong"))

    def test_issue_and_verify_session(self) -> None:
        env = {"ADMIN_USERNAME": "admin", "ADMIN_PASSWORD": "secret"}
        with mock.patch.dict(os.environ, env, clear=False):
            token = issue_session_token("admin")
            self.assertEqual(verify_session_token(token), "admin")
            self.assertIsNone(verify_session_token("broken-token"))


if __name__ == "__main__":
    unittest.main()