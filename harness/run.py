"""Run one agent cycle — the entry point the cron job calls (README §6).

`run_cycle(...)` executes measure -> decide -> (execute) -> log once and returns the
final state. By default it uses a dependency-free **manual runner** (identical node
logic, no LangGraph needed) so the loop works today; pass `use_langgraph=True` to run
the real compiled graph instead (needs `pip install langgraph`).

A GitHub Actions cron job runs this once per invocation; state (peak mark + IV history)
persists via the StateStore between runs.
"""
from __future__ import annotations

from . import nodes
from .executor import default_executor
from .llm import default_decider


def run_cycle(
    source,
    state_store,
    *,
    decider=default_decider,
    executor=default_executor,
    day_pnl_pct: float = 0.0,
    index_symbol: str = "SPY",
    use_langgraph: bool = False,
) -> dict:
    """Run one observe->decide->execute->log cycle; return the final state dict."""
    if use_langgraph:
        from .graph import build_graph

        graph = build_graph(
            source, state_store, decider=decider, executor=executor,
            index_symbol=index_symbol, day_pnl_pct=day_pnl_pct,
        )
        return dict(graph.invoke({"day_pnl_pct": day_pnl_pct}))

    # Manual runner — same nodes, sequential, no external dependency.
    state: dict = {"day_pnl_pct": day_pnl_pct}
    state.update(nodes.measure(source, state_store, day_pnl_pct, index_symbol))
    state.update(nodes.decide(state["context"], decider))
    if nodes.route_after_decide(state["decision"], state["context"]) == "execute":
        state.update(nodes.execute(state["decision"], state["context"], executor))
    state.update(nodes.log_cycle(state["context"], state.get("decision"), state.get("execution")))
    return state
