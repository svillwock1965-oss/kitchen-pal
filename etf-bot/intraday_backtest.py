"""
Intraday backtest of the Market Pulse score.

Question: when the score is extreme partway through the day, does the move
CONTINUE into the close?

For each day (~2 years of hourly data from Yahoo) the score is computed at
10:30, 11:30 and 13:30 ET, using the same formula as market-pulse.html:
  * every stock/ETF's change = price at the checkpoint vs. yesterday's close
  * 3-month trend = checkpoint price vs. the average of the last 63 daily closes
  * volume = QQQ's volume so far today vs. the average volume by the same
    time over the previous 20 days
Then we measure QQQ from the checkpoint to the 4:00 PM close, and test:
  grade A -> buy TQQQ at the checkpoint, sell at the close
  grade F -> buy SQQQ at the checkpoint, sell at the close

Usage:  python3 intraday_backtest.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from score_backtest import TECH, SECT

HERE = Path(__file__).parent
SYMS = TECH + SECT + ["QQQ", "SPY", "VIXY", "TQQQ", "SQQQ"]
CHECKPOINTS = {"10:30": "09:30", "11:30": "10:30", "13:30": "12:30"}  # checkpoint -> bar whose close it is
COST = 0.0005


def load():
    cache = HERE / "data" / "intraday_60m.pkl"
    if cache.exists():
        return pd.read_pickle(cache)
    d = yf.download(SYMS, period="730d", interval="60m", auto_adjust=True, progress=False, prepost=False)
    d = d[["Close", "Volume"]]
    d.to_pickle(cache)
    return d


def main():
    d = load()
    c, v = d["Close"], d["Volume"]
    day = c.index.date
    hhmm = c.index.strftime("%H:%M")

    daily_close = c.groupby(day).last()
    prev_close = daily_close.shift(1)
    ma63 = daily_close.rolling(63).mean().shift(1)          # prior 63 closes
    cumvol = v["QQQ"].groupby(day).cumsum()

    rows = []
    for cp, bar in CHECKPOINTS.items():
        at = c[hhmm == bar]
        at.index = at.index.date
        cv = cumvol[hhmm == bar]; cv.index = cv.index.date
        avg_cv = cv.shift(1).rolling(20).mean()
        days = at.index.intersection(prev_close.dropna(how="all").index)
        for dd in days:
            p, pc = at.loc[dd], prev_close.loc[dd]
            chg = p / pc - 1
            cl = lambda x: np.clip(x, -1, 1)
            tech = 25 * np.nanmean(cl(chg[TECH] / 0.02))
            sect = 20 * np.nanmean(cl(chg[SECT] / 0.02))
            qqq = 12 * cl(chg.QQQ / 0.015)
            spy = 8 * cl(chg.SPY / 0.015)
            vix = 15 * cl(-chg.VIXY / 0.05)
            m = ma63.loc[dd]
            trend = 20 * (cl((p.QQQ / m.QQQ - 1) / 0.05) + cl((p.SPY / m.SPY - 1) / 0.05)) / 2
            raw = tech + sect + qqq + spy + vix + (0 if np.isnan(trend) else trend)
            ratio = cv.loc[dd] / avg_cv.loc[dd] if not np.isnan(avg_cv.loc[dd]) else 1.0
            score = float(np.clip(raw * (1 + 0.3 * np.clip(ratio - 1, -0.5, 1)), -100, 100))
            close = daily_close.loc[dd]
            rows.append({"date": dd, "checkpoint": cp, "score": score,
                         "tech": tech, "sector": sect, "qqq": qqq, "spy": spy, "vix": vix, "trend": trend,
                         "qqq_so_far": chg.QQQ,
                         "qqq_to_close": close.QQQ / p.QQQ - 1,
                         "tqqq_to_close": close.TQQQ / p.TQQQ - 1,
                         "sqqq_to_close": close.SQQQ / p.SQQQ - 1})
    f = pd.DataFrame(rows).dropna(subset=["qqq_to_close"])
    f["grade"] = pd.cut(f.score, [-101, -60, -25, 25, 60, 101], labels=["F", "D", "C", "B", "A"])
    f.to_csv(HERE / "intraday_scores.csv", index=False)

    n_days = f.date.nunique()
    print(f"Days: {n_days} ({f.date.min()} to {f.date.max()})\n")
    for cp in CHECKPOINTS:
        s = f[f.checkpoint == cp]
        print(f"=== Score at {cp} ET -> what QQQ did from then to the 4:00 close ===")
        g = s.groupby("grade", observed=True).agg(
            days=("score", "size"),
            qqq_so_far_avg_pct=("qqq_so_far", lambda x: round(x.mean() * 100, 2)),
            rest_of_day_avg_pct=("qqq_to_close", lambda x: round(x.mean() * 100, 3)),
            continued_pct=("qqq_to_close", lambda x: np.nan),
        )
        # "continued" = rest of day moved in the same direction as the score
        for gr in g.index:
            sub = s[s.grade == gr]
            sign = np.sign(sub.score)
            g.loc[gr, "continued_pct"] = round(100 * (np.sign(sub.qqq_to_close) == sign).mean(), 1) if gr != "C" else np.nan
        print(g.to_string())
        print(f"  all days: rest-of-day avg {s.qqq_to_close.mean()*100:.3f}%")
        print("  correlation with rest of day: " + ", ".join(
            f"{k} {s[k].corr(s.qqq_to_close):+.2f}" for k in ["tech", "sector", "qqq", "vix", "trend", "score"]))

        # trading tests
        for label, a_side, f_side in [("follow (A->TQQQ, F->SQQQ)", "tqqq_to_close", "sqqq_to_close"),
                                      ("fade   (F->TQQQ, A->SQQQ)", "sqqq_to_close", "tqqq_to_close")]:
            for thr_name, hi, lo in [("A/F only", ["A"], ["F"]), ("A+B / D+F", ["A", "B"], ["D", "F"])]:
                r = np.where(s.grade.isin(hi), s[a_side], np.where(s.grade.isin(lo), s[f_side], 0.0))
                trades = (r != 0).sum()
                r = np.where(r != 0, r - 2 * COST, 0)
                eq = np.cumprod(1 + r)
                dd = (eq / np.maximum.accumulate(eq) - 1).min()
                wins = (r[r != 0] > 0).mean() * 100 if trades else 0
                avg = r[r != 0].mean() * 100 if trades else 0
                print(f"  {label} {thr_name:10}: {trades:4d} trades, win {wins:4.1f}%, avg {avg:+.2f}%/trade, "
                      f"total {(eq[-1]-1)*100:+7.1f}%, worst drop {dd*100:.1f}%")
        print()
    q = daily_close.QQQ.loc[f.date.min():]
    print(f"Hold QQQ over the same period: {(q.iloc[-1]/q.iloc[0]-1)*100:+.1f}%")


if __name__ == "__main__":
    main()
