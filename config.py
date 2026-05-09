"""
Configuration — All environment variables and constants.m
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Central configuration for Aurora Parasite."""

    # Deriv API
    DERIV_APP_ID: str = os.getenv("DERIV_APP_ID", "")
    DERIV_API_TOKEN: str = os.getenv("DERIV_API_TOKEN", "")
    DERIV_LOGIN: str = os.getenv("DERIV_LOGIN", "")

    # Supabase
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    # Trading Instruments
    INSTRUMENTS: list = [
        "R_10", "R_25", "R_50", "R_75", "R_100",
        "1HZ10V", "1HZ25V", "1HZ50V", "1HZ75V", "1HZ100V",
        "BOOM300", "BOOM500", "BOOM1000",
        "CRASH300", "CRASH500", "CRASH1000"
    ]

    # Cross-instrument pairs (volatility indices)
    CROSS_INSTRUMENT_PAIRS: list = [
        ("R_50", "1HZ50V"),
        ("R_100", "1HZ100V"),
        ("BOOM500", "CRASH500")
    ]

    # Nervous System
    TICK_WINDOW: int = 500
    VELOCITY_WINDOW: float = 1.0  # seconds
    SPREAD_WINDOW: int = 20

    # Neural Cortex
    MAX_BRANCHES: int = 50
    CONFIDENCE_BOOST: float = 0.05
    CONFIDENCE_DECAY: float = 0.01
    MIN_TEST_TRADES: int = 10
    PROMOTION_WIN_RATE: float = 0.55
    KILL_WIN_RATE: float = 0.35

    # Permanent Laws
    PERMANENT_LAW_TRADES: int = 500
    PERMANENT_LAW_SHARPE: float = 1.5

    # Priming
    PRIMING_HOURS: int = 24

    # Layer Risk (R per trade)
    LAYER_RISK: dict = {
        "spread_capture": 0.003,    # 0.3% R
        "tick_momentum": 0.005,     # 0.5% R
        "fade_engine": 0.007,       # 0.7% R
        "news_scalper": 0.010,      # 1.0% R
        "cross_instrument": 0.004,  # 0.4% R
    }

    # Spread Capture (Layer 1)
    SPREAD_CAPTURE_MAX_VELOCITY: float = 5.0
    SPREAD_CAPTURE_SPREAD_RATIO: float = 1.5
    SPREAD_CAPTURE_MAX_DURATION: float = 10.0

    # Tick Momentum (Layer 2)
    TICK_MOMENTUM_MIN_VELOCITY: float = 10.0
    TICK_MOMENTUM_MAX_SPREAD: float = 1.2
    TICK_MOMENTUM_CONSECUTIVE_TICKS: int = 3

    # Fade Engine (Layer 3)
    FADE_VELOCITY_SPIKE: float = 30.0
    FADE_SPREAD_RATIO: float = 2.0
    FADE_PRICE_JUMP: float = 0.002
    FADE_MAX_DURATION: float = 30.0

    # News Scalper (Layer 4)
    NEWS_VELOCITY_SPIKE: float = 50.0
    NEWS_SIMULTANEOUS_INSTRUMENTS: int = 3

    # Cross-Instrument (Layer 5)
    CROSS_INSTRUMENT_STD_THRESHOLD: float = 2.0

    # Dynamic Exposure
    NORMAL_VOL_EXPOSURE: float = 0.10  # 10% max exposure
    LOW_VOL_EXPOSURE: float = 0.15
    HIGH_VOL_EXPOSURE: float = 0.06
    EXTREME_VOL_EXPOSURE: float = 0.03

    # Position Limits
    MAX_POSITIONS_PER_INSTRUMENT: int = 3
    INITIAL_CAPITAL: float = 10000.0

    # System
    EVOLUTION_INTERVAL: int = 3600  # Hourly
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration."""
        if not cls.DERIV_APP_ID or not cls.DERIV_API_TOKEN:
            raise ValueError("DERIV_APP_ID and DERIV_API_TOKEN are required")
        if not cls.SUPABASE_URL or not cls.SUPABASE_SERVICE_ROLE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        return True


config = Config()
