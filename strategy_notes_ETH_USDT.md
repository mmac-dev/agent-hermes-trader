# Trading Agent Strategy Notes
# Version: 1.2
# Last updated: 2026-03-24

## Overview
Autonomous swing trading strategy for ETH/USDT. Multi-timeframe analysis (15m, 1h, 4h).
Agent refines this document after every 5 closed trades based on outcome data.

---

## Current Strategy Framework

### Pre-Trade Filters (check before ANY ETH entry)

**1. BTC Health Check:**
- ETH has 0.85–0.92 correlation with BTC — tighter than most alts. ETH rarely moves independently of BTC in the short term.
- If BTC is within 1% of a major S/R level ($60k, $65k, $70k, $75k) OR BTC 4h RSI is above 75 or below 25, DEFER the ETH entry by one scan cycle.
- If BTC 4h trend is strongly bearish (RSI < 40, MACD negative, price below EMA50), reduce confidence on ETH longs by 20% (not 15% like SOL — ETH amplifies BTC downside more aggressively).
- If BTC 4h trend is strongly bullish, increase confidence on ETH longs by 10% only if ETH's own setup criteria are already met.

**2. ETH/BTC Ratio Check:**
- If ETH/BTC ratio is at or near multi-month lows AND ETH is at a major support level, this is a contrarian long signal — add 5% confidence for long bounce setups.
- If ETH/BTC ratio is declining sharply (>3% drop in 7 days), reduce confidence on all ETH longs by 10% — capital is rotating out of ETH specifically.

**3. Volatility Sizing:**
- Normal position size when ETH 1h ATR is within 20% of its 20-period average.
- Reduce position size by 40% when ATR exceeds 1.5x its 20-period average (ETH vol spikes are sharper than SOL — use 40% reduction not 30%).
- Increase position size by 15% when ATR is below 0.7x its 20-period average AND a breakout setup is forming.

**4. Macro Event Filter:**
- ETH is highly sensitive to FOMC decisions, CPI releases, and Ethereum-specific catalysts (hard forks, ETF flow reports).
- On days with scheduled macro events, reduce max confidence by 10% for trades opened within 4 hours before the event.
- After the event, wait one full scan cycle before re-evaluating.

---

### Entry Criteria (as of v1.0 — evolved from trade data)

#### TREND CLASSIFICATION STANDARD (apply consistently across ALL timeframes)
- **BULLISH**: Price above EMA50 AND EMA20 > EMA50 AND RSI > 50
- **BEARISH**: Price below EMA50 AND EMA20 < EMA50 AND RSI < 50
- **NEUTRAL**: Any condition that does not meet BULLISH or BEARISH criteria

Apply this SAME classification to the 15m, 1h, and 4h timeframes. The multi-timeframe summary line (15m: X, 1h: X, 4h: X) and the LLM reasoning MUST use the same classification. Consistency between the summary and the reasoning is mandatory — no more contradictions.

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

**Range Bounce Setup (v1.2 — ETH-specific):**

Conditions:
- 4h trend: NEUTRAL or mildly bullish/bearish (NOT strongly trending against the bounce direction)
- Price within 3% of a defined support or resistance level (ETH uses wider zone than SOL due to larger absolute price swings)
- 1h BB position < 0.12 (for long bounce) or > 0.88 (for short bounce)
- 15m timing: RSI divergence, BB band touch + reversal candle, or MACD cross in bounce direction
- 15m RSI: between 20–38 for long bounce, between 62–80 for short bounce

