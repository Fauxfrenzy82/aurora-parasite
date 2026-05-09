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

        @app.get("/api/trades/stats")
        async def get_trade_stats():
            stats = await parasite.db.get_trade_stats()
            return JSONResponse(stats)

        @app.get("/api/laws")
        async def get_laws():
            return JSONResponse(parasite.memory.get_stats())

        @app.get("/api/layers")
        async def get_layers():
            return JSONResponse({
                "spread_capture": parasite.spread_capture.get_stats(),
                "tick_momentum": parasite.tick_momentum.get_stats(),
                "fade_engine": parasite.fade_engine.get_stats(),
                "news_scalper": parasite.news_scalper.get_stats(),
                "cross_instrument": parasite.cross_instrument.get_stats(),
            })

        @app.get("/api/exposure")
        async def get_exposure():
            return JSONResponse(parasite.dynamic_exposure.get_stats())

        @app.get("/api/nervous_system")
        async def get_nervous_system():
            return JSONResponse(parasite.nervous_system.get_stats())

        @app.post("/api/control")
        async def control(action: str = Query(...)):
            action = action.lower().strip()
            if action == "halt":
                parasite.halt("Manual halt via API")
                return {"status": "halted"}
            elif action == "resume":
                parasite.resume()
                return {"status": "resumed"}
            elif action == "close_all":
                count = 0
                for pos_id in list(parasite.execution.active_positions.keys()):
                    await parasite.execution._close_position(pos_id, 0)
                    count += 1
                return {"status": "closed", "count": count}
            else:
                return {"status": "error", "message": f"Unknown action: {action}"}

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            async with self.ws_lock:
                self.active_websockets.append(websocket)

            try:
                await websocket.send_json({
                    "type": "state_update",
                    "data": parasite.get_stats(),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

                while True:
                    try:
                        data = await asyncio.wait_for(websocket.receive_text(), timeout=10)
                        if data == "ping":
                            await websocket.send_text("pong")
                    except asyncio.TimeoutError:
                        try:
                            await websocket.send_json({
                                "type": "heartbeat",
                                "data": parasite.get_stats(),
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            })
                        except:
                            break

            except WebSocketDisconnect:
                pass
            finally:
                async with self.ws_lock:
                    if websocket in self.active_websockets:
                        self.active_websockets.remove(websocket)
