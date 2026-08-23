"""Demo: one full agent cycle through the harness skeleton (README §4).

Runs measure -> decide -> execute -> log once with the offline MockDataSource and the
stub decider/executor — no LangGraph, no Alpaca, no network. Shows the loop end to end
and the orders it WOULD place (dry run).

    python demo_harness.py
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from feed import MockDataSource, StateStore
from harness import run_cycle


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="harness_")) / "state.json"
    state = run_cycle(MockDataSource(), StateStore(tmp))

    print(f"{'='*66}\n ONE AGENT CYCLE  (manual runner, stub decide/execute)\n{'='*66}")
    print("DECISION")
    print(f"  approved  = {state['decision']['approved']}")
    print(f"  reasoning = {state['decision']['reasoning']}")
    print("EXECUTION (dry run - orders it would place)")
    for o in state.get("execution", {}).get("orders", []):
        legs = ", ".join(f"{l['action']} {l['right']}{l['strike']:.0f}" for l in o["legs"])
        print(f"  {o['structure']:14s} {o['symbol']} x{o['contracts']} "
              f"({o['net_side']}, {o['expiry_days']}d): {legs}")
    print("LOG")
    print(f"  {state['log']}")

    # sanity: the loop produced every stage
    assert "context" in state and "decision" in state and "log" in state
    json.dumps(state["context"])  # context stays JSON-serializable through the loop
    print(f"\n{'='*66}\n CYCLE OK  [dry-run]\n{'='*66}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
