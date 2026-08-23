"""The LangGraph wiring (README §4, §6).

    measure --> decide --> (execute | log) --> END

`langgraph` is imported lazily inside `build_graph`, so importing this package never
requires the dep — install it (`pip install langgraph`, already in requirements.txt)
only when you want the real graph. The node LOGIC lives in `nodes.py`; here we just
bind dependencies (the data source, state store, decider, executor) and wire the edges.
"""
from __future__ import annotations

from . import nodes
from .executor import default_executor
from .llm import default_decider


def build_graph(
    source,
    state_store,
    *,
    decider=default_decider,
    executor=default_executor,
    index_symbol: str = "SPY",
    day_pnl_pct: float = 0.0,
):
    """Compile the LangGraph agent loop bound to a data source + state store."""
    from langgraph.graph import END, StateGraph  # lazy: only needed for the real graph

    from .state import GraphState

    def _measure(state: GraphState) -> dict:
        return nodes.measure(
            source, state_store,
            day_pnl_pct=state.get("day_pnl_pct", day_pnl_pct),
            index_symbol=index_symbol,
        )

    def _decide(state: GraphState) -> dict:
        return nodes.decide(state["context"], decider)

    def _route(state: GraphState) -> str:
        return nodes.route_after_decide(state["decision"], state["context"])

    def _execute(state: GraphState) -> dict:
        return nodes.execute(state["decision"], state["context"], executor)

    def _log(state: GraphState) -> dict:
        return nodes.log_cycle(state["context"], state.get("decision"), state.get("execution"))

    g = StateGraph(GraphState)
    g.add_node("measure", _measure)
    g.add_node("decide", _decide)
    g.add_node("execute", _execute)
    g.add_node("log", _log)

    g.set_entry_point("measure")
    g.add_edge("measure", "decide")
    g.add_conditional_edges("decide", _route, {"execute": "execute", "log": "log"})
    g.add_edge("execute", "log")
    g.add_edge("log", END)
    return g.compile()
