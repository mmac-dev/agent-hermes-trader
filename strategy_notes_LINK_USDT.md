# Trading Agent Strategy Notes
# Version: 1.2
# Last updated: 2026-03-24

## Overview
Autonomous swing trading strategy for LINK/USDT. Multi-timeframe analysis (15m, 1h, 4h).
Agent refines this document after every 5 closed trades based on outcome data.

---

## Current Strategy Framework

### Pre-Trade Filters (check before ANY LINK entry)

**1. BTC Health Check:**
- LINK has 0.90 correlation with BTC — the tightest of all four assets traded. LINK almost never moves independently of BTC in the short term.
- If BTC is within 1% of a major S/R level ($65k, $70k, $75k) OR BTC 4h RSI is above 75 or below 25, DEFER the LINK entry by one scan cycle.
- If BTC 4h trend is strongly bearish (RSI < 40, MACD negative, price below EMA50), reduce confidence on LINK longs by 25% and increase confidence on LINK shorts by 10%.
- The 25% penalty is the highest of all four assets because LINK amplifies BTC downside the most due to its lower liquidity and higher beta.

**2. Liquidity Check:**
- LINK's 24h volume is significantly lower than the other three assets. Before any entry, check that 15m volume is not anomalously low (below 50% of the 20-period average). Trading into thin order books increases slippage and stop-hunt risk.
- If 15m volume is below 50% of its 20-period average, DEFER the entry by one scan cycle regardless of how good the setup looks.
- If volume surges above 2x the 20-period average, this confirms a genuine move — add 5% confidence to any aligned setup.

**3. Volatility Sizing:**
- Normal position size when LINK 1h ATR is within 20% of its 20-period average.
- Reduce position size by 50% when ATR exceeds 1.5x its 20-period average (LINK vol spikes are the sharpest of all four assets — needs the largest reduction).
- Increase position size by 10% when ATR is below 0.7x its 20-period average AND a breakout setup is forming.

---

### Entry Criteria (as of v1.0 — evolved from trade data)

#### TREND CLASSIFICATION STANDARD (apply consistently across ALL timeframes)
- **BULLISH**: Price above EMA50 AND EMA20 > EMA50 AND RSI > 50
- **BEARISH**: Price below EMA50 AND EMA20 < EMA50 AND RSI < 50
- **NEUTRAL**: Any condition that does not meet BULLISH or BEARISH criteria

Apply this SAME classification to the 15m, 1h, and 4h timeframes. The multi-timeframe summary line (15m: X, 1h: X, 4h: X) and the LLM reasoning MUST use the same classification. Consistency between the summary and the reasoning is mandatory.

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

**Range Bounce Setup (v1.2 — LINK-specific):**

Conditions:
- 4h trend: NEUTRAL or mildly bullish/bearish (NOT strongly trending against the bounce direction)
- Price within 3% of a defined support or resistance level
- 1h BB position < 0.15 (for long bounce) or > 0.85 (for short bounce)
- 15m timing: RSI divergence, BB band touch + reversal candle, or MACD cross in bounce direction
- 15m RSI: between 25–40 for long bounce, between 60–75 for short bounce

Entry: On 15m confirmation signal at the S/R level
Stop Loss: 2.0x ATR beyond the S/R level (LINK wicks are wider than BTC/ETH/SOL relative to price — needs the widest stops of all four assets)
Take Profit: Opposite range boundary or mid-range (whichever gives minimum 2:1 R:R)
Confidence: Start at 55% base, add 5% for each: RSI divergence present, volume spike on bounce candle, 4h MACD in bounce direction

Key LINK levels to monitor (updated 2026-03-24 — review weekly):
- Support zone: $8.50–$8.80 (structural floor, multiple bounces), $7.50–$8.00 (major — breakdown trigger if lost)
- Resistance zone: $9.17–$9.40 (Fibonacci 0.618 + VWAP cluster, repeated rejections), $10.00 (psychological)
- Mid-range: $8.90–$9.10 (current price area — avoid new entries here unless BB extremes reached)

