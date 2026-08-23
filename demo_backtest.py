"""Demo: backtest the strategy vs buy-and-hold through a calm->crash->recovery tape.

Shows the pitch's core claim: the hedged/income agent controls drawdown and volatility
(and harvests premium) even when raw return is comparable. Offline, deterministic.

    python demo_backtest.py
"""
from __future__ import annotations

from backtest import run_backtest, synthetic_series


def main() -> int:
    result = run_backtest(synthetic_series(), start_equity=100_000)

    print(f"{'='*62}\n BACKTEST  (calm -> crash -> recovery, weekly cycles)\n{'='*62}")
    for line in result.as_lines():
        print("  " + line)

    # the crash window: strategy vs buy&hold at the worst point
    worst = min(result.records, key=lambda r: r["overlay_pnl"])
    best = max(result.records, key=lambda r: r["overlay_pnl"])
    print("\n  worst overlay cycle:", worst["posture"].split(" ")[0],
          f"overlay ${worst['overlay_pnl']:,.0f}  (risk {worst['risk_score']})")
    print("  best  overlay cycle:", best["posture"].split(" ")[0],
          f"overlay ${best['overlay_pnl']:,.0f}  (risk {best['risk_score']})")

    s, u = result.strategy_metrics(), result.unhedged_metrics()
    print(f"\n{'='*62}")
    print(f"  drawdown: strategy {s['max_drawdown']*100:.1f}%  vs  buy&hold "
          f"{u['max_drawdown']*100:.1f}%   (lower is better)")
    print(f"  sharpe:   strategy {s['sharpe']:.2f}  vs  buy&hold {u['sharpe']:.2f}")
    print(f"{'='*62}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
