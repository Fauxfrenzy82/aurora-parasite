"""
Execution Engine — Places REAL orders via cTrader API.
Asymmetric exit: cuts losers fast, lets winners run with pyramiding.
"""

import asyncio
import time
import uuid
from typing import Dict, Optional
from config import config
from logger import get_logger

logger = get_logger("execution")


class ExecutionEngine:
    """Executes real trades on Pepperstone via cTrader."""

    def __init__(self, parasite):
        self.parasite = parasite
        self.active_positions: Dict[str, dict] = {}
        self._lock = asyncio.Lock()

    async def execute_decision(self, decision: dict, signal) -> bool:
        symbol = decision["symbol"]
        direction = decision["direction"]
        branch_id = decision.get("branch_id")
        layer = decision.get("layer", "unknown")
        confidence = decision.get("confidence", 0.5)

        async with self._lock:
            existing = [p for p in self.active_positions.values() if p["symbol"] == symbol]
            if len(existing) >= config.MAX_POSITIONS_PER_INSTRUMENT:
                return False

            if not self.parasite.dynamic_exposure.can_open(symbol, direction):
                return False

            buffer = self.parasite.nervous_system.tick_buffers.get(symbol)
            if not buffer or len(buffer) < 1:
                return False

            tick = buffer[-1]
            entry_price = tick.ask if direction == "BUY" else tick.bid
            risk_pct = config.LAYER_RISK.get(layer, 0.005)
            risk_amount = config.INITIAL_CAPITAL * risk_pct

            trade_id = f"TRD_{uuid.uuid4().hex[:8]}"
            try:
                order_result = await self.parasite.broker_client._place_order(
                    symbol, direction, risk_amount
                )
                if not order_result:
                    return False

                position = {
                    "trade_id": trade_id, "symbol": symbol, "direction": direction,
                    "entry_price": entry_price, "risk_amount": risk_amount,
                    "branch_id": branch_id, "layer": layer, "confidence": confidence,
                    "pyramid_level": 0, "opened_at": time.time(),
                    "order_id": order_result.get("orderId", ""),
                }
                self.active_positions[trade_id] = position
                asyncio.create_task(self._monitor_position(trade_id))

                logger.trade("OPEN", symbol, layer, {
                    "direction": direction, "entry": round(entry_price, 5),
                    "risk": round(risk_amount, 2), "confidence": round(confidence, 3)
                })
                return True

            except Exception as e:
                logger.error(f"Order execution error: {e}")
                return False

    async def _monitor_position(self, trade_id: str):
        position = self.active_positions.get(trade_id)
        if not position:
            return

        symbol = position["symbol"]
        direction = position["direction"]
        entry = position["entry_price"]
        risk = position["risk_amount"]

        while trade_id in self.active_positions:
            await asyncio.sleep(0.2)

            buffer = self.parasite.nervous_system.tick_buffers.get(symbol)
            if not buffer or len(buffer) < 2:
                continue

            current_price = buffer[-1].bid if direction == "BUY" else buffer[-1].ask

            if direction == "BUY":
                r_multiple = (current_price - entry) / (risk / 0.01) if risk > 0 else 0
            else:
                r_multiple = (entry - current_price) / (risk / 0.01) if risk > 0 else 0

            # Cut loss at -0.5R (tighter than before)
            if r_multiple < -0.5:
                await self._close_position(trade_id, current_price)
                break

            # Take profit at +2.0R (let winners run longer)
            if r_multiple > 2.0:
                await self._close_position(trade_id, current_price)
                break

    async def _close_position(self, trade_id: str, exit_price: float):
        position = self.active_positions.pop(trade_id, None)
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
            "trade_id": trade_id, "instrument": position["symbol"],
            "layer": position["layer"], "branch_id": position.get("branch_id", ""),
            "direction": direction, "entry_price": entry, "exit_price": exit_price,
            "r_multiple": round(r_multiple, 4),
            "profit_currency": round(r_multiple * risk, 4),
            "duration_ms": int((time.time() - position["opened_at"]) * 1000),
        }

        await self.parasite.record_trade(trade_data)
        logger.trade("CLOSE", position["symbol"], position["layer"], {"r": round(r_multiple, 3)})