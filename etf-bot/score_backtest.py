"""
Backtest of the Market Pulse score (same formula as market-pulse.html).

For every trading day since 2016 the score is rebuilt from that day's CLOSE:
breadth of the tech and sector lists, QQQ/SPY daily move, VIXY move,
3-month trend, and full-day volume vs. the 20-day average.

Then we look at what happened NEXT: QQQ's return the following day and over
the following 5 days, grouped by grade. A simple trading test is also run:
  grade A at the close -> hold TQQQ the next day
  grade F at the close -> hold SQQQ the next day
  otherwise            -> cash

Caveats:
  * The live page scores intraday; this uses end-of-day data only.
  * The stock lists are TODAY's leaders, which flatters the past a little
    (survivorship bias).

Usage:  python3 score_backtest.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

HERE = Path(__file__).parent
TECH = "AAPL MSFT NVDA GOOGL AMZN META AVGO TSLA ORCL AMD NFLX ADBE CRM CSCO QCOM INTC TXN MU AMAT PLTR".split()
SECT = "JPM BAC XOM CVX UNH LLY JNJ WMT COST PG HD CAT GE NEE LIN".split()
ETFS = ["QQQ", "SPY", "VIXY", "TQQQ", "SQQQ"]
START = "2015-06-01"


def load():
    cache = HERE / "data" / "score_daily.pkl"
    if cache.exists():
        return pd.read_pickle(cache)
    d = yf.download(TECH + SECT + ETFS, start=START, auto_adjust=True, progress=False)
    d = d[["Close", "Volume"]]
    d.to_pickle(cache)
    return d


def scores(d):
    c, v = d["Close"], d["Volume"]
    r = c.pct_change()
    cl = lambda x: x.clip(-1, 1)

    def breadth(lst):
        return cl(r[lst] / 0.02).mean(axis=1)  # mean over available names

    f = pd.DataFrame(index=c.index)
    f["tech"] = 25 * breadth(TECH)
    f["sector"] = 20 * breadth(SECT)
    f["qqq"] = 12 * cl(r.QQQ / 0.015)
    f["spy"] = 8 * cl(r.SPY / 0.015)
    f["vix"] = 15 * cl(-r.VIXY / 0.05)
    trend = (cl((c.QQQ / c.QQQ.rolling(63).mean() - 1) / 0.05) +
             cl((c.SPY / c.SPY.rolling(63).mean() - 1) / 0.05)) / 2
    f["trend"] = 20 * trend
    raw = f.sum(axis=1)
    ratio = v.QQQ / v.QQQ.shift(1).rolling(20).mean()
    f["vol_factor"] = 1 + 0.3 * (ratio - 1).clip(-0.5, 1)
    f["score"] = (raw * f.vol_factor).clip(-100, 100)
    f["grade"] = pd.cut(f.score, [-101, -60, -25, 25, 60, 101], labels=["F", "D", "C", "B", "A"])
    f["next1"] = r.QQQ.shift(-1)
    f["next5"] = c.QQQ.shift(-5) / c.QQQ - 1
    f["tqqq_next"] = r.TQQQ.shift(-1)
    f["sqqq_next"] = r.SQQQ.shift(-1)
    return f.dropna(subset=["score", "next1"]).loc["2016":]


def stats(curve):
    yrs = (curve.index[-1] - curve.index[0]).days / 365.25
    return {"total_%": round((curve.iloc[-1] - 1) * 100, 1),
            "per_year_%": round((curve.iloc[-1] ** (1 / yrs) - 1) * 100, 1),
            "worst_drop_%": round((curve / curve.cummax() - 1).min() * 100, 1)}


def main():
    d = load()
    f = scores(d)
    print(f"Days scored: {len(f)}  ({f.index[0].date()} to {f.index[-1].date()})\n")

    g = f.groupby("grade", observed=True).agg(
        days=("score", "size"),
        next_day_avg_pct=("next1", lambda x: round(x.mean() * 100, 3)),
        next_day_up_pct=("next1", lambda x: round((x > 0).mean() * 100, 1)),
        next_5d_avg_pct=("next5", lambda x: round(x.mean() * 100, 2)),
        next_5d_up_pct=("next5", lambda x: round((x > 0).mean() * 100, 1)),
    )
    print("What QQQ did AFTER each grade:")
    print(g.to_string())
    print(f"\nAll days: next-day avg {f.next1.mean()*100:.3f}%, up {100*(f.next1>0).mean():.1f}% of the time; "
          f"5-day avg {f.next5.mean()*100:.2f}%")

    print("\nWhich factors carry information? (correlation with QQQ's next-day / next-5-day return)")
    for col in ["tech", "sector", "qqq", "spy", "vix", "trend", "score"]:
        print(f"  {col:7} next day {f[col].corr(f.next1):+.3f}   next 5 days {f[col].corr(f.next5):+.3f}")

    # Trading tests
    tq = f.tqqq_next.fillna(0); sq = f.sqqq_next.fillna(0)
    tests = {
        "A -> TQQQ, F -> SQQQ (follow the score)": np.where(f.grade == "A", tq, np.where(f.grade == "F", sq, 0)),
        "F -> TQQQ, A -> SQQQ (fade the score)": np.where(f.grade == "F", tq, np.where(f.grade == "A", sq, 0)),
        "A or B -> TQQQ, else cash": np.where(f.grade.isin(["A", "B"]), tq, 0),
        "Not D/F -> TQQQ, else cash": np.where(~f.grade.isin(["D", "F"]), tq, 0),
        "Hold TQQQ every day": tq.values,
    }
    print("\nTrading tests (enter at the close on the signal, hold one day, 0.05% cost per switch):")
    qqq_curve = (1 + f.next1).cumprod()
    print(f"  {'Hold QQQ':45}", stats(qqq_curve))
    for name, rets in tests.items():
        rets = pd.Series(rets, index=f.index)
        pos = (rets != 0).astype(int)
        cost = pos.diff().abs().fillna(pos.iloc[0]) * 0.0005
        curve = (1 + rets - cost).cumprod()
        print(f"  {name:45}", stats(curve), f"days in market {int(pos.sum())}")

    f.to_csv(HERE / "score_history.csv")
    print("\nDaily scores saved to score_history.csv")


if __name__ == "__main__":
    main()
