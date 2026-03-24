# Trading Agent Strategy Notes
# Version: 1.0 (seed)
# Last updated: Initial seed — agent will evolve this document

## Overview
Autonomous swing trading strategy for BTC/USDT. Multi-timeframe analysis (15m, 1h, 4h).
Agent refines this document after every 5 closed trades based on outcome data.

---

## Current Strategy Framework

### Entry Criteria (as of v1.0 — to be evolved)

**Long Setup:**
- 4h trend is bullish or neutral (price above EMA50)
- 1h shows momentum confirmation (EMA20 > EMA50, RSI > 50)
- 15m provides timing entry (EMA9 cross up, MACD cross up, or bounce from support)
- RSI not overbought (< 70 on 1h)
- Volume surge on entry candle is a plus

**Short Setup:**
- 4h trend is bearish (price below EMA50)
- 1h shows bearish momentum (EMA20 < EMA50, RSI < 50)
- 15m timing: EMA9 cross down, rejection from resistance, or MACD cross down
- RSI not oversold (> 30 on 1h)

### Minimum Thresholds
- Minimum R:R ratio: 2.0 (risk 1 to make 2)
- Minimum confidence to open paper trade: 65%
- Maximum concurrent open positions: 2

### Stop Loss Placement
- Long: Below recent swing low or below 1.5x ATR from entry
- Short: Above recent swing high or above 1.5x ATR from entry

### Take Profit Placement
- Primary: Next significant resistance/support level
- Minimum TP distance: 2x the stop loss distance

---

## What Has Worked (tracked by agent)
*(agent will populate this from trade review)*

## What Has Failed (tracked by agent)
*(agent will populate this from trade review)*

## Adaptations Made
- v1.0: Initial seed strategy. No data yet.

---

## Notes for LLM Analysis
- Always check higher timeframe (4h) first for trend context
- 15m is for timing only — don't trade against 1h trend
- Be cautious in ranging/sideways markets (look at BB width — narrow = compression)
- High volume on breakout candles increases conviction
- Divergence (price vs RSI/MACD) is a strong signal when aligned with trend
