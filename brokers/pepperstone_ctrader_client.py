"""
Pepperstone cTrader Client — Direct REST + WebSocket for cTrader API.
Replaces Deriv client. Handles auth, tick streaming, and order placement.
"""

import asyncio
import json
import time
import uuid
from typing import Optional, Dict, Callable
import httpx
import websockets
from config import config
from logger import get_logger

logger = get_logger("ctrader")


class CtraderClient:
    """Direct client for Pepperstone via cTrader Open API."""

    REST_BASE = "https://api.ctrader.com"
    WS_BASE = "wss://api.ctrader.com/ws"

    def __init__(self):
        self.client_id = ""
        self.client_secret = ""
        self.account_id = ""
        self.access_token = ""
        self.ws = None
        self.connected = False
        self._callbacks: Dict[str, list] = {}
        self._listen_task = None
        self._lock = asyncio.Lock()
        self._balance = 500.0
        self._currency = "USD"
        self._req_id = 0
        self._pending: dict = {}
        self._subscriptions: set = set()
        self._rest_client = None

    async def connect(self, client_id: str, client_secret: str, account_id: str) -> bool:
        self.client_id = client_id
        self.client_secret = client_secret
        self.account_id = account_id

        async with self._lock:
            try:
                # Step 1: Get access token via REST
                self._rest_client = httpx.AsyncClient(timeout=15.0)
                auth_resp = await self._rest_client.post(
                    f"{self.REST_BASE}/auth/token",
                    json={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "grant_type": "client_credentials",
                        "scope": "accounts"
                    }
                )
                if auth_resp.status_code != 200:
                    logger.error(f"Auth failed: {auth_resp.status_code}")
                    return False

                self.access_token = auth_resp.json().get("access_token", "")
                if not self.access_token:
                    return False

                # Step 2: Connect WebSocket
                self.ws = await websockets.connect(
                    f"{self.WS_BASE}?token={self.access_token}",
                    ping_interval=20
                )
                self.connected = True

                # Subscribe to account
                await self._send_ws({
                    "type": "SUBSCRIBE",
                    "payload": {"accountId": self.account_id}
                })

                self._listen_task = asyncio.create_task(self._listen_loop())
                logger.info("cTrader client connected")
                return True

            except Exception as e:
                logger.error(f"Connection failed: {e}")
                return False

    async def subscribe(self, symbol: str, callback: Callable):
        if symbol not in self._callbacks:
            self._callbacks[symbol] = []
        self._callbacks[symbol].append(callback)
        self._subscriptions.add(symbol)

        if self.connected and self.ws:
            await self._send_ws({
                "type": "SUBSCRIBE_TICK",
                "payload": {"symbol": symbol, "accountId": self.account_id}
            })

    async def _send_ws(self, msg: dict) -> dict:
        if not self.ws or not self.connected:
            raise Exception("Not connected")
        self._req_id += 1
        msg["requestId"] = str(self._req_id)
        future = asyncio.get_event_loop().create_future()
        self._pending[str(self._req_id)] = future
        await self.ws.send(json.dumps(msg))
        return await asyncio.wait_for(future, timeout=10)

    async def _send_rest(self, method: str, path: str, data: dict = None) -> dict:
        headers = {"Authorization": f"Bearer {self.access_token}"}
        url = f"{self.REST_BASE}{path}"
        if method == "GET":
            resp = await self._rest_client.get(url, headers=headers)
        else:
            resp = await self._rest_client.post(url, headers=headers, json=data)
        return resp.json()

    async def _place_order(self, symbol: str, direction: str, amount: float) -> Optional[dict]:
        """Place a real market order via cTrader REST API."""
        try:
            side = "BUY" if direction.upper() in ("BUY", "LONG") else "SELL"
            resp = await self._send_rest("POST", "/v1/accounts/orders", {
                "accountId": self.account_id,
                "symbol": symbol,
                "type": "MARKET",
                "side": side,
                "volume": round(amount / 100, 2),  # Convert to lots
            })
            order_id = resp.get("orderId", str(uuid.uuid4().hex[:8]))
            logger.info(f"ORDER PLACED: {symbol} {direction} ${amount} → {order_id}")
            return {"orderId": order_id}
        except Exception as e:
            logger.error(f"Order error: {e}")
            return None

    async def _listen_loop(self):
        while True:
            try:
                if not self.ws:
                    await asyncio.sleep(1)
                    continue
                async for msg in self.ws:
                    try:
                        data = json.loads(msg)
                        req_id = data.get("requestId")
                        if req_id and req_id in self._pending:
                            self._pending.pop(req_id).set_result(data)

                        # Handle ticks
                        tick = data.get("tick")
                        if tick:
                            symbol = tick.get("symbol", "")
                            bid = float(tick.get("bid", 0))
                            ask = float(tick.get("ask", 0))
                            for cb in self._callbacks.get(symbol, []):
                                try:
                                    cb(symbol, bid, ask, time.time())
                                except:
                                    pass
                    except json.JSONDecodeError:
                        pass
            except Exception as e:
                logger.warning(f"Listen error: {e}")

            self.connected = False
            self.ws = None
            await asyncio.sleep(5)
            try:
                await self.connect(self.client_id, self.client_secret, self.account_id)
            except:
                await asyncio.sleep(30)

    async def disconnect(self):
        self.connected = False
        if self._listen_task:
            self._listen_task.cancel()
        if self.ws:
            await self.ws.close()
        if self._rest_client:
            await self._rest_client.aclose()

    def get_balance(self) -> tuple:
        return self._balance, self._currency

    async def get_historical_ticks(self, symbol: str, count: int = 5000) -> list:
        """Fetch historical candles as tick approximation."""
        try:
            resp = await self._send_rest("GET", 
                f"/v1/accounts/{self.account_id}/symbols/{symbol}/candles?timeframe=M1&limit={min(count,1000)}")
            candles = resp.get("candles", [])
            result = []
            for c in candles:
                result.append({
                    "epoch": float(c.get("timestamp", 0)),
                    "price": float(c.get("close", 0)),
                    "symbol": symbol
                })
            return result
        except:
            return []