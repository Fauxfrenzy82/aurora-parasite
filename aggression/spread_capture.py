"""
Spread Capture Engine — Layer 1.
Bidirectional spread capture during low-volatility regimes.
Places simultaneous buy/sell limit orders and captures the spread.
"""

import asyncio
import time
import uuid
from config import config
from logger import get_logger

logger = get_logger("spread_capture")


class SpreadCapture:
    """Captures spread expansions by placing limit orders on both sides."""

    def __init__(self, parasite):
        self.parasite = parasite
        self.running = False
        self.active_captures: dict = {}
        self.total_trades = 0
        self.total_wins = 0
        self.total_r = 0.0
        self.last_activity = time.time()
        self._cooldowns: dict = {}

    async def run(self):
        self.running = True
        logger.info("Spread Capture Engine online")

        while self.running:
            try:
                if self.parasite.halted:
                    await asyncio.sleep(1)
                    continue

                for symbol in config.INSTRUMENTS:
                    await self._check_symbol(symbol)

                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Spread capture error: {e}")
                await asyncio.sleep(1)

    async def _check_symbol(self, symbol: str):
        if symbol in self.active_captures:
            return

        if symbol in self._cooldowns and time.time() < self._cooldowns[symbol]:
            return

        existing = [
            p for p in self.parasite.execution.active_positions.values()
            if p["symbol"] == symbol and p["layer"] == "spread_capture"
        ]
        if len(existing) >= config.MAX_POSITIONS_PER_INSTRUMENT:
            return

        buffer = self.parasite.nervous_system.tick_buffers.get(symbol)
        if not buffer or len(buffer) < 20:
            return

        latest = buffer[-1]

        if latest.tick_velocity > config.SPREAD_CAPTURE_MAX_VELOCITY:
            return
        if latest.spread_ratio < config.SPREAD_CAPTURE_SPREAD_RATIO:
            return

        spread = latest.ask - latest.bid
        if spread <= 0 or spread > latest.mid_price * 0.01:
            return

        await self._execute_capture(symbol, latest.bid, latest.ask)

    async def _execute_capture(self, symbol: str, bid: float, ask: float):
        capture_id = f"SC_{uuid.uuid4().hex[:8]}"
        risk_pct = config.LAYER_RISK.get("spread_capture", 0.003)
        risk_amount = config.INITIAL_CAPITAL * risk_pct

        buy_order = await self.parasite.execution._place_order(symbol, "BUY", risk_amount)
        sell_order = await self.parasite.execution._place_order(symbol, "SELL", risk_amount)

        if not buy_order or not sell_order:
            return

        self.active_captures[symbol] = {
            "capture_id": capture_id, "symbol": symbol,
            "bid": bid, "ask": ask,
            "buy_order_id": buy_order.get("orderId", ""),
            "sell_order_id": sell_order.get("orderId", ""),
            "risk_amount": risk_amount, "opened_at": time.time(),
        }

        asyncio.create_task(self._monitor_capture(symbol, capture_id))
        logger.layer("spread_capture", "OPEN", f"{symbol} bid={bid:.5f} ask={ask:.5f}")

    async def _monitor_capture(self, symbol: str, capture_id: str):
        capture = self.active_captures.get(symbol)
        if not capture:
            return

        start_time = time.time()
        max_duration = config.SPREAD_CAPTURE_MAX_DURATION
        min_hold = 3.0
        check_interval = 0.3

        while symbol in self.active_captures:
            await asyncio.sleep(check_interval)
            elapsed = time.time() - start_time

            if elapsed < min_hold:
                continue

            if elapsed > max_duration:
                await self._cancel_capture(symbol)
                break

            buffer = self.parasite.nervous_system.tick_buffers.get(symbol)
            if not buffer or len(buffer) < 5:
                continue

            current_mid = buffer[-1].mid_price
            entry_mid = (capture["bid"] + capture["ask"]) / 2
            spread = capture["ask"] - capture["bid"]

            if spread <= 0:
                continue

            if abs(current_mid - entry_mid) > spread * 2.0:
                await self._cancel_capture(symbol)
                break

            recent_ticks = list(buffer)[-5:]
            recent_lows = min(t.bid for t in recent_ticks)
            recent_highs = max(t.ask for t in recent_ticks)

            if recent_lows <= capture["bid"]:
                exit_price = capture["ask"]
                await self._close_capture(symbol, "BUY", capture["bid"], exit_price)
                break

            if recent_highs >= capture["ask"]:
                exit_price = capture["bid"]
                await self._close_capture(symbol, "SELL", capture["ask"], exit_price)
                break

    async def _close_capture(self, symbol: str, filled_side: str, fill_price: float, exit_price: float):
        capture = self.active_captures.pop(symbol, None)
        if not capture:
            return

        self._cooldowns[symbol] = time.time() + 2.0

        spread = capture["ask"] - capture["bid"]
        risk_amount = capture["risk_amount"]

        if filled_side == "BUY":
            profit = exit_price - fill_price
        else:
            profit = fill_price - exit_price

        r_multiple = profit / spread if spread > 0 else 0

        trade_data = {
            "trade_id": f"TRD_{capture['capture_id']}",
            "instrument": symbol, "layer": "spread_capture", "branch_id": "",
            "direction": filled_side, "entry_price": fill_price, "exit_price": exit_price,
            "r_multiple": round(r_multiple, 4),
            "profit_currency": round(r_multiple * risk_amount, 4),
            "duration_ms": int((time.time() - capture["opened_at"]) * 1000),
        }

        await self.parasite.record_trade(trade_data)
        self.total_trades += 1
        if r_multiple > 0:
            self.total_wins += 1
        self.total_r += r_multiple

        logger.trade("CLOSE", symbol, "spread_capture", {"r": round(r_multiple, 3)})

    async def _cancel_capture(self, symbol: str):
        capture = self.active_captures.pop(symbol, None)
        if not capture:
            return

        self._cooldowns[symbol] = time.time() + 2.0

        loss_r = -0.5
        trade_data = {
            "trade_id": f"TRD_{capture['capture_id']}",
            "instrument": symbol, "layer": "spread_capture", "branch_id": "",
            "direction": "CANCEL",
            "entry_price": (capture["bid"] + capture["ask"]) / 2,
            "exit_price": (capture["bid"] + capture["ask"]) / 2,
            "r_multiple": loss_r,
            "profit_currency": round(loss_r * capture["risk_amount"], 4),
            "duration_ms": int((time.time() - capture["opened_at"]) * 1000),
        }

        await self.parasite.record_trade(trade_data)
        self.total_trades += 1
        self.total_r += loss_r

    def get_stats(self) -> dict:
        return {
            "active": self.running,
            "total_trades": self.total_trades,
            "wins": self.total_wins,
            "win_rate": self.total_wins / max(self.total_trades, 1),
            "total_r": round(self.total_r, 2),
            "avg_r": round(self.total_r / max(self.total_trades, 1), 3),
        }