"""
Logger — Structured logging with console and file output.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


class AuroraLogger:
    """Custom logger for Aurora Parasite."""

    def __init__(self, name: str):
        self.logger = logging.getLogger(f"parasite.{name}")
        self.logger.setLevel(logging.DEBUG)

        if not self.logger.handlers:
            # Console handler
            console = logging.StreamHandler(sys.stdout)
            console.setLevel(logging.INFO)
            console.setFormatter(logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(message)s",
                "%H:%M:%S"
            ))
            self.logger.addHandler(console)

            # File handler
            file_handler = logging.FileHandler(
                LOG_DIR / f"parasite_{datetime.now().strftime('%Y%m%d')}.log"
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s",
                "%Y-%m-%d %H:%M:%S"
            ))
            self.logger.addHandler(file_handler)

    def info(self, msg: str):
        self.logger.info(msg)

    def warning(self, msg: str):
        self.logger.warning(msg)

    def error(self, msg: str):
        self.logger.error(msg)

    def debug(self, msg: str):
        self.logger.debug(msg)

    def trade(self, action: str, symbol: str, layer: str, details: dict):
        self.logger.info(
            f"TRADE | {action:6} | {layer:16} | {symbol:10} | "
            + " | ".join(f"{k}={v}" for k, v in details.items())
        )

    def layer(self, layer: str, action: str, detail: str):
        self.logger.info(f"LAYER | {layer:16} | {action:6} | {detail}")

    def evolution(self, event: str, detail: str):
        self.logger.info(f"EVOLVE | {event:20} | {detail}")


def get_logger(name: str) -> AuroraLogger:
    return AuroraLogger(name)