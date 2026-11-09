"""
Stress test back to 1999 using SIMULATED TQQQ / SQQQ.

TQQQ and SQQQ only exist since 2010, so before that we build them from QQQ:
    simulated TQQQ daily return = +3 x QQQ daily return - daily cost
    simulated SQQQ daily return = -3 x QQQ daily return - daily cost
The yearly cost (fees + borrowing) is calibrated so the simulation matches the
real funds over 2010-2026. Over the real period the simulation is checked
against the actual prices.

Usage:  python3 stress_test.py      (needs data/yahoo_close.csv)
"""
from pathlib import Path

import numpy as np
import pandas as pd

from backtest import run, stats

HERE = Path(__file__).parent


def simulate(q, drag):
    r = q.pct_change().fillna(0)
    d = drag / 252
    t = (1 + 3 * r - d).clip(lower=0).cumprod()
    s = (1 - 3 * r - d).clip(lower=0).cumprod()
    return t, s


def calibrate(raw):
    real = raw.dropna()
    best = {}
    for name, sign in (("TQQQ", 1), ("SQQQ", -1)):
        actual = np.log(real[name].iloc[-1] / real[name].iloc[0])
        errs = {}
        for drag in np.arange(0, 0.10, 0.0025):
            t, s = simulate(real["QQQ"], drag)
            sim = t if sign == 1 else s
            errs[drag] = abs(np.log(sim.iloc[-1] / sim.iloc[0]) - actual)
        best[name] = min(errs, key=errs.get)
    return best


def main():
    raw = pd.read_csv(HERE / "data" / "yahoo_close.csv", index_col=0, parse_dates=True)
    drag = calibrate(raw)
    print(f"Calibrated yearly cost: TQQQ {drag['TQQQ']:.2%}, SQQQ {drag['SQQQ']:.2%}")

    q = raw["QQQ"].dropna()
    t, _ = simulate(q, drag["TQQQ"])
    _, s = simulate(q, drag["SQQQ"])
    px = pd.DataFrame({"QQQ": q, "TQQQ": t, "SQQQ": s})

    real = raw.dropna()
    for name in ("TQQQ", "SQQQ"):
        a = real[name] / real[name].iloc[0]
        b = px[name].loc[real.index] / px[name].loc[real.index[0]]
        print(f"  check {name} 2010-2026: real {a.iloc[-1]:.1f}x, simulated {b.iloc[-1]:.1f}x")

    rules = [
        ("breakout_cash", 60, 0.15, 0.10, "best rule from the 2022-2026 test"),
        ("breakout_cash", 60, None, 0.10, ""),
        ("breakout_cash", 20, None, 0.10, ""),
        ("breakout_cash", 10, None, None, ""),
        ("breakout_cash", 100, None, 0.10, ""),
        ("breakout_cash", 120, None, 0.15, ""),
        ("resistance", 3, None, None, "the +210% rule from the short test"),
        ("resistance", 5, None, None, ""),
    ]
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
        p = px.loc[a:b]
        base = {"period": label}
        rows.append({**base, "rule": "hold QQQ", **stats(p.QQQ / p.QQQ.iloc[0])})
        rows.append({**base, "rule": "hold TQQQ (sim)", **stats(p.TQQQ / p.TQQQ.iloc[0])})
        for strat, n, stop, trail, _ in rules:
            curve, trades = run(p, strat, n, stop, trail)
            name = f"{strat} {n}d" + (f" stop{int(stop*100)}" if stop else "") + (f" trail{int(trail*100)}" if trail else "")
            rows.append({**base, "rule": name, **stats(curve, trades)})
    res = pd.DataFrame(rows)
    res.to_csv(HERE / "stress_results.csv", index=False)
    pd.set_option("display.width", 200)
    for label in periods:
        print(f"\n=== {label} ===")
        print(res[res.period == label].drop(columns="period").to_string(index=False))


if __name__ == "__main__":
    main()
