"""
Aurora Parasite — Central Configuration.
Pepperstone cTrader Edition.
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
    CTRADER_ENV: str = os.getenv("CTRADER_ENV", "demo")

    # ── Supabase ─────────────────────────────────────
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    # ── Account ──────────────────────────────────────
    ACCOUNT_TYPE: str = os.getenv("ACCOUNT_TYPE", "DEMO")
    INITIAL_CAPITAL: float = float(os.getenv("INITIAL_CAPITAL", "500.0"))
    BALANCE_CAP: float = float(os.getenv("BALANCE_CAP", "1000000.0"))

    # ── Risk ─────────────────────────────────────────
    MAX_DRAWDOWN_PCT: float = 0.40
    MAX_EXPOSURE_PCT: float = 0.80
    MAX_POSITIONS_PER_INSTRUMENT: int = 3
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

    # ── Instruments ──────────────────────────────────
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

    CROSS_INSTRUMENT_PAIRS: List[tuple] = [
        ("EURUSD", "GBPUSD"),
        ("AUDUSD", "NZDUSD"),
        ("XAUUSD", "XAGUSD"),
        ("USOIL", "UKOIL"),
        ("EURUSD", "USDCHF"),
    ]

    # ── Nervous System ───────────────────────────────
    TICK_WINDOW: int = 200
    VELOCITY_WINDOW: float = 3.0
    SPREAD_WINDOW: int = 30
    JUMP_THRESHOLD: float = 0.0002

    # ── Neural Cortex ────────────────────────────────
    MIN_TEST_TRADES: int = 3
    PROMOTION_WIN_RATE: float = 0.50
    KILL_WIN_RATE: float = 0.40
    CONFIDENCE_DECAY: float = 0.05
    CONFIDENCE_BOOST: float = 0.05
    MAX_BRANCHES: int = 500
    BRANCH_SCAN_INTERVAL: int = 30
    PERMANENT_LAW_TRADES: int = 200
    PERMANENT_LAW_SHARPE: float = 1.0

    # ── Execution ────────────────────────────────────
    PYRAMID_LEVELS: List[Dict] = [
        {"r_trigger": 0.3, "size_ratio": 0.4, "stop_move": 0.0},
        {"r_trigger": 0.7, "size_ratio": 0.3, "stop_move": 0.3},
        {"r_trigger": 1.2, "size_ratio": 0.2, "stop_move": 0.7},
    ]
    MAX_COMBINED_SIZE: float = 1.9

    # ── Layer Thresholds ─────────────────────────────
    SPREAD_CAPTURE_MAX_VELOCITY: float = 8.0
    SPREAD_CAPTURE_SPREAD_RATIO: float = 1.2
    SPREAD_CAPTURE_MAX_DURATION: float = 15.0

    TICK_MOMENTUM_MIN_VELOCITY: float = 4.0
    TICK_MOMENTUM_MAX_SPREAD: float = 1.4
    TICK_MOMENTUM_CONSECUTIVE_TICKS: int = 2

    FADE_VELOCITY_SPIKE: float = 8.0
    FADE_SPREAD_RATIO: float = 1.1
    FADE_PRICE_JUMP: float = 0.00015

    NEWS_VELOCITY_SPIKE: float = 10.0
    NEWS_SIMULTANEOUS_INSTRUMENTS: int = 2

    CROSS_INSTRUMENT_STD_THRESHOLD: float = 1.2
    CROSS_INSTRUMENT_TIMEOUT: float = 120.0

    # ── Dynamic Exposure ─────────────────────────────
    LOW_VOL_EXPOSURE: float = 0.80
    NORMAL_VOL_EXPOSURE: float = 0.65
    HIGH_VOL_EXPOSURE: float = 0.40
    EXTREME_VOL_EXPOSURE: float = 0.20
    EXPOSURE_UPDATE_INTERVAL: int = 300

    # ── System ───────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    EVOLUTION_INTERVAL: int = 1800
    PERSIST_INTERVAL: int = 300
    PRIMING_HOURS: int = 4

    @classmethod
    def validate(cls) -> bool:
        required = [
            "CTRADER_CLIENT_ID",
            "CTRADER_CLIENT_SECRET",
            "CTRADER_ACCOUNT_ID",
            "SUPABASE_URL",
            "SUPABASE_SERVICE_ROLE_KEY",
        ]
        missing = [k for k in required if not getattr(cls, k)]
        if missing:
            raise ValueError(f"Missing config: {', '.join(missing)}")
        return True


config = Config()