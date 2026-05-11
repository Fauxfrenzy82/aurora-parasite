"""
Pepperstone cTrader Client — cTrader Open API.
Correct endpoints for demo/live.
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

    AUTH_URL = "https://openapi.ctrader.com/apps/token"
    WS_DEMO = "wss://demo.ctraderapi.com:5036"
    WS_LIVE = "wss://live.ctraderapi.com:5036"

    def __init__(self):
        self.client_id = ""
        self.client_secret = ""
        self.account_id = ""
        self.access_token = ""
        self.ws = None
        self.connected = False
        self._callbacks: Dict[str, list] = {}
        self._lock = asyncio.Lock()
        self._balance = config.INITIAL_CAPITAL
        self._currency = "USD"
        self._req_id = 0
        self._pending: dict = {}
        self._subscriptions: set = set()
        self._rest_client = None
        self._listen_task = None

    async def connect(self, client_id: str, client_secret: str, account_id: str) -> bool:
        self.client_id = client_id
        self.client_secret = client_secret
        self.account_id = account_id

        async with self._lock:
            try:
                self._rest_client = httpx.AsyncClient(timeout=15.0)

                # Get access token
                auth_resp = await self._rest_client.post(
                    self.AUTH_URL,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

                logger.info(f"Auth response: {auth_resp.status_code}")

                if auth_resp.status_code != 200:
                    logger.error(f"Auth failed: {auth_resp.status_code} {auth_resp.text}")
                    return False

                token_data = auth_resp.json()
                self.access_token = token_data.get("accessToken") or token_data.get("access_token", "")

                if not self.access_token:
                    logger.error(f"No access token in response: {token_data}")
                    return False

                logger.info(f"Access token obtained: {self.access_token[:20]}...")

                # Connect WebSocket
                ws_url = self.WS_DEMO if config.CTRADER_ENV == "demo" else self.WS_LIVE
                logger.info(f"Connecting WebSocket: {ws_url}")

                self.ws = await websockets.connect(
                    ws_url,
                    ping_interval=20,
                    ping_timeout=10,
                )
                self.connected = True

                # Authenticate on WebSocket
                await self.ws.send(json.dumps({
                    "payloadType": "PROTO_OA_APPLICATION_AUTH_REQ",
                    "clientMsgId": "auth_app",
                    "payload": {
                        "clientId": self.client_id,
                        "clientSecret": self.client_secret,
                    }
                }))

                self._listen_task = asyncio.create_task(self._listen_loop())
                await asyncio.sleep(1)

                logger.info("cTrader client connected successfully")
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
            try:
                await self.ws.send(json.dumps({
                    "payloadType": "PROTO_OA_SUBSCRIBE_SPOTS_REQ",
                    "clientMsgId": f"sub_{symbol}",
                    "payload": {
                        "ctidTraderAccountId": int(self.account_id),
                        "symbolName": symbol,
                    }
                }))
            except Exception as e:
                logger.error(f"Subscribe error {symbol}: {e}")

    async def _place_order(self, symbol: str, direction: str, amount: float) -> Optional[dict]:
        try:
            side = "BUY" if direction.upper() in ("BUY", "LONG") else "SELL"
            order_id = uuid.uuid4().hex[:8]

            if self.connected and self.ws:
                await self.ws.send(json.dumps({
                    "payloadType": "PROTO_OA_NEW_ORDER_REQ",
                    "clientMsgId": order_id,
                    "payload": {
                        "ctidTraderAccountId": int(self.account_id),
                        "symbolName": symbol,
                        "tradeSide": side,
                        "volume": max(1000, int(amount * 100)),
                        "orderType": "MARKET",
                    }
                }))

            logger.info(f"ORDER: {symbol} {direction} ${amount:.2f} → {order_id}")
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

                async for raw in self.ws:
                    try:
                        msg = json.loads(raw)
                        payload_type = msg.get("payloadType", "")
                        payload = msg.get("payload", {})

                        if payload_type == "PROTO_OA_SPOT_EVENT":
                            symbol = payload.get("symbolName", "")
                            bid = float(payload.get("bid", 0)) / 100000
                            ask = float(payload.get("ask", 0)) / 100000
                            if bid > 0 and ask > 0:
                                for cb in self._callbacks.get(symbol, []):
                                    try:
                                        cb(symbol, bid, ask, time.time())
                                    except Exception:
                                        pass

                        elif payload_type == "PROTO_OA_APPLICATION_AUTH_RES":
                            logger.info("App authenticated on cTrader WS")
                            await self.ws.send(json.dumps({
                                "payloadType": "PROTO_OA_ACCOUNT_AUTH_REQ",
                                "clientMsgId": "auth_account",
                                "payload": {
                                    "ctidTraderAccountId": int(self.account_id),
                                    "accessToken": self.access_token,
                                }
                            }))

                        elif payload_type == "PROTO_OA_ACCOUNT_AUTH_RES":
                            logger.info(f"Account {self.account_id} authenticated")
                            # Re-subscribe all symbols
                            for symbol in self._subscriptions:
                                await self.subscribe(symbol, lambda s, b, a, t: None)

                        elif payload_type == "PROTO_OA_ERROR_RES":
                            logger.error(f"cTrader error: {payload}")

                    except json.JSONDecodeError:
                        pass

            except Exception as e:
                logger.warning(f"WS listen error: {e}")

            self.connected = False
            self.ws = None
            await asyncio.sleep(5)

            try:
                ws_url = self.WS_DEMO if config.CTRADER_ENV == "demo" else self.WS_LIVE
                self.ws = await websockets.connect(ws_url, ping_interval=20)
                self.connected = True
                await self.ws.send(json.dumps({
                    "payloadType": "PROTO_OA_APPLICATION_AUTH_REQ",
                    "clientMsgId": "auth_app_reconnect",
                    "payload": {
                        "clientId": self.client_id,
                        "clientSecret": self.client_secret,
                    }
                }))
            except Exception as e:
                logger.error(f"Reconnect failed: {e}")
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