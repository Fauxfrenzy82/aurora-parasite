"""
Execution Engine — Asymmetric money management with micro-pyramiding.
"""

import asyncio
import time
import uuid
from typing import Dict, Optional
from config import config
from logger import get_logger

logger = get_logger("execution")


class ExecutionEngine:
    """Executes trades with asymmetric risk management."""

    def __init__(self, parasite):
        self.parasite = parasite
        self.active_positions: Dict[str, dict] = {}
        self._lock = asyncio.Lock()

    async def execute_decision(self, decision: dict, signal) -> bool:
        """Execute a trading decision from the cortex."""
        symbol = decision["symbol"]
        direction = decision["direction"]
        branch_id = decision.get("branch_id")
        layer = decision.get("layer", "unknown")
        confidence = decision.get("confidence", 0.5)

        async with self._lock:
            # Check position limits
            existing = [p for p in self.active_positions.values() if p["symbol"] == symbol]
            if len(existing) >= config.MAX_POSITIONS_PER_INSTRUMENT:
                return False

            # Check exposure
            if not self.parasite.dynamic_exposure.can_open(symbol, direction):
                return False

            # Get current price
            bid, ask = await self._get_price(symbol)
            if not bid or not ask:
                return False

            entry_price = ask if direction == "BUY" else bid
            risk_pct = config.LAYER_RISK.get(layer, 0.005)
            risk_amount = config.INITIAL_CAPITAL * risk_pct

            # Place order
            trade_id = f"TRD_{uuid.uuid4().hex[:8]}"
            try:
                order_result = await self._place_order(symbol, direction, entry_price, risk_amount)
                if not order_result:
                    return False

                position = {
                    "trade_id": trade_id,
                    "symbol": symbol,
                    "direction": direction,
                    "entry_price": entry_price,
                    "risk_amount": risk_amount,
                    "branch_id": branch_id,
                    "layer": layer,
                    "confidence": confidence,
                    "pyramid_level": 0,
                    "opened_at": time.time(),
                    "order_id": order_result.get("orderId", ""),
                }
                self.active_positions[trade_id] = position

                # Start position monitor
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
        """Monitor position for pyramiding and exit signals."""
        position = self.active_positions.get(trade_id)
        if not position:
            return

        symbol = position["symbol"]
        direction = position["direction"]
        entry = position["entry_price"]
        risk = position["risk_amount"]

        while trade_id in self.active_positions:
            await asyncio.sleep(0.5)

            bid, ask = await self._get_price(symbol)
            if not bid or not ask:
                continue

            current_price = bid if direction == "BUY" else ask

            # Calculate R-multiple
            if direction == "BUY":
                r_multiple = (current_price - entry) / (risk / 0.01) if risk > 0 else 0
            else:
                r_multiple = (entry - current_price) / (risk / 0.01) if risk > 0 else 0

            # Check pyramiding levels
            pos = self.active_positions.get(trade_id)
            if pos:
                for level in config.PYRAMID_LEVELS:
                    if r_multiple >= level["r_trigger"] and pos["pyramid_level"] < config.PYRAMID_LEVELS.index(level) + 1:
                        # Add pyramid layer
                        add_size = position["risk_amount"] * level["size_ratio"]
                        await self._place_order(symbol, direction, current_price, add_size)
                        pos["pyramid_level"] = config.PYRAMID_LEVELS.index(level) + 1
                        logger.trade("PYRAMID", symbol, position["layer"], {"level": pos["pyramid_level"], "r": round(r_multiple, 2)})

            # Check exit — tight stop if losing
            if r_multiple < -0.7:
                await self._close_position(trade_id, current_price)
                break

    async def _close_position(self, trade_id: str, exit_price: float):
        """Close a position and record the trade."""
        position = self.active_positions.pop(trade_id, None)
        if not position:
            return

        # Calculate R-multiple
        entry = position["entry_price"]
        direction = position["direction"]
        risk = position["risk_amount"]
        if direction == "BUY":
            r_multiple = (exit_price - entry) / (risk / 0.01) if risk > 0 else 0
        else:
            r_multiple = (entry - exit_price) / (risk / 0.01) if risk > 0 else 0

        trade_data = {
            "trade_id": trade_id,
            "instrument": position["symbol"],
            "layer": position["layer"],
            "branch_id": position.get("branch_id", ""),
            "direction": direction,
            "entry_price": entry,
            "exit_price": exit_price,
            "r_multiple": round(r_multiple, 4),
            "profit_currency": round(r_multiple * risk, 4),
            "duration_ms": int((time.time() - position["opened_at"]) * 1000),
        }

        await self.parasite.record_trade(trade_data)
        logger.trade("CLOSE", position["symbol"], position["layer"], {
            "r": round(r_multiple, 3), "duration_ms": trade_data["duration_ms"]
        })

    async def _get_price(self, symbol: str):
        """Get current bid/ask from tick client."""
        # Simplified — in production, would poll the latest tick
        try:
            # This would be implemented via the tick client's latest data
            return 0, 0  # Placeholder
        except:
            return None, None

    async def _place_order(self, symbol: str, direction: str, price: float, amount: float) -> Optional[dict]:
        """Place an order via the tick client."""
        # In production, this calls the Deriv API
        return {"orderId": str(uuid.uuid4().hex[:8])}