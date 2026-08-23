"""The agent harness — the loop that drives the engine (README §4, §6).

    from feed import AlpacaDataSource, StateStore
    from harness import run_cycle
    state = run_cycle(AlpacaDataSource(), StateStore("state.json"))  # one cron tick
    print(state["log"])

`run_cycle` works today with no extra deps (manual runner). For the real LangGraph graph
use `build_graph(...)` or `run_cycle(..., use_langgraph=True)` (needs `pip install
langgraph`). Swap `default_decider` (llm.py) and `default_executor` (executor.py) for the
real LLM + Alpaca order placement — the node contracts stay the same.
"""
from __future__ import annotations

from .executor import BrokerExecutor, DryRunBroker, default_executor
from .llm import default_decider
from .orders import OptionLeg, OrderIntent, plan_to_orders
from .run import run_cycle
from .state import GraphState

__all__ = [
    "run_cycle",
    "GraphState",
    "default_decider",
    "default_executor",
    "BrokerExecutor",
    "DryRunBroker",
    "OrderIntent",
    "OptionLeg",
    "plan_to_orders",
    "build_graph",
    "make_mcp_executor",
]


def __getattr__(name: str):
    # Lazy — importing `harness` never imports langgraph or langchain-mcp-adapters;
    # only touching these attributes does.
    if name == "build_graph":
        from .graph import build_graph

        return build_graph
    if name == "make_mcp_executor":
        from .mcp_executor import make_mcp_executor

        return make_mcp_executor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
