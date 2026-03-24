# Trading Agent Strategy Notes
# Version: 1.2 (updated 2026-03-24)
# Last updated: Lessons updated, ranging market overhaul, BTC correlation filter, trend classification standardised, SOL-specific BB width thresholds

## Overview
Autonomous swing trading strategy for SOL/USDT. Multi-timeframe analysis (15m, 1h, 4h).
Agent refines this document after every 5 closed trades based on outcome data.

---

## Current Strategy Framework

### Pre-Trade Filters (check before ANY entry)

**1. BTC Health Check:**
- SOL has 0.75-0.85 correlation with BTC. Before any SOL entry, check BTC's 4h trend.
- If BTC is within 1% of a major S/R level ($60k, $65k, $70k, $75k) OR BTC 4h RSI is above 75 or below 25, DEFER the SOL entry by one scan cycle. BTC moves at these levels will drag SOL regardless of SOL's own setup.
- If BTC 4h trend is strongly bearish (RSI < 40, MACD negative, price below EMA50), reduce confidence on SOL longs by 15% and increase confidence on SOL shorts by 10%.

**2. Volatility Sizing:**
- Normal position size when SOL 1h ATR is within 20% of its 20-period average
- Reduce position size by 30% when ATR exceeds 1.5x its 20-period average (volatility expansion)
- Increase position size by 20% when ATR is below 0.7x its 20-period average AND a breakout setup is forming (low vol compression before expansion)

---

### Entry Criteria (as of v1.0 — evolved from trade data)

**TREND CLASSIFICATION STANDARD (use consistently across all timeframes):**
- BULLISH: Price above EMA50 AND EMA20 > EMA50 AND RSI > 50
- BEARISH: Price below EMA50 AND EMA20 < EMA50 AND RSI < 50
- NEUTRAL: Any condition that does not meet BULLISH or BEARISH criteria

Apply this SAME classification to the 15m, 1h, and 4h timeframes. The multi-timeframe summary line (15m: X, 1h: X, 4h: X) and the LLM reasoning MUST use the same classification. If the summary says "4h: bullish" but price is above EMA50 while RSI is below 50, classify it as NEUTRAL, not bullish. Consistency between the summary and the reasoning is mandatory.

---

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

**Range Bounce Setup (v1.2 — SOL specific):**
- 4h trend: NEUTRAL or mildly bullish/bearish (NOT strongly trending against the bounce direction)
- Price within 2% of a defined support or resistance level
- 1h BB position < 0.15 (for long bounce) or > 0.85 (for short bounce)
- 15m timing: RSI divergence, BB band touch + reversal candle, or MACD cross in bounce direction
- 15m RSI: between 25-40 for long bounce, between 60-75 for short bounce (confirms stretched but not extreme)
- Entry: On 15m confirmation signal at the S/R level
- Stop Loss: 1.0x ATR beyond the S/R level (tighter than trend stops — expect the level to hold)
- Take Profit: Opposite range boundary or mid-range (whichever gives minimum 2:1 R:R)
- Confidence scoring: Start at 55% base, add 5% for each: RSI divergence present, volume spike on bounce candle, 4h MACD in bounce direction

**Key SOL levels to monitor (update weekly):**
- Support zones: $85-$88 (strong), $80-$82 (major)
- Resistance zones: $94-$96 (strong), $100 (psychological)

---

### CRITICAL: Minimum Thresholds (ENFORCED)
- **Minimum R:R ratio: 2.0** (risk 1 to make 2)
- **Minimum confidence to open trade: 65%** — NO EXCEPTIONS
- Maximum concurrent open positions: 2
- **BB WIDTH CONSOLIDATION FILTER** (SOL-specific thresholds):
  - No TREND trade when 15m BB width < 0.8% (SOL's higher base volatility needs a wider threshold than BTC)
  - No RANGE BOUNCE trade when 15m BB width < 0.3% (extreme compression — even bounces are unreliable)
  - When 15m BB width exceeds 1.5%, increase confidence by 5% for trend-following setups (confirmed expansion)
  - Note: The old 0.5% threshold was calibrated for BTC. SOL's typical daily range is 3-5% with higher baseline volatility, so the consolidation filter is set higher to be meaningful.

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
- Binary ranging market block killed all trades in range-bound conditions
- BTC/SOL strategy scope mismatch caused false rejections (fixed in v1.2)
- Multi-timeframe summary and LLM reasoning used different trend classification logic
- BB width filter was calibrated for BTC volatility, too tight for SOL

## Adaptations Made
- v1.0: Initial seed strategy. No data yet.
- v1.0: Added hard block on confidence < 65%. Added BB width filter for consolidation detection. Clarified that confidence should be LOW in sideways markets, not high.
- v1.2: Replaced binary ranging block with graduated mean-reversion logic. Added Range Bounce Setup. Added BTC correlation pre-trade filter. Standardised 3-condition trend classification. Updated BB width thresholds for SOL volatility profile.

---

## Notes for LLM Analysis
- Always check higher timeframe (4h) first for trend context
- 15m is for timing only — don't trade against 1h trend
- Be cautious in ranging/sideways markets (look at BB width — narrow = compression)
- High volume on breakout candles increases conviction
- Divergence (price vs RSI/MACD) is a strong signal when aligned with trend
- SOL spends ~60% of time in consolidation/range — strategy must handle this, not just block it
- BTC correlation (0.75-0.85) means always check BTC before SOL entries
- Range bounce setups are valid when trend setups aren't — both modes needed
- Update S/R levels weekly based on 4h chart structure
- **RANGING MARKET HANDLING**: If 4h AND 1h are both NEUTRAL:
  - Cap maximum confidence at 50% (below the 65% threshold required to trade — effectively no trade unless at range extremes)
  - ONLY allow entries if price is at BB extremes: BB position < 0.15 (near lower band) OR BB position > 0.85 (near upper band) on the 1h timeframe
  - Require 15m RSI divergence or BB band touch as timing confirmation
  - If BB position is between 0.15 and 0.85 (mid-range), do NOT trade — this is true consolidation
  - Reduce position size by 50% for any ranging market trade that qualifies
- **NEW**: Confidence scoring must decrease when timeframes conflict or when in consolidation
- **NEW**: Reasoning that ends with 'violating the' = DO NOT TRADE
---

## Self-Tuning Framework
See shared reference: self_tuning_framework.md — applies identically to all four assets.

