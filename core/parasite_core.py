"""
Aurora Parasite Core — Pepperstone cTrader Edition.
All 5 layers active. No cortex gating. Real orders. Full aggression.
"""

import asyncio
import time
import os
import json
from config import config
from logger import get_logger
from brokers.pepperstone_ctrader_client import CtraderClient
from core.nervous_system import NervousSystem
from core.neural_cortex import NeuralCortex
from core.execution_engine import ExecutionEngine
from core.dynamic_exposure import DynamicExposure
from aggression.spread_capture import SpreadCapture
from aggression.tick_momentum import TickMomentum
from aggression.fade_engine import FadeEngine
from aggression.news_scalper import NewsScalper
from aggression.cross_instrument import CrossInstrumentArb

logger = get_logger("parasite")

# Path for persisting refresh token between restarts
TOKEN_CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", ".token_cache.json")


class ParasiteCore:
    def __init__(self):
        self.running = False
        self.halted = False
        self.start_time = time.time()
        self.initial_capital = config.INITIAL_CAPITAL
        self.current_balance = config.INITIAL_CAPITAL
        self.total_trades = 0
        self.total_r = 0.0
        self.trade_log = []

        # Core components
        self.broker_client = CtraderClient()
        self.nervous_system = NervousSystem(config.INSTRUMENTS)
        self.cortex = NeuralCortex()
        self.execution = ExecutionEngine(self)
        self.dynamic_exposure = DynamicExposure()

        # All 5 aggression layers
        self.spread_capture = SpreadCapture(self)
        self.tick_momentum = TickMomentum(self)
        self.fade_engine = FadeEngine(self)
        self.news_scalper = NewsScalper(self)
        self.cross_instrument = CrossInstrumentArb(self)

    # ═══════════════════════════════════════════════════════════════
    # AUTH FIX: Proper OAuth2 Authorization Code + Refresh Token Flow
    # ═══════════════════════════════════════════════════════════════

    def _load_cached_token(self) -> str | None:
        """Load a previously saved refresh token from disk."""
        try:
            if os.path.exists(TOKEN_CACHE_PATH):
                with open(TOKEN_CACHE_PATH, "r") as f:
                    data = json.load(f)
                    token = data.get("refresh_token")
                    if token:
                        logger.info("Loaded cached refresh token")
                        return token
        except Exception as e:
            logger.warning(f"Failed to load token cache: {e}")
        return None

    def _save_cached_token(self, refresh_token: str):
        """Persist the refresh token to disk for subsequent restarts."""
        try:
            cache_dir = os.path.dirname(TOKEN_CACHE_PATH)
            os.makedirs(cache_dir, exist_ok=True)
            with open(TOKEN_CACHE_PATH, "w") as f:
                json.dump({"refresh_token": refresh_token}, f)
            logger.info("Refresh token cached to disk")
        except Exception as e:
            logger.warning(f"Failed to save token cache: {e}")

    def _get_auth_url(self) -> str:
        """Build the authorization URL for first-time browser login."""
        base_url = "https://id.ctrader.com/oauth/authorize"
        params = {
            "client_id": config.CTRADER_CLIENT_ID,
            "redirect_uri": "https://127.0.0.1:8000/callback",  # local callback
            "scope": "accounts offline_access",
            "response_type": "code",
            "state": "aurora_parasite",
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{base_url}?{query}"

    async def _exchange_code_for_token(self, auth_code: str) -> dict | None:
        """Exchange authorization code for access + refresh tokens."""
        try:
            token_url = "https://id.ctrader.com/oauth/token"
            payload = {
                "grant_type": "authorization_code",
                "code": auth_code,
                "redirect_uri": "https://127.0.0.1:8000/callback",
                "client_id": config.CTRADER_CLIENT_ID,
                "client_secret": config.CTRADER_CLIENT_SECRET,
            }
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(token_url, data=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        logger.info("Successfully exchanged auth code for tokens")
                        return data
                    else:
                        error_body = await resp.text()
                        logger.error(f"Token exchange failed: {resp.status} — {error_body}")
                        return None
        except Exception as e:
            logger.error(f"Token exchange exception: {e}")
            return None

    async def _refresh_access_token(self, refresh_token: str) -> dict | None:
        """Use refresh token to get a new access token."""
        try:
            token_url = "https://id.ctrader.com/oauth/token"
            payload = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": config.CTRADER_CLIENT_ID,
                "client_secret": config.CTRADER_CLIENT_SECRET,
            }
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(token_url, data=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        logger.info("Successfully refreshed access token")
                        return data
                    else:
                        error_body = await resp.text()
                        logger.error(f"Token refresh failed: {resp.status} — {error_body}")
                        return None
        except Exception as e:
            logger.error(f"Token refresh exception: {e}")
            return None

    async def _authenticate(self) -> str | None:
        """
        Full OAuth2 flow:
        1. Try cached refresh token first
        2. If that fails, require manual browser auth (one-time)
        3. Return valid access token or None
        """
        # --- Step 1: Try cached refresh token ---
        cached_refresh = self._load_cached_token()
        if cached_refresh:
            token_data = await self._refresh_access_token(cached_refresh)
            if token_data:
                refresh_token = token_data.get("refresh_token", cached_refresh)
                self._save_cached_token(refresh_token)
                return token_data.get("access_token")

        # --- Step 2: First-time auth required ---
        auth_url = self._get_auth_url()
        logger.warning("=" * 60)
        logger.warning("MANUAL AUTHENTICATION REQUIRED (ONE-TIME)")
        logger.warning("1. Open this URL in a browser:")
        logger.warning(f"   {auth_url}")
        logger.warning("2. Log in to your Pepperstone cTrader account")
        logger.warning("3. After redirect, copy the 'code' parameter from the URL")
        logger.warning("4. Set it as env var: PEPPERSTONE_AUTH_CODE=<code>")
        logger.warning("   Then restart the application.")
        logger.warning("=" * 60)

        # Check if auth code was provided via environment variable
        auth_code = os.getenv("PEPPERSTONE_AUTH_CODE")
        if not auth_code:
            logger.error("No PEPPERSTONE_AUTH_CODE environment variable set")
            return None

        token_data = await self._exchange_code_for_token(auth_code)
        if not token_data:
            return None

        refresh_token = token_data.get("refresh_token")
        if refresh_token:
            self._save_cached_token(refresh_token)

        return token_data.get("access_token")

    # ═══════════════════════════════════════════════════════════════
    # END AUTH FIX
    # ═══════════════════════════════════════════════════════════════

    async def start(self):
        logger.info("🦠 PARASITE AWAKENING — PEPPERSTONE MODE")
        config.validate()

        # --- Authenticate first (new flow) ---
        access_token = await self._authenticate()
        if not access_token:
            raise RuntimeError(
                "Failed to authenticate with Pepperstone cTrader. "
                "Set PEPPERSTONE_AUTH_CODE env var after browser login."
            )

        # --- Connect with access token ---
        connected = await self.broker_client.connect(
            config.CTRADER_CLIENT_ID,
            config.CTRADER_CLIENT_SECRET,
            config.CTRADER_ACCOUNT_ID,
            access_token=access_token,  # Pass the token
        )
        if not connected:
            raise RuntimeError("Failed to connect to Pepperstone cTrader")

        await self.nervous_system.start(self.broker_client)
        await self.cortex.start()
        await self.dynamic_exposure.start(self)

        logger.info("Warming tick buffers (10s)...")
        await asyncio.sleep(10)

        self.running = True
        logger.info("All 5 layers launching simultaneously 🦠")

        await asyncio.gather(
            self.spread_capture.run(),
            self.tick_momentum.run(),
            self.fade_engine.run(),
            self.news_scalper.run(),
            self.cross_instrument.run(),
            self._cortex_signal_loop(),
            self._evolution_loop(),
            self._risk_monitor(),
            self._balance_sync_loop(),
        )

    async def _cortex_signal_loop(self):
        while self.running:
            try:
                signal = await asyncio.wait_for(
                    self.nervous_system.signal_queue.get(), timeout=1.0
                )
                decision = await self.cortex.process_signal(signal)
                if decision and decision.get("confidence", 0) > 0.65:
                    await self.execution.execute_decision(decision, signal)
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                logger.error(f"Cortex loop error: {e}")

    async def _evolution_loop(self):
        while self.running:
            await asyncio.sleep(config.EVOLUTION_INTERVAL)
            try:
                self.cortex.scan_for_patterns()
                await self.cortex.decay_branches()
                promoted = len([
                    b for b in self.cortex.branches.values()
                    if b.status == "PROMOTED"
                ])
                logger.info(f"Evolution complete: {promoted} branches promoted")
            except Exception as e:
                logger.error(f"Evolution error: {e}")

    async def _risk_monitor(self):
        while self.running:
            await asyncio.sleep(5)
            try:
                drawdown = (
                    (self.initial_capital - self.current_balance)
                    / self.initial_capital
                )
                if drawdown >= config.HARD_STOP_DRAWDOWN:
                    self.halted = True
                    logger.warning(f"HARD STOP TRIGGERED: drawdown={drawdown:.1%}")
                elif self.halted and drawdown < config.HARD_STOP_DRAWDOWN * 0.8:
                    self.halted = False
                    logger.info("Hard stop cleared — trading resumed")
            except Exception as e:
                logger.error(f"Risk monitor error: {e}")

    async def _balance_sync_loop(self):
        while self.running:
            await asyncio.sleep(60)
            try:
                balance, currency = self.broker_client.get_balance()
                if balance > 0:
                    self.current_balance = balance
            except Exception as e:
                logger.error(f"Balance sync error: {e}")

    async def record_trade(self, trade_data: dict):
        self.total_trades += 1
        r = trade_data.get("r_multiple", 0.0)
        self.total_r += r
        profit = trade_data.get("profit_currency", 0.0)
        self.current_balance += profit
        self.trade_log.append({
            **trade_data,
            "balance_after": round(self.current_balance, 4),
            "timestamp": time.time(),
        })
        if len(self.trade_log) > 5000:
            self.trade_log = self.trade_log[-5000:]

    def get_status(self) -> dict:
        uptime = time.time() - self.start_time
        return {
            "running": self.running,
            "halted": self.halted,
            "initial_capital": self.initial_capital,
            "current_balance": round(self.current_balance, 4),
            "balance_cap": config.BALANCE_CAP,
            "cap_halted": self.current_balance >= config.BALANCE_CAP,
            "uptime_seconds": round(uptime, 2),
            "total_trades": self.total_trades,
            "total_r": round(self.total_r, 4),
            "avg_r_per_trade": round(
                self.total_r / max(self.total_trades, 1), 4
            ),
            "instruments": config.INSTRUMENTS,
            "nervous_system": self.nervous_system.get_stats(),
            "cortex": self.cortex.get_stats(),
            "exposure": self.dynamic_exposure.get_stats(),
            "layers": {
                "spread_capture": self.spread_capture.get_stats(),
                "tick_momentum": self.tick_momentum.get_stats(),
                "fade_engine": self.fade_engine.get_stats(),
                "news_scalper": self.news_scalper.get_stats(),
                "cross_instrument": self.cross_instrument.get_stats(),
            },
        }