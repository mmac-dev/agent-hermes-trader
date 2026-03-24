# Trading Agent Strategy Notes
# Version: 1.1
# Last updated: 2026-03-24

## Overview
Autonomous swing trading strategy for BTC/USDT. Multi-timeframe analysis (15m, 1h, 4h).
Agent refines this document after every 5 closed trades based on outcome data.

---

## Current Strategy Framework

### Pre-Trade Filters (check before ANY BTC entry)

**1. Market Regime Check:**
- BTC is the market base asset — no correlation checks needed for other crypto
- If 4h BB width < 0.3% (extreme compression), do NOT open new trend trades
- If 4h BB width > 2.5% (volatility expansion), reduce position size by 20%
- Wait for 4h close above/below EMA50 before confirming trend direction

**2. BTC Dominance Check:**
- If BTC.D rising sharply (>2% in 7 days), capital flowing into BTC — increase confidence on BTC longs by 10%
- If BTC.D falling sharply while BTC price stable, capital rotating to alts — reduce confidence on BTC longs by 10%
- If both BTC price AND BTC.D falling, avoid longs entirely (macro bearish for entire crypto market)

**3. Volatility Sizing:**
- Normal position size when BTC 1h ATR is within 20% of its 20-period average
- Reduce position size by 30% when ATR exceeds 1.5x its 20-period average
- Increase position size by 10% when ATR is below 0.7x its 20-period average AND a breakout setup is forming

**4. Macro Event Filter:**
- BTC is sensitive to FOMC decisions, CPI releases, and US macro data
- On days with scheduled macro events, reduce max confidence by 10% for trades opened within 4 hours before the event
- After the event, wait one full scan cycle before re-evaluating
- BTC price often spikes on event openings — prefer entries after the initial volatility settles

**5. Geopolitical Sensitivity Filter:**
- BTC has become highly correlated with Nasdaq (0.75 correlation in 2026) and reacts sharply to geopolitical escalation, particularly Middle East tensions and US-Iran developments.
- If a major geopolitical event breaks during a scan cycle (e.g., military strikes, sanctions announcements, Strait of Hormuz disruptions), DEFER all new entries for 2 scan cycles. BTC's initial reaction to geopolitical shocks is typically a sharp sell-off followed by a recovery within 48–72 hours. Do not trade the initial spike.
- If gold is rising sharply (>2% in 24h) while BTC is falling, this signals a "risk-off" rotation — reduce confidence on all BTC longs by 15% until the divergence resolves.
- If BTC and gold are BOTH falling, this signals broad liquidation / margin call event — pause all trading for 2 scan cycles.

---

### TREND CLASSIFICATION STANDARD (apply consistently across ALL timeframes)
- **BULLISH**: Price above EMA50 AND EMA20 > EMA50 AND RSI > 50
- **BEARISH**: Price below EMA50 AND EMA20 < EMA50 AND RSI < 50
- **NEUTRAL**: Any condition that does not meet BULLISH or BEARISH criteria

Apply this SAME classification to the 15m, 1h, and 4h timeframes. The multi-timeframe summary line (15m: X, 1h: X, 4h: X) and the LLM reasoning MUST use the same classification. Consistency between the summary and the reasoning is mandatory — no more contradictions.

---

### Entry Criteria (as of v1.0 — evolved from trade data)

**Long Setup:**
- 4h trend is bullish or neutral (price above EMA50)
- 1h shows momentum confirmation (EMA20 > EMA50, RSI > 50)
- 15m provides timing entry (EMA9 cross up, MACD cross up, or bounce from support)
- RSI not overbought (< 70 on 1h)
- Volume surge on entry candle is a plus
- BB width > 0.4% on 15m (not in compression)

**Short Setup:**
- 4h trend is bearish (price below EMA50)
- 1h shows bearish momentum (EMA20 < EMA50, RSI < 50)
- 15m timing: EMA9 cross down, rejection from resistance, or MACD cross down
- RSI not oversold (> 30 on 1h)
- BB width > 0.4% on 15m (not in compression)

