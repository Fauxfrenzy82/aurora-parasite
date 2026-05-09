"""
Deriv Tick Client — Raw WebSocket tick stream.
Handles OTP authentication and subscribes to tick data for all instruments.
"""

import asyncio
import json
import time
from typing import Optional, Dict, Callable
import websockets
import httpx
from config import config
from logger import get_logger

logger = get_logger("tick_client")


class DerivTickClient:
    """Raw WebSocket tick client for Deriv API."""

    REST_API_BASE = "https://api.derivws.com"
    WS_PING_INTERVAL = 20

    def __init__(self):
        self.app_id = ""
        self.api_token = ""
        self.deriv_login = ""
        self.ws = None
        self.connected = False
        self._callbacks: Dict[str, list] = {}
        self._listen_task = None
        self._lock = asyncio.Lock()
        self._account_id = ""
        self._balance = 10000.0
        self._currency = "USD"
        self._req_id = 0
        self._pending: dict = {}

    async def connect(self, app_id: str, api_token: str) -> bool:
        """Connect to Deriv and authenticate."""
        self.app_id = app_id
        self.api_token = api_token

        async with self._lock:
            try:
                ws_url = await self._get_otp_url()
                if not ws_url:
                    return False

                self.ws = await websockets.connect(ws_url, ping_interval=self.WS_PING_INTERVAL)
                self.connected = True
                self._listen_task = asyncio.create_task(self._listen_loop())
                logger.info("Deriv tick client connected")
                return True
            except Exception as e:
                logger.error(f"Connection failed: {e}")
                return False

    async def _get_otp_url(self) -> Optional[str]:
        """Get one-time WebSocket URL via REST."""
        headers = {
            "Deriv-App-ID": self.app_id,
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                list_url = f"{self.REST_API_BASE}/trading/v1/options/accounts"
                list_resp = await client.get(list_url, headers=headers)
                if list_resp.status_code == 200:
                    accounts = list_resp.json().get("data", [])
                    if accounts:
                        self._account_id = accounts[0].get("account_id", "")
                    else:
                        create_resp = await client.post(list_url, headers=headers, json={
                            "currency": "USD", "group": "row", "account_type": "demo"
                        })
                        if create_resp.status_code in (200, 201):
                            self._account_id = create_resp.json().get("data", {}).get("account_id", "")
                        else:
                            return None

                if not self._account_id:
                    return None

                otp_url = f"{self.REST_API_BASE}/trading/v1/options/accounts/{self._account_id}/otp"
                otp_resp = await client.post(otp_url, headers=headers)
                if otp_resp.status_code == 200:
                    data = otp_resp.json().get("data", {})
                    return data.get("url") or data.get("websocket_url")
        except Exception as e:
            logger.error(f"OTP error: {e}")
        return None

    async def subscribe(self, symbol: str, callback: Callable):
        """Subscribe to tick data for a symbol. Fire-and-forget — no response expected."""
        if symbol not in self._callbacks:
            self._callbacks[symbol] = []
        self._callbacks[symbol].append(callback)

        if self.connected and self.ws:
            msg = {"ticks": symbol, "subscribe": 1}
            self._req_id += 1
            msg["req_id"] = self._req_id
            try:
                await self.ws.send(json.dumps(msg))
                logger.debug(f"Subscribed to {symbol}")
            except Exception as e:
                logger.error(f"Subscribe error for {symbol}: {e}")

    async def _send(self, msg: dict, timeout: float = 10) -> dict:
        """Send message and await response. Only used for non-streaming requests."""
        if not self.ws:
            raise Exception("Not connected")
        future = asyncio.get_event_loop().create_future()
        self._req_id += 1
        msg["req_id"] = self._req_id
        self._pending[self._req_id] = future
        await self.ws.send(json.dumps(msg))
        return await asyncio.wait_for(future, timeout=timeout)

    async def _listen_loop(self):
        """Listen for incoming messages and dispatch to callbacks."""
        self._pending = {}
        while True:
            try:
                if not self.ws:
                    await asyncio.sleep(1)
                    continue
                async for msg in self.ws:
                    try:
                        data = json.loads(msg)
                        req_id = data.get("req_id")
                        if req_id and req_id in self._pending:
                            self._pending.pop(req_id).set_result(data)

                        # Dispatch ticks
                        tick = data.get("tick")
                        if tick:
                            symbol = tick.get("symbol", "")
                            bid = float(tick.get("bid", 0))
                            ask = float(tick.get("ask", 0))
                            epoch = float(tick.get("epoch", time.time()))
                            for cb in self._callbacks.get(symbol, []):
                                try:
                                    cb(symbol, bid, ask, epoch)
                                except Exception:
                                    pass
                    except json.JSONDecodeError:
                        pass
            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket closed — reconnecting...")
            except Exception as e:
                logger.warning(f"Listen error: {e}")

            self.connected = False
            self.ws = None
            await asyncio.sleep(5)
            
            # Reconnect and re-subscribe
            try:
                if await self.connect(self.app_id, self.api_token):
                    for symbol in self._callbacks:
                        msg = {"ticks": symbol, "subscribe": 1}
                        self._req_id += 1
                        msg["req_id"] = self._req_id
                        try:
                            await self.ws.send(json.dumps(msg))
                        except:
                            pass
            except:
                await asyncio.sleep(30)

    async def get_historical_ticks(self, symbol: str, count: int = 5000) -> list:
        """Fetch historical tick data for priming."""
        try:
            resp = await self._send({
                "ticks_history": symbol,
                "count": min(count, 5000),
                "style": "ticks",
                "end": "latest"
            })
            ticks = resp.get("history", {}).get("times", [])
            prices = resp.get("history", {}).get("prices", [])
            result = []
            for i in range(len(ticks)):
                if i < len(prices):
                    result.append({
                        "epoch": float(ticks[i]),
                        "price": float(prices[i]),
                        "symbol": symbol
                    })
            return result
        except Exception as e:
            logger.error(f"Historical ticks error: {e}")
            return []

    async def disconnect(self):
        """Disconnect from Deriv."""
        self.connected = False
        if self._listen_task:
            self._listen_task.cancel()
        if self.ws:
            await self.ws.close()

    def get_balance(self) -> tuple:
        """Get cached balance."""
        return self._balance, self._currency