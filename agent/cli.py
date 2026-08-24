"""JSON-only bridge used by the DSH bundle during the local vertical slice."""

from __future__ import annotations

import argparse
import json

from .candidates import build_decision_context
from .contracts import AgentDecision
from .gate import validate_decision
from .ledger import record_dry_run
from .scenarios import get_scenario


def _context(scenario: str):
    portfolio, market = get_scenario(scenario)
    return build_decision_context(portfolio, market, scenario_id=scenario)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    context_parser = sub.add_parser("context")
    context_parser.add_argument("--scenario", required=True)

    submit_parser = sub.add_parser("submit")
    submit_parser.add_argument("--scenario", required=True)
    submit_parser.add_argument("--context-id", required=True)
    submit_parser.add_argument("--candidate-id", required=True)
    submit_parser.add_argument("--reason", required=True)
    submit_parser.add_argument("--decision-id", required=True)
    submit_parser.add_argument("--ledger", required=True)

    args = parser.parse_args()
    context = _context(args.scenario)
    if args.command == "context":
        print(json.dumps(context.to_model_dict(), sort_keys=True))
        return 0

    decision = AgentDecision(args.context_id, args.candidate_id, args.reason)
    result = validate_decision(context, decision)
    row = record_dry_run(
        args.ledger,
        args.decision_id,
        args.scenario,
        decision,
        result,
    )
    print(json.dumps(row, sort_keys=True))
    return 0 if result.approved else 2


if __name__ == "__main__":
    raise SystemExit(main())
