"""
Aurora Parasite — Main entry point.
Self-evolving market organism with tick-level learning.
Auto-halts when balance cap is reached.
Polls live balance from Deriv every 30 seconds.
"""

import asyncio
import os
import signal
import sys
import time
from config import config
from logger import get_logger
from brokers.deriv_tick_client import DerivTickClient
from database.parasite_db import ParasiteDB
from core.nervous_system import NervousSystem
from core.neural_cortex import NeuralCortex
from core.memory_bank import MemoryBank
from core.evolution_loop import EvolutionLoop
from core.execution_engine import ExecutionEngine
from core.tick_priming import TickPrimer
from aggression.spread_capture import SpreadCapture
from aggression.tick_momentum import TickMomentum
from aggression.fade_engine import FadeEngine
from aggression.news_scalper import NewsScalper
from aggression.cross_instrument import CrossInstrumentArb
from risk.dynamic_exposure import DynamicExposure
from risk.correlation_matrix import CorrelationMatrix
from monitor import MonitorAPI
import uvicorn

logger = get_logger("main")


class AuroraParasite:
    """Main organism orchestrating all components."""

    def __init__(self):
        self.running = True
        self.halted = False
        self.start_time = time.time()
        self.total_trades = 0
        self.total_r = 0.0

        self.balance_cap = float(os.getenv("BALANCE_CAP", "500.0"))
        self.cap_halted = False

        self.tick_client = DerivTickClient()
        self.db = ParasiteDB()
        self.nervous_system = NervousSystem(config.INSTRUMENTS)
        self.cortex = NeuralCortex()
        self.memory = MemoryBank(self.db)
        self.execution = ExecutionEngine(self)
        self.dynamic_exposure = DynamicExposure()
        self.correlation = CorrelationMatrix()

        self.spread_capture = SpreadCapture(self)
        self.tick_momentum = TickMomentum(self)
        self.fade_engine = FadeEngine(self)
        self.news_scalper = NewsScalper(self)
        self.cross_instrument = CrossInstrumentArb(self)

        self.evolution_loop = EvolutionLoop(self)
        self.monitor_api = MonitorAPI(self)
        self.primer = TickPrimer(self.tick_client, self.nervous_system, self.cortex)

    async def initialize(self) -> bool:
        logger.info("=" * 60)
        logger.info("AURORA PARASITE INITIALIZING")
        logger.info("=" * 60)

        try:
            config.validate()
        except ValueError as e:
            logger.error(f"Config error: {e}")
            return False

        if not await self.tick_client.connect(config.DERIV_APP_ID, config.DERIV_API_TOKEN):
            logger.error("Failed to connect to Deriv")
            return False

        laws = await self.memory.load_laws()
        logger.info(f"Loaded {len(laws)} permanent laws from memory")

        await self.nervous_system.start(self.tick_client)
        await self.cortex.start()

        logger.info(f"Priming cortex with {config.PRIMING_HOURS}h of historical tick data...")
        branches_created = await self.primer.prime(config.PRIMING_HOURS)

        if branches_created == 0:
            logger.warning("Priming created no branches — forcing scan on available data")
            self.cortex.scan_for_patterns()
            logger.info(f"Post-scan branches: {len(self.cortex.branches)}")

        self.dynamic_exposure.max_exposure = 0.55

        asyncio.create_task(self._process_signal_queue())

        logger.info(f"Aurora Parasite initialized — {len(self.cortex.branches)} branches ready")
        logger.info(f"Balance Cap: ${self.balance_cap:.2f}")
        return True

    async def _balance_updater(self):
        """Poll live balance from Deriv every 30 seconds."""
        await asyncio.sleep(10)  # Wait for connection to stabilize
        while self.running:
            try:
                if self.tick_client.connected and self.tick_client.ws:
                    resp = await self.tick_client._send({"balance": 1})
                    if resp.get("balance"):
                        b = resp["balance"]
                        if isinstance(b, dict):
                            self.tick_client._balance = float(b.get("balance", 10000.0))
                            self.tick_client._currency = b.get("currency", "USD")
                        else:
                            self.tick_client._balance = float(b) if b else 10000.0
            except Exception:
                pass
            await asyncio.sleep(30)

    async def _process_signal_queue(self):
        logger.info("Signal processing loop started")
        while self.running:
            try:
                signal = await asyncio.wait_for(
                    self.nervous_system.signal_queue.get(),
                    timeout=1.0
                )
                if self.halted:
                    continue

                decision = await self.cortex.process_signal(signal)
                if decision:
                    await self.execution.execute_decision(decision, signal)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Signal processing error: {e}")

    async def start_aggression(self):
        logger.info("Starting aggression layers...")
        asyncio.create_task(self.spread_capture.run())
        asyncio.create_task(self.tick_momentum.run())
        asyncio.create_task(self.fade_engine.run())
        asyncio.create_task(self.news_scalper.run())
        asyncio.create_task(self.cross_instrument.run())
        logger.info("All 5 aggression layers online")

    async def run(self):
        if not await self.initialize():
            logger.critical("Initialization failed — exiting")
            return

        await self.start_aggression()
        asyncio.create_task(self.evolution_loop.run())
        asyncio.create_task(self._balance_updater())

        logger.info("AURORA PARASITE IS LIVE")
        logger.info(f"   Instruments: {len(config.INSTRUMENTS)}")
        logger.info(f"   Branches: {len(self.cortex.branches)}")
        logger.info(f"   Balance Cap: ${self.balance_cap:.2f}")

        while self.running:
            await asyncio.sleep(1)

            # Auto-halt when balance cap is reached
            if not self.cap_halted and not self.halted:
                try:
                    current_balance = self.tick_client._balance
                    if current_balance >= self.balance_cap:
                        self.halt(f"Balance cap reached: ${current_balance:.2f} (cap: ${self.balance_cap:.2f})")
                        self.cap_halted = True
                        logger.info(f"💰 BALANCE CAP HIT: ${current_balance:.2f}")
                except Exception:
                    pass

    async def shutdown(self):
        logger.info("Shutting down Aurora Parasite...")
        self.running = False
        await self.tick_client.disconnect()
        logger.info("Shutdown complete")

    def halt(self, reason: str = ""):
        self.halted = True
        logger.critical(f"EMERGENCY HALT: {reason}")

    def resume(self):
        self.halted = False
        self.cap_halted = False
        logger.info("Trading resumed")

    def get_stats(self) -> dict:
        layers_stats = {
            "spread_capture": self.spread_capture.get_stats(),
            "tick_momentum": self.tick_momentum.get_stats(),
            "fade_engine": self.fade_engine.get_stats(),
            "news_scalper": self.news_scalper.get_stats(),
            "cross_instrument": self.cross_instrument.get_stats(),
        }

        return {
            "running": self.running,
            "halted": self.halted,
            "initial_capital": config.INITIAL_CAPITAL,
            "current_balance": self.tick_client._balance,
            "balance_cap": self.balance_cap,
            "cap_halted": self.cap_halted,
            "uptime_seconds": time.time() - self.start_time,
            "total_trades": self.total_trades,
            "total_r": round(self.total_r, 2),
            "avg_r_per_trade": round(self.total_r / max(self.total_trades, 1), 4),
            "instruments": config.INSTRUMENTS,
            "nervous_system": self.nervous_system.get_stats(),
            "cortex": self.cortex.get_stats(),
            "memory": self.memory.get_stats(),
            "dynamic_exposure": self.dynamic_exposure.get_stats(),
            "correlation": self.correlation.get_stats(),
            "layers": layers_stats,
        }

    async def record_trade(self, trade_data: dict):
        self.total_trades += 1
        r = trade_data.get("r_multiple", 0)
        self.total_r += r

        await self.db.save_trade(trade_data)

        branch_id = trade_data.get("branch_id", "")
        if branch_id:
            await self.cortex.record_outcome(branch_id, r)


async def main():
    parasite = AuroraParasite()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(parasite.shutdown()))
        except NotImplementedError:
            pass

    config_uvicorn = uvicorn.Config(
        parasite.monitor_api.app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
    server = uvicorn.Server(config_uvicorn)
    asyncio.create_task(server.serve())

    await parasite.run()


if __name__ == "__main__":
    asyncio.run(main())