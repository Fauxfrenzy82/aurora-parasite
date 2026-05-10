"""
Cross-Instrument Arbitrage — Layer 5.
Trades divergence between correlated pairs. Timeout-protected.
"""

import asyncio
import time
import uuid
import numpy as np
from config import config
from logger import get_logger

logger = get_logger("cross_instrument")


class CrossInstrumentArb:
    """Detects divergence and trades convergence with timeout protection."""

    def __init__(self, parasite):
        self.parasite = parasite
        self.running = False
        self.active_pairs: dict = {}
        self.total_trades = 0
        self.total_wins = 0
        self.total_r = 0.0
        self.spread_history: dict = {}

    async def run(self):
        self.running = True
        logger.info("Cross-Instrument Arbitrage online — TIMEOUT PROTECTED")

        for pair in config.CROSS_INSTRUMENT_PAIRS:
            self.spread_history[pair] = []

        while self.running:
            try:
                if self.parasite.halted:
                    await asyncio.sleep(1)
                    continue

                for pair in config.CROSS_INSTRUMENT_PAIRS:
                    await self._check_pair(pair)

                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Cross-instrument error: {e}")
                await asyncio.sleep(1)

    async def _check_pair(self, pair: tuple):
        sym_a, sym_b = pair
        pair_key = f"{sym_a}_{sym_b}"

        if pair_key in self.active_pairs:
            return

        buffer_a = self.parasite.nervous_system.tick_buffers.get(sym_a)
        buffer_b = self.parasite.nervous_system.tick_buffers.get(sym_b)

        if not buffer_a or not buffer_b or len(buffer_a) < 10 or len(buffer_b) < 10:
            return

        mid_a = buffer_a[-1].mid_price
        mid_b = buffer_b[-1].mid_price
        if mid_a == 0 or mid_b == 0:
            return

        current_spread = (mid_a - mid_b) / mid_b

        self.spread_history[pair].append(current_spread)
        if len(self.spread_history[pair]) > 200:
            self.spread_history[pair].pop(0)

        if len(self.spread_history[pair]) < 30:
            return

        spreads = np.array(self.spread_history[pair])
        mean_spread = np.mean(spreads)
        std_spread = np.std(spreads)
        if std_spread == 0:
            return

        z_score = (current_spread - mean_spread) / std_spread

        if abs(z_score) < config.CROSS_INSTRUMENT_STD_THRESHOLD:
            return

        await self._enter_pair(pair, z_score)

    async def _enter_pair(self, pair: tuple, z_score: float):
        sym_a, sym_b = pair
        pair_key = f"{sym_a}_{sym_b}"
        trade_id = f"CI_{uuid.uuid4().hex[:8]}"
        risk_pct = config.LAYER_RISK.get("cross_instrument", 0.004)
        risk_amount = config.INITIAL_CAPITAL * risk_pct

        if z_score > 0:
            dir_a = "SELL"
            dir_b = "BUY"
        else:
            dir_a = "BUY"
            dir_b = "SELL"

        order_a = await self.parasite.execution._place_order(sym_a, dir_a, risk_amount)
        order_b = await self.parasite.execution._place_order(sym_b, dir_b, risk_amount)

        if not order_a or not order_b:
            return

        buffer_a = self.parasite.nervous_system.tick_buffers.get(sym_a)
        buffer_b = self.parasite.nervous_system.tick_buffers.get(sym_b)
        entry_a = buffer_a[-1].bid if dir_a == "SELL" else buffer_a[-1].ask if buffer_a else 0
        entry_b = buffer_b[-1].ask if dir_b == "BUY" else buffer_b[-1].bid if buffer_b else 0

        self.active_pairs[pair_key] = {
            "trade_id": trade_id, "sym_a": sym_a, "sym_b": sym_b,
            "dir_a": dir_a, "dir_b": dir_b,
            "entry_a": entry_a, "entry_b": entry_b,
            "risk_amount": risk_amount, "opened_at": time.time(),
            "leg_a_closed": False, "leg_b_closed": False,
            "r_a": 0.0, "r_b": 0.0,
        }

        asyncio.create_task(self._monitor_pair(pair_key))
        logger.layer("cross_instrument", "ENTER", f"{sym_a}/{sym_b}")

    async def _monitor_pair(self, pair_key: str):
        position = self.active_pairs.get(pair_key)
        if not position:
            return

        risk = position["risk_amount"]
        start_time = time.time()

        while pair_key in self.active_pairs:
            await asyncio.sleep(0.3)

            # Timeout protection
            if time.time() - start_time > config.CROSS_INSTRUMENT_TIMEOUT:
                pos = self.active_pairs.get(pair_key)
                if pos:
                    pos["leg_a_closed"] = True
                    pos["leg_b_closed"] = True
                await self._exit_pair(pair_key)
                break

            pos = self.active_pairs.get(pair_key)
            if not pos:
                break

            buffer_a = self.parasite.nervous_system.tick_buffers.get(pos["sym_a"])
            buffer_b = self.parasite.nervous_system.tick_buffers.get(pos["sym_b"])

            if not buffer_a or not buffer_b or len(buffer_a) < 2 or len(buffer_b) < 2:
                continue

            tick_a = buffer_a[-1]
            tick_b = buffer_b[-1]

            exit_a = tick_a.bid if pos["dir_a"] == "BUY" else tick_a.ask
            exit_b = tick_b.ask if pos["dir_b"] == "BUY" else tick_b.bid

            if pos["dir_a"] == "BUY":
                r_a = (exit_a - pos["entry_a"]) / (risk / 0.01) if risk > 0 else 0
            else:
                r_a = (pos["entry_a"] - exit_a) / (risk / 0.01) if risk > 0 else 0

            if pos["dir_b"] == "BUY":
                r_b = (exit_b - pos["entry_b"]) / (risk / 0.01) if risk > 0 else 0
            else:
                r_b = (pos["entry_b"] - exit_b) / (risk / 0.01) if risk > 0 else 0

            if not pos["leg_a_closed"] and r_a < -0.4:
                pos["leg_a_closed"] = True
                pos["r_a"] = r_a
            if not pos["leg_b