================================================================================
HERMES TRADER SELF-DIAGNOSTIC REPORT
================================================================================

CHECK 1 — STRATEGY NOTES LOADING:
================================================================================

--- BTC ---
✓ File exists: /home/agentneo/hermes-trader/strategy_notes_BTC_USDT.md
  First line: '# Trading Agent Strategy Notes'
  ⚠ First line does NOT contain 'BTC' explicitly - but content is BTC-specific
  ✓ Version: Version: 1.1

--- ETH ---
✓ File exists: /home/agentneo/hermes-trader/strategy_notes_ETH_USDT.md
  First line: '# Trading Agent Strategy Notes'
  ⚠ First line does NOT contain 'ETH' explicitly - but content is ETH-specific
  ✓ Version: Version: 1.2

--- SOL ---
✓ File exists: /home/agentneo/hermes-trader/strategy_notes_SOL_USDT.md
  First line: '# Trading Agent Strategy Notes'
  ⚠ First line does NOT contain 'SOL' explicitly - but content is SOL-specific
  ✓ Version: Version: 1.2 (updated 2026-03-24)

--- LINK ---
✓ File exists: /home/agentneo/hermes-trader/strategy_notes_LINK_USDT.md
  First line: '# Trading Agent Strategy Notes'
  ⚠ First line does NOT contain 'LINK' explicitly - but content is LINK-specific
  ✓ Version: Version: 1.2

NOTE: First line should ideally be: "# {ASSET} Trading Agent Strategy Notes"

================================================================================
CHECK 2 — SYMBOL CONSISTENCY:
================================================================================

--- trader.py (BTC) ---
  SYMBOL = BTC/USDT
  ✓ SYMBOL matches expected: BTC/USDT
  STRATEGY_NOTES_PATH = /home/agentneo/hermes-trader/strategy_notes_BTC_USDT.md
  ✓ STRATEGY_NOTES_PATH correct

--- eth_trader.py (ETH) ---
  SYMBOL = ETH/USDT
  ✓ SYMBOL matches expected: ETH/USDT
  STRATEGY_NOTES_PATH = /home/agentneo/hermes-trader/strategy_notes_ETH_USDT.md
  ✓ STRATEGY_NOTES_PATH correct

--- sol_trader.py (SOL) ---
  SYMBOL = SOL/USDT
  ✓ SYMBOL matches expected: SOL/USDT
  STRATEGY_NOTES_PATH = /home/agentneo/hermes-trader/strategy_notes_SOL_USDT.md
  ✓ STRATEGY_NOTES_PATH correct

--- link_trader.py (LINK) ---
  SYMBOL = LINK/USDT
  ✓ SYMBOL matches expected: LINK/USDT
  STRATEGY_NOTES_PATH = /home/agentneo/hermes-trader/strategy_notes_LINK_USDT.md
  ✓ STRATEGY_NOTES_PATH correct

--- get_signals.py (hardcoded symbol check) ---
  Found symbol references: {'BTC/USDT'}
  ✓ Only one hardcoded symbol reference (BTC/USDT - default only)

================================================================================
CHECK 3 — TREND CLASSIFICATION:
================================================================================

All trader files (trader.py, eth_trader.py, sol_trader.py, link_trader.py) use
the same tf_summary() function embedded in format_telegram_report().

tf_summary() checks (lines 276-282 in each trader file):
  if price > ema50 and ema20 > ema50 and rsi > 50:
      trend = "bullish"
  elif price < ema50 and ema20 < ema50 and rsi < 50:
      trend = "bearish"
  else:
      trend = "neutral"

✓ ALL 4 traders use the CORRECT 3-condition standard:
  - BULLISH: price > EMA50 AND EMA20 > EMA50 AND RSI > 50
  - BEARISH: price < EMA50 AND EMA20 < EMA50 AND RSI < 50
  - NEUTRAL: everything else

No RSI-only logic detected.

================================================================================
CHECK 4 — BB WIDTH FORMAT:
================================================================================

From indicators.py format_indicators_for_llm() (lines 206-213):

  if bb_w < 0.3:    bw_note = ' (EXTREME COMPRESSION)'
  elif bb_w < 0.8:  bw_note = ' (consolidating)'
  elif bb_w > 1.5:  bw_note = ' (expanding — trend confirmation)'
  else:             bw_note = ''
  lines.append(f"  BB width: {bb_w:.2f}%{bw_note}")

