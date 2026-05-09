"""
Correlation Matrix — Cross-instrument correlation tracking.
Prevents overconcentration in correlated instruments.
"""

import numpy as np
from collections import deque
from config import config
from logger import get_logger

logger = get_logger("correlation")


class CorrelationMatrix:
    """
    Tracks rolling correlation between all instruments.
    Used to prevent overexposure to correlated pairs.
    """

    def __init__(self):
        self.price_history = {s: deque(maxlen=100) for s in config.INSTRUMENTS}
        self.correlation_matrix = None
        self.last_update = 0

    def update(self, nervous_system):
        """Update correlation matrix from latest price data."""
        for symbol in config.INSTRUMENTS:
            buffer = nervous_system.tick_buffers.get(symbol)
            if buffer and len(buffer) > 0:
                self.price_history[symbol].append(buffer[-1].mid_price)

        # Recalculate every 30 seconds
        import time
        now = time.time()
        if now - self.last_update < 30:
            return
        self.last_update = now

        # Build returns matrix
        returns_data = {}
        for symbol in config.INSTRUMENTS:
            prices = list(self.price_history[symbol])
            if len(prices) >= 20:
                price_series = np.array(prices)
                returns = np.diff(price_series) / price_series[:-1]
                if len(returns) >= 10:
                    returns_data[symbol] = returns

        if len(returns_data) >= 2:
            symbols = list(returns_data.keys())
            n = len(symbols)
            matrix = np.zeros((n, n))
            for i in range(n):
                for j in range(n):
                    if i == j:
                        matrix[i][j] = 1.0
                    else:
                        corr = np.corrcoef(
                            returns_data[symbols[i]],
                            returns_data[symbols[j]]
                        )[0][1]
                        matrix[i][j] = 0.0 if np.isnan(corr) else corr
            self.correlation_matrix = matrix

    def get_correlation(self, sym_a: str, sym_b: str) -> float:
        """Get correlation between two instruments."""
        if self.correlation_matrix is None:
            return 0.0
        try:
            symbols = list(self.price_history.keys())
            idx_a = symbols.index(sym_a)
            idx_b = symbols.index(sym_b)
            return float(self.correlation_matrix[idx_a][idx_b])
        except (ValueError, IndexError):
            return 0.0

    def is_overcorrelated(self, symbol: str, threshold: float = 0.7) -> bool:
        """Check if a symbol is highly correlated with existing positions."""
        # Placeholder — would check against active positions
        return False

    def get_stats(self) -> dict:
        return {
            "instruments_tracked": len(self.price_history),
            "matrix_available": self.correlation_matrix is not None,
        }