"""
Dynamic Exposure Engine — Updates every 5 minutes based on volatility regime.
Protects capital during high-vol, unleashes during low-vol.
"""

import asyncio
import time
import numpy as np
from typing import Dict
from config import config
from logger import get_logger

logger = get_logger("dynamic_exposure")


class DynamicExposure:
    def __init__(self):
        self.current_exposure = 0.0
        self.max_exposure = config.LOW_VOL_EXPOSURE
        self.regime = "LOW"
        self.by_layer: Dict[str, float] = {
            "spread_capture": 0.0,
            "tick_momentum": 0.0,
            "fade_engine": 0.0,
            "news_scalper": 0.0,
            "cross_instrument": 0.0,
        }
        self.running = False
        self._parasite = None

    async def start(self, parasite):
        self.running = True
        self._parasite = parasite
        asyncio.create_task(self._update_loop())
        logger.info("Dynamic exposure online — 5-minute update cycle")

    async def _update_loop(self):
        while self.running:
            await asyncio.sleep(config.EXPOSURE_UPDATE_INTERVAL)
            try:
                await self._recalculate()
            except Exception as e:
                logger.error(f"Exposure update error: {e}")

    async def _recalculate(self):
        velocities = []
        for symbol in config.INSTRUMENTS:
            buffer = self._parasite.nervous_system.tick_buffers.get(symbol)
            if buffer and len(buffer) >= 5:
                recent = list(buffer)[-5:]
                velocities.append(np.mean([t.tick_velocity for t in recent]))

        if not velocities:
            return

        avg_velocity = np.mean(velocities)

        if avg_velocity < 3.0:
            self.regime = "LOW"
            self.max_exposure = config.LOW_VOL_EXPOSURE
        elif avg_velocity < 6.0:
            self.regime = "NORMAL"
            self.max_exposure = config.NORMAL_VOL_EXPOSURE
        elif avg_velocity < 10.0:
            self.regime = "HIGH"
            self.max_exposure = config.HIGH_VOL_EXPOSURE
        else:
            self.regime = "EXTREME"
            self.max_exposure = config.EXTREME_VOL_EXPOSURE

        logger.info(
            f"Exposure recalculated: regime={self.regime} "
            f"max={self.max_exposure:.0%} avg_vel={avg_velocity:.1f}"
        )

    def can_open(self, symbol: str, direction: str) -> bool:
        return self.current_exposure < self.max_exposure

    def register_open(self, layer: str, amount: float):
        self.current_exposure += amount / config.INITIAL_CAPITAL
        self.by_layer[layer] = self.by_layer.get(layer, 0.0) + amount / config.INITIAL_CAPITAL

    def register_close(self, layer: str, amount: float):
        self.current_exposure = max(0.0, self.current_exposure - amount / config.INITIAL_CAPITAL)
        self.by_layer[layer] = max(
            0.0, self.by_layer.get(layer, 0.0) - amount / config.INITIAL_CAPITAL
        )

    def get_stats(self) -> dict:
        return {
            "current_exposure": round(self.current_exposure, 4),
            "max_exposure": self.max_exposure,
            "regime": self.regime,
            "by_layer": {k: round(v, 4) for k, v in self.by_layer.items()},
        }