✓ BB width is formatted as PERCENTAGE (e.g., "0.82%")
  - Uses bb_width from ta library (which outputs percentage)
  - Formatted with {bb_w:.2f}%

Strategy threshold comparisons:
  BTC: 0.5%    ✓ (format uses %, threshold uses %)
  ETH: 0.6%    ✓ (format uses %, threshold uses %)
  SOL: 0.7%    ✓ (format uses %, threshold uses %)
  LINK: 1.0%   ✓ (format uses %, threshold uses %)

All units are consistent (percentage format).

================================================================================
CHECK 5 — CANDLE DEPTH:
================================================================================

From market_data.py (lines 12-16):

  TIMEFRAMES = {
      "15m": {"limit": 250, "label": "15-minute"},
      "1h":  {"limit": 250, "label": "1-hour"},
      "4h":  {"limit": 250, "label": "4-hour"},
  }

✓ All timeframes fetch exactly 250 candles

From indicators.py (lines 26-29):

  df['ema_9']   = ta.trend.ema_indicator(close, window=9)
  df['ema_20']  = ta.trend.ema_indicator(close, window=20)
  df['ema_50']  = ta.trend.ema_indicator(close, window=50)
  df['ema_200'] = ta.trend.ema_indicator(close, window=200)

✓ EMA200 column name is 'ema_200'

From extract_signal_data() (lines 75-87):

  def safe(col, default=None):
      try:
          val = row.get(col)
          return round(float(val), 4) if pd.notna(val) else default
      except Exception:
          return default

✓ NaN/None handling is present via pd.notna() check
✓ All values go through safe() function which handles None/NaN

================================================================================
CHECK 6 — SCHEMA FIELDS:
================================================================================

From get_signals.py (lines 50-66), the OUTPUT SCHEMA includes:

{
  "direction": "LONG" | "SHORT" | "NONE",
  "deferred": true | false,                    <-- PRESENT ✓
  "confidence": 0-100 (int),
  "setup_confidence": 0-100 (int),             <-- PRESENT ✓
  "entry_price": float,
  "stop_loss": float,
  "take_profit": float,
  "rr_ratio": float,
  "expected_duration": "1-3 days" | "3-7 days" | "1-2 weeks" | "2-4 weeks",
  "leverage": 1-20 (int),
  "reasoning": "string",
  "key_reasons": ["string", ...],
  "risks": ["string", ...],
  "timeframe_alignment": { "15m": "bullish" | "bearish" | "neutral", ... }
}

✓ Both "deferred" and "setup_confidence" fields are present in schema

FIELD DEFINITIONS (lines 76-80):
- setup_confidence: "The quality of the underlying technical setup, INDEPENDENT 
  of pre-trade filters. Score this as if all pre-trade filters were passing..."

================================================================================
CHECK 7 — STRATEGY NOTES SIZE:
================================================================================

--- BTC ---
  Characters: 16,772
  ✗ OVER 12,000 characters! [ACTION REQUIRED]

--- ETH ---
  Characters: 15,249
  ✗ OVER 12,000 characters! [ACTION REQUIRED]

--- SOL ---
  Characters: 12,494
  ✗ OVER 12,000 characters! [ACTION REQUIRED]

--- LINK ---
  Characters: 16,524
  ✗ OVER 12,000 characters! [ACTION REQUIRED]

All 4 strategy notes files exceed the 12,000 character limit.

================================================================================
CHECK 8 — PARSE ERROR HISTORY:
================================================================================

Database file exists at: /home/agentneo/hermes-trader/trade_log.db

NOTE: Terminal commands blocked by security scan - could not query database.
Recommendation: Run the following query manually to check parse error rates:

  sqlite3 /home/agentneo/hermes-trader/trade_log.db \
  "SELECT symbol, COUNT(*) as total, SUM(CASE WHEN reasoning = 'Parse error' THEN 1 ELSE 0 END) as parse_errors FROM signals WHERE symbol IN ('BTC/USDT','ETH/USDT','SOL/USDT','LINK/USDT') AND timestamp >= datetime('now', '-30 days') GROUP BY symbol"

================================================================================
CHECK 9 — PRE-TRADE FILTER DATA:
================================================================================

From indicators.py extract_signal_data() function (lines 64-152):

Fields included in output:
  - bb_position: ✓ (line 141 - calculated for 1h data)
  - volume: ✓ (line 146)
  - atr: ✓ (line 143)

For non-BTC traders (ETH, SOL, LINK):
From sol_trader.py (lines 394-434):
  ✓ BTC correlation data IS included for SOL trader

