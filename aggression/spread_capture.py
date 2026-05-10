"""
Spread Capture Engine — Layer 1.
Bidirectional spread capture during low-volatility regimes.
Upgraded: No cooldowns. 3 positions per instrument. Faster checks.
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

    async def run(self):
        self.running = True
        logger.info("Spread Capture Engine online — AGGRESSIVE MODE")

        while self.running:
            try:
                if self.parasite.halted:
                    await asyncio.sleep(1)
                    continue

                for symbol in config.INSTRUMENTS:
                    await self._check_symbol(symbol)

                await asyncio.sleep(0.1)  # Was 0.5 — 5x faster

            except Exception as e:
                logger.error(f"Spread capture error: {e}")
                await asyncio.sleep(0.5)

    async def _check_symbol(self, symbol: str):
        buffer = self.parasite.nervous_system.tick_buffers.get(symbol)
        if not buffer or len(buffer) < 10:
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

        self.active_captures[capture_id] = {
            "capture_id": capture_id, "symbol": symbol,
            "bid": bid, "ask": ask,
            "buy_order_id": buy_order.get("orderId", ""),
            "sell_order_id": sell_order.get("orderId", ""),
            "risk_amount": risk_amount, "opened_at": time.time(),
        }

        asyncio.create_task(self._monitor_capture(capture_id))
        logger.layer("spread_capture", "OPEN", f"{symbol} bid={bid:.5f} ask={ask:.5f}")

    async def _monitor_capture(self, capture_id: str):
        capture = self.active_captures.get(capture_id)
        if not capture:
            return

        symbol = capture["symbol"]
        start_time = time.time()
        min_hold = 1.0  # Was 3.0 — faster turnover
        max_duration = config.SPREAD_CAPTURE_MAX_DURATION

        while capture_id in self.active_captures:
            await asyncio.sleep(0.15)

            elapsed = time.time() - start_time
            if elapsed < min_hold:
                continue
            if elapsed > max_duration:
                await self._cancel_capture(capture_id)
                break

            buffer = self.parasite.nervous_system.tick_buffers.get(symbol)
            if not buffer or len(buffer) < 3:
                continue

            current_mid = buffer[-1].mid_price
            entry_mid = (capture["bid"] + capture["ask"]) / 2
            spread = capture["ask"] - capture["bid"]

            if spread <= 0:
                continue

            if abs(current_mid - entry_mid) > spread * 2.0:
                await self._cancel_capture(capture_id)
                break

            recent_ticks = list(buffer)[-3:]
            recent_lows = min(t.bid for t in recent_ticks)
            recent_highs = max(t.ask for t in recent_ticks)

            if recent_lows <= capture["bid"]:
                exit_price = capture["ask"]
                await self._close_capture(capture_id, "BUY", capture["bid"], exit_price)
                break

            if recent_highs >= capture["ask"]:
                exit_price = capture["bid"]
                await self._close_capture(capture_id, "SELL", capture["ask"], exit_price)
                break

    async def _close_capture(self, capture_id: str, filled_side: str, fill_price: float, exit_price: float):
        capture = self.active_captures.pop(capture_id, None)
        if not capture:
            return

        spread = capture["ask"] - capture["bid"]
        risk_amount = capture["risk_amount"]

        if filled_side == "BUY":
            profit = exit_price - fill_price
        else:
            profit = fill_price - exit_price

        r_multiple = profit / spread if spread > 0 else 0

        trade_data = {
            "trade_id": f"TRD_{capture['capture_id']}",
            "instrument": capture["symbol"], "layer": "spread_capture", "branch_id": "",
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

        logger.trade("CLOSE", capture["symbol"], "spread_capture", {"r": round(r_multiple, 3)})

    async def _cancel_capture(self, capture_id: str):
        capture = self.active_captures.pop(capture_id, None)
        if not capture:
            return

        loss_r = -0.5
        trade_data = {
            "trade_id": f"TRD_{capture['capture_id']}",
            "instrument": capture["symbol"], "layer": "spread_capture", "branch_id": "",
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