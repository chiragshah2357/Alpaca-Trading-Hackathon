"""Tests for the harness skeleton — the agent loop wiring (dependency-free runner).

Covers the node routing and a full cycle with the offline MockDataSource + stubs, so
the loop is verified without LangGraph or Alpaca.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from feed import MockDataSource, StateStore
from harness import default_decider, run_cycle
from harness import nodes


class TestHarness(unittest.TestCase):
    def _state_store(self):
        return StateStore(Path(tempfile.mkdtemp(prefix="harn_")) / "s.json")

    def test_full_cycle_dry_run(self):
        state = run_cycle(MockDataSource(), self._state_store())
        for key in ("context", "decision", "log"):
            self.assertIn(key, state)
        self.assertTrue(state["decision"]["approved"])
        # MockDataSource is a harvest cycle -> should propose orders (dry run)
        self.assertIn("execution", state)
        self.assertTrue(state["execution"]["dry_run"])
        self.assertGreater(len(state["execution"]["orders"]), 0)
        self.assertIsInstance(state["log"], str)

    def test_route_skips_execute_when_nothing_to_do(self):
        # a SIT context: no income legs, hedge hold -> route to 'log'
        ctx = {"plan": {"income": {"legs": []}, "hedge": {"action": "hold"}}}
        decision = default_decider(
            {"plan": {"posture": "SIT", "income": {"legs": []},
                      "hedge": {"action": "hold"}}}
        )
        self.assertEqual(nodes.route_after_decide(decision, ctx), "log")

    def test_route_executes_when_income_present(self):
        ctx = {"plan": {"income": {"legs": [{"kind": "iron_condor"}]},
                        "hedge": {"action": "hold"}}}
        self.assertEqual(nodes.route_after_decide({"approved": True}, ctx), "execute")

    def test_daily_halt_flows_through_loop(self):
        # a big down day -> validate halts income -> loop still completes cleanly
        state = run_cycle(MockDataSource(), self._state_store(), day_pnl_pct=-0.07)
        self.assertFalse(state["context"]["plan"]["income"]["legs"])
        self.assertFalse(state["context"]["validation"]["ok"])
        self.assertIn("log", state)


if __name__ == "__main__":
    unittest.main(verbosity=2)
