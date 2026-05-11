"""
Aurora Parasite — Pepperstone cTrader Edition.
Entry point. Boots FastAPI which launches the parasite on startup.
"""

import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import config
from logger import get_logger
from core.parasite_core import ParasiteCore

logger = get_logger("main")

app = FastAPI(title="Aurora Parasite — Pepperstone")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

parasite: ParasiteCore = None


@app.on_event("startup")
async def startup():
    global parasite
    parasite = ParasiteCore()
    asyncio.create_task(parasite.start())
    logger.info("Aurora Parasite booting...")


@app.get("/api/status")
async def status():
    if not parasite:
        return {"running": False}
    return parasite.get_status()


@app.get("/api/trades")
async def trades(limit: int = 100):
    if not parasite:
        return []
    return parasite.trade_log[-limit:]


@app.post("/api/halt")
async def halt():
    if parasite:
        parasite.halted = True
    return {"halted": True}


@app.post("/api/resume")
async def resume():
    if parasite:
        parasite.halted = False
    return {"halted": False}


@app.get("/api/layers")
async def layers():
    if not parasite:
        return {}
    return parasite.get_status().get("layers", {})


@app.get("/api/cortex")
async def cortex():
    if not parasite:
        return {}
    return parasite.cortex.get_stats()


@app.post("/api/control")
async def control(action: str):
    if not parasite:
        return {"error": "not running"}
    if action == "halt":
        parasite.halted = True
    elif action == "resume":
        parasite.halted = False
    elif action == "close_all":
        parasite.halted = True
        await asyncio.sleep(0.5)
        parasite.halted = False
    return {"action": action, "halted": parasite.halted}


if __name__ == "__main__":
    uvicorn.run(
        "parasite:app",
        host="0.0.0.0",
        port=config.API_PORT,
        reload=False,
        log_level="info",
    )