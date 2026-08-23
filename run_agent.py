"""Cron entry point — run ONE agent cycle (README §6).

Called by `.github/workflows/agent.yml` on a schedule (and runnable locally). Uses live
Alpaca data when `ALPACA_API_KEY`/`ALPACA_SECRET_KEY` are set, otherwise the offline
MockDataSource so it still runs (dry demo). Persists state (peak-equity mark + rolling
IV history) to `state/state.json` between the otherwise-stateless runs.

Execution is still the dry-run stub, so this is SAFE to schedule now: it observes live
data and logs the plan it *would* trade, without placing any orders. Swap in the real
executor (harness/executor.py) when you're ready to actually trade.

    python run_agent.py            # local (mock unless ALPACA_* set)
    AGENT_STATE_PATH=/tmp/s.json python run_agent.py
"""
from __future__ import annotations

import os
from pathlib import Path


def _load_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass  # dotenv optional; CI passes env directly


def main() -> int:
    _load_env()
    from feed import StateStore
    from harness import run_cycle

    state_path = Path(os.getenv("AGENT_STATE_PATH", "state/state.json"))
    have_creds = bool(os.getenv("ALPACA_API_KEY") and os.getenv("ALPACA_SECRET_KEY"))

    if have_creds:
        from feed import AlpacaDataSource

        source = AlpacaDataSource()
        mode = "LIVE"
    else:
        from feed import MockDataSource

        source = MockDataSource()
        mode = "MOCK (no ALPACA_* creds)"

    state = StateStore(state_path)
    day_pnl = float(os.getenv("DAY_PNL_PCT", "0") or 0.0)

    result = run_cycle(source, state, day_pnl_pct=day_pnl)
    print(f"[{mode}] {result['log']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
