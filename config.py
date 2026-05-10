"""
Aurora Parasite — Central Configuration.
Upgraded for Pepperstone cTrader.
No artificial limits. No cooldowns. Maximum frequency.
"""

import os
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ── Pepperstone cTrader ──────────────────────────
    CTRADER_CLIENT_ID: str = os.getenv("CTRADER_CLIENT_ID", "")
    CTRADER_CLIENT_SECRET: str = os.getenv("CTRADER_CLIENT_SECRET", "")
    CTRADER_ACCOUNT_ID: str = os.getenv("CTRADER_ACCOUNT_ID", "")
    CTRADER_ENV: str = os.getenv("CTRADER_ENV", "demo")  # demo or live

    # ── Supabase ─────────────────────────────────────
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    # ── Account ──────────────────────────────────────
    ACCOUNT_TYPE: str = os.getenv("ACCOUNT_TYPE", "DEMO")
    INITIAL_CAPITAL: float = float(os.getenv("INITIAL_CAPITAL", "500.0"))

    # ── Risk (Aggressive — No Limits) ────────────────
    MAX_DRAWDOWN_PCT: float = 0.40
    MAX_EXPOSURE_PCT: float = 0.80
    MAX_POSITIONS_PER_INSTRUMENT: int = 3  # Was 1, now allows pyramiding
    BASE_RISK_PCT: float = 0.02
    KELLY_FRACTION: float = 0.5
    HARD_STOP_DRAWDOWN: float = 0.40

    # ── Per-Layer Risk ───────────────────────────────
    LAYER_RISK: Dict[str, float] = {
        "spread_capture": 0.003,
        "tick_momentum": 0.005,
        "fade_engine": 0.007,
        "news_scalper": 0.01,
        "cross_instrument": 0.004,
    }

    # ── Pepperstone Forex Instruments ────────────────
    INSTRUMENTS: List[str] = [
        "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
        "EURGBP", "EURJPY", "GBPJPY", "EURCHF", "GBPCHF", "AUDJPY", "NZDJPY",
        "EURAUD", "EURCAD", "GBPAUD", "GBPCAD", "AUDCAD", "AUDCHF", "CHFJPY",
        "CADJPY", "CADCHF", "NZDCAD", "NZDCHF",
        "XAUUSD", "XAGUSD", "USOIL", "UKOIL",
        "BTCUSD", "ETHUSD",
    ]

    JPY_PAIRS: List[str] = [
        "USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "NZDJPY", "CHFJPY", "CADJPY"
    ]

    # ── CROSS_INSTRUMENT PAIRS ───────────────────────
    CROSS_INSTRUMENT_PAIRS: List[tuple] = [
        ("EURUSD", "GBPUSD"),
        ("AUDUSD", "NZDUSD"),
        ("XAUUSD", "XAGUSD"),
        ("USOIL", "UKOIL"),
        ("EURUSD", "USDCHF"),
    ]

    # ── Nervous System ───────────────────────────────
    TICK_WINDOW: int = 200
    VELOCITY_WINDOW: float = 3.0  # Was 5.0, faster detection
    SPREAD_WINDOW: int = 30       # Was 50
    JUMP_THRESHOLD: float = 0.0002  # Was 0.0003

    # ── Neural Cortex ────────────────────────────────
    MIN_TEST_TRADES: int = 3      # Was 10, faster promotion
    PROMOTION_WIN_RATE: float = 0.50  # Was 0.52
    KILL_WIN_RATE: float = 0.40   # Was 0.45
    CONFIDENCE_DECAY: float = 0.05
    CONFIDENCE_BOOST: float = 0.05
    MAX_BRANCHES: int = 500       # Was 200
    BRANCH_SCAN_INTERVAL: int = 30  # Was 60, scan twice as often
    PERMANENT_LAW_TRADES: int = 200  # Was 500
    PERMANENT_LAW_SHARPE: float = 1.0  # Was 1.5

    # ── Execution Engine ─────────────────────────────
    PYRAMID_LEVELS: List[Dict] = [
        {"r_trigger": 0.3, "size_ratio": 0.4, "stop_move": 0.0},
        {"r_trigger": 0.7, "size_ratio": 0.3, "stop_move": 0.3},
        {"r_trigger": 1.2, "size_ratio": 0.2, "stop_move": 0.7},
    ]
    MAX_COMBINED_SIZE: float = 1.9

    # ── Aggression Layers ────────────────────────────
    SPREAD_CAPTURE_MAX_VELOCITY: float = 8.0
    SPREAD_CAPTURE_SPREAD_RATIO: float = 1.2  # Was 1.3
    SPREAD_CAPTURE_MAX_DURATION: float = 15.0  # Was 30, faster turnover

    TICK_MOMENTUM_MIN_VELOCITY: float = 4.0    # Was 6.0
    TICK_MOMENTUM_MAX_SPREAD: float = 1.4      # Was 1.3
    TICK_MOMENTUM_CONSECUTIVE_TICKS: int = 2   # Was 3

    FADE_VELOCITY_SPIKE: float = 8.0            # Was 12.0
    FADE_SPREAD_RATIO: float = 1.1              # Was 1.2
    FADE_PRICE_JUMP: float = 0.00015            # Was 0.0003

    NEWS_VELOCITY_SPIKE: float = 10.0           # Was 15.0
    NEWS_SIMULTANEOUS_INSTRUMENTS: int = 2       # Was 2

    CROSS_INSTRUMENT_STD_THRESHOLD: float = 1.2  # Was 1.5, tighter triggers
    CROSS_INSTRUMENT_TIMEOUT: float = 120.0      # New: force-close after 2 min

    # ── Dynamic Exposure ─────────────────────────────
    LOW_VOL_EXPOSURE: float = 0.80               # Was 0.70
    NORMAL_VOL_EXPOSURE: float = 0.65            # Was 0.55
    HIGH_VOL_EXPOSURE: float = 0.40              # Was 0.30
    EXTREME_VOL_EXPOSURE: float = 0.20           # Was 0.15
    EXPOSURE_UPDATE_INTERVAL: int = 300          # New: 5 minutes, was hourly

    # ── System ───────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    EVOLUTION_INTERVAL: int = 1800  # 30 minutes, was 3600
    PERSIST_INTERVAL: int = 300
    PRIMING_HOURS: int = 4          # Less priming, more live learning
    BALANCE_CAP: float = float(os.getenv("BALANCE_CAP", "1000000.0"))

    @classmethod
    def validate(cls) -> bool:
        required = ["CTRADER_CLIENT_ID", "CTRADER_CLIENT_SECRET", "CTRADER_ACCOUNT_ID",
                   "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"]
        missing = [k for k in required if not getattr(cls, k)]
        if missing:
            raise ValueError(f"Missing config: {', '.join(missing)}")
        return True


config = Config()