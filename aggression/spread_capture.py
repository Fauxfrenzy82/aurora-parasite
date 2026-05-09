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
    """
    Captures spread expansions by placing limit orders on both sides.
    When one fills, the other becomes the exit. Exploits mean reversion
    of synthetic index spreads.
    """

    def __init__(self, parasite):
        self.parasite = parasite
        self.running = False
        self.active_captures: dict = {}
        self.total_trades = 0
        self.total_wins = 0
        self.total_r = 0.0
        self.last_activity = time.time()

    async def run(self):
        """Main spread capture loop."""
        self.running = True
        logger.info("Spread Capture Engine online")

        while self.running:
            try:
                if self.parasite.halted:
                    await asyncio.sleep(1)
                    continue

                for symbol in config.INSTRUMENTS:
                    await self._check_symbol(symbol)

                await asyncio.sleep(0.5)  # Check every 500ms

            except Exception as e:
                logger.error(f"Spread capture error: {e}")
                await asyncio.sleep(1)

    async def _check_symbol(self, symbol: str):
        """Check if spread capture conditions are met for a symbol."""
        # Skip if already capturing this symbol
        if symbol in self.active_captures:
            return

        # Skip if at max positions per instrument
        existing = [
            p for p in self.parasite.execution.active_positions.values()
            if p["symbol"] == symbol and p["layer"] == "spread_capture"
        ]
        if len(existing) >= config.MAX_POSITIONS_PER_INSTRUMENT:
            return

        # Get latest tick data
        buffer = self.parasite.nervous_system.tick_buffers.get(symbol)
        if not buffer or len(buffer) < 10:
            return

        latest = buffer[-1]

        # Check conditions:
        # 1. Tick velocity below threshold (quiet market)
        # 2. Spread above threshold (widened — capture opportunity)
        if latest.tick_velocity > config.SPREAD_CAPTURE_MAX_VELOCITY:
            return
        if latest.spread_ratio < config.SPREAD_CAPTURE_SPREAD_RATIO:
            return

        # Execute bidirectional capture
        await self._execute_capture(symbol, latest.bid, latest.ask)

    async def _execute_capture(self, symbol: str, bid: float, ask: float):
        """Execute a spread capture on both sides."""
        capture_id = f"SC_{uuid.uuid4().hex[:8]}"
        risk_pct = config.LAYER_RISK.get("spread_capture", 0.003)
        risk_amount = config.INITIAL_CAPITAL * risk_pct

        # Place buy at bid
        buy_order = await self.parasite.execution._place_order(
            symbol, "BUY", bid, risk_amount
        )
        # Place sell at ask
        sell_order = await self.parasite.execution._place_order(
            symbol, "SELL", ask, risk_amount
        )

        if not buy_order or not sell_order:
            return

        self.active_captures[symbol] = {
            "capture_id": capture_id,
            "symbol": symbol,
            "bid": bid,
            "ask": ask,
            "buy_order_id": buy_order.get("orderId", ""),
            "sell_order_id": sell_order.get("orderId", ""),
            "risk_amount": risk_amount,
            "opened_at": time.time(),
        }

        # Monitor for fill and exit
        asyncio.create_task(self._monitor_capture(symbol, capture_id))

        logger.layer("spread_capture", "OPEN", f"{symbol} bid={bid:.5f} ask={ask:.5f}")

    async def _monitor_capture(self, symbol: str, capture_id: str):
        """Monitor capture for fill and manage exit."""
        capture = self.active_captures.get(symbol)
        if not capture:
            return

        start_time = time.time()
        max_duration = config.SPREAD_CAPTURE_MAX_DURATION

        while symbol in self.active_captures:
            await asyncio.sleep(0.1)

            elapsed = time.time() - start_time
            if elapsed > max_duration:
                # Timeout — cancel both
                await self._cancel_capture(symbol)
                break

            # Check if price moved against us
            buffer = self.parasite.nervous_system.tick_buffers.get(symbol)
            if not buffer or len(buffer) < 2:
                continue

            current_mid = buffer[-1].mid_price
            entry_mid = (capture["bid"] + capture["ask"]) / 2

            # If price moved more than 1.5x the spread, exit
            spread = capture["ask"] - capture["bid"]
            if abs(current_mid - entry_mid) > spread * 1.5:
                await self._cancel_capture(symbol)
                break

            # Simulate fill detection (in production, poll order status)
            if len(buffer) >= 5:
                # Assume buy filled if price touched bid
                if buffer[-1].bid <= capture["bid"]:
                    await self._close_capture(symbol, "BUY", capture["bid"])
                    break
                # Assume sell filled if price touched ask
                if buffer[-1].ask >= capture["ask"]:
                    await self._close_capture(symbol, "SELL", capture["ask"])
                    break

    async def _close_capture(self, symbol: str, filled_side: str, fill_price: float):
        """Close a filled capture and record result."""
        capture = self.active_captures.pop(symbol, None)
        if not capture:
            return

        # The other side is the exit
        exit_price = capture["ask"] if filled_side == "BUY" else capture["bid"]
        spread = capture["ask"] - capture["bid"]
        r_multiple = spread / (capture["risk_amount"] / 0.01) if capture["risk_amount"] > 0 else 0

        trade_data = {
            "trade_id": f"TRD_{capture['capture_id']}",
            "instrument": symbol,
            "layer": "spread_capture",
            "branch_id": "",
            "direction": filled_side,
            "entry_price": fill_price,
            "exit_price": exit_price,
            "r_multiple": round(r_multiple, 4),
            "profit_currency": round(r_multiple * capture["risk_amount"], 4),
            "duration_ms": int((time.time() - capture["opened_at"]) * 1000),
        }

        await self.parasite.record_trade(trade_data)
        self.total_trades += 1
        if r_multiple > 0:
            self.total_wins += 1
        self.total_r += r_multiple

        logger.trade("CLOSE", symbol, "spread_capture", {"r": round(r_multiple, 3)})

    async def _cancel_capture(self, symbol: str):
        """Cancel an unfilled capture (loss)."""
        capture = self.active_captures.pop(symbol, None)
        if not capture:
            return

        loss_r = -0.4  # Estimated loss for timeout/unfavorable move
        trade_data = {
            "trade_id": f"TRD_{capture['capture_id']}",
            "instrument": symbol,
            "layer": "spread_capture",
            "branch_id": "",
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