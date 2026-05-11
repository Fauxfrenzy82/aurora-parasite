"""
The Parasite — Central orchestrator for Pepperstone cTrader.
All 5 layers active. No cortex gating. Real orders. Full aggression.
"""

import asyncio
import time
from config import config
from logger import get_logger
from brokers.pepperstone_ctrader_client import CtraderClient
from core.nervous_system import NervousSystem
from core.neural_cortex import NeuralCortex
from core.execution_engine import ExecutionEngine
from core.dynamic_exposure import DynamicExposure
from aggression.spread_capture import SpreadCapture
from aggression.tick_momentum import TickMomentum
from aggression.fade_engine import FadeEngine
from aggression.news_scalper import NewsScalper
from aggression.cross_instrument import CrossInstrumentArb

logger = get_logger("parasite")


class Parasite:
    def __init__(self):
        self.running = False
        self.halted = False
        self.start_time = time.time()
        self.initial_capital = config.INITIAL_CAPITAL
        self.current_balance = config.INITIAL_CAPITAL
        self.total_trades = 0
        self.total_r = 0.0
        self.trade_log = []

        # Core components
        self.broker_client = CtraderClient()
        self.nervous_system = NervousSystem(config.INSTRUMENTS)
        self.cortex = NeuralCortex()
        self.execution = ExecutionEngine(self)
        self.dynamic_exposure = DynamicExposure()

        # All 5 aggression layers
        self.spread_capture = SpreadCapture(self)
        self.tick_momentum = TickMomentum(self)
        self.fade_engine = FadeEngine(self)
        self.news_scalper = NewsScalper(self)
        self.cross_instrument = CrossInstrumentArb(self)

    async def start(self):
        logger.info("🦠 PARASITE AWAKENING — PEPPERSTONE MODE")
        config.validate()

        connected = await self.broker_client.connect(
            config.CTRADER_CLIENT_ID,
            config.CTRADER_CLIENT_SECRET,
            config.CTRADER_ACCOUNT_ID,
        )
        if not connected:
            raise RuntimeError("Failed to connect to Pepperstone cTrader")

        await self.nervous_system.start(self.broker_client)
        await self.cortex.start()
        await self.dynamic_exposure.start(self)

        logger.info("Warming tick buffers (10s)...")
        await asyncio.sleep(10)

        self.running = True
        logger.info("All 5 layers launching simultaneously 🦠")

        await asyncio.gather(
            self.spread_capture.run(),
            self.tick_momentum.run(),
            self.fade_engine.run(),
            self.news_scalper.run(),
            self.cross_instrument.run(),
            self._cortex_signal_loop(),
            self._evolution_loop(),
            self._risk_monitor(),
            self._balance_sync_loop(),
        )

    async def _cortex_signal_loop(self):
        """Feed nervous system signals into cortex for branch learning.
        Cortex decisions are SUPPLEMENTARY — layers fire independently."""
        while self.running:
            try:
                signal = await asyncio.wait_for(
                    self.nervous_system.signal_queue.get(), timeout=1.0
                )
                decision = await self.cortex.process_signal(signal)
                if decision and decision.get("confidence", 0) > 0.65:
                    await self.execution.execute_decision(decision, signal)
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                logger.error(f"Cortex loop error: {e}")

    async def _evolution_loop(self):
        """Evolve cortex branches every 30 minutes."""
        while self.running:
            await asyncio.sleep(config.EVOLUTION_INTERVAL)
            try:
                self.cortex.scan_for_patterns()
                await self.cortex.decay_branches()
                promoted = len([b for b in self.cortex.branches.values()
                                if b.status == "PROMOTED"])
                logger.info(f"Evolution complete: {promoted} branches promoted")
            except Exception as e:
                logger.error(f"Evolution error: {e}")

    async def _risk_monitor(self):
        """Hard stop if drawdown exceeds limit."""
        while self.running:
            await asyncio.sleep(5)
            try:
                drawdown = (
                    (self.initial_capital - self.current_balance) / self.initial_capital
                )
                if drawdown >= config.HARD_STOP_DRAWDOWN:
                    self.halted = True
                    logger.warning(f"HARD STOP TRIGGERED: drawdown={drawdown:.1%}")
                elif self.halted and drawdown < config.HARD_STOP_DRAWDOWN * 0.8:
                    self.halted = False
                    logger.info("Hard stop cleared — trading resumed")
            except Exception as e:
                logger.error(f"Risk monitor error: {e}")

    async def _balance_sync_loop(self):
        """Sync real balance from broker every 60 seconds."""
        while self.running:
            await asyncio.sleep(60)
            try:
                balance, currency = self.broker_client.get_balance()
                if balance > 0:
                    self.current_balance = balance
            except Exception as e:
                logger.error(f"Balance sync error: {e}")

    async def record_trade(self, trade_data: dict):
        self.total_trades += 1
        r = trade_data.get("r_multiple", 0.0)
        self.total_r += r
        profit = trade_data.get("profit_currency", 0.0)
        self.current_balance += profit

        self.trade_log.append({
            **trade_data,
            "balance_after": round(self.current_balance, 4),
            "timestamp": time.time(),
        })

        # Keep last 5000 trades in memory
        if len(self.trade_log) > 5000:
            self.trade_log = self.trade_log[-5000:]

    def get_status(self) -> dict:
        uptime = time.time() - self.start_time
        return {
            "running": self.running,
            "halted": self.halted,
            "initial_capital": self.initial_capital,
            "current_balance": round(self.current_balance, 4),
            "balance_cap": config.BALANCE_CAP,
            "cap_halted": self.current_balance >= config.BALANCE_CAP,
            "uptime_seconds": round(uptime, 2),
            "total_trades": self.total_trades,
            "total_r": round(self.total_r, 4),
            "avg_r_per_trade": round(
                self.total_r / max(self.total_trades, 1), 4
            ),
            "instruments": config.INSTRUMENTS,
            "nervous_system": self.nervous_system.get_stats(),
            "cortex": self.cortex.get_stats(),
            "dynamic_exposure": self.dynamic_exposure.get_stats(),
            "layers": {
                "spread_capture": self.spread_capture.get_stats(),
                "tick_momentum": self.tick_momentum.get_stats(),
                "fade_engine": self.fade_engine.get_stats(),
                "news_scalper": self.news_scalper.get_stats(),
                "cross_instrument": self.cross_instrument.get_stats(),
            },
        }