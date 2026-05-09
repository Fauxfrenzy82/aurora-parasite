"""
Tick Priming — Pre-feeds the cortex with historical tick data.
The parasite arrives at the market with pre-tested hypotheses.
"""

import asyncio
import time
from config import config
from logger import get_logger

logger = get_logger("priming")


class TickPrimer:
    """
    Feeds 24 hours of historical tick data through the nervous system
    and cortex at accelerated speed before live trading begins.
    """

    def __init__(self, tick_client, nervous_system, cortex):
        self.tick_client = tick_client
        self.nervous_system = nervous_system
        self.cortex = cortex
        self.branches_created = 0

    async def prime(self, hours: int = None) -> int:
        """
        Prime the cortex with historical data.
        
        Args:
            hours: Hours of historical data to process (default from config)
            
        Returns:
            Number of branches created during priming
        """
        if hours is None:
            hours = config.PRIMING_HOURS

        logger.info(f"🧠 Priming cortex with {hours}h of historical tick data...")
        start_time = time.time()

        for symbol in config.INSTRUMENTS:
            await self._prime_symbol(symbol, hours)

        # Run initial pattern scan on primed data
        self.cortex.scan_for_patterns()

        duration = time.time() - start_time
        self.branches_created = len(self.cortex.branches)
        logger.info(
            f"✅ Priming complete — {self.branches_created} branches "
            f"created in {duration:.1f}s"
        )
        return self.branches_created

    async def _prime_symbol(self, symbol: str, hours: int):
        """Prime a single instrument with historical ticks."""
        try:
            ticks = await self.tick_client.get_historical_ticks(
                symbol, count=hours * 3600  # Approximate ticks per hour
            )

            if not ticks:
                logger.warning(f"No historical ticks for {symbol}")
                return

            logger.debug(f"Priming {symbol} with {len(ticks)} historical ticks")

            # Feed ticks through nervous system at accelerated speed
            for i, tick in enumerate(ticks):
                bid = tick.get("price", 0)
                ask = bid * 1.0001  # Approximate ask from bid
                timestamp = tick.get("epoch", time.time())

                # Call the nervous system's tick handler directly
                self.nervous_system._on_tick(symbol, bid, ask, timestamp)

                # Small yield to prevent blocking
                if i % 1000 == 0:
                    await asyncio.sleep(0)

            logger.debug(f"Completed priming {symbol}")

        except Exception as e:
            logger.error(f"Priming error for {symbol}: {e}")

    def get_stats(self) -> dict:
        return {
            "branches_created": self.branches_created,
            "promoted_after_priming": len(
                [b for b in self.cortex.branches.values() if b.status == "PROMOTED"]
            ),
        }