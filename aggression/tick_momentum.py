"""
Tick Momentum Engine — Layer 2.
Surfs micro-trends. No cortex dependency. Fires independently.
"""

import asyncio
import time
import uuid
from config import config
from logger import get_logger

logger = get_logger("tick_momentum")


class TickMomentum:
    """Detects micro-trends via consecutive directional ticks."""

    def __init__(self, parasite):
        self.parasite = parasite
        self.running = False
        self.active_trends: dict = {}
        self.total_trades = 0
        self.total_wins = 0
        self.total_r = 0.0

    async def run(self):
        self.running = True
        logger.info("Tick Momentum Engine online — INDEPENDENT MODE")

        while self.running:
            try:
                if self.parasite.halted:
                    await asyncio.sleep(1)
                    continue

                for symbol in config.INSTRUMENTS:
                    await self._check_symbol(symbol)

                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Tick momentum error: {e}")
                await asyncio.sleep(0.5)

    async def _check_symbol(self, symbol: str):
        if symbol in self.active_trends:
            return

        buffer = self.parasite.nervous_system.tick_buffers.get(symbol)
        if not buffer or len(buffer) < 8:
            return

        latest = buffer[-1]

        if latest.tick_velocity < config.TICK_MOMENTUM_MIN_VELOCITY:
            return
        if latest.spread_ratio > config.TICK_MOMENTUM_MAX_SPREAD:
            return

        direction = latest.direction
        if direction == 0:
            return

        consecutive = 0
        for t in reversed(buffer):
            if hasattr(t, 'direction') and t.direction == direction:
                consecutive += 1
            else:
                break

        if consecutive < config.TICK_MOMENTUM_CONSECUTIVE_TICKS:
            return

        await self._enter_trend(symbol, direction, latest)

    async def _enter_trend(self, symbol: str, direction: int, tick):
        trade_id = f"TM_{uuid.uuid4().hex[:8]}"
        risk_pct = config.LAYER_RISK.get("tick_momentum", 0.005)
        risk_amount = config.INITIAL_CAPITAL * risk_pct

        dir_str = "BUY" if direction == 1 else "SELL"

        order = await self.parasite.execution._place_order(symbol, dir_str, risk_amount)
        if not order:
            return

        self.active_trends[trade_id] = {
            "trade_id": trade_id, "symbol": symbol, "direction": dir_str,
            "entry_price": tick.ask if direction == 1 else tick.bid,
            "risk_amount": risk_amount,
            "pyramid_level": 0, "consecutive_count": 0,
            "opened_at": time.time(), "order_id": order.get("orderId", ""),
        }

        asyncio.create_task(self._monitor_trend(trade_id))
        logger.layer("tick_momentum", "ENTER", f"{symbol} {dir_str}")

    async def _monitor_trend(self, trade_id: str):
        position = self.active_trends.get(trade_id)
        if not position:
            return

        symbol = position["symbol"]
        direction = position["direction"]
        entry = position["entry_price"]
        risk = position["risk_amount"]

        while trade_id in self.active_trends:
            await asyncio.sleep(0.1)

            buffer = self.parasite.nervous_system.tick_buffers.get(symbol)
            if not buffer or len(buffer) < 2:
                continue

            latest = buffer[-1]
            pos = self.active_trends.get(trade_id)
            if not pos:
                break

            # Reversal exit
            if (direction == "BUY" and latest.direction == -1) or (direction == "SELL" and latest.direction == 1):
                exit_price = latest.bid if direction == "BUY" else latest.ask
                await self._exit_trend(trade_id, exit_price)
                break

            # Pyramiding
            if latest.direction == (1 if direction == "BUY" else -1):
                pos["consecutive_count"] += 1
                if pos["consecutive_count"] >= 2 and pos["pyramid_level"] < 3:
                    add_size = pos["risk_amount"] * 0.5
                    await self.parasite.execution._place_order(symbol, direction, add_size)
                    pos["pyramid_level"] += 1
                    pos["consecutive_count"] = 0
            else:
                pos["consecutive_count"] = 0

            # R-based exit
            current_price = latest.bid if direction == "BUY" else latest.ask
            if direction == "BUY":
                r_multiple = (current_price - entry) / (risk / 0.01) if risk > 0 else 0
            else:
                r_multiple = (entry - current_price) / (risk / 0.01) if risk > 0 else 0

            if r_multiple < -0.5:
                await self._exit_trend(trade_id, current_price)
                break
            if r_multiple > 2.0:
                await self._exit_trend(trade_id, current_price)
                break

    async def _exit_trend(self, trade_id: str, exit_price: float):
        position = self.active_trends.pop(trade_id, None)
        if not position:
            return

        entry = position["entry_price"]
        direction = position["direction"]
        risk = position["risk_amount"]

        if direction == "BUY":
            r_multiple = (exit_price - entry) / (risk / 0.01) if risk > 0 else 0
        else:
            r_multiple = (entry - exit_price) / (risk / 0.01) if risk > 0 else 0

        trade_data = {
            "trade_id": f"TRD_{position['trade_id']}",
            "instrument": position["symbol"], "layer": "tick_momentum", "branch_id": "",
            "direction": direction, "entry_price": entry, "exit_price": exit_price,
            "r_multiple": round(r_multiple, 4),
            "profit_currency": round(r_multiple * risk, 4),
            "duration_ms": int((time.time() - position["opened_at"]) * 1000),
        }

        await self.parasite.record_trade(trade_data)
        self.total_trades += 1
        if r_multiple > 0:
            self.total_wins += 1
        self.total_r += r_multiple

        logger.trade("CLOSE", position["symbol"], "tick_momentum", {"r": round(r_multiple, 3)})

    def get_stats(self) -> dict:
        return {
            "active": self.running,
            "total_trades": self.total_trades,
            "wins": self.total_wins,
            "win_rate": self.total_wins / max(self.total_trades, 1),
            "total_r": round(self.total_r, 2),
            "avg_r": round(self.total_r / max(self.total_trades, 1), 3),
        }