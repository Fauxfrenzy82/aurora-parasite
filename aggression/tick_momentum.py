"""
Tick Momentum Engine — Layer 2.
Surfs micro-trends detected through consecutive directional ticks.
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
        logger.info("Tick Momentum Engine online")

        while self.running:
            try:
                if self.parasite.halted:
                    await asyncio.sleep(1)
                    continue

                for symbol in config.INSTRUMENTS:
                    await self._check_symbol(symbol)

                await asyncio.sleep(0.3)

            except Exception as e:
                logger.error(f"Tick momentum error: {e}")
                await asyncio.sleep(1)

    async def _check_symbol(self, symbol: str):
        if symbol in self.active_trends:
            return

        buffer = self.parasite.nervous_system.tick_buffers.get(symbol)
        if not buffer or len(buffer) < 10:
            return

        latest = buffer[-1]

        if latest.tick_velocity < 6.0:
            return
        if latest.spread_ratio > 1.3:
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

        if consecutive < 3:
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

        self.active_trends[symbol] = {
            "trade_id": trade_id, "symbol": symbol, "direction": dir_str,
            "entry_price": tick.ask if direction == 1 else tick.bid,
            "risk_amount": risk_amount,
            "pyramid_level": 0, "consecutive_count": 0,
            "opened_at": time.time(), "order_id": order.get("orderId", ""),
        }

        asyncio.create_task(self._monitor_trend(symbol))
        logger.layer("tick_momentum", "ENTER", f"{symbol} {dir_str}")

    async def _monitor_trend(self, symbol: str):
        position = self.active_trends.get(symbol)
        if not position:
            return

        while symbol in self.active_trends:
            await asyncio.sleep(0.2)

            buffer = self.parasite.nervous_system.tick_buffers.get(symbol)
            if not buffer or len(buffer) < 2:
                continue

            latest = buffer[-1]
            pos = self.active_trends.get(symbol)
            if not pos:
                break

            direction = pos["direction"]

            if (direction == "BUY" and latest.direction == -1) or (direction == "SELL" and latest.direction == 1):
                exit_price = latest.bid if direction == "BUY" else latest.ask
                await self._exit_trend(symbol, exit_price)
                break

            if latest.direction == (1 if direction == "BUY" else -1):
                pos["consecutive_count"] += 1
                if pos["consecutive_count"] >= 3 and pos["pyramid_level"] < 4:
                    add_size = pos["risk_amount"] * 0.5
                    await self.parasite.execution._place_order(symbol, direction, add_size)
                    pos["pyramid_level"] += 1
                    pos["consecutive_count"] = 0
            else:
                pos["consecutive_count"] = 0

    async def _exit_trend(self, symbol: str, exit_price: float):
        position = self.active_trends.pop(symbol, None)
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
            "instrument": symbol, "layer": "tick_momentum", "branch_id": "",
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

        logger.trade("CLOSE", symbol, "tick_momentum", {"r": round(r_multiple, 3)})

    def get_stats(self) -> dict:
        return {
            "active": self.running,
            "total_trades": self.total_trades,
            "wins": self.total_wins,
            "win_rate": self.total_wins / max(self.total_trades, 1),
            "total_r": round(self.total_r, 2),
            "avg_r": round(self.total_r / max(self.total_trades, 1), 3),
        }