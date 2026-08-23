"""The DECIDE step — the one place a model makes a judgment call (README §4, §5).

`default_decider` is a STUB: it approves the already risk-validated plan unchanged, so
the loop runs end-to-end today. Swap it for a real LLM call that reads `context`
(the JSON snapshot + proposed plan) and returns the same shape of decision — e.g. read
the numbers + any news, then approve / adjust sizing / skip. Keep the return contract
identical so nothing downstream changes.
"""
from __future__ import annotations


def default_decider(context: dict) -> dict:
    """Approve the risk-validated plan as-is (deterministic stub, no model)."""
    plan = context["plan"]
    return {
        "approved": True,
        "posture": plan["posture"],
        "income_legs": plan["income"]["legs"],
        "hedge": plan["hedge"],
        "reasoning": "stub decider: approve the risk-validated plan unchanged",
    }
