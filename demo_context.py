"""Demo: the exact JSON the harness gets each cycle from `get_strategy_context`.

This is the seam between the engine and the agent loop — one call in, one plain JSON
dict out (already risk-capped). Run offline with the MockDataSource:

    python demo_context.py
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from feed import MockDataSource, StateStore
from strategy_api import get_strategy_context_json


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="ctx_")) / "state.json"
    print(get_strategy_context_json(MockDataSource(), StateStore(tmp)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