**Range Bounce Setup (v1.0 — BTC-specific):**

Conditions:
- 4h trend: NEUTRAL or mildly bullish/bearish (NOT strongly trending against the bounce direction)
- Price within 3% of a defined support or resistance level
- 1h BB position < 0.15 (for long bounce) or > 0.85 (for short bounce)
- 15m timing: RSI divergence, BB band touch + reversal candle, or MACD cross in bounce direction
- 15m RSI: between 25–40 for long bounce, between 60–75 for short bounce

Entry: On 15m confirmation signal at the S/R level
Stop Loss: 1.5x ATR beyond the S/R level
Take Profit: Opposite range boundary or mid-range (whichever gives minimum 2:1 R:R)
Confidence: Start at 55% base, add 5% for each: RSI divergence present, volume spike on bounce candle, 4h MACD in bounce direction

Key BTC levels to monitor (updated 2026-03-24 — review weekly):
- Support zone: $66,000–$68,000 (structural, multiple bounces in March), $60,000–$62,000 (major floor — bottom of multi-month range)
- Resistance zone: $74,000–$75,000 (key ceiling, April 2025 low turned resistance, repeated rejections), $78,000–$80,000 (psychological + order block)
- Mid-range: $69,000–$72,000 (current price area — avoid new range bounce entries here unless BB extremes reached)
- Macro pivot: $88,000–$90,000 (200-EMA zone — reclaiming this would signal structural trend reversal)

Important: BTC is currently trading near $70,000–$71,000, which is MID-RANGE within the broader consolidation. Do not force range bounce entries at current price. Wait for moves toward $66,000–$68,000 (long bounce) or $74,000–$75,000 (short bounce) before engaging the Range Bounce Setup.

BTC-specific note: BTC respects psychological round numbers ($60k, $65k, $70k, $75k, $80k) strongly. Weight these levels higher in bounce setups.

---

**Macro Trend Context (BTC-specific — review weekly):**

BTC peaked at $126,000 in October 2025 and is currently trading around $70,000 — a 44% drawdown. The medium-term trend channel is bearish. Price remains well below the 200-EMA (~$88,000). Until price reclaims $88,000 on a daily close with above-average volume, treat the broader structure as bearish.

- Long trades are counter-trend: Require **70% confidence minimum** (not 65%) for any long entry.
- Short setups with 4h bearish alignment get a **5% confidence bonus** (trading with macro trend).
- Long take-profits should be conservative: Target mid-range or nearest resistance, not full range width.
- If price breaks below $60,000 on daily close: pause all long entries until price reclaims $62,000. Only shorts allowed below $60,000.
- If price reclaims $88,000 on daily close with above-average volume: REMOVE this bearish bias and revert to symmetric long/short treatment.

Note: This bias is less aggressive than ETH's equivalent because BTC's drawdown (44%) is shallower than ETH's (55%+), BTC has stronger institutional bid support (spot ETF inflows), and BTC's range floor ($60,000) has been defended more convincingly than ETH's ($1,800). The macro bias exists but BTC is closer to neutral than ETH.

⚠️ Review this section weekly. Remove entirely when macro trend shifts.

---

