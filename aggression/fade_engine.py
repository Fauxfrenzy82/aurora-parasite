"""
Fade Engine — Layer 3.
Fades panic spikes. Independent of cortex.
"""

import asyncio
import time
import uuid
from config import config
from logger import get_logger

logger = get_logger("fade_engine")


class FadeEngine:
    """Detects panic spikes and places fade orders."""

    def __init__(self, parasite):
        self.parasite = parasite
        self.running = False
        self.active_fades: dict = {}
        self.total_trades = 0
        self.total_wins = 0
        self.total_r = 0.0

    async def run(self):
        self.running = True
        logger.info("Fade Engine online — INDEPENDENT MODE")

        while self.running:
            try:
                if self.parasite.halted:
                    await asyncio.sleep(1)
                    continue

                for symbol in config.INSTRUMENTS:
                    await self._check_symbol(symbol)

                await asyncio.sleep(0.15)

            except Exception as e:
                logger.error(f"Fade engine error: {e}")
                await asyncio.sleep(0.5)

    async def _check_symbol(self, symbol: str):
        buffer = self.parasite.nervous_system.tick_buffers.get(symbol)
        if not buffer or len(buffer) < 8:
            return

        latest = buffer[-1]

        if latest.tick_velocity < config.FADE_VELOCITY_SPIKE:
            return
        if latest.spread_ratio < config.FADE_SPREAD_RATIO:
            return
        if latest.price_jump < config.FADE_PRICE_JUMP:
            return

        if len(buffer) >= 3:
            recent_move = buffer[-1].mid_price - buffer[-3].mid_price
            if abs(recent_move) < config.FADE_PRICE_JUMP * buffer[-3].mid_price:
                return
            spike_direction = "BUY" if recent_move > 0 else "SELL"
        else:
            return

        fade_direction = "SELL" if spike_direction == "BUY" else "BUY"
        await self._enter_fade(symbol, fade_direction, latest)

    async def _enter_fade(self, symbol: str, direction: str, tick):
        trade_id = f"FD_{uuid.uuid4().hex[:8]}"
        risk_pct = config.LAYER_RISK.get("fade_engine", 0.007)
        risk_amount = config.INITIAL_CAPITAL * risk_pct

        order = await self.parasite.execution._place_order(symbol, direction, risk_amount)
        if not order:
            return

        self.active_fades[trade_id] = {
            "trade_id": trade_id, "symbol": symbol, "direction": direction,
            "entry_price": tick.ask if direction == "BUY" else tick.bid,
            "risk_amount": risk_amount, "opened_at": time.time(),
            "order_id": order.get("orderId", ""),
        }

        asyncio.create_task(self._monitor_fade(trade_id))
        logger.layer("fade_engine", "ENTER", f"{symbol} {direction}")

    async def _monitor_fade(self, trade_id: str):
        position = self.active_fades.get(trade_id)
        if not position:
            return

        symbol = position["symbol"]
        direction = position["direction"]
        entry_price = position["entry_price"]
        risk = position["risk_amount"]

        while trade_id in self.active_fades:
            await asyncio.sleep(0.15)

            buffer = self.parasite.nervous_system.tick_buffers.get(symbol)
            if not buffer or len(buffer) < 2:
                continue

            current_mid = buffer[-1].mid_price

            # Profit on reversion
            if direction == "SELL" and current_mid <= entry_price:
                await self._exit_fade(trade_id, current_mid)
                break
            if direction == "BUY" and current_mid >= entry_price:
                await self._exit_fade(trade_id, current_mid)
                break

            # Stop loss
            if direction == "SELL" and current_mid > entry_price + (risk / 0.01) * 1.2:
                await self._exit_fade(trade_id, current_mid)
                break
            if direction == "BUY" and current_mid < entry_price - (risk / 0.01) * 1.2:
                await self._exit_fade(trade_id, current_mid)
                break

    async def _exit_fade(self, trade_id: str, exit_price: float):
        position = self.active_fades.pop(trade_id, None)
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
            "instrument": position["symbol"], "layer": "fade_engine", "branch_id": "",
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

        logger.trade("CLOSE", position["symbol"], "fade_engine", {"r": round(r_multiple, 3)})

    def get_stats(self) -> dict:
        return {
            "active": self.running,
            "total_trades": self.total_trades,
            "wins": self.total_wins,
            "win_rate": self.total_wins / max(self.total_trades, 1),
            "total_r": round(self.total_r, 2),
            "avg_r": round(self.total_r / max(self.total_trades, 1), 3),
        }