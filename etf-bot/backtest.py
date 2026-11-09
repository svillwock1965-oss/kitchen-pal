"""
Backtester for TQQQ / SQQQ rules driven by QQQ highs and lows.

Each rule looks at QQQ's closing price every day:
  * "new N-day high"  = today's close is the highest close of the last N days
  * "new N-day low"   = today's close is the lowest close of the last N days

Strategies:
  resistance : new high -> hold SQQQ (expect a pullback); new low -> hold TQQQ (expect a bounce)
  breakout   : new high -> hold TQQQ (ride momentum);    new low -> hold SQQQ
  breakout_cash : new high -> hold TQQQ; new low -> go to cash (never short)

Optional exits, applied to whatever is held:
  stop     : sell if the position is down X% from where it was bought
  trail    : sell if the position is down X% from its best close since buying
After a stop the bot sits in cash until the next new signal.

Simplifications (be aware):
  * Decisions and trades both happen at the daily close (a bot can trade a few
    minutes before the close, so this is roughly achievable).
  * Stops are checked on closing prices only, not intraday.
  * A 0.05% cost is charged per trade for slippage. No taxes.

Usage:  python3 backtest.py
"""
from itertools import product
from pathlib import Path

import pandas as pd

DATA = Path(__file__).parent / "data"
COST = 0.0005


def load():
    px = {s: pd.read_csv(DATA / f"{s}.csv", index_col="date", parse_dates=True)["close"]
          for s in ("QQQ", "TQQQ", "SQQQ")}
    return pd.DataFrame(px).dropna()


def run(px, strategy, n, stop=None, trail=None):
    q = px["QQQ"]
    hi = q >= q.rolling(n).max()
    lo = q <= q.rolling(n).min()
    rets = px.pct_change().fillna(0)

    hold, entry, peak = None, None, None   # hold: "TQQQ" | "SQQQ" | None (cash)
    equity, curve, trades = 1.0, [], []
    for i, day in enumerate(px.index):
        # 1) earn today's return on what we held overnight
        if hold:
            equity *= 1 + rets[hold].iloc[i]
            price = px[hold].iloc[i]
            peak = max(peak, price)
            # 2) stops
            if (stop and price <= entry * (1 - stop)) or (trail and price <= peak * (1 - trail)):
                trades.append(price / entry - 1)
                equity *= 1 - COST
                hold = None
        # 3) signals
        want = "keep"
        if i >= n:
            if hi.iloc[i]:
                want = {"resistance": "SQQQ", "breakout": "TQQQ", "breakout_cash": "TQQQ"}[strategy]
            elif lo.iloc[i]:
                want = {"resistance": "TQQQ", "breakout": "SQQQ", "breakout_cash": None}[strategy]
        if want != "keep" and want != hold:
            if hold:
                trades.append(px[hold].iloc[i] / entry - 1)
                equity *= 1 - COST
            hold = want
            if hold:
                entry = peak = px[hold].iloc[i]
                equity *= 1 - COST
        curve.append(equity)
    if hold:
        trades.append(px[hold].iloc[-1] / entry - 1)
    return pd.Series(curve, index=px.index), trades


def stats(curve, trades=None):
    years = (curve.index[-1] - curve.index[0]).days / 365.25
    dd = (curve / curve.cummax() - 1).min()
    out = {
        "total_%": round((curve.iloc[-1] - 1) * 100, 1),
        "per_year_%": round((curve.iloc[-1] ** (1 / years) - 1) * 100, 1),
        "worst_drop_%": round(dd * 100, 1),
    }
    if trades is not None:
        out["trades"] = len(trades)
        out["win_%"] = round(100 * sum(t > 0 for t in trades) / max(len(trades), 1))
    return out


def main():
    px = load()
    print(f"Data: {px.index[0].date()} to {px.index[-1].date()} ({len(px)} trading days)\n")

    print("Benchmarks (just buy and hold):")
    for s in ("QQQ", "TQQQ", "SQQQ"):
        print(f"  {s:5}", stats(px[s] / px[s].iloc[0]))
    both = 0.5 * px["TQQQ"] / px["TQQQ"].iloc[0] + 0.5 * px["SQQQ"] / px["SQQQ"].iloc[0]
    print("  half TQQQ + half SQQQ, never sold", stats(both))

    rows = []
    for strat, n, stop, trail in product(
        ["resistance", "breakout", "breakout_cash"],
        [3, 5, 10, 20, 60],
        [None, 0.08, 0.15],
        [None, 0.10, 0.20],
    ):
        curve, trades = run(px, strat, n, stop, trail)
        rows.append({"strategy": strat, "days": n,
                     "stop": f"{int(stop*100)}%" if stop else "-",
                     "trail": f"{int(trail*100)}%" if trail else "-",
                     **stats(curve, trades)})
    res = pd.DataFrame(rows)
    res.to_csv(Path(__file__).parent / "results.csv", index=False)

    pd.set_option("display.width", 200)
    print("\nBest 15 rule combinations by total return:")
    print(res.sort_values("total_%", ascending=False).head(15).to_string(index=False))
    print("\nBest version of each strategy (no stops vs. best with stops):")
    for strat in res.strategy.unique():
        sub = res[res.strategy == strat]
        print(sub[(sub.stop == "-") & (sub.trail == "-")].sort_values("total_%").tail(1).to_string(index=False, header=False))
        print(sub.sort_values("total_%").tail(1).to_string(index=False, header=False))
    print("\nFull table saved to results.csv")


if __name__ == "__main__":
    main()
