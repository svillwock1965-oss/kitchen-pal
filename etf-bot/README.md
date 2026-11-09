# ETF bot (TQQQ / SQQQ) — backtester

Tests rules that switch between TQQQ and SQQQ based on QQQ hitting N-day highs/lows.
**Research only — places no trades.**

- `data/` — daily prices for QQQ, TQQQ, SQQQ (Jan 2022 – Nov 2026, from Webull)
- `backtest.py` — runs every rule combination; `python3 backtest.py`
- `results.csv` — full results table

See the docstring at the top of `backtest.py` for the rules and simplifications.
