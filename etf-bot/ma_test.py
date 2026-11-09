"""
200-day moving-average rule, 1999-2026 (simulated TQQQ before 2010).

Rule: at each daily close, if QQQ is above its N-day average price -> hold the fund,
otherwise -> cash. "band" adds a buffer to reduce flip-flopping: buy only when QQQ is
band% ABOVE the average, sell only when it is band% BELOW it.

Nearby windows (150, 250 days) are tested too: a real pattern should work across
them, not only at exactly 200.

Usage:  python3 ma_test.py
"""
from pathlib import Path

import pandas as pd

from backtest import COST, stats
from stress_test import HERE, calibrate, simulate


def run_ma(px, fund, n, band=0.0):
    q = px["QQQ"]
    ma = q.rolling(n).mean()
    r = px[fund].pct_change().fillna(0)
    inn, equity, curve, entry, trades = False, 1.0, [], None, []
    for i in range(len(px)):
        if inn:
            equity *= 1 + r.iloc[i]
        if i >= n:
            if not inn and q.iloc[i] > ma.iloc[i] * (1 + band):
                inn, entry = True, px[fund].iloc[i]
                equity *= 1 - COST
            elif inn and q.iloc[i] < ma.iloc[i] * (1 - band):
                inn = False
                trades.append(px[fund].iloc[i] / entry - 1)
                equity *= 1 - COST
        curve.append(equity)
    if inn:
        trades.append(px[fund].iloc[-1] / entry - 1)
    return pd.Series(curve, index=px.index), trades


def main():
    raw = pd.read_csv(HERE / "data" / "yahoo_close.csv", index_col=0, parse_dates=True)
    drag = calibrate(raw)
    q = raw["QQQ"].dropna()
    t, _ = simulate(q, drag["TQQQ"])
    px = pd.DataFrame({"QQQ": q, "TQQQ": t})

    rules = [("QQQ", 200, 0.0), ("TQQQ", 200, 0.0), ("TQQQ", 200, 0.03),
             ("TQQQ", 150, 0.0), ("TQQQ", 250, 0.0), ("TQQQ", 150, 0.03), ("TQQQ", 250, 0.03)]
    periods = {
        "1999-2026 (all)": ("1999", "2026"),
        "2000-2002 dot-com crash": ("2000-03", "2002-12"),
        "2003-2007 recovery": ("2003", "2007"),
        "2008 financial crisis": ("2007-10", "2009-03"),
        "2009-2021 bull market": ("2009-03", "2021-12"),
        "2022-2026": ("2022", "2026"),
    }
    rows = []
    for label, (a, b) in periods.items():
        # warm up the average on earlier data, then measure only inside the period
        for fund, n, band in rules:
            curve, trades = run_ma(px.loc[:b], fund, n, band)
            c = curve.loc[a:b]
            name = f"{fund} above {n}d avg" + (f" (+/-{int(band*100)}% band)" if band else "")
            row = {"period": label, "rule": name, **stats(c / c.iloc[0])}
            if a == "1999":  # trade count only meaningful for the full run
                row["trades"] = len(trades)
            rows.append(row)
        p = px.loc[a:b]
        rows.append({"period": label, "rule": "hold QQQ", **stats(p.QQQ / p.QQQ.iloc[0])})
        rows.append({"period": label, "rule": "hold TQQQ (sim)", **stats(p.TQQQ / p.TQQQ.iloc[0])})
    res = pd.DataFrame(rows)
    res.to_csv(HERE / "ma_results.csv", index=False)
    pd.set_option("display.width", 200)
    for label in periods:
        print(f"\n=== {label} ===")
        print(res[res.period == label].drop(columns="period").to_string(index=False))


if __name__ == "__main__":
    main()
