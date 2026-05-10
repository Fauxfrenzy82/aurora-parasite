"""
The Nervous System — raw tick ingestion and microstructure extraction.
Upgraded for 30 instruments. Faster processing. No dead instruments.
"""

import asyncio
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np

from config import config
from logger import get_logger

logger = get_logger("nervous_system")


@dataclass
class MicroTick:
    symbol: str
    timestamp: float
    bid: float
    ask: float
    spread: float
    mid_price: float
    tick_velocity: float
    spread_ratio: float
    price_jump: float
    direction: int
    volume_signature: float
    quote_imbalance: float


@dataclass
class SignalVector:
    symbol: str
    timestamp: float
    features: np.ndarray


class NervousSystem:
    """Ingests raw ticks and extracts microstructure features at high speed."""

    def __init__(self, symbols: List[str]):
        self.symbols = symbols
        self.tick_buffers: Dict[str, deque] = {s: deque(maxlen=config.TICK_WINDOW) for s in symbols}
        self.signal_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self.running = False
        self.tick_count: Dict[str, int] = {s: 0 for s in symbols}
        self.start_time: Optional[float] = None

    async def start(self, broker_client):
        """Start tick ingestion for all instruments."""
        self.running = True
        self.start_time = asyncio.get_event_loop().time()

        for symbol in self.symbols:
            await broker_client.subscribe(symbol, self._on_tick)

        logger.info(f"Nervous system online — {len(self.symbols)} instruments")

    def _on_tick(self, symbol: str, bid: float, ask: float, timestamp: float):
        if not self.running:
            return

        self.tick_count[symbol] = self.tick_count.get(symbol, 0) + 1
        buffer = self.tick_buffers.get(symbol)
        if buffer is None:
            return

        spread = ask - bid
        mid_price = (bid + ask) / 2.0

        cutoff = timestamp - config.VELOCITY_WINDOW
        recent = [t for t in buffer if t.timestamp > cutoff]
        tick_velocity = len(recent) / max(config.VELOCITY_WINDOW, 0.1)

        if len(buffer) >= 5:
            recent_spreads = [t.spread for t in list(buffer)[-config.SPREAD_WINDOW:]]
            avg_spread = np.mean(recent_spreads) if recent_spreads else spread
            spread_ratio = spread / avg_spread if avg_spread > 0 else 1.0
        else:
            spread_ratio = 1.0

        if len(buffer) > 0:
            last_mid = buffer[-1].mid_price
            price_jump = abs(mid_price - last_mid) / max(last_mid, 0.0001)
            direction = 1 if mid_price > last_mid else (-1 if mid_price < last_mid else 0)
        else:
            price_jump = 0.0
            direction = 0

        same_dir = sum(1 for t in reversed(buffer) if hasattr(t, 'direction') and t.direction == direction and direction != 0)
        volume_signature = same_dir / max(len(buffer), 1)

        quote_imbalance = 1.0 / spread_ratio if spread_ratio > 1.0 else spread_ratio

        micro_tick = MicroTick(
            symbol=symbol, timestamp=timestamp, bid=bid, ask=ask,
            spread=spread, mid_price=mid_price, tick_velocity=tick_velocity,
            spread_ratio=spread_ratio, price_jump=price_jump, direction=direction,
            volume_signature=volume_signature, quote_imbalance=quote_imbalance
        )
        buffer.append(micro_tick)

        # Generate signal every 5 ticks for faster response
        if len(buffer) >= 10 and self.tick_count[symbol] % 5 == 0:
            features = self._extract_features(buffer)
            signal = SignalVector(symbol=symbol, timestamp=timestamp, features=features)
            try:
                self.signal_queue.put_nowait(signal)
            except asyncio.QueueFull:
                pass

    def _extract_features(self, buffer: deque) -> np.ndarray:
        ticks = list(buffer)[-20:]
        if len(ticks) < 5:
            return np.zeros(12)

        mids = np.array([t.mid_price for t in ticks])
        spreads = np.array([t.spread for t in ticks])
        velocities = np.array([t.tick_velocity for t in ticks])
        jumps = np.array([t.price_jump for t in ticks])

        features = np.array([
            np.mean(velocities),
            np.std(velocities),
            np.mean(spreads) / (np.mean(mids) + 1e-10),
            spreads[-1] / (np.mean(spreads) + 1e-10),
            (mids[-1] - mids[0]) / (mids[0] + 1e-10),
            np.sum(np.diff(mids) > 0) / max(len(mids) - 1, 1),
            np.max(jumps[-5:]) if len(jumps) >= 5 else 0,
            np.mean(jumps[-10:]) if len(jumps) >= 10 else 0,
            ticks[-1].volume_signature,
            ticks[-1].quote_imbalance,
            ticks[-1].spread_ratio,
            float(len(ticks)) / config.TICK_WINDOW,
        ])

        return np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0)

    def get_stats(self) -> dict:
        return {
            "running": self.running,
            "symbols": len(self.symbols),
            "total_ticks": sum(self.tick_count.values()),
            "ticks_per_symbol": self.tick_count,
            "signal_queue_size": self.signal_queue.qsize(),
        }