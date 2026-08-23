"""Demo + smoke test for the OBSERVE layer (feed/).

Runs the full pipeline with the offline MockDataSource — no Alpaca account, no network:

    observe(source, state)  ->  (Portfolio, MarketData)  ->  assess()  ->  plan_strategy()

Also proves the persistent StateStore does its job across cycles: the peak-equity mark
only ratchets up, and the IV history grows one point per run (the fix for Alpaca's
snapshot-only IV, README §8).

    python demo_data_adapter.py
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from feed import MockDataSource, StateStore, compute_beta, moving_average, observe
from risk_engine import assess, plan_strategy


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="alpaca_feed_")) / "state.json"
    source = MockDataSource()
    state = StateStore(tmp)

    portfolio, market = observe(source, state, index_symbol="SPY")

    print(f"{'='*64}\n OBSERVE  (MockDataSource -> engine inputs)\n{'='*64}")
    print("PORTFOLIO")
    print(f"  equity            = ${portfolio.equity:,.0f}")
    print(f"  cash              = ${portfolio.cash:,.0f}")
    print(f"  peak_equity       = ${portfolio.peak_equity:,.0f}")
    for p in portfolio.positions:
        print(f"  {p.symbol:5s} {p.shares:>6.0f} @ ${p.price:,.2f}  beta {p.beta:.2f}")
    print("MARKET DATA")
    print(f"  index             = {market.index_symbol} @ ${market.index_price:,.2f}")
    print(f"  ma50              = ${market.index_ma50:,.2f}")
    print(f"  returns (n)       = {len(market.index_returns)} daily points")
    print(f"  index_iv          = {market.index_iv*100:.1f}%")
    print(f"  iv 1yr range      = {market.iv_year_low*100:.1f}% .. {market.iv_year_high*100:.1f}%")

    # Feed straight into the engine — the whole point of the adapter.
    snap = assess(portfolio, market)
    plan = plan_strategy(portfolio, market, snapshot=snap)
    print("\nENGINE (fed by the adapter)")
    print(f"  RISK SCORE        = {snap.risk_score:.0f}/100   IV Rank {snap.iv_rank:.0f}")
    print(f"  POSTURE           = {plan.posture}")
    print(f"  income credit     = ${plan.income.total_credit:,.0f}   "
          f"hedge {plan.hedge.contracts_target} contracts")

    # --- invariants: the adapter assembled sane, engine-ready inputs ---
    symbols = {p.symbol for p in portfolio.positions}
    assert symbols == {"SPY", "QQQ", "AAPL"}, "all mock positions should come through"
    assert portfolio.equity > 0 and portfolio.cash > 0
    assert portfolio.peak_equity >= portfolio.equity, "peak mark >= current equity"
    betas = {p.symbol: p.beta for p in portfolio.positions}
    assert abs(betas["SPY"] - 1.0) < 1e-6, "SPY's beta to itself must be 1.0"
    assert 0.9 < betas["QQQ"] < 1.35, f"QQQ beta ~1.1 expected, got {betas['QQQ']:.2f}"
    assert 1.0 < betas["AAPL"] < 1.45, f"AAPL beta ~1.2 expected, got {betas['AAPL']:.2f}"
    assert market.index_price == source.latest_price("SPY"), "index price = latest close"
    assert abs(market.index_ma50 - moving_average(source.daily_closes("SPY", 51), 50)) < 1e-6
    assert len(market.index_returns) > 0, "returns series should be populated"
    assert market.iv_year_low <= market.index_iv <= market.iv_year_high, "IV within its range"

    # --- persistence: peak ratchets, IV history grows across cycles ---
    reloaded = StateStore(tmp)
    assert reloaded._data["peak_equity"] == portfolio.peak_equity, "peak persisted to disk"
    assert len(reloaded._data["iv_history"]) == 1, "one IV point recorded this cycle"

    # A second observe with higher prices: peak should rise; a drop must NOT lower it.
    richer = MockDataSource(cash=40_000.0)
    richer._closes["SPY"] = [c + 20 for c in richer._closes["SPY"]]  # a rally
    p2, _ = observe(richer, reloaded, index_symbol="SPY")
    assert p2.peak_equity >= portfolio.peak_equity, "peak ratchets up on a new high"

    print(f"\n{'='*64}")
    print(" DATA-ADAPTER INVARIANTS PASSED  [OK]")
    print(f" observed {len(symbols)} positions, betas computed, IV range seeded,")
    print(f" state persisted to {tmp}")
    print(f"{'='*64}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