Entry: On 15m confirmation signal at the S/R level
Stop Loss: 1.5x ATR beyond the S/R level (wider than SOL due to ETH's tendency for deeper wicks before reversing)
Take Profit: Opposite range boundary or mid-range (whichever gives minimum 2:1 R:R)
Confidence: Start at 55% base, add 5% for each: RSI divergence present, volume spike on bounce candle, 4h MACD in bounce direction

Key ETH levels to monitor (update weekly):
- Support zone: $2,000–$2,050 (psychological + structural), $1,800 (major — February low)
- Resistance zone: $2,200–$2,250 (EMA50 cluster + breakdown level), $2,350–$2,400 (strong rejection zone)
- Mid-range: $2,100–$2,150 (avoid entries here — no edge)

ETH-specific note: ETH respects round psychological levels ($2,000, $2,500, $3,000) more strongly than SOL. Weight these levels higher in bounce setups.

---

**Bearish Macro Context Rules (ETH-specific — review weekly):**

ETH has been in a macro downtrend since October 2025 ($4,831 → ~$2,100). Until price reclaims $2,400 on the daily with volume, treat the broader structure as bearish.

- Long trades are counter-trend: Require **70% confidence minimum** (not 65%) for any long entry. Shorts only need standard 65%.
- Long take-profits should be conservative: Target mid-range or nearest resistance, not the full range width.
- Short setups with 4h alignment get a **5% confidence bonus** (trading with macro trend).
- If price breaks below $2,000 on daily close: pause all long entries until price reclaims $2,050. Only shorts allowed below $2,000.
- If price reclaims $2,400 on daily close with above-average volume: remove this bearish bias entirely and revert to symmetric long/short treatment.

⚠️ Review this section weekly. Remove entirely when macro trend shifts.

---

### CRITICAL: Minimum Thresholds (ENFORCED)
- **Minimum R:R ratio: 2.0** (risk 1 to make 2)
- **Minimum confidence to open trade: 65%** — NO EXCEPTIONS
- Maximum concurrent open positions: 2
- **BB WIDTH CONSOLIDATION FILTER (ETH-specific)**:
  - No TREND trade when 15m BB width < 0.6% (ETH's base volatility is lower than SOL but higher than BTC)
  - No RANGE BOUNCE trade when 15m BB width < 0.25% (extreme compression — ETH can compress very tightly before violent expansion)
  - When 15m BB width exceeds 1.2%, increase confidence by 5% for trend-following setups (confirmed expansion)
  - When 15m BB width exceeds 2.0%, this signals potential volatility event — reduce position size by 25% as whipsaws become likely
  - Note: ETH tends to compress for longer periods than SOL before expanding. The 0.6% threshold is calibrated between BTC (tighter) and SOL (wider) to reflect ETH's intermediate volatility profile. The 2.0% upper warning is ETH-specific — SOL handles high BB width better due to its more liquid order book at current price levels.

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
- Binary ranging market block killed all trades during consolidation phases
- BTC/ETH strategy scope mismatch caused false rejections (fixed)
- Multi-timeframe summary and LLM reasoning used different trend classification
- BB width filter was calibrated for BTC, not ETH volatility profile
- No mechanism to account for ETH's macro bearish structure

## Adaptations Made
- v1.0: Initial seed strategy. No data yet.
- v1.0: Added hard block on confidence < 65%. Added BB width filter for consolidation detection. Clarified that confidence should be LOW in sideways markets, not high.
- v1.2 (2026-03-24): Added trend classification standard. Replaced binary ranging block with graduated ranging market handler (BB extremes 0.12/0.88). Added Range Bounce Setup. Added Pre-Trade Filters (BTC health, ETH/BTC ratio, volatility sizing, macro events). Recalibrated BB width thresholds for ETH volatility profile (0.6% trend, 0.25% range bounce). Added Bearish Macro Context Rules.

---

## Notes for LLM Analysis
- Always check higher timeframe (4h) first for trend context
- 15m is for timing only — don't trade against 1h trend
- Be cautious in ranging/sideways markets (look at BB width — narrow = compression)
- High volume on breakout candles increases conviction
- Divergence (price vs RSI/MACD) is a strong signal when aligned with trend
- **ETH is in a macro downtrend — longs are counter-trend until $2,400 is reclaimed**
- ETH/BTC correlation is 0.85–0.92, tighter than SOL/BTC — always check BTC first
- ETH respects psychological round numbers ($2,000, $2,500) more than SOL
- ETH compresses longer than SOL before expanding — patience on breakout entries
- Range bounce setups need wider stops (1.5x ATR) due to deeper wicks
- Macro events (FOMC, CPI, hard forks) cause outsized ETH moves — filter for these
- Update S/R levels weekly based on 4h chart structure
- **NEW**: RANGING MARKET HANDLING (ETH-specific):
  - If 4h AND 1h are both NEUTRAL:
    - Cap maximum confidence at 50%
    - ONLY allow entries if price is at BB extremes: BB position < 0.12 (near lower band) OR BB position > 0.88 (near upper band) on the 1h timeframe
    - Require 15m RSI divergence or BB band touch as timing confirmation
    - If BB position is between 0.12 and 0.88 (mid-range), do NOT trade
    - Reduce position size by 50% for any ranging market trade
  - Note: ETH uses tighter BB thresholds (0.12/0.88) than SOL (0.15/0.85) because ETH consolidates in narrower bands relative to its price and tends to produce sharper mean-reversion moves from extremes. Only trade when price is truly stretched.
- **NEW**: Confidence scoring must decrease when timeframes conflict or when in consolidation
- **NEW**: Reasoning that ends with 'violating the' = DO NOT TRADE
---

## Self-Tuning Framework
See shared reference: self_tuning_framework.md — applies identically to all four assets.

