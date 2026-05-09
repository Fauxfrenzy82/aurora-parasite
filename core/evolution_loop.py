"""
Evolution Loop — Hourly cycle for branch management.
Promotes winners, kills losers, discovers new patterns.
"""

import asyncio
import time
from config import config
from logger import get_logger

logger = get_logger("evolution")


class EvolutionLoop:
    """Hourly evolution cycle."""

    def __init__(self, parasite):
        self.parasite = parasite
        self.running = False
        self.cycles_completed = 0

    async def run(self):
        """Run evolution loop every hour."""
        self.running = True
        while self.running:
            await asyncio.sleep(config.EVOLUTION_INTERVAL)
            await self._cycle()

    async def _cycle(self):
        """Execute one evolution cycle."""
        start = time.time()
        self.cycles_completed += 1

        # Decay confidence on all branches
        await self.parasite.cortex.decay_branches()

        # Scan for new patterns
        self.parasite.cortex.scan_for_patterns()

        # Check for permanent law candidates
        for branch in list(self.parasite.cortex.branches.values()):
            if branch.status == "PROMOTED" and branch.trades >= config.PERMANENT_LAW_TRADES:
                await self.parasite.memory.check_and_promote(branch)

        # Update dynamic exposure
        self.parasite.dynamic_exposure.update(
            self.parasite.nervous_system,
            self.parasite.cortex
        )

        # Log cycle
        stats = self.parasite.cortex.get_stats()
        duration = time.time() - start
        logger.evolution(
            f"Cycle {self.cycles_completed}",
            f"Branches: {stats['total_branches']} | "
            f"Promoted: {stats['promoted']} | "
            f"Laws: {self.parasite.memory.law_count} | "
            f"Duration: {duration:.1f}s"
        )

    def get_stats(self) -> dict:
        return {"cycles_completed": self.cycles_completed, "running": self.running}