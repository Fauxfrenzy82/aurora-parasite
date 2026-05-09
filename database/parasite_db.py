"""
Parasite Database — Supabase interface for persistent storage.
Stores branches, permanent laws, and trade history.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict
from supabase import create_client, Client
from config import config
from logger import get_logger

logger = get_logger("database")


class ParasiteDB:
    """Persistent storage for Aurora Parasite."""

    def __init__(self):
        self.client: Client = create_client(
            config.SUPABASE_URL,
            config.SUPABASE_SERVICE_ROLE_KEY
        )
        self._ensure_tables()

    def _ensure_tables(self):
        """Create tables if they don't exist."""
        # Run schema creation on initialization
        pass

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── Branches ──────────────────────────────────────

    async def save_branch(self, branch_data: dict) -> bool:
        """Save or update a decision branch."""
        try:
            branch_data["updated_at"] = self._now()
            self.client.table("parasite_branches").upsert(
                branch_data, on_conflict="branch_id"
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Save branch error: {e}")
            return False

    async def load_branches(self, status: str = None) -> list:
        """Load branches from database."""
        try:
            query = self.client.table("parasite_branches").select("*")
            if status:
                query = query.eq("status", status)
            result = query.execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Load branches error: {e}")
            return []

    async def delete_branch(self, branch_id: str) -> bool:
        """Delete a killed branch."""
        try:
            self.client.table("parasite_branches").delete().eq(
                "branch_id", branch_id
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Delete branch error: {e}")
            return False

    # ── Permanent Laws ────────────────────────────────

    async def save_law(self, law_data: dict) -> bool:
        """Save a permanent law."""
        try:
            law_data["updated_at"] = self._now()
            self.client.table("parasite_laws").upsert(
                law_data, on_conflict="law_id"
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Save law error: {e}")
            return False

    async def load_laws(self) -> list:
        """Load all permanent laws."""
        try:
            result = self.client.table("parasite_laws").select("*").execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Load laws error: {e}")
            return []

    # ── Trades ────────────────────────────────────────

    async def save_trade(self, trade_data: dict) -> bool:
        """Save a completed trade."""
        try:
            trade_data["created_at"] = self._now()
            self.client.table("parasite_trades").insert(trade_data).execute()
            return True
        except Exception as e:
            logger.error(f"Save trade error: {e}")
            return False

    async def get_trades(self, limit: int = 100, layer: str = None) -> list:
        """Fetch recent trades."""
        try:
            query = self.client.table("parasite_trades").select("*").order(
                "created_at", desc=True
            ).limit(limit)
            if layer:
                query = query.eq("layer", layer)
            result = query.execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Get trades error: {e}")
            return []

    async def get_trade_stats(self) -> dict:
        """Get aggregate trade statistics."""
        trades = await self.get_trades(limit=10000)
        if not trades:
            return {"total": 0, "win_rate": 0, "avg_r": 0, "total_r": 0}

        total = len(trades)
        wins = [t for t in trades if (t.get("r_multiple") or 0) > 0]
        total_r = sum(t.get("r_multiple", 0) or 0 for t in trades)

        return {
            "total": total,
            "wins": len(wins),
            "win_rate": len(wins) / total if total > 0 else 0,
            "avg_r": total_r / total if total > 0 else 0,
            "total_r": round(total_r, 2),
        }