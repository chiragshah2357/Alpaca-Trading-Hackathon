"""MVP risk engine for the Track-3 hedging agent.

Deterministic math only (README §7.0 "must-build essentials"). Given a portfolio
and market data, it computes a risk snapshot + a Risk Score (0-100), maps that to a
target hedge coverage, and sizes a protective-put hedge. No LLM, no broker calls —
those layers sit on top and read this engine's output.

Pure standard library (math/statistics/dataclasses) so it runs with zero installs.
"""
from __future__ import annotations

from .types import HedgePlan, MarketData, Portfolio, Position, RiskSnapshot
from .engine import assess, plan_hedge
from .book import (
    DEFAULT_BOOK,
    BookEntry,
    build_portfolio,
    current_weights,
    rebalance_orders,
    target_cash_weight,
)
from .payoffs import (
    CollarPayoff,
    ProtectivePutPayoff,
    PutSpreadPayoff,
    StressResult,
    collar_payoff,
    protective_put_payoff,
    put_spread_payoff,
    stress_pnl,
)

__all__ = [
    "Position",
    "Portfolio",
    "MarketData",
    "RiskSnapshot",
    "HedgePlan",
    "assess",
    "plan_hedge",
    # payoffs (§7.5, §7.8, §7.9)
    "ProtectivePutPayoff",
    "CollarPayoff",
    "PutSpreadPayoff",
    "StressResult",
    "protective_put_payoff",
    "collar_payoff",
    "put_spread_payoff",
    "stress_pnl",
]
