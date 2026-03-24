"""
get_signals.py - Standalone LLM signal analysis module.

Encapsulates the market analysis logic so it can be reused
and tested independently from the main trader loop.
"""

import json
import requests
import os
from pathlib import Path

# Add trader dir to path
TRADER_DIR = Path(__file__).parent
if str(TRADER_DIR) not in __import__('sys').path:
    __import__('sys').path.insert(0, str(TRADER_DIR))

from config import OPENROUTER_API_KEY, ANALYSIS_MODEL, llm_call


def get_signals(
    indicator_text: str,
    strategy_notes: str,
    open_count: int,
    model: str = None,
    symbol: str = "BTC/USDT",
) -> dict:
    """
    Ask the LLM to analyse current market conditions and generate a signal.
    
    Returns a parsed signal dict with fields:
      - direction: 'LONG', 'SHORT', or 'NONE'
      - confidence: 0-100%
      - entry_price, stop_loss, take_profit
      - rr_ratio, expected_duration, leverage
      - reasoning, key_reasons, risks
      - timeframe_alignment (per-timeframe signals)
    
    All numeric fields are floats or None.
    """
    model = model or ANALYSIS_MODEL
    
    system = f"""You are an expert crypto swing trader analysing {symbol}.
You have access to multi-timeframe technical indicator data.
Your job is to identify high-probability swing trade setups.

STRATEGY NOTES (your evolved strategy - follow these):
{strategy_notes}

OUTPUT SCHEMA (return JSON with these exact keys):
{{
  "direction": "LONG" | "SHORT" | "NONE",
  "deferred": true | false,
  "confidence": 0-100 (int),
  "setup_confidence": 0-100 (int),
  "entry_price": float,
  "stop_loss": float,
  "take_profit": float,
  "rr_ratio": float,
  "expected_duration": "1-3 days" | "3-7 days" | "1-2 weeks" | "2-4 weeks",
  "leverage": 1-20 (int),
  "reasoning": "string",
  "key_reasons": ["string", ...],
  "risks": ["string", ...],
  "timeframe_alignment": {{ "15m": "bullish" | "bearish" | "neutral", ... }}
}}

FIELD DEFINITIONS:
- direction: Your execution decision. LONG/SHORT only if ready to execute NOW. NONE otherwise.
- deferred: Set true if a pre-trade filter (BTC health check, liquidity check, macro event, etc.)
  is blocking execution but the underlying setup is otherwise valid. Set false if there is simply
  no setup present.
- confidence: Execution confidence — how confident you are to open THIS trade RIGHT NOW.
  Set to 0 if direction=NONE and deferred=false (no setup). Set to 0 if direction=NONE and
  deferred=true (blocked by filter, not ready to execute).
- setup_confidence: The quality of the underlying technical setup, INDEPENDENT of pre-trade
  filters. Score this as if all pre-trade filters were passing. If there is no setup at all,
  set to 0. If a valid setup exists but is blocked by a filter, score the setup honestly here
  (e.g. 50% for a ranging-market setup at BB extreme, 65% for a strong trend setup blocked
  by a BTC health defer). This field preserves setup quality information across defer cycles.

RULES:
1. Only set direction=LONG/SHORT if ALL pre-trade filters pass AND confidence >= 55%
2. RR must be >= 2.0, otherwise direction=NONE
3. If a pre-trade filter triggers a defer, set direction=NONE, deferred=true, confidence=0,
   and populate setup_confidence with honest setup quality score
4. If there is no valid setup (not deferred, just no setup), set direction=NONE, deferred=false,
   confidence=0, setup_confidence=0
5. Entry price should be near current market price
6. Stop loss must be beyond recent swing/high-volatility level
7. Take profit should be at least 2x risk, ideally at next major liquidity zone
8. Leverage 3-5x for swing trades; up to 10x if multiple timeframes align
"""

    user = f"""RECENT MARKET DATA:
{indicator_text}

CURRENT CONDITIONS:
- Open positions: {open_count}
- Symbol: {symbol}

Analyse the data and generate a signal according to your strategy notes."""
    
    # Call LLM
    raw = llm_call(model, system, user, max_tokens=1500)
    
    # Clean response (strip markdown code blocks if present)
    raw = raw.strip()
    if raw.startswith('```'):
        raw = raw.split('\n', 1)[1].rsplit('```', 1)[0].strip()
    
    # Parse JSON
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        print(f"[get_signals] LLM JSON parse failed:\n{raw}")
        return {'direction': 'NONE', 'confidence': 0, 'reasoning': 'Parse error'}
    
    return result
