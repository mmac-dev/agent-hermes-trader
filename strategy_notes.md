# Trading Agent Strategy Notes
# Version: 1.1
# Last updated: After 5 trades reviewed

## Overview
Autonomous swing trading strategy for BTC/USDT. Multi-timeframe analysis (15m, 1h, 4h).
Agent refines this document after every 5 closed trades based on outcome data.

---

## Current Strategy Framework

### Entry Criteria (as of v1.1 — evolved from trade data)

**Long Setup:**
- 4h trend is bullish or neutral (price above EMA50)
- 1h shows momentum confirmation (EMA20 > EMA50, RSI > 50)
- 15m provides timing entry (EMA9 cross up, MACD cross up, or bounce from support)
- RSI not overbought (< 70 on 1h)
- Volume surge on entry candle is a plus
- BB width > 0.5% on 15m (not in compression)

**Short Setup:**
- 4h trend is bearish (price below EMA50)
- 1h shows bearish momentum (EMA20 < EMA50, RSI < 50)
- 15m timing: EMA9 cross down, rejection from resistance, or MACD cross down
- RSI not oversold (> 30 on 1h)
- BB width > 0.5% on 15m (not in compression)

### CRITICAL: Minimum Thresholds (ENFORCED)
- **Minimum R:R ratio: 2.0** (risk 1 to make 2)
- **Minimum confidence to open trade: 65%** — NO EXCEPTIONS
- Maximum concurrent open positions: 2
- **BLOCKED**: Do not trade when BB width < 0.5% on 15m (consolidation = false moves)

### Stop Loss Placement
- Long: Below recent swing low or below 1.5x ATR from entry
- Short: Above recent swing high or above 1.5x ATR from entry

### Take Profit Placement
- Primary: Next significant resistance/support level
- Minimum TP distance: 2x the stop loss distance

---

## What Has Worked (tracked by agent)
- Long entries at lower Bollinger Band with 4h bullish alignment and volume confirmation (trade #5)
- Trading with the 4h trend direction (LONG bias in bullish 4h)
- Using 15m oversold bounce at support for timing entries

## What Has Failed (tracked by agent)
- Executing trades with 0% confidence despite reasoning explicitly stating criteria violated — this is a critical logic failure
- Opening positions in consolidation/ranging markets (BB compression)
- High confidence scores in sideways markets with conflicting timeframe signals
- Trading against neutral 1h/4h trends (no clear momentum direction)

## Adaptations Made
- v1.0: Initial seed strategy. No data yet.
- v1.1: Added hard block on confidence < 65%. Added BB width filter for consolidation detection. Clarified that confidence should be LOW in sideways markets, not high.

---

## Notes for LLM Analysis
- Always check higher timeframe (4h) first for trend context
- 15m is for timing only — don't trade against 1h trend
- Be cautious in ranging/sideways markets (look at BB width — narrow = compression)
- High volume on breakout candles increases conviction
- Divergence (price vs RSI/MACD) is a strong signal when aligned with trend
- **NEW**: If 4h AND 1h are both neutral (no clear trend), the market is ranging — do not trade
- **NEW**: Confidence scoring must decrease when timeframes conflict or when in consolidation
- **NEW**: Reasoning that ends with 'violating the' = DO NOT TRADE