From eth_trader.py and link_trader.py:
  ⚠ No BTC correlation data fetched (unlike sol_trader.py)

From indicators.py format_indicators_for_llm() function (lines 155-229):

Fields sent to LLM:
  - bb_position: ✓ (lines 197-203)
  - volume: ✓ (line 217 - via volume_surge)
  - atr: ✓ (line 216)

⚠ SUMMARY: BTC price data included only for SOL trader, not for ETH/LINK traders.
[ACTION REQUIRED] Consider adding BTC correlation data to ETH and LINK traders.

================================================================================
CHECK 10 — SELF-TUNING FRAMEWORK:
================================================================================

From strategy_notes files (lines 188+ for BTC, 169+ for others):

--- BTC ---
✓ Self-Tuning Framework section found (lines 188-264)
  Section length: 76 lines

--- ETH ---
✓ Self-Tuning Framework section found (lines 169-246)
  Section length: 77 lines

--- SOL ---
✓ Self-Tuning Framework section found (lines 132-209)
  Section length: 77 lines

--- LINK ---
✓ Self-Tuning Framework section found (lines 171-248)
  Section length: 77 lines

All 4 assets have the Self-Tuning Framework section present.

================================================================================
SUMMARY TABLE
================================================================================

Asset | Notes ✓/✗ | Symbol ✓/✗ | Trend ✓/✗ | BB fmt ✓/✗ | Candles ✓/✗ | Schema ✓/✗ | Notes Size  | Parse Errors | Filters ✓/✗ | STF ✓/✗
------|-----------|------------|-----------|------------|-------------|------------|-------------|--------------|-------------|-----------
BTC   | ⚠/✓     | ✓         | ✓        | ✓         | ✓          | ✓         | 16,772 (>12K) | ?          | ✓          | ✓
ETH   | ⚠/✓     | ✓         | ✓        | ✓         | ✓          | ✓         | 15,249 (>12K) | ?          | ✗          | ✓
SOL   | ⚠/✓     | ✓         | ✓        | ✓         | ✓          | ✓         | 12,494 (>12K) | ?          | ✓          | ✓
LINK  | ⚠/✓     | ✓         | ✓        | ✓         | ✓          | ✓         | 16,524 (>12K) | ?          | ✗          | ✓

Legend:
✓ = PASS
✗ = FAIL
⚠ = PARTIAL (first line doesn't contain asset name explicitly)
? = COULD NOT CHECK (database query blocked)

================================================================================
KEY FINDINGS & RECOMMENDATIONS
================================================================================

ISSUES FOUND:

1. STRATEGY NOTES SIZE (ALL 4 ASSETS - HIGH PRIORITY)
   - All 4 strategy notes files exceed 12,000 characters
   - BTC: 16,772 chars, ETH: 15,249 chars, SOL: 12,494 chars, LINK: 16,524 chars
   [ACTION REQUIRED] Consider summarizing or modularizing strategy notes

2. BTC CORRELATION DATA (ETH, LINK - MEDIUM PRIORITY)
   - sol_trader.py fetches BTC correlation data (lines 394-434)
   - eth_trader.py and link_trader.py do NOT fetch BTC data
   [ACTION REQUIRED] Add BTC correlation data fetching to ETH and LINK traders

3. FIRST LINE FORMAT (ALL 4 ASSETS - LOW PRIORITY)
   - All strategy notes start with "# Trading Agent Strategy Notes"
   - Should ideally be "# {ASSET} Trading Agent Strategy Notes" for easier parsing
   [OPTIONAL] Update first line format for clarity

PASSED CHECKS:

✓ SYMBOL CONSISTENCY - All 4 traders have correct SYMBOL and STRATEGY_NOTES_PATH
✓ TREND CLASSIFICATION - All use proper 3-condition standard (price, EMA20, EMA50, RSI)
✓ BB WIDTH FORMAT - All use percentage format consistent with thresholds
✓ CANDLE DEPTH - All fetch 250 candles per timeframe
✓ EMA200 HANDLING - Column name 'ema_200' with proper NaN handling
✓ SCHEMA FIELDS - Both 'deferred' and 'setup_confidence' present
✓ PRE-TRADE FILTER DATA - bb_position, volume, atr included
✓ SELF-TUNING FRAMEWORK - Present in all 4 strategy notes files

================================================================================
DIAGNOSTIC COMPLETE
================================================================================
