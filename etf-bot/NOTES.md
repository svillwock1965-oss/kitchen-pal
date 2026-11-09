# TQQQ / SQQQ project — notes so far (Nov 2026)

## How the funds work
- TQQQ = +3x the Nasdaq-100 **per day**; SQQQ = −3x per day. Both reset daily.
- Steady trend: leverage helps (5 days of +1% → TQQQ +15.9%).
- Chop: both lose (±5% for 10 days → QQQ −1.2%, TQQQ and SQQQ each −10.8%).
- $100 in TQQQ became ~$21 in 2022. A −10% Nasdaq day takes $100 → $70.
- Tradeable all day like a stock; day-trade limits depend on account type (cash vs. margin, $25k rule).

## What we tested (all on real or calibrated data)
| Idea | Result |
|---|---|
| Buy both, hold | +9% over ~5 yrs, −48% worst drop (decay) |
| N-day high/low "resistance" (high → SQQQ, low → TQQQ) | 3-day worked 2022-26 (+210%) but lost 74% over 1999-2026 — a fluke |
| N-day breakout to cash + trailing stop | +147% 2022-26, only +200% over 1999-2026 vs QQQ +1,426% |
| 200-day average rule (TQQQ above avg, else cash, 3% band) | +2,126% over 1999-2026 (beat QQQ) but −91% worst drop in dot-com |
| Market Pulse score, daily close → next day | Works backwards: big down days bounce, big up days stall. Following lost 96%; fading +196% (still < QQQ) |
| Market Pulse score, intraday (10:30/11:30/1:30 → close) | No reliable edge; results flip by checkpoint. Fade at 10:30 +46% on 58 trades (noise-level) |

## Things that keep showing up
1. **Mean reversion short-term**: after big one-day moves (daily or by 10:30), the Nasdaq tends to partly reverse — matches the original "highs are resistance" instinct.
2. **Trend works long-term**: slow rules (200-day, 120-day + trailing stop) beat fast ones.
3. Holding SQQQ for any length of time loses.
4. Breadth (how many leaders are down 2%+) is a good picture of the market but not a timing signal by itself.

## Open ideas
- Trade journal inside Market Pulse: log the user's own trades with the score at entry, to measure their instinct.
- Combine: long-term trend filter (200-day) + short-term fade (buy TQQQ on F-days only when above the 200-day).
- Re-run tests with the user's real tech and sector lists.

## Files
- `market-pulse.html` — live dashboard (https://claude.ai/artifact/UfaSMvowM5YA4eP1QkWhB7)
- `backtest.py`, `stress_test.py`, `ma_test.py`, `score_backtest.py`, `intraday_backtest.py` + their CSV results
