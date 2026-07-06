from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MESSAGES_PATH = ROOT / "messages.json"
LOG_PATH = ROOT / "bridge.log"
PID_PATH = ROOT / ".bridge.pid"
ENV_PATH = ROOT / ".env"
ENV_EXAMPLE_PATH = ROOT / ".env.example"