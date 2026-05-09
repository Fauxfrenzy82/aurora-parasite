"""
News Scalper — Layer 4.
Detects simultaneous volatility spikes across multiple instruments.
"""

import asyncio
import time
import uuid
from config import config
from logger import get_logger

logger = get_logger("news_scalper")


class NewsScalper:
    """Detects news events and trades post-news volatility collapse."""

    def __init__(self, parasite):
        self.parasite = parasite
        self.running = False
        self.active_scalps: dict = {}
        self.total_trades = 0
        self.total_wins = 0
        self.total_r = 0.0
        self.news_detected = False
        self.last_news_time = 0
        self.news_cooldown = 120

    async def run(self):
        self.running = True
        logger.info("News Scalper online")

        while self.running:
            try:
                if self.parasite.halted:
                    await asyncio.sleep(1)
                    continue

                await self._detect_news()
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"News scalper error: {e}")
                await asyncio.sleep(1)

    async def _detect_news(self):
        if self.news_detected:
            now = time.time()
            if now - self.last_news_time > 60:
                self.news_detected = False
            return

        spike_count = 0
        spike_symbols = []

        for symbol in config.INSTRUMENTS:
            buffer = self.parasite.nervous_system.tick_buffers.get(symbol)
            if not buffer or len(buffer) < 5:
                continue

            latest = buffer[-1]
            if latest.tick_velocity > 15.0:
                spike_count += 1
                spike_symbols.append(symbol)

        if spike_count >= 2:
            now = time.time()
            if now - self.last_news_time < self.news_cooldown:
                return

            self.news_detected = True
            self.last_news_time = now
            logger.info(f"NEWS DETECTED — {spike_count} instruments spiking")

            for symbol in spike_symbols[:3]:
                await self._execute_straddle(symbol)

    async def _execute_straddle(self, symbol: str):
        trade_id = f"NW_{uuid.uuid4().hex[:8]}"
        risk_pct = config.LAYER_RISK.get("news_scalper", 0.01)
        risk_amount = config.INITIAL_CAPITAL * risk_pct

        buffer = self.parasite.nervous_system.tick_buffers.get(symbol)
        if not buffer:
            return
        tick = buffer[-1]

        buy_order = await self.parasite.execution._place_order(symbol, "BUY", risk_amount)
        sell_order = await self.parasite.execution._place_order(symbol, "SELL", risk_amount)

        if not buy_order or not sell_order:
            return

        self.active_scalps[symbol] = {
            "trade_id": trade_id, "symbol": symbol,
            "entry_buy": tick.ask, "entry_sell": tick.bid,
            "risk_amount": risk_amount,
            "buy_order_id": buy_order.get("orderId", ""),
            "sell_order_id": sell_order.get("orderId", ""),
            "opened_at": time.time(),
            "buy_exited": False, "sell_exited": False,
            "buy_r": 0.0, "sell_r": 0.0,
        }

        asyncio.create_task(self._monitor_straddle(symbol))
        logger.layer("news_scalper", "STRADDLE", f"{symbol}")

    async def _monitor_straddle(self, symbol: str):
        position = self.active_scalps.get(symbol)
        if not position:
            return

        trail_stop_pct = 0.001
        buy_high = position["entry_buy"]
        sell_low = position["entry_sell"]
        risk = position["risk_amount"]

        while symbol in self.active_scalps:
            await asyncio.sleep(0.3)

            buffer = self.parasite.nervous_system.tick_buffers.get(symbol)
            if not buffer or len(buffer) < 2:
                continue

            current_mid = buffer[-1].mid_price
            pos = self.active_scalps.get(symbol)
            if not pos:
                break

            if not pos["buy_exited"] and current_mid > buy_high:
                buy_high = current_mid
            if not pos["buy_exited"] and current_mid < buy_high * (1 - trail_stop_pct):
                pos["buy_exited"] = True
                pos["buy_r"] = (current_mid - pos["entry_buy"]) / (risk / 0.01) if risk > 0 else 0

            if not pos["sell_exited"] and current_mid < sell_low:
                sell_low = current_mid
            if not pos["sell_exited"] and current_mid > sell_low * (1 + trail_stop_pct):
                pos["sell_exited"] = True
                pos["sell_r"] = (pos["entry_sell"] - current_mid) / (risk / 0.01) if risk > 0 else 0

            if pos["buy_exited"] and pos["sell_exited"]:
                await self._close_straddle(symbol)
                break

    async def _close_straddle(self, symbol: str):
        position = self.active_scalps.pop(symbol, None)
        if not position:
            return

        combined_r = position["buy_r"] + position["sell_r"]
        risk = position["risk_amount"]

        trade_data = {
            "trade_id": f"TRD_{position['trade_id']}",
            "instrument": symbol, "layer": "news_scalper", "branch_id": "",
            "direction": "STRADDLE",
            "entry_price": (position["entry_buy"] + position["entry_sell"]) / 2,
            "exit_price": 0, "r_multiple": round(combined_r, 4),
            "profit_currency": round(combined_r * risk, 4),
            "duration_ms": int((time.time() - position["opened_at"]) * 1000),
        }

        await self.parasite.record_trade(trade_data)
        self.total_trades += 1
        if combined_r > 0:
            self.total_wins += 1
        self.total_r += combined_r

        logger.trade("CLOSE", symbol, "news_scalper", {"r": round(combined_r, 3)})

    def get_stats(self) -> dict:
        return {
            "active": self.running,
            "total_trades": self.total_trades,
            "wins": self.total_wins,
            "win_rate": self.total_wins / max(self.total_trades, 1),
            "total_r": round(self.total_r, 2),
            "avg_r": round(self.total_r / max(self.total_trades, 1), 3),
        }