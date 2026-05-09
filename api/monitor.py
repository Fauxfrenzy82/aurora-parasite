"""
Monitor API — FastAPI server for live dashboard.
Shows real-time system state, trade stream, and controls.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import config
from logger import get_logger

logger = get_logger("monitor")


class MonitorAPI:
    """Live monitoring API for Aurora Parasite."""

    def __init__(self, parasite):
        self.parasite = parasite
        self.app = FastAPI(title="Aurora Parasite API", version="1.0.0")
        self.active_websockets: List[WebSocket] = []
        self.ws_lock = asyncio.Lock()
        self.start_time = datetime.now(timezone.utc)

        # Setup CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Register routes
        self._register_routes()

    def _register_routes(self):
        """Register all API routes."""
        app = self.app
        parasite = self.parasite

        @app.get("/")
        async def root():
            return {
                "name": "Aurora Parasite API",
                "version": "1.0.0",
                "status": "running" if parasite.running else "stopped",
                "uptime_seconds": (datetime.now(timezone.utc) - self.start_time).total_seconds(),
            }

        @app.get("/api/status")
        async def get_status():
            return JSONResponse(parasite.get_stats())

        @app.get("/api/cortex")
        async def get_cortex():
            return JSONResponse(parasite.cortex.get_stats())

        @app.get("/api/branches")
        async def get_branches():
            branches = []
            for b in parasite.cortex.branches.values():
                branches.append({
                    "id": b.branch_id,
                    "symbol": b.symbol,
                    "feature": b.feature_name,
                    "status": b.status,
                    "wr": round(b.win_rate, 3),
                    "avg_r": round(b.avg_r, 3),
                    "sharpe": round(b.sharpe, 2),
                    "trades": b.trades,
                    "confidence": round(b.confidence, 3),
                })
            return JSONResponse({"branches": branches, "total": len(branches)})

        @app.get("/api/trades")
        async def get_trades(limit: int = Query(50, ge=1, le=500)):
            trades = await parasite.db.get_trades(limit=limit)
            return JSONResponse(trades)

        @app