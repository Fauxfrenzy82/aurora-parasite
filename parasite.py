"""
Aurora Parasite — Main entry point.
"""

import asyncio
import signal
import sys
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

        # Core components
        self.tick_client = DerivTickClient()
        self.db = ParasiteDB()
        self.nervous_system = NervousSystem(config.INSTRUMENTS)
        self.cortex = NeuralCortex()
        self.memory = MemoryBank(self.db)
        self.execution = ExecutionEngine(self)
        self.dynamic_exposure = DynamicExposure()
        self.correlation = CorrelationMatrix()

        # Aggression layers
        self.spread_capture = SpreadCapture(self)
        self.tick_momentum = TickMomentum(self)
        self.fade_engine = FadeEngine(self)
        self.news_scalper = NewsScalper(self)
        self.cross_instrument = CrossInstrumentArb(self)

        # Evolution
        self.evolution_loop = EvolutionLoop(self)

        # Monitoring
        self.monitor_api = MonitorAPI(self)

        # Priming
        self.primer = TickPrimer(self.tick_client, self.nervous_system, self.cortex)

    async def initialize(self) -> bool:
        """Initialize all components."""
        logger.info("=" * 60)
        logger.info("AURORA PARASITE INITIALIZING")
        logger.info("=" * 60)

        # Validate config
        try:
            config.validate()
        except ValueError as e:
            logger.error(f"Config error: {e}")
            return False

        # Connect to Deriv
        if not await self.tick_client.connect(config.DERIV_APP_ID, config.DERIV_API_TOKEN):
            logger.error("Failed to connect to Deriv")
            return False

        # Load branches and laws from database
        branches = await self.db.load_branches()
        for branch in branches:
            # Reconstruct branch from data
            pass

        await self.memory.load_laws()

        # Start nervous system
        await self.nervous_system.start(self.tick_client)

        # Start cortex
        await self.cortex.start()

        # Prime with historical data
        await self.primer.prime(config.PRIMING_HOURS)

        logger.info("Aurora Parasite initialization complete")
        return True

    async def start_aggression(self):
        """Start all aggression layers."""
        asyncio.create_task(self.spread_capture.run())
        asyncio.create_task(self.tick_momentum.run())
        asyncio.create_task(self.fade_engine.run())
        asyncio.create_task(self.news_scalper.run())
        asyncio.create_task(self.cross_instrument.run())

    async def run(self):
        """Main run loop."""
        if not await self.initialize():
            logger.critical("Initialization failed — exiting")
            return

        await self.start_aggression()
        asyncio.create_task(self.evolution_loop.run())

        logger.info("Aurora Parasite is LIVE")

        # Keep running
        while self.running:
            await asyncio.sleep(1)

    async def shutdown(self):
        """Graceful shutdown."""
        logger.info("Shutting down Aurora Parasite...")
        self.running = False
        await self.tick_client.disconnect()
        logger.info("Shutdown complete")

    def halt(self, reason: str = ""):
        """Emergency halt."""
        self.halted = True
        logger.critical(f"EMERGENCY HALT: {reason}")

    def resume(self):
        """Resume trading."""
        self.halted = False
        logger.info("Trading resumed")

    def get_stats(self) -> dict:
        """Get system statistics."""
        return {
            "running": self.running,
            "halted": self.halted,
            "initial_capital": config.INITIAL_CAPITAL,
            "instruments": config.INSTRUMENTS,
            "nervous_system": self.nervous_system.get_stats(),
            "cortex": self.cortex.get_stats(),
            "memory": self.memory.get_stats(),
            "dynamic_exposure": self.dynamic_exposure.get_stats(),
            "correlation": self.correlation.get_stats(),
        }

    async def record_trade(self, trade_data: dict):
        """Record a trade outcome."""
        await self.db.save_trade(trade_data)

        # Update cortex with result
        branch_id = trade_data.get("branch_id", "")
        r_multiple = trade_data.get("r_multiple", 0)
        if branch_id:
            await self.cortex.record_outcome(branch_id, r_multiple)


async def main():
    """Entry point."""
    parasite = AuroraParasite()

    # Handle shutdown signals
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(parasite.shutdown()))

    # Start API server
    config_uvicorn = uvicorn.Config(
        parasite.monitor_api.app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
    server = uvicorn.Server(config_uvicorn)
    asyncio.create_task(server.serve())

    # Run parasite
    await parasite.run()


if __name__ == "__main__":
    asyncio.run(main())