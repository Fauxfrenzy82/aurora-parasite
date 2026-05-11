"""
FastAPI — Status, control, and trade history endpoints.
"""

import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.parasite import Parasite

app = FastAPI(title="Aurora Parasite — Pepperstone")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

parasite: Parasite = None


@app.on_event("startup")
async def startup():
    global parasite
    parasite = Parasite()
    asyncio.create_task(parasite.start())


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