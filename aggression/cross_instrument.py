"""
Cross-Instrument Arbitrage — Layer 5.
Trades divergence between correlated volatility index pairs.
Exploits temporary spreads that must converge.
"""

import asyncio
import time
import uuid
import numpy as np
from config import config
from logger import get_logger

logger = get_logger("cross_instrument")


class CrossInstrumentArb:
    """
    Detects divergence between paired instruments and trades convergence.
    Pairs are related volatility indices with shared generation components.
    """

    def __init__(self, parasite):
        self.parasite = parasite
        self.running = False
        self.active_pairs: dict = {}
        self.total_trades = 0
        self.total_wins = 0
        self.total_r = 0.0
        self.spread_history: dict = {}  # Pair -> list of spreads

    async def run(self):
        """Main cross-instrument arbitrage loop."""
        self.running = True
        logger.info("Cross-Instrument Arbitrage online")

        # Initialize spread history
        for pair in config.CROSS_INSTRUMENT_PAIRS:
            self.spread_history[pair] = []

        while self.running:
            try:
                if self.parasite.halted:
                    await asyncio.sleep(1)
                    continue

                for pair in config.CROSS_INSTRUMENT_PAIRS:
                    await self._check_pair(pair)

                await asyncio.sleep(1.0)  # Check every second

            except Exception as e:
                logger.error(f"Cross-instrument error: {e}")
                await asyncio.sleep(1)

    async def _check_pair(self, pair: tuple):
        """Check a pair for divergence."""
        sym_a, sym_b = pair
        pair_key = f"{sym_a}_{sym_b}"

        if pair_key in self.active_pairs:
            return

        buffer_a = self.parasite.nervous_system.tick_buffers.get(sym_a)
        buffer_b = self.parasite.nervous_system.tick_buffers.get(sym_b)

        if not buffer_a or not buffer_b or len(buffer_a) < 10 or len(buffer_b) < 10:
            return

        # Calculate current spread (normalized)
        mid_a = buffer_a[-1].mid_price
        mid_b = buffer_b[-1].mid_price
        if mid_a == 0 or mid_b == 0:
            return

        current_spread = (mid_a - mid_b) / mid_b

        # Update spread history
        self.spread_history[pair].append(current_spread)
        if len(self.spread_history[pair]) > 200:
            self.spread_history[pair].pop(0)

        if len(self.spread_history[pair]) < 50:
            return

        # Calculate statistics
        spreads = np.array(self.spread_history[pair])
        mean_spread = np.mean(spreads)
        std_spread = np.std(spreads)
        if std_spread == 0:
            return

        z_score = (current_spread - mean_spread) / std_spread

        # Check divergence threshold
        if abs(z_score) < config.CROSS_INSTRUMENT_STD_THRESHOLD:
            return

        # Enter pair trade
        await self._enter_pair(pair, z_score, buffer_a[-1], buffer_b[-1])

    async def _enter_pair(self, pair: tuple, z_score: float, tick_a, tick_b):
        """Enter a pair convergence trade."""
        sym_a, sym_b = pair
        pair_key = f"{sym_a}_{sym_b}"
        trade_id = f"CI_{uuid.uuid4().hex[:8]}"
        risk_pct = config.LAYER_RISK.get("cross_instrument", 0.004)
        risk_amount = config.INITIAL_CAPITAL * risk_pct

        # Determine which is overvalued
        if z_score > 0:
            # A is overvalued relative to B
            # Short A, Long B
            dir_a = "SELL"
            dir_b = "BUY"
        else:
            # A is undervalued relative to B
            # Long A, Short B
            dir_a = "BUY"
            dir_b = "SELL"

        # Place both orders
        entry_a = tick_a.bid if dir_a == "SELL" else tick_a.ask
        entry_b = tick_b.ask if dir_b == "BUY" else tick_b.bid

        order_a = await self.parasite.execution._place_order(
            sym_a, dir_a, entry_a, risk_amount
        )
        order_b = await self.parasite.execution._place_order(
            sym_b, dir_b, entry_b, risk_amount
        )

        if not order_a or not order_b:
            return

        self.active_pairs[pair_key] = {
            "trade_id": trade_id,
            "sym_a": sym_a,
            "sym_b": sym_b,
            "dir_a": dir_a,
            "dir_b": dir_b,
            "entry_a": entry_a,
            "entry_b": entry_b,
            "risk_amount": risk_amount,
            "opened_at": time.time(),
            "z_score_entry": z_score,
            "order_id_a": order_a.get("orderId", ""),
            "order_id_b": order_b.get("orderId", ""),
        }

        asyncio.create_task(self._monitor_pair(pair_key))
        logger.layer("cross_instrument", "ENTER", f"{sym_a}/{sym_b} z={z_score:.1f}")

    async def _monitor_pair(self, pair_key: str):
        """Monitor pair for spread convergence."""
        position = self.active_pairs.get(pair_key)
        if not position:
            return

        while pair_key in self.active_pairs:
            await asyncio.sleep(0.5)

            sym_a = position["sym_a"]
            sym_b = position["sym_b"]

            buffer_a = self.parasite.nervous_system.tick_buffers.get(sym_a)
            buffer_b = self.parasite.nervous_system.tick_buffers.get(sym_b)

            if not buffer_a or not buffer_b or len(buffer_a) < 2 or len(buffer_b) < 2:
                continue

            mid_a = buffer_a[-1].mid_price
            mid_b = buffer_b[-1].mid_price
            if mid_b == 0:
                continue

            current_spread = (mid_a - mid_b) / mid_b

            # Exit when spread normalizes (within 0.5 std)
            spreads = np.array(self.spread_history.get((sym_a, sym_b), []))
            if len(spreads) >= 50:
                mean = np.mean(spreads)
                std = np.std(spreads)
                if std > 0:
                    current_z = (current_spread - mean) / std
                    if abs(current_z) < 0.5:
                        await self._exit_pair(pair_key, buffer_a[-1], buffer_b[-1])
                        break

            # Timeout after 120 seconds
            if time.time() - position["opened_at"] > 120:
                await self._exit_pair(pair_key, buffer_a[-1], buffer_b[-1])
                break

    async def _exit_pair(self, pair_key: str, tick_a, tick_b):
        """Exit pair trade and record combined result."""
        position = self.active_pairs.pop(pair_key, None)
        if not position:
            return

        # Calculate R for each leg
        risk = position["risk_amount"]
        entry_a = position["entry_a"]
        entry_b = position["entry_b"]
        dir_a = position["dir_a"]
        dir_b = position["dir_b"]

        exit_a = tick_a.bid if dir_a == "BUY" else tick_a.ask
        exit_b = tick_b.ask if dir_b == "BUY" else tick_b.bid

        if dir_a == "BUY":
            r_a = (exit_a - entry_a) / (risk / 0.01) if risk > 0 else 0
        else:
            r_a = (entry_a - exit_a) / (risk / 0.01) if risk > 0 else 0

        if dir_b == "BUY":
            r_b = (exit_b - entry_b) / (risk / 0.01) if risk > 0 else 0
        else:
            r_b = (entry_b - exit_b) / (risk / 0.01) if risk > 0 else 0

        combined_r = r_a + r_b

        trade_data = {
            "trade_id": f"TRD_{position['trade_id']}",
            "instrument": f"{position['sym_a']}/{position['sym_b']}",
            "layer": "cross_instrument",
            "branch_id": "",
            "direction": "PAIR",
            "entry_price": (entry_a + entry_b) / 2,
            "exit_price": (exit_a + exit_b) / 2,
            "r_multiple": round(combined_r, 4),
            "profit_currency": round(combined_r * risk, 4),
            "duration_ms": int((time.time() - position["opened_at"]) * 1000),
        }

        await self.parasite.record_trade(trade_data)
        self.total_trades += 1
        if combined_r > 0:
            self.total_wins += 1
        self.total_r += combined_r

        logger.trade("CLOSE", f"{position['sym_a']}/{position['sym_b']}", "cross_instrument", {"r": round(combined_r, 3)})

    def get_stats(self) -> dict:
        return {
            "active": self.running,
            "total_trades": self.total_trades,
            "wins": self.total_wins,
            "win_rate": self.total_wins / max(self.total_trades, 1),
            "total_r": round(self.total_r, 2),
            "avg_r": round(self.total_r / max(self.total_trades, 1), 3),
        }