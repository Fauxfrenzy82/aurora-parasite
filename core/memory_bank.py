"""
Memory Bank — Permanent law storage and retrieval.
Laws that survive 500+ trades with high Sharpe are permanent.
"""

from typing import List, Dict
from config import config
from logger import get_logger

logger = get_logger("memory")


class MemoryBank:
    """Stores and retrieves permanent trading laws."""

    def __init__(self, db):
        self.db = db
        self.laws: Dict[str, dict] = {}
        self.law_count = 0

    async def load_laws(self) -> List[dict]:
        """Load all permanent laws from database."""
        laws = await self.db.load_laws()
        for law in laws:
            self.laws[law.get("law_id", "")] = law
        self.law_count = len(self.laws)
        logger.info(f"Memory bank loaded {self.law_count} permanent laws")
        return laws

    async def check_and_promote(self, branch) -> bool:
        """Check if a branch qualifies for permanent status."""
        if branch.trades < config.PERMANENT_LAW_TRADES:
            return False
        if branch.sharpe < config.PERMANENT_LAW_SHARPE:
            return False
        if branch.win_rate < 0.50:
            return False

        law_data = {
            "law_id": f"LAW_{branch.symbol}_{branch.feature_index}_{int(branch.threshold*10000)}",
            "instrument": branch.symbol,
            "feature_index": branch.feature_index,
            "threshold": branch.threshold,
            "direction": branch.direction,
            "total_trades": branch.trades,
            "win_rate": round(branch.win_rate, 4),
            "avg_r": round(branch.avg_r, 4),
            "sharpe": round(branch.sharpe, 4),
        }

        await self.db.save_law(law_data)
        self.laws[law_data["law_id"]] = law_data
        self.law_count = len(self.laws)
        logger.info(f"PERMANENT LAW CREATED: {law_data['law_id']}")
        return True

    def get_stats(self) -> dict:
        return {
            "total_laws": self.law_count,
            "laws": [
                {"id": k, "symbol": v["instrument"], "sharpe": v["sharpe"]}
                for k, v in sorted(self.laws.items(), key=lambda x: x[1]["sharpe"], reverse=True)[:10]
            ],
        }