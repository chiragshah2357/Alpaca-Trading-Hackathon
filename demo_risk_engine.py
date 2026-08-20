"""Demo + smoke test for the MVP risk engine.

Runs the SAME base book through a CALM and a STRESSED market and prints the risk
snapshot + hedge plan for each. Shows the core Track-3 behavior: calm -> no hedge
(zero drag); stress -> step in and buy protective puts. Asserts the invariants.

    python demo_risk_engine.py
"""
from __future__ import annotations

import math

from risk_engine import (
    MarketData,
    Portfolio,
    Position,
    assess,
    collar_payoff,
    plan_hedge,
    protective_put_payoff,
    put_spread_payoff,
    stress_pnl,
)
from risk_engine import blackscholes as bs
from risk_engine import metrics


def base_book(spy_price: float, qqq_price: float, peak: float) -> Portfolio:
    return Portfolio(
        positions=[
            Position("SPY", shares=100, price=spy_price, beta=1.0),
            Position("QQQ", shares=50, price=qqq_price, beta=1.1),
        ],
        cash=20_000.0,
        peak_equity=peak,
    )


CALM = MarketData(
    index_symbol="SPY",
    index_price=560.0,
    index_ma50=545.0,  # price above its 50-day MA -> risk-on
    index_returns=[0.003, -0.002, 0.004, 0.001, -0.003, 0.002, 0.0, 0.003, -0.001, 0.002],
    index_iv=0.13,
    iv_year_low=0.10,
    iv_year_high=0.40,
)

STRESSED = MarketData(
    index_symbol="SPY",
    index_price=520.0,
    index_ma50=550.0,  # price ~5.5% below its 50-day MA -> risk-off
    index_returns=[-0.005, 0.002, -0.020, -0.025, -0.018, -0.030, 0.010, -0.022, -0.015, -0.028],
    index_iv=0.30,
    iv_year_low=0.10,
    iv_year_high=0.40,
)


def show(title: str, portfolio: Portfolio, market: MarketData):
    snap = assess(portfolio, market)
    plan = plan_hedge(portfolio, market, snap, current_contracts=0)
    print(f"\n{'='*60}\n {title}\n{'='*60}")
    print("RISK SNAPSHOT")
    for line in snap.as_lines():
        print("  " + line)
    print("HEDGE PLAN")
    for line in plan.as_lines():
        print("  " + line)
    return snap, plan


