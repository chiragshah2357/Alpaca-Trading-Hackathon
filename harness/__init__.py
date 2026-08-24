"""The agent harness — the loop that drives the engine (README §4, §6).

    from feed import AlpacaDataSource, StateStore
    from harness import run_cycle
    state = run_cycle(AlpacaDataSource(), StateStore("state.json"))  # one cron tick
    print(state["log"])

A plain, dependency-free Python loop (`run_cycle`) — no LangGraph. Swap `default_decider`
(llm.py) and `default_executor` (executor.py) for the real LLM + Alpaca order placement;
the node contracts stay the same.
"""
from __future__ import annotations

from .executor import BrokerExecutor, DryRunBroker, default_executor
from .llm import default_decider, make_llm_decider
from .orders import OptionLeg, OrderIntent, plan_to_orders
from .run import run_cycle

__all__ = [
    "run_cycle",
    "default_decider",
    "make_llm_decider",
    "default_executor",
    "BrokerExecutor",
    "DryRunBroker",
    "OrderIntent",
    "OptionLeg",
    "plan_to_orders",
    "make_mcp_executor",
]


def __getattr__(name: str):
    # Lazy — importing `harness` never imports langchain-mcp-adapters; only touching
    # make_mcp_executor does.
    if name == "make_mcp_executor":
        from .mcp_executor import make_mcp_executor

        return make_mcp_executor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
