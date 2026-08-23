"""The income overlay — the P&L engine (README §3 profit engine, §7.7-7.9).

Turns rich implied volatility into *collected premium* via three defined-risk legs:

  * covered calls        — sell calls against stock we own (income + a cushion)
  * cash-secured puts    — sell puts backed by cash (paid to maybe buy lower)
  * bull put spreads     — sell a put, buy a lower one (capital-light defined risk)

How much to deploy scales with `scoring.income_aggressiveness` (rich IV + calm market
-> harvest; risk-off -> stop selling), the mirror image of the hedge dial. Everything
is priced with Black-Scholes and sized against real capital/position limits, so it runs
offline and the executor just places what it returns. No broker, no LLM here.

Pricing note: Alpaca gives per-name IV only as a live snapshot, so offline we price each
leg with the *index* IV as a proxy (documented approximation, same spirit as §7.1's
Black-Scholes fallback). Production swaps in the live per-contract quote.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import floor

from . import blackscholes as bs
from . import payoffs, scoring
from .metrics import variance_risk_premium
from .types import MarketData, Portfolio, RiskSnapshot

# --- Tunable knobs (calibrated on the dev account, kept simple for the MVP) ---
DEFAULT_EXPIRY_DAYS = 30
TARGET_CALL_DELTA = 0.30      # sell ~30-delta calls (OTM, ~70% chance kept)
TARGET_PUT_DELTA = 0.30       # sell ~30-delta puts
CSP_CASH_FRACTION = 0.50      # use at most half the cash sleeve for cash-secured puts
RISKON_MAX = 0.30             # regime below this -> allow cash-secured puts; above -> spreads only
SPREAD_WIDTH_PCT = 0.05       # bull put spread width as a fraction of spot
MAX_DEFINED_RISK_FRAC = 0.10  # cap total credit-spread max-loss at 10% of equity


@dataclass(frozen=True)
class IncomeLeg:
    """One premium-selling position the agent proposes."""

    kind: str                    # "covered_call" | "cash_secured_put" | "bull_put_spread"
    symbol: str
    short_strike: float
    long_strike: float | None    # None for single-leg (covered call / cash-secured put)
    expiry_days: int
    short_delta: float
    contracts: int
    credit: float                # $ premium collected (positive)
    max_loss: float              # $ defined risk this leg adds (0 for a covered call)
    capital_reserved: float      # $ tied up (cash for CSP, spread width for the spread)
    theta_per_day: float         # $ income/day from decay (positive — we are short)
    note: str = ""

    def as_lines(self) -> list[str]:
        strikes = (
            f"${self.short_strike:.0f}"
            if self.long_strike is None
            else f"sell ${self.short_strike:.0f} / buy ${self.long_strike:.0f}"
        )
        return [
            f"{self.kind:16s} {self.symbol}  x{self.contracts}  ({self.expiry_days}d, {strikes}, delta {self.short_delta:+.2f})",
            f"    credit ${self.credit:,.0f}   max_loss ${self.max_loss:,.0f}   "
            f"reserved ${self.capital_reserved:,.0f}   theta +${self.theta_per_day:,.0f}/day",
        ]


@dataclass(frozen=True)
class IncomePlan:
    """The full income overlay for one cycle."""

    legs: list[IncomeLeg]
    total_credit: float
    total_max_loss: float
    capital_reserved: float
    net_theta_per_day: float     # premium decay we collect each day (positive)
    aggressiveness: float        # 0..1 posture that produced this
    annualized_yield: float      # total_credit/equity, annualized over the expiry

    def as_lines(self) -> list[str]:
        head = [
            f"aggressiveness    = {self.aggressiveness:.2f}  ({len(self.legs)} legs)",
            f"total_credit      = ${self.total_credit:,.0f}",
            f"net_theta/day     = +${self.net_theta_per_day:,.0f}",
            f"capital_reserved  = ${self.capital_reserved:,.0f}   defined_risk ${self.total_max_loss:,.0f}",
            f"annualized_yield  = {self.annualized_yield*100:.1f}%  (credit vs equity)",
        ]
        for leg in self.legs:
            head.extend(leg.as_lines())
        return head


def _empty_plan(aggressiveness: float = 0.0) -> IncomePlan:
    return IncomePlan(
        legs=[],
        total_credit=0.0,
        total_max_loss=0.0,
        capital_reserved=0.0,
        net_theta_per_day=0.0,
        aggressiveness=aggressiveness,
        annualized_yield=0.0,
    )


def plan_income(
    portfolio: Portfolio,
    market: MarketData,
    snapshot: RiskSnapshot,
    *,
    expiry_days: int = DEFAULT_EXPIRY_DAYS,
    target_call_delta: float = TARGET_CALL_DELTA,
    target_put_delta: float = TARGET_PUT_DELTA,
) -> IncomePlan:
    """Build the premium-selling overlay sized to the current IV/regime posture.

    Returns an empty plan when premium isn't worth selling (cheap IV or risk-off).
    """
    equity = portfolio.equity
    S = market.index_price
    r = market.risk_free_rate
    iv = market.index_iv  # index IV as the per-name proxy (see module docstring)
    T = expiry_days / 365.0

    vrp = variance_risk_premium(iv, snapshot.annual_vol, use_variance=False)
    agg = scoring.income_aggressiveness(snapshot.iv_rank, vrp, snapshot.regime_signal)
    if agg <= 0.0 or T <= 0.0 or iv <= 0.0:
        return _empty_plan(agg)

    legs: list[IncomeLeg] = []

    # --- Covered calls on stock we already own (income + a small cushion) ------
    for pos in portfolio.positions:
        capacity = int(floor(pos.shares / 100))
        n = int(round(agg * capacity))
        if n <= 0:
            continue
        Ps = pos.price
        Kc = round(bs.strike_for_call_delta(Ps, target_call_delta, T, r, iv))
        prem = bs.call_price(Ps, Kc, T, r, iv)
        if prem <= 0.0:
            continue
        pay = payoffs.covered_call_payoff(Ps, Kc, prem)
        theta = -bs.call_theta_per_day(Ps, Kc, T, r, iv) * 100.0 * n  # short -> income
        legs.append(
            IncomeLeg(
                kind="covered_call",
                symbol=pos.symbol,
                short_strike=float(Kc),
                long_strike=None,
                expiry_days=expiry_days,
                short_delta=bs.call_delta(Ps, Kc, T, r, iv),
                contracts=n,
                credit=pay.credit * n,
                max_loss=0.0,  # covered by stock we hold; only caps upside
                capital_reserved=0.0,
                theta_per_day=theta,
                note=f"caps upside above ${Kc:.0f}",
            )
        )

    # --- Short-put income: cash-secured put if calm & affordable, else a spread -
    Kp = round(bs.strike_for_put_delta(S, target_put_delta, T, r, iv))
    put_prem = bs.put_price(S, Kp, T, r, iv)
    csp_notional = Kp * 100.0
    cash_budget = portfolio.cash * CSP_CASH_FRACTION

    if snapshot.regime_signal < RISKON_MAX and cash_budget >= csp_notional and put_prem > 0.0:
        max_n = int(floor(cash_budget / csp_notional))
        n = max(1, int(round(agg * max_n))) if max_n > 0 else 0
        n = min(n, max_n)
        if n > 0:
            pay = payoffs.cash_secured_put_payoff(Kp, put_prem)
            theta = -bs.put_theta_per_day(S, Kp, T, r, iv) * 100.0 * n
            legs.append(
                IncomeLeg(
                    kind="cash_secured_put",
                    symbol=market.index_symbol,
                    short_strike=float(Kp),
                    long_strike=None,
                    expiry_days=expiry_days,
                    short_delta=bs.put_delta(S, Kp, T, r, iv),
                    contracts=n,
                    credit=pay.credit * n,
                    max_loss=pay.max_loss * n,
                    capital_reserved=pay.capital_reserved * n,
                    theta_per_day=theta,
                    note=f"willing to buy {market.index_symbol} at ${Kp:.0f}",
                )
            )
    else:
        # Defined-risk bull put spread: capital-light, safe to run in any regime.
        width = max(1.0, round(S * SPREAD_WIDTH_PCT))
        Kl = Kp - width
        long_prem = bs.put_price(S, Kl, T, r, iv)
        credit_share = put_prem - long_prem
        if credit_share > 0.0:
            pay = payoffs.bull_put_spread_payoff(Kp, Kl, put_prem, long_prem)
            if pay.max_loss > 0.0:
                budget = equity * MAX_DEFINED_RISK_FRAC
                max_n = int(floor(budget / pay.max_loss))
                n = min(max_n, max(1, int(round(agg * max_n)))) if max_n > 0 else 0
                if n > 0:
                    theta = (
                        -bs.put_theta_per_day(S, Kp, T, r, iv)
                        + bs.put_theta_per_day(S, Kl, T, r, iv)
                    ) * 100.0 * n
                    legs.append(
                        IncomeLeg(
                            kind="bull_put_spread",
                            symbol=market.index_symbol,
                            short_strike=float(Kp),
                            long_strike=float(Kl),
                            expiry_days=expiry_days,
                            short_delta=bs.put_delta(S, Kp, T, r, iv),
                            contracts=n,
                            credit=pay.net_credit * n,
                            max_loss=pay.max_loss * n,
                            capital_reserved=pay.max_loss * n,  # margin ≈ defined risk
                            theta_per_day=theta,
                            note="defined-risk credit spread",
                        )
                    )

    total_credit = sum(leg.credit for leg in legs)
    total_max_loss = sum(leg.max_loss for leg in legs)
    capital_reserved = sum(leg.capital_reserved for leg in legs)
    net_theta = sum(leg.theta_per_day for leg in legs)
    # Annualize the collected credit as a rough yield headline.
    ann_yield = (total_credit / equity) * (365.0 / expiry_days) if equity else 0.0

    return IncomePlan(
        legs=legs,
        total_credit=total_credit,
        total_max_loss=total_max_loss,
        capital_reserved=capital_reserved,
        net_theta_per_day=net_theta,
        aggressiveness=agg,
        annualized_yield=ann_yield,
    )
