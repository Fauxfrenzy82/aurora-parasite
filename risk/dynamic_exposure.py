"""
Dynamic Exposure — Real-time risk allocation.
Adjusts exposure limits based on volatility regime.
"""

import numpy as np
from config import config
from logger import get_logger

logger = get_logger("dynamic_exposure")


class DynamicExposure:
    """
    Adjusts maximum allowed exposure based on current market conditions.
    Higher volatility = lower exposure, and vice versa.
    """

    def __init__(self):
        self.current_exposure = 0.0
        self.max_exposure = config.NORMAL_VOL_EXPOSURE
        self.volatility_regime = "NORMAL"
        self._exposure_by_layer = {
            "spread_capture": 0.0,
            "tick_momentum": 0.0,
            "fade_engine": 0.0,
            "news_scalper": 0.0,
            "cross_instrument": 0.0,
        }

    def update(self, nervous_system, cortex):
        """Update exposure limits based on current market conditions."""
        vol_ratios = []
        for symbol in config.INSTRUMENTS:
            buffer = nervous_system.tick_buffers.get(symbol)
            if buffer and len(buffer) >= 20:
                ticks = list(buffer)[-20:]
                velocities = [t.tick_velocity for t in ticks]
                if velocities:
                    vol_ratios.append(np.mean(velocities))

        if not vol_ratios:
            # No data yet — keep current limits
            return

        avg_velocity = np.mean(vol_ratios)

        # Classify regime
        if avg_velocity < 5:
            self.volatility_regime = "LOW"
            self.max_exposure = config.LOW_VOL_EXPOSURE
        elif avg_velocity < 15:
            self.volatility_regime = "NORMAL"
            self.max_exposure = config.NORMAL_VOL_EXPOSURE
        elif avg_velocity < 30:
            self.volatility_regime = "HIGH"
            self.max_exposure = config.HIGH_VOL_EXPOSURE
        else:
            self.volatility_regime = "EXTREME"
            self.max_exposure = config.EXTREME_VOL_EXPOSURE

        # Ensure minimum exposure for operation
        if self.max_exposure < 0.30:
            self.max_exposure = 0.55

    def can_open(self, symbol: str, direction: str) -> bool:
        """Check if a new position can be opened."""
        total_exposure = sum(self._exposure_by_layer.values())
        if total_exposure >= self.max_exposure:
            return False
        return True

    def add_exposure(self, layer: str, amount: float):
        """Register a new position's exposure."""
        if layer in self._exposure_by_layer:
            self._exposure_by_layer[layer] += amount
        self.current_exposure = sum(self._exposure_by_layer.values())

    def remove_exposure(self, layer: str, amount: float):
        """Remove a closed position's exposure."""
        if layer in self._exposure_by_layer:
            self._exposure_by_layer[layer] = max(0, self._exposure_by_layer[layer] - amount)
        self.current_exposure = sum(self._exposure_by_layer.values())

    def get_stats(self) -> dict:
        return {
            "current_exposure": round(self.current_exposure, 4),
            "max_exposure": self.max_exposure,
            "regime": self.volatility_regime,
            "by_layer": {k: round(v, 4) for k, v in self._exposure_by_layer.items()},
        }