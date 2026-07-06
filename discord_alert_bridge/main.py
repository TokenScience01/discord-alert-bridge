from __future__ import annotations

import asyncio
import logging
import sys

from .config import ConfigError, load_config
from .discord_gateway import UserGatewayClient
from .forwarders import build_forwarder


def run() -> None:
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"Configuration error:\n{exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    client = UserGatewayClient(config=config, forwarder=build_forwarder(config))
    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        print("Stopped.")