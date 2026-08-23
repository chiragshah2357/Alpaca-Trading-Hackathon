"""The EXECUTE step — place the approved orders on Alpaca (README §6).

`default_executor` is a STUB: it does a DRY RUN, returning the exact orders it *would*
place, so you can see the loop's output before wiring real trades. Swap it for a live
executor that submits via Alpaca (the `alpacahq/alpaca-skills` through MCP/CLI, or
alpaca-py directly), enforcing idempotency + the liquidity gate (`metrics.is_liquid`).
Return the same shape so LOG/tests keep working.
"""
from __future__ import annotations


def default_executor(decision: dict, context: dict) -> dict:
    """Dry-run: translate the decision into the orders it would submit."""
    orders: list[dict] = []
    for leg in decision.get("income_legs", []):
        orders.append({
            "structure": leg["kind"],
            "symbol": leg["symbol"],
            "contracts": leg["contracts"],
            "side": "sell_to_open",   # income legs are net-credit (we sell premium)
        })
    hedge = decision.get("hedge", {})
    if hedge.get("action") != "hold" and hedge.get("contracts_delta"):
        orders.append({
            "structure": "protective_put",
            "symbol": context.get("index_symbol", "SPY"),
            "contracts": abs(hedge["contracts_delta"]),
            "side": "buy_to_open" if hedge["contracts_delta"] > 0 else "sell_to_close",
        })
    return {"dry_run": True, "orders": orders, "note": "no live executor wired — dry-run only"}