LINK-specific notes:
- LINK trades in a very tight range ($8.50–$9.40) — less than 10% width. Range bounces need to be quick in and out.
- LINK has the lowest 24h volume of the four assets (~$236M vs BTC's $53B). This means wider spreads, more slippage, and less reliable order book depth at extremes. Factor this into position sizing.
- LINK respects round numbers ($8, $9, $10) and Fibonacci levels more cleanly than the other three assets due to lower noise.

---

**Macro Trend Context (LINK-specific — review weekly):**

LINK peaked at approximately $28 in late 2024 / early 2025 and is currently trading around $9 — a ~68% drawdown, the deepest of all four assets traded. The macro structure is clearly bearish with a descending triangle pattern (lower highs, flat support). Until price reclaims $10.50 on a daily close with above-average volume, treat the broader structure as bearish.

- Long trades are counter-trend: Require **70% confidence minimum** (not 65%) for any long entry.
- Short setups with 4h bearish alignment get a **5% confidence bonus** (trading with macro trend).
- Long take-profits should be conservative: Target mid-range or nearest resistance, not full range width.
- If price breaks below $8.00 on daily close: pause all long entries until price reclaims $8.50. Only shorts allowed below $8.00.
- If price reclaims $10.50 on daily close with above-average volume: REMOVE this bearish bias and revert to symmetric long/short treatment.

Note: LINK has the steepest macro drawdown of all four assets (68% vs BTC's 44%, ETH's 55%, SOL's ~50%). This warrants the most cautious long bias. However, LINK also has strong fundamental catalysts (CCIP adoption, institutional oracle partnerships) that could trigger sharp reversals — hence the relatively accessible $10.50 lift level rather than requiring a full trend reversal.

⚠️ Review this section weekly. Remove entirely when macro trend shifts.

---

### CRITICAL: Minimum Thresholds (ENFORCED)
- **Minimum R:R ratio: 2.0** (risk 1 to make 2)
- **Minimum confidence to open trade: 65%** — NO EXCEPTIONS
- Maximum concurrent open positions: 2
- **BB WIDTH CONSOLIDATION FILTER (LINK-specific)**:
  - No TREND trade when 15m BB width < 1.0% (LINK's base volatility is higher than BTC/ETH relative to price due to its mid-cap nature and lower liquidity)
  - No RANGE BOUNCE trade when 15m BB width < 0.4% (extreme compression — even bounces unreliable in this state)
  - When 15m BB width exceeds 2.0%, increase confidence by 5% for trend-following setups (confirmed expansion)
  - When 15m BB width exceeds 3.0%, this signals potential volatility event — reduce position size by 30% as whipsaws and stop-hunts become likely in LINK's thinner order book
  - Note: LINK's BB width thresholds are the widest of all four assets because its percentage moves are larger. A 0.5% BB width that signals compression on BTC is normal background noise on LINK. The 1.0% trend filter and 3.0% upper warning are calibrated to LINK's actual volatility range.

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
- BTC/LINK strategy scope mismatch caused false rejections in multiple scans (now fixed by asset-specific strategy loading)
- Multi-timeframe summary and LLM reasoning used different trend classification logic
- BB width filter at 0.5% was calibrated for BTC, far too tight for LINK's higher relative volatility
- No mechanism to account for LINK's macro bearish structure (68% drawdown from peak)
- No liquidity filter despite LINK having significantly thinner order books than the other three assets

## Adaptations Made
- v1.0: Initial seed strategy. No data yet.
- v1.0: Added hard block on confidence < 65%. Added BB width filter for consolidation detection. Clarified that confidence should be LOW in sideways markets, not high.
- v1.2 (2026-03-24): Added trend classification standard. Replaced binary neutral block with graduated ranging rule. Added range bounce setup with LINK-specific S/R levels. Added pre-trade filters (BTC correlation, liquidity check, volatility sizing). Recalibrated BB width from 0.5% to 1.0% for LINK volatility. Added bearish macro context bias ($10.50 lift level). All thresholds calibrated to LINK's specific characteristics (lowest liquidity, highest beta, tightest BTC correlation, deepest macro drawdown).

---

## Notes for LLM Analysis
- Always check higher timeframe (4h) first for trend context
- 15m is for timing only — don't trade against 1h trend
- Be cautious in ranging/sideways markets (look at BB width — narrow = compression)
- High volume on breakout candles increases conviction
- Divergence (price vs RSI/MACD) is a strong signal when aligned with trend
- **LINK has the tightest BTC correlation (0.90) — always check BTC first, LINK rarely moves alone**
- LINK has the lowest liquidity of the four assets — check volume before entries, defer in thin markets
- LINK's tight $8.50–$9.40 range means range bounces need quick execution and tight management
- LINK wicks are wider relative to price than BTC/ETH/SOL — use 2.0x ATR stops (widest of all assets)
- LINK respects Fibonacci levels and round numbers ($8, $9, $10) cleanly due to lower market noise
- **Macro structure is the most bearish of all four assets (68% drawdown) — longs are counter-trend**
- Update S/R levels weekly based on 4h chart structure
- **NEW**: RANGING MARKET HANDLING (LINK-specific):
  - If 4h AND 1h are both NEUTRAL:
    - Cap maximum confidence at 50%
    - ONLY allow entries if price is at BB extremes: BB position < 0.15 (near lower band) OR BB position > 0.85 (near upper band) on the 1h timeframe
    - Require 15m RSI divergence or BB band touch as timing confirmation
    - If BB position is between 0.15 and 0.85 (mid-range), do NOT trade
    - Reduce position size by 50% for any ranging market trade
  - Note: LINK is a mid-cap alt with lower liquidity than BTC/ETH/SOL. It spends extended periods in tight ranges, then moves violently on breakouts. The 50% position reduction reflects the higher slippage risk and wider spreads during low-volume consolidation periods.
- **NEW**: Confidence scoring must decrease when timeframes conflict or when in consolidation
- **NEW**: Reasoning that ends with 'violating the' = DO NOT TRADE
---

## Self-Tuning Framework
See shared reference: self_tuning_framework.md — applies identically to all four assets.

