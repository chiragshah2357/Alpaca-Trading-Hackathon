"""The graph state — the shared bag passed between nodes each cycle (README §4).

A plain TypedDict so it works with LangGraph *and* the no-dependency manual runner.
Nodes return partial updates that get merged into this state.
"""
from __future__ import annotations

from typing import TypedDict


class GraphState(TypedDict, total=False):
    day_pnl_pct: float   # today's P&L as a fraction of equity (feeds the daily-loss halt)
    context: dict        # get_strategy_context() output: snapshot + risk-capped plan
    decision: dict       # DECIDE node output: approved?, chosen legs, reasoning
    execution: dict      # EXECUTE node output: orders placed (or dry-run)
    log: str             # LOG node output: one-line cycle summary