def show_core_upgrades(snap, market: MarketData):
    """Exercise the §7.0.1 Core upgrades that sit alongside the MVP engine."""
    print(f"\n{'='*60}\n CORE UPGRADES  (§7.0.1 — the Core layer beyond the MVP)\n{'='*60}")

    equity = snap.equity

    # A representative crash month: mostly small gains punctuated by sharp down days
    # -> left-skewed, fat-tailed, exactly the shape normal VaR understates.
    crash_rets = [
        0.004, -0.002, 0.006, 0.003, -0.061, 0.005, -0.008, 0.002, -0.047,
        0.004, 0.003, -0.013, 0.006, -0.002, 0.005, -0.021, 0.004, -0.009,
    ]
    skew = metrics.skewness(crash_rets)
    kurt = metrics.excess_kurtosis(crash_rets)
    crash_daily_vol = math.sqrt(metrics.sample_variance(crash_rets))

    var95 = metrics.parametric_var(equity, crash_daily_vol, metrics.Z_95)
    cf_var95 = metrics.cornish_fisher_var(equity, crash_daily_vol, skew, kurt, metrics.Z_95)
    hist_var95 = metrics.historical_var(equity, crash_rets, 0.05)
    es95 = metrics.expected_shortfall(equity, crash_rets, 0.05)
    realized_annual = snap.annual_vol
    vrp = metrics.variance_risk_premium(market.index_iv, realized_annual, use_variance=False)

    # option greeks on a one-expected-move-down put (§7.1)
    S, r, iv = market.index_price, market.risk_free_rate, market.index_iv
    K = round(S - snap.expected_move_30d)
    T = 30 / 365.0
    gamma = bs.gamma(S, K, T, r, iv)
    vega = bs.vega_per_point(S, K, T, r, iv)
    pdelta = bs.put_delta(S, K, T, r, iv)

    # structures (§7.5, §7.8, §7.9) — round numbers off the live put price
    put_prem = bs.put_price(S, K, T, r, iv)
    call_prem = bs.call_price(S, round(S + snap.expected_move_30d), T, r, iv)
    pput = protective_put_payoff(S, K, put_prem)
    collar = collar_payoff(S, K, round(S + snap.expected_move_30d), put_prem, call_prem)
    spread = put_spread_payoff(K, K - round(snap.expected_move_30d), put_prem,
                               bs.put_price(S, K - round(snap.expected_move_30d), T, r, iv))
    stress = stress_pnl(snap.beta_weighted_delta, -0.05, S,
                        hedge_contracts=5, put_delta=pdelta)

    print("  TAIL RISK (§7.4 — on a left-skewed crash tape)")
    print(f"    skew={skew:+.2f}  excess_kurt={kurt:+.2f}")
    print(f"    95% VaR: normal ${var95:,.0f}  ->  Cornish-Fisher ${cf_var95:,.0f}"
          f"  |  historical ${hist_var95:,.0f}")
    print(f"    95% Expected Shortfall (ES/CVaR) = ${es95:,.0f}")
    print(f"  EDGE (§7.7)   VRP (IV - realized vol) = {vrp*100:+.1f} vol pts")
    print(f"  GREEKS (§7.1) put@${K:.0f}: delta {pdelta:+.2f}  gamma {gamma:.4f}"
          f"  vega ${vega:,.2f}/pt")
    print("  STRUCTURES")
    print(f"    protective put : " + "  ".join(pput.as_lines()))
    print(f"    collar         : " + "  ".join(collar.as_lines()))
    print(f"    put spread     : " + "  ".join(spread.as_lines()))
    print(f"    stress -5%     : " + "  ".join(stress.as_lines()))

    # --- invariants for the upgrades ---
    assert es95 >= hist_var95, "ES must be >= VaR at the same alpha"
    assert cf_var95 > var95, "Cornish-Fisher must exceed normal VaR on a fat left tail"
    assert skew < 0 and kurt > 0, "the crash tape is left-skewed and fat-tailed"
    assert gamma > 0 and vega > 0, "gamma/vega positive for a long option"
    assert spread.net_debit < pput.cost, "put spread must be cheaper than the outright put"
    assert stress.net_pnl > stress.unhedged_pnl, "the hedge must cushion a -5% shock"
    assert collar.max_loss < abs(stress.unhedged_pnl) * 100, "collar caps the downside"
    mkt = market.index_returns
    dbeta = metrics.downside_beta([p * 1.2 for p in mkt], mkt)  # asset moves 1.2x the market
    assert dbeta != 0.0, "downside beta should compute over the down days"
    print("\n  CORE-UPGRADE INVARIANTS PASSED  [OK]")


def main() -> int:
    calm_snap, calm_plan = show(
        "CALM MARKET  (SPY above MA, low vol, cheap IV)",
        base_book(spy_price=560, qqq_price=480, peak=100_000),
        CALM,
    )
    stress_snap, stress_plan = show(
        "STRESSED MARKET  (SPY below MA, high vol, drawdown, dear IV)",
        base_book(spy_price=520, qqq_price=440, peak=106_000),
        STRESSED,
    )
    show_core_upgrades(stress_snap, STRESSED)

    # --- invariants (the adaptive behavior we claim) ---
    assert calm_snap.risk_score < stress_snap.risk_score, "stress should score higher"
    assert calm_snap.target_coverage < stress_snap.target_coverage, "stress should hedge more"
    assert calm_plan.contracts_target <= 1, "calm should hold ~no hedge"
    assert stress_plan.contracts_target >= 1, "stress should buy protection"
    assert stress_plan.action == "increase", "stress should step in"
    assert 0.0 <= stress_snap.target_coverage <= 1.0
    assert stress_snap.iv_rank > calm_snap.iv_rank, "IV should be dearer under stress"

    print(f"\n{'='*60}")
    print(" ALL INVARIANTS PASSED  [OK]")
    print(f" calm score {calm_snap.risk_score:.0f} -> {calm_plan.contracts_target} contracts   |   "
          f"stress score {stress_snap.risk_score:.0f} -> {stress_plan.contracts_target} contracts")
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
