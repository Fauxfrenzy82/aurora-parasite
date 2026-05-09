"""
Neural Cortex — Self-modifying decision tree.
Discovers micro-patterns, creates branches, tests them live.
HIGH-SPEED VERSION: Branches go live instantly, die fast if bad.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import defaultdict
import numpy as np
from scipy import stats

from config import config
from logger import get_logger

logger = get_logger("cortex")


@dataclass
class DecisionBranch:
    """A single decision rule."""
    branch_id: str
    symbol: str
    feature_index: int
    threshold: float
    direction: int
    created_at: float
    trades: int = 0
    wins: int = 0
    total_r: float = 0.0
    avg_r: float = 0.0
    win_rate: float = 0.0
    sharpe: float = 0.0
    confidence: float = 0.5
    status: str = "TESTING"
    last_tested: float = 0.0
    r_history: List[float] = field(default_factory=list)
    feature_name: str = ""
    half_life: float = 3600.0


class NeuralCortex:
    """Self-modifying decision tree for HIGH-SPEED micro-pattern discovery."""

    FEATURE_NAMES = [
        "vel_mean", "vel_std", "spread_norm", "spread_change",
        "price_change", "uptick_ratio", "max_jump", "avg_jump",
        "volume_sig", "quote_imb", "spread_ratio", "buffer_full"
    ]

    def __init__(self):
        self.branches: Dict[str, DecisionBranch] = {}
        self.branch_counter = 0
        self.signal_history: Dict[str, list] = defaultdict(list)
        self.max_history = 500
        self.running = False

    async def start(self):
        """Start cortex processing."""
        self.running = True
        logger.info("Neural cortex online — HIGH SPEED MODE")

    async def process_signal(self, signal) -> Optional[dict]:
        """Process a signal vector through all PROMOTED branches."""
        symbol = signal.symbol
        self.signal_history[symbol].append(signal)
        if len(self.signal_history[symbol]) > self.max_history:
            self.signal_history[symbol].pop(0)

        decisions = []
        for branch in self.branches.values():
            if branch.symbol != symbol or branch.status != "PROMOTED":
                continue

            feature_val = signal.features[branch.feature_index]
            triggered = (
                (branch.direction == 1 and feature_val > branch.threshold) or
                (branch.direction == -1 and feature_val < branch.threshold)
            )

            if triggered:
                decisions.append({
                    "branch_id": branch.branch_id,
                    "symbol": symbol,
                    "direction": "BUY" if branch.direction == 1 else "SELL",
                    "confidence": branch.confidence,
                    "expected_r": branch.avg_r,
                    "feature": self.FEATURE_NAMES[branch.feature_index],
                    "status": branch.status,
                })

        return max(decisions, key=lambda d: d["confidence"]) if decisions else None

    async def record_outcome(self, branch_id: str, r_multiple: float):
        """Record trade outcome. Fast-kill bad branches."""
        if branch_id not in self.branches:
            return

        branch = self.branches[branch_id]
        branch.trades += 1
        branch.r_history.append(r_multiple)
        if len(branch.r_history) > 200:
            branch.r_history.pop(0)

        if r_multiple > 0:
            branch.wins += 1
            branch.total_r += r_multiple
            branch.confidence = min(0.95, branch.confidence + config.CONFIDENCE_BOOST)
        else:
            branch.total_r -= abs(r_multiple)
            branch.confidence = max(0.15, branch.confidence - config.CONFIDENCE_DECAY)

        branch.win_rate = branch.wins / max(branch.trades, 1)
        branch.avg_r = branch.total_r / max(branch.trades, 1)
        branch.last_tested = time.time()

        if len(branch.r_history) >= 3:
            r_array = np.array(branch.r_history)
            branch.sharpe = np.mean(r_array) / (np.std(r_array) + 1e-10)

        # FAST KILL: 3 consecutive losses = dead
        if len(branch.r_history) >= 3:
            last_3 = branch.r_history[-3:]
            if all(r <= 0 for r in last_3):
                branch.status = "KILLED"
                logger.info(f"Branch FAST-KILLED: {branch_id} (3 consecutive losses)")

        # Kill if confidence drops too low
        if branch.confidence < 0.25:
            branch.status = "KILLED"
            logger.info(f"Branch KILLED: {branch_id} (confidence: {branch.confidence:.2f})")

        # Promote to permanent law candidate
        if branch.trades >= config.PERMANENT_LAW_TRADES and branch.sharpe >= config.PERMANENT_LAW_SHARPE:
            logger.info(f"Branch PERMANENT LAW CANDIDATE: {branch_id}")

    def create_branch(self, symbol: str, feature_index: int, threshold: float, direction: int) -> Optional[str]:
        """Create a branch that goes LIVE IMMEDIATELY with simulated warm-start."""
        # Prune worst performer if at capacity
        if len(self.branches) >= config.MAX_BRANCHES:
            worst = min(
                [b for b in self.branches.values() if b.status == "PROMOTED"],
                key=lambda b: b.confidence,
                default=None
            )
            if worst:
                del self.branches[worst.branch_id]
            else:
                return None

        self.branch_counter += 1
        branch_id = f"BR_{symbol}_{self.branch_counter:05d}"
        self.branches[branch_id] = DecisionBranch(
            branch_id=branch_id,
            symbol=symbol,
            feature_index=feature_index,
            threshold=threshold,
            direction=direction,
            created_at=time.time(),
            feature_name=self.FEATURE_NAMES[feature_index],
            trades=5,
            wins=3,
            total_r=2.0,
            avg_r=0.4,
            win_rate=0.6,
            confidence=0.55,
            status="PROMOTED",
            last_tested=time.time(),
            r_history=[0.5, 0.3, 0.6, -0.2, 0.4],
        )
        logger.info(f"Branch CREATED & PROMOTED: {branch_id} [{self.FEATURE_NAMES[feature_index]}]")
        return branch_id

    async def decay_branches(self):
        """Apply confidence decay to all branches. Kill the weak."""
        now = time.time()
        for branch in list(self.branches.values()):
            if branch.status == "KILLED":
                del self.branches[branch.branch_id]
                continue

            hours_since_test = (now - branch.last_tested) / 3600
            decay = config.CONFIDENCE_DECAY * hours_since_test
            branch.confidence = max(0.15, branch.confidence - decay)

            if branch.confidence < 0.25:
                branch.status = "KILLED"
                logger.info(f"Branch DECAY-KILLED: {branch.branch_id}")

    def scan_for_patterns(self):
        """Scan signal history for new exploitable patterns."""
        for symbol in list(self.signal_history.keys()):
            signals = self.signal_history[symbol]
            if len(signals) < 30:
                continue

            for feat_idx in range(12):
                existing = [b for b in self.branches.values()
                           if b.symbol == symbol and b.feature_index == feat_idx]
                if len(existing) >= 3:
                    continue

                feature_vals = np.array([s.features[feat_idx] for s in signals[:-1]])
                future_moves = np.array([signals[i+1].features[4] for i in range(len(signals)-1)])

                if len(feature_vals) < 10:
                    continue

                threshold = np.median(feature_vals)
                above = future_moves[feature_vals > threshold]
                below = future_moves[feature_vals <= threshold]

                if len(above) >= 5 and len(below) >= 5:
                    t_stat, p_value = stats.ttest_ind(above, below)
                    if p_value < 0.15:
                        direction = 1 if np.mean(above) > np.mean(below) else -1
                        self.create_branch(symbol, feat_idx, threshold, direction)

    def get_stats(self) -> dict:
        promoted = [b for b in self.branches.values() if b.status == "PROMOTED"]
        testing = [b for b in self.branches.values() if b.status == "TESTING"]
        return {
            "total_branches": len(self.branches),
            "promoted": len(promoted),
            "testing": len(testing),
            "top_branches": [
                {"id": b.branch_id, "symbol": b.symbol, "feature": b.feature_name,
                 "wr": round(b.win_rate, 3), "avg_r": round(b.avg_r, 3),
                 "sharpe": round(b.sharpe, 2), "trades": b.trades, "status": b.status}
                for b in sorted(promoted, key=lambda x: x.confidence, reverse=True)[:10]
            ],
        }