### BB WIDTH CONSOLIDATION FILTER (BTC-specific):
- No TREND trade when 15m BB width < 0.5% (BTC's base volatility is lower than ETH/SOL)
- No RANGE BOUNCE trade when 15m BB width < 0.20% (extreme compression — BTC can compress very tightly before violent expansion)
- When 15m BB width exceeds 1.5%, increase confidence by 5% for trend-following setups (confirmed expansion)
- When 15m BB width exceeds 2.5%, this signals potential volatility event — reduce position size by 20% as whipsaws become likely

Note: BTC tends to compress for longer periods than ETH/SOL before expanding. The 0.5% threshold is calibrated for BTC's relatively stable volatility profile. The 2.5% upper warning is BTC-specific — BTC handles high BB width better than smaller caps due to its deeper liquidity.

---

### RANGING MARKET HANDLING (BTC-specific):
- If 4h AND 1h are both NEUTRAL per the Trend Classification Standard:
  - Cap maximum confidence at 50%
  - ONLY allow entries if price is at BB extremes: BB position < 0.15 (near lower band) OR BB position > 0.85 (near upper band) on the 1h timeframe
  - Require 15m RSI divergence or BB band touch as timing confirmation
  - If BB position is between 0.15 and 0.85 (mid-range), do NOT trade
  - Reduce position size by 40% for any ranging market trade
- Note: BTC has been consolidating in a broad $60,000–$75,000 range since late 2024. This rule prevents the agent from sitting idle during extended neutral periods while still requiring price to be at range extremes before entering. The 40% position reduction (vs SOL's 50%) reflects BTC's deeper liquidity and more orderly mean-reversion at range boundaries.

---

### CRITICAL: Minimum Thresholds (ENFORCED)
- **Minimum R:R ratio: 2.0** (risk 1 to make 2)
- **Minimum confidence to open trade: 65%** — NO EXCEPTIONS
- Maximum concurrent open positions: 2
- **BLOCKED**: Do not trade when 15m BB width < 0.5% (consolidation = false moves)

### Stop Loss Placement
- Long: Below recent swing low or below 1.5x ATR from entry
- Short: Above recent swing high or above 1.5x ATR from entry

### Take Profit Placement
- Primary: Next significant resistance/support level
- Minimum TP distance: 2x the stop loss distance

---

## What Has Worked (seeded from SOL/ETH learnings — update with BTC-specific data after trades)
- Long entries at lower BB with 4h bullish alignment (proven on SOL)
- Trading with 4h trend direction
- 15m oversold bounce for timing entries
- Range bounce setups at defined S/R levels with BB extreme confirmation
- Waiting for 15m MACD cross or RSI divergence as timing trigger (patience pays)

## What Has Failed (seeded from SOL/ETH learnings — update with BTC-specific data after trades)
- Binary "both neutral = don't trade" rule killed all activity during ranging markets
- Executing trades with 0% confidence (critical logic bug — now fixed)
- Trading in BB compression zones (false breakouts)
- High confidence assignments in sideways markets without BB extreme confirmation
- Ignoring macro trend direction (longs in a downtrend without higher confidence bar)
- Mismatched trend classification between summary and LLM reasoning (now standardised)

## Adaptations Made
- v1.0: Initial seed strategy with pre-trade filters, trend classification, range bounce setup, BB width calibration, and macro event filter.
- v1.1 (2026-03-24): Added ranging market graduated rule (4h+1h neutral handling). Updated S/R levels to current market ($66k–$68k support, $74k–$75k resistance). Added bearish macro context bias (longs require 70% confidence until $88k reclaimed). Added geopolitical sensitivity filter (gold divergence, risk-off detection). Seeded lessons from SOL/ETH trading experience. All changes calibrated to BTC's specific characteristics (deeper liquidity, institutional bid, Nasdaq correlation).

---

## Notes for LLM Analysis
- Always check higher timeframe (4h) first for trend context
- 15m is for timing only — don't trade against 1h trend
- Be cautious in ranging/sideways markets (look at BB width — narrow = compression)
- High volume on breakout candles increases conviction
- Divergence (price vs RSI/MACD) is a strong signal when aligned with trend
- **BTC is the market base asset — no correlation checks needed for other crypto**
- BTC dominates market sentiment — if BTC is weak, alts are weaker
- BTC respects psychological round numbers ($60k, $65k, $70k, $75k, $80k) strongly
- BTC compresses longer than ETH/SOL before expanding — patience on breakout entries
- Range bounce setups need wider stops (1.5x ATR) due to deeper wicks
- Macro events (FOMC, CPI, US jobs data) cause outsized BTC moves — filter for these
- Update S/R levels weekly based on 4h chart structure
- BTC.D rising = good for BTC longs, bad for alts
- BTC.D falling = bad for BTC longs (capital rotating to alts), good for alt longs
---

## Self-Tuning Framework
See shared reference: self_tuning_framework.md — applies identically to all four assets.

