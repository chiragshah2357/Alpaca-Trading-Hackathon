"""Seed (or top up) the Track-3 core book on the Alpaca paper account (README §9 step 1).

Sizes the fixed target-weight book (risk_engine/book.py) against the account's live
equity and prices, then places the *buy deltas* needed to reach target — skipping names
already at/above target, so re-running is idempotent (a top-up, never a double-buy).

SAFE BY DEFAULT: prints the plan and places nothing. Pass --execute to actually submit
paper market orders.

    python scripts/seed_book.py              # dry run — show the plan
    python scripts/seed_book.py --execute    # place the paper buy orders
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _load_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")
    except Exception:
        pass


def _prices(source, symbols) -> dict[str, float]:
    out: dict[str, float] = {}
    for sym in symbols:
        try:
            out[sym] = source.latest_price(sym)
        except Exception as e:  # never let one bad quote abort sizing
            print(f"  ! no price for {sym}: {type(e).__name__}: {e}")
    return out


def build_plan(equity: float, prices: dict[str, float], held: dict[str, float]):
    """Return [(symbol, target_shares, buy_shares, price, dollars)] for names under target."""
    from risk_engine.book import DEFAULT_BOOK, build_portfolio

    target = build_portfolio(equity, prices)  # whole-share sizing of the book
    rows = []
    for pos in target.positions:
        have = held.get(pos.symbol, 0.0)
        buy = pos.shares - have
        if buy <= 0:
            continue
        rows.append((pos.symbol, pos.shares, buy, pos.price, buy * pos.price))
    return rows, DEFAULT_BOOK


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="actually place paper orders")
    args = parser.parse_args()

    _load_env()
    from feed import AlpacaDataSource
    from risk_engine.book import DEFAULT_BOOK

    source = AlpacaDataSource()
    equity, cash = source.account()
    held = {sym: shares for sym, shares, _ in source.positions()}
    symbols = [e.symbol for e in DEFAULT_BOOK]
    prices = _prices(source, symbols)

    rows, _ = build_plan(equity, prices, held)

    print(f"account: equity=${equity:,.0f}  cash=${cash:,.0f}")
    if not rows:
        print("book already at/above target — nothing to buy.")
        return 0
    print(f"{'PLAN' if not args.execute else 'PLACING'} — buy deltas to reach target weights:")
    total = 0.0
    for sym, tgt, buy, px, dollars in rows:
        total += dollars
        print(f"  {sym:5s}  buy {buy:>6.0f} sh @ ${px:,.2f}  = ${dollars:,.0f}   (target {tgt:.0f} sh)")
    print(f"  {'':5s}  total ${total:,.0f}  ({total/equity*100:.0f}% of equity)")

    if not args.execute:
        print("\ndry run — nothing placed. Re-run with --execute to submit these paper orders.")
        return 0

    placed = 0
    for sym, _tgt, buy, _px, _d in rows:
        if buy <= 0:
            continue  # nothing to buy — skip non-positive deltas before placing
        try:
            # submit_market_order validates whole-share qty (rounds near-integer float
            # sizing to the nearest share, raises on genuinely fractional / non-positive);
            # the logged count matches the rounded value it actually submits.
            order_id = source.submit_market_order(sym, buy)
            print(f"  placed {sym}: buy {int(round(buy))} -> order {order_id}")
            placed += 1
        except (TypeError, ValueError) as e:
            print(f"  ! invalid qty for {sym}: {e}")
        except Exception as e:
            print(f"  ! order failed for {sym}: {type(e).__name__}: {e}")
    print(f"\nsubmitted {placed}/{len(rows)} orders (paper). Market must be open for market orders to fill.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
