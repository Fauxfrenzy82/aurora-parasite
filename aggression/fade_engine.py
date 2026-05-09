"""
Fade Engine — Layer 3.
Fades panic spikes by placing limit orders into the spike.
Exploits temporary liquidity imbalances that revert rapidly.
"""

import asyncio
import time
import uuid
from config import config
from logger import get_logger

logger = get_logger("fade_engine")


class FadeEngine:
    """
    Detects panic spikes (velocity surge + spread expansion + price jump)
    and places fade orders expecting rapid reversion.
    """

    def __init__(self, parasite):
        self.parasite = parasite
        self.running = False
        self.active_fades: dict = {}
        self.total_trades = 0
        self.total_wins = 0
        self.total_r = 0.0

    async def run(self):
        """Main fade engine loop."""
        self.running = True
        logger.info("Fade Engine online")

        while self.running:
            try:
                if self.parasite.halted:
                    await asyncio.sleep(1)
                    continue

                for symbol in config.INSTRUMENTS:
                    await self._check_symbol(symbol)

                await asyncio.sleep(0.4)

            except Exception as e:
                logger.error(f"Fade engine error: {e}")
                await asyncio.sleep(1)

    async def _check_symbol(self, symbol: str):
        """Check for panic spike conditions."""
        if symbol in self.active_fades:
            return

        buffer = self.parasite.nervous_system.tick_buffers.get(symbol)
        if not buffer or len(buffer) < 10:
            return

        latest = buffer[-1]

        # Conditions:
        # 1. Velocity spike
        # 2. Spread expansion
        # 3. Price jump
        if latest.tick_velocity < config.FADE_VELOCITY_SPIKE:
            return
        if latest.spread_ratio < config.FADE_SPREAD_RATIO:
            return
        if latest.price_jump < config.FADE_PRICE_JUMP:
            return

        # Determine the spike direction
        if len(buffer) >= 3:
            recent_move = buffer[-1].mid_price - buffer[-3].mid_price
            if abs(recent_move) < config.FADE_PRICE_JUMP * buffer[-3].mid_price:
                return
            spike_direction = "BUY" if recent_move > 0 else "SELL"
        else:
            return

        # Fade: enter against the spike
        fade_direction = "SELL" if spike_direction == "BUY" else "BUY"
        await self._enter_fade(symbol, fade_direction, latest)

    async def _enter_fade(self, symbol: str, direction: str, tick):
        """Enter a fade position."""
        trade_id = f"FD_{uuid.uuid4().hex[:8]}"
        risk_pct = config.LAYER_RISK.get("fade_engine", 0.007)
        risk_amount = config.INITIAL_CAPITAL * risk_pct

        entry_price = tick.ask if direction == "BUY" else tick.bid

        order = await self.parasite.execution._place_order(
            symbol, direction, entry_price, risk_amount
        )
        if not order:
            return

        self.active_fades[symbol] = {
            "trade_id": trade_id,
            "symbol": symbol,
            "direction": direction,
            "entry_price": entry_price,
            "risk_amount": risk_amount,
            "opened_at": time.time(),
            "order_id": order.get("orderId", ""),
        }

        asyncio.create_task(self._monitor_fade(symbol))
        logger.layer("fade_engine", "ENTER", f"{symbol} {direction} @ {entry_price:.5f}")

    async def _monitor_fade(self, symbol: str):
        """Monitor fade for reversion or timeout."""
        position = self.active_fades.get(symbol)
        if not position:
            return

        start_time = time.time()
        max_duration = config.FADE_MAX_DURATION
        entry_price = position["entry_price"]

        while symbol in self.active_fades:
            await asyncio.sleep(0.3)

            buffer = self.parasite.nervous_system.tick_buffers.get(symbol)
            if not buffer or len(buffer) < 2:
                continue

            elapsed = time.time() - start_time
            current_mid = buffer[-1].mid_price

            # Exit on reversion (price returns to pre-spike level)
            if position["direction"] == "SELL":
                if current_mid <= entry_price:
                    await self._exit_fade(symbol, current_mid)
                    break
            else:
                if current_mid >= entry_price:
                    await self._exit_fade(symbol, current_mid)
                    break

            # Timeout exit
            if elapsed > max_duration:
                exit_price = buffer[-1].bid if position["direction"] == "SELL" else buffer[-1].ask
                await self._exit_fade(symbol, exit_price)
                break

            # Stop loss: if price continues 1.5R against us
            risk = position["risk_amount"]
            if position["direction"] == "SELL":
                if current_mid > entry_price + (risk / 0.01) * 1.5:
                    await self._exit_fade(symbol, current_mid)
                    break
            else:
                if current_mid < entry_price - (risk / 0.01) * 1.5:
                    await self._exit_fade(symbol, current_mid)
                    break

    async def _exit_fade(self, symbol: str, exit_price: float):
        """Exit fade and record result."""
        position = self.active_fades.pop(symbol, None)
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
            "instrument": symbol,
            "layer": "fade_engine",
            "branch_id": "",
            "direction": direction,
            "entry_price": entry,
            "exit_price": exit_price,
            "r_multiple": round(r_multiple, 4),
            "profit_currency": round(r_multiple * risk, 4),
            "duration_ms": int((time.time() - position["opened_at"]) * 1000),
        }

        await self.parasite.record_trade(trade_data)
        self.total_trades += 1
        if r_multiple > 0:
            self.total_wins += 1
        self.total_r += r_multiple

        logger.trade("CLOSE", symbol, "fade_engine", {"r": round(r_multiple, 3)})

    def get_stats(self) -> dict:
        return {
            "active": self.running,
            "total_trades": self.total_trades,
            "wins": self.total_wins,
            "win_rate": self.total_wins / max(self.total_trades, 1),
            "total_r": round(self.total_r, 2),
            "avg_r": round(self.total_r / max(self.total_trades, 1), 3),
        }