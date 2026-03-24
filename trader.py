"""
trader.py — Main trading agent orchestration script.
Called by Hermes cron every 5 minutes.

Flow:
  1. Fetch candles + calculate indicators (all timeframes)
  2. Check open positions for TP/SL hits
  3. Send indicator data to LLM for analysis
  4. If signal meets threshold → log → open paper position → Telegram alert
  5. If 5 trades closed since last review → trigger strategy review
"""

import os
import sys
import json
import requests
from pathlib import Path
from datetime import datetime, timezone

# Add trader dir to path
TRADER_DIR = Path(__file__).parent
sys.path.insert(0, str(TRADER_DIR))

from market_data import fetch_all_timeframes, get_current_price
from indicators import calculate_indicators, extract_signal_data, format_indicators_for_llm
from trade_log import (
    init_db, log_signal, open_position, check_and_close_positions,
    get_open_positions, get_closed_trades, get_stats,
    count_closed_since_last_review, log_strategy_review,
)

# --- Config ---
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '')
ANALYSIS_MODEL     = 'qwen/qwen3.5-27b'    # upgraded from 3B, cheaper than 70B models
REVIEW_MODEL       = 'minimax/minimax-m2.1'     # better reasoning for strategy review
SYMBOL             = 'BTC/USDT'
MIN_RR             = 2.0
MIN_CONFIDENCE     = 55
MAX_OPEN_POSITIONS = 2
REVIEW_EVERY_N     = 3   # trigger strategy review after this many closed trades
POSITION_TIMEOUT_HOURS = 48  # auto-close positions older than this

STRATEGY_NOTES_PATH = TRADER_DIR / 'strategy_notes.md'
TELEGRAM_NOTIFY_PATH = TRADER_DIR / '.telegram_notify'  # Hermes reads this for outbound msgs


def load_strategy_notes() -> str:
    if STRATEGY_NOTES_PATH.exists():
        return STRATEGY_NOTES_PATH.read_text()
    return "No strategy notes yet. Use common technical analysis principles."


def save_strategy_notes(content: str):
    STRATEGY_NOTES_PATH.write_text(content)


def llm_call(model: str, system: str, user: str, max_tokens: int = 1500) -> str:
    """Call OpenRouter inference with retry logic."""
    import time
    headers = {
        'Authorization': f'Bearer {OPENROUTER_API_KEY}',
        'Content-Type': 'application/json',
        'HTTP-Referer': 'https://greynode.co.uk',
        'X-Title': 'Hermes Trading Agent',
    }
    payload = {
        'model': model,
        'max_tokens': max_tokens,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user',   'content': user},
        ],
    }
    max_retries = 3
    delay_seconds = 2
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
            if content and content.strip():
                return content.strip()
            print(f"[trader] LLM empty response on attempt {attempt}/{max_retries}")
        except requests.exceptions.Timeout:
            print(f"[trader] LLM timeout on attempt {attempt}/{max_retries}")
        except requests.exceptions.RequestException as e:
            print(f"[trader] LLM request error on attempt {attempt}/{max_retries}: {e}")
        except Exception as e:
            print(f"[trader] LLM unexpected error on attempt {attempt}/{max_retries}: {e}")
        if attempt < max_retries:
            print(f"[trader] Retrying in {delay_seconds}s...")
            time.sleep(delay_seconds)
    raise RuntimeError(f"LLM call failed after {max_retries} attempts")


def analyse_market(indicator_text: str, strategy_notes: str, open_count: int) -> dict:
    """
    Ask the LLM to analyse current market conditions and generate a signal.
    Returns parsed signal dict.
    """
    system = f"""You are an expert crypto swing trader analysing BTC/USDT.
You have access to multi-timeframe technical indicator data.
Your job is to identify high-probability swing trade setups.

STRATEGY NOTES (your evolved strategy — follow these):
{strategy_notes}

RULES:
- Only recommend trades with R:R >= {MIN_RR}
- Only recommend if confidence >= {MIN_CONFIDENCE}% (lowered from 65% to improve trade frequency)
- Currently {open_count}/{MAX_OPEN_POSITIONS} positions open — {'DO NOT open new trades, max reached.' if open_count >= MAX_OPEN_POSITIONS else 'can open new position.'}
- Choose leverage 1-20x based on setup quality:
  - 1x: uncertain/low confidence setups
  - 2-5x: moderate confidence, aligned timeframes
  - 5-10x: high confidence, strong trend alignment, clear levels
  - 10-20x: exceptional setups only — all timeframes aligned, high volume, clear breakout
- Higher leverage = higher risk. Be conservative unless the setup is exceptional.
- Be conservative — no trade is better than a bad trade
- You MUST respond in valid JSON only, no markdown, no preamble

RESPONSE FORMAT:
{{
  "direction": "LONG" | "SHORT" | "NONE",
  "confidence": 0-100,
  "entry_price": float or null,
  "stop_loss": float or null,
  "take_profit": float or null,
  "rr_ratio": float or null,
  "leverage": 1-20,
  "expected_duration": "e.g. 12-36 hours",
  "timeframe_alignment": {{
    "15m": "bullish" | "bearish" | "neutral" | "mixed",
    "1h":  "bullish" | "bearish" | "neutral" | "mixed",
    "4h":  "bullish" | "bearish" | "neutral" | "mixed"
  }},
  "key_reasons": ["reason 1", "reason 2", "reason 3"],
  "risks": ["risk 1", "risk 2"],
  "reasoning": "Full reasoning paragraph (2-4 sentences)"
}}"""

    user = indicator_text

    raw = llm_call(ANALYSIS_MODEL, system, user, max_tokens=800)

    # Strip any accidental markdown fences
    raw = raw.strip()
    if raw.startswith('```'):
        raw = raw.split('\n', 1)[1].rsplit('```', 1)[0].strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"[trader] JSON parse failed:\n{raw}")
        return {'direction': 'NONE', 'confidence': 0, 'reasoning': raw}


def run_strategy_review():
    """
    Pull last N closed trades, ask MiniMax M2.1 to review performance,
    update strategy_notes.md, and return a summary string for Telegram.
    """
    trades = get_closed_trades(limit=20)
    stats  = get_stats(last_n=20)

    if not trades:
        return None

    trades_text = json.dumps([{
        'direction':   t['direction'],
        'entry':       t['entry_price'],
        'exit':        t['exit_price'],
        'exit_reason': t['exit_reason'],
        'pnl_r':       t['pnl_r'],
        'pnl_pct':     t['pnl_pct'],
        'confidence':  t.get('confidence'),
        'reasoning':   t.get('reasoning', '')[:300],  # truncate
        'opened_at':   t['opened_at'],
        'closed_at':   t['closed_at'],
    } for t in trades], indent=2)

    current_notes = load_strategy_notes()

    system = """You are a quantitative trading strategist reviewing a paper trading agent's performance.
Your job is to:
1. Identify patterns in what worked and what didn't
2. Update the strategy document to improve future performance
3. Be specific — mention which indicators/setups are working or failing

Respond in this exact JSON format:
{
  "review_summary": "2-3 sentence summary of performance patterns",
  "what_worked": ["specific observation 1", "specific observation 2"],
  "what_failed": ["specific failure 1", "specific failure 2"],
  "recommended_changes": ["change 1", "change 2"],
  "updated_strategy_notes": "FULL updated strategy_notes.md content (keep the same format, update the relevant sections)"
}
Respond with valid JSON only."""

    user = f"""RECENT TRADE DATA:
{trades_text}

PERFORMANCE STATS:
{json.dumps(stats, indent=2)}

CURRENT STRATEGY NOTES:
{current_notes}

Review performance and produce updated strategy notes."""

    raw = llm_call(REVIEW_MODEL, system, user, max_tokens=2500)

    raw = raw.strip()
    if raw.startswith('```'):
        raw = raw.split('\n', 1)[1].rsplit('```', 1)[0].strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        print(f"[trader] Strategy review JSON parse failed:\n{raw}")
        return None

    # Save updated strategy notes
    if 'updated_strategy_notes' in result:
        save_strategy_notes(result['updated_strategy_notes'])

    # Log the review
    log_strategy_review(
        trades_reviewed=len(trades),
        win_rate=stats.get('win_rate', 0),
        avg_rr=stats.get('avg_r', 0),
        summary=result.get('review_summary', ''),
        changes_made='\n'.join(result.get('recommended_changes', [])),
    )

    return result


def format_telegram_signal(signal: dict, symbol: str, result: dict) -> str:
    """Format a trade signal for Telegram delivery."""
    direction = signal.get('direction', 'NONE')
    emoji = '🟢' if direction == 'LONG' else '🔴'

    tf = signal.get('timeframe_alignment', {})

    def tf_emoji(val):
        if val == 'bullish': return '✅'
        if val == 'bearish': return '❌'
        return '⚠️'

    reasons = signal.get('key_reasons', [])
    reasons_text = '\n'.join(f'• {r}' for r in reasons[:4])

    risks = signal.get('risks', [])
    risks_text = ' | '.join(risks[:2]) if risks else 'N/A'

    entry  = signal.get('entry_price')
    sl     = signal.get('stop_loss')
    tp     = signal.get('take_profit')
    rr     = signal.get('rr_ratio')
    conf   = signal.get('confidence')
    dur    = signal.get('expected_duration', 'N/A')
    leverage = signal.get('leverage', result.get('leverage', 1))

    sl_pct = abs(entry - sl) / entry * 100 if entry and sl else 0
    tp_pct = abs(tp - entry) / entry * 100 if entry and tp else 0

    return f"""{emoji} *{symbol} — {direction} SETUP*
━━━━━━━━━━━━━━━━━━━━━
Entry:       ${entry:,.2f}
Stop Loss:   ${sl:,.2f}  (-{sl_pct:.1f}%)
Take Profit: ${tp:,.2f}  (+{tp_pct:.1f}%)
Risk/Reward: {rr:.1f}R

Leverage:    {leverage}x | Size: ${result['position_size']:,.2f}
Margin:      ${result['margin_used']:,.2f} | Risk: ${result['risk_amount']:,.2f}

Timeframes: 15m {tf_emoji(tf.get('15m'))}  1h {tf_emoji(tf.get('1h'))}  4h {tf_emoji(tf.get('4h'))}
Confidence: {conf}%
Duration:   {dur}

📝 *Reasoning:*
{signal.get('reasoning', 'N/A')}

📊 *Key factors:*
{reasons_text}

⚠️ *Risks:* {risks_text}

🧪 Paper trade #{result['id']} | Strategy v{_get_strategy_version()}"""


def format_telegram_close(pos: dict) -> str:
    """Format a position close notification for Telegram."""
    emoji = '✅' if pos['pnl_r'] > 0 else '❌'
    reason_text = {
        'TP_HIT': '🎯 Take profit hit',
        'SL_HIT': '🛑 Stop loss hit',
        'TIMEOUT': '⏱ Time exit',
        'MANUAL': '✋ Manual close',
    }.get(pos.get('exit_reason', ''), pos.get('exit_reason', ''))

    return f"""{emoji} *{pos['symbol']} {pos['direction']} CLOSED*
{reason_text}
Exit: ${pos['exit_price']:,.2f}
P&L: {'+' if pos['pnl_pct'] > 0 else ''}{pos['pnl_pct']:.2f}% ({'+' if pos['pnl_r'] > 0 else ''}{pos['pnl_r']:.2f}R)"""


def format_telegram_review(review: dict, stats: dict) -> str:
    """Format strategy review for Telegram."""
    changes = '\n'.join(f'• {c}' for c in review.get('recommended_changes', [])[:4])
    worked  = '\n'.join(f'• {w}' for w in review.get('what_worked', [])[:3])
    failed  = '\n'.join(f'• {f}' for f in review.get('what_failed', [])[:3])

    return f"""🔬 *STRATEGY REVIEW*
━━━━━━━━━━━━━━━━━━━━━
Trades reviewed: {stats.get('total', 0)}
Win rate: {stats.get('win_rate', 0):.1f}%
Avg R: {stats.get('avg_r', 0):.2f}R
Total R: {stats.get('total_r', 0):.2f}R

✅ *Working:*
{worked or 'Not enough data'}

❌ *Failing:*
{failed or 'Not enough data'}

🔧 *Changes made:*
{changes or 'No changes this review'}

📋 {review.get('review_summary', '')}"""


def format_telegram_report(
    symbol: str,
    current_price: float,
    tf_signals: dict,
    signal: dict,
    open_positions: list,
    stats: dict,
) -> str:
    """Format a full scan report for Telegram — sent every 5 minutes."""

    def trend_emoji(bias):
        if bias == 'bullish': return '🟢'
        if bias == 'bearish': return '🔴'
        return '🟡'

    def fmt(val, decimals=2):
        if val is None: return 'N/A'
        return f"{val:.{decimals}f}"

    # Market section per timeframe
    tf_lines = []
    for tf in ['15m', '1h', '4h']:
        d = tf_signals.get(tf, {})
        bias = d.get('trend_bias', 'N/A')
        emoji = trend_emoji(bias)
        rsi = fmt(d.get('rsi'), 1)
        macd = fmt(d.get('macd'), 2)
        macd_sig = fmt(d.get('macd_signal'), 2)
        ema9 = fmt(d.get('ema_9'), 0)
        ema20 = fmt(d.get('ema_20'), 0)
        ema50 = fmt(d.get('ema_50'), 0)
        bb = fmt(d.get('bb_position'), 0) if d.get('bb_position') is not None else 'N/A'
        tf_lines.append(
            f"{tf:>3} {emoji} {bias.upper():8s} | RSI {rsi:>5} | MACD {macd}/{macd_sig}\n"
            f"     EMA 9/20/50: {ema9}/{ema20}/{ema50} | BB: {bb}%"
        )
    market_text = '\n'.join(tf_lines)

    # Signal assessment
    direction = signal.get('direction', 'NONE')
    confidence = signal.get('confidence', 0)
    rr = signal.get('rr_ratio') or 0
    reasoning = signal.get('reasoning', 'N/A')
    if direction == 'NONE':
        sig_emoji = '⏸'
        sig_action = 'NO TRADE'
    elif confidence >= MIN_CONFIDENCE and rr >= MIN_RR:
        sig_emoji = '🟢' if direction == 'LONG' else '🔴'
        sig_action = f'{direction} OPENED'
    else:
        sig_emoji = '⚠️'
        sig_action = f'{direction} REJECTED'

    # Positions section
    if open_positions:
        pos_lines = []
        for p in open_positions:
            pos_lines.append(
                f"  #{p['id']} {p['direction']} @ ${p['entry_price']:,.2f} "
                f"SL ${p['stop_loss']:,.2f} TP ${p['take_profit']:,.2f}"
            )
        pos_text = '\n'.join(pos_lines)
    else:
        pos_text = '  None'

    # Stats
    total = stats.get('total', 0)
    if total > 0:
        stats_text = (
            f"Trades: {total} | Win rate: {stats.get('win_rate', 0):.0f}% | "
            f"Avg R: {stats.get('avg_r', 0):.2f} | Total R: {stats.get('total_r', 0):.2f}"
        )
    else:
        stats_text = 'No closed trades yet'

    return f"""📊 BTC/USDT SCAN REPORT
━━━━━━━━━━━━━━━━━━━━━
💰 Price: ${current_price:,.2f}

📈 MARKET:
{market_text}

{sig_emoji} SIGNAL: {sig_action}
Confidence: {confidence}% | R:R: {rr:.1f}
{reasoning[:300]}

📋 OPEN POSITIONS:
{pos_text}

📊 RECORD:
{stats_text}

🕐 {datetime.now(timezone.utc).strftime('%H:%M UTC')} | v{_get_strategy_version()}"""


def _get_strategy_version() -> str:
    """Extract version number from strategy_notes.md."""
    try:
        notes = load_strategy_notes()
        for line in notes.split('\n'):
            if 'Version:' in line or 'version:' in line.lower():
                return line.split(':')[-1].strip().split(' ')[0]
    except Exception:
        pass
    return '?'


def notify_telegram(message: str):
    """Send message directly via Telegram Bot API."""
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
    if not bot_token or not chat_id:
        print(f"[trader] WARN: Telegram credentials not set, skipping notification")
        return
    try:
        resp = requests.post(
            f'https://api.telegram.org/bot{bot_token}/sendMessage',
            json={'chat_id': chat_id, 'text': message, 'parse_mode': 'Markdown'},
            timeout=10,
        )
        if resp.status_code == 200:
            print(f"[trader] Telegram notification sent")
        else:
            print(f"[trader] Telegram send failed: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        print(f"[trader] Telegram send error: {e}")


def main():
    print(f"[trader] Scan started at {datetime.now(timezone.utc).isoformat()}")
    init_db()

    if not OPENROUTER_API_KEY:
        print("[trader] ERROR: OPENROUTER_API_KEY not set")
        sys.exit(1)

    # Buffer all Telegram messages to send ONE consolidated message per scan
    telegram_messages = []

    # 1. Get current price + check open positions
    current_price = get_current_price(SYMBOL)
    if current_price is None:
        print(f"[trader] Could not fetch price for {SYMBOL}, aborting")
        sys.exit(1)

    print(f"[trader] {SYMBOL} = ${current_price:,.2f}")

    # 2. Check and auto-close positions that hit TP/SL or timeout
    closed_positions = check_and_close_positions({SYMBOL: current_price}, POSITION_TIMEOUT_HOURS)
    for pos in closed_positions:
        msg = format_telegram_close(pos)
        telegram_messages.append(msg)
        print(f"[trader] Closed position {pos['id']}: {pos['exit_reason']} {pos['pnl_r']:.2f}R")

    # 3. Check if strategy review is due
    closed_since_review = count_closed_since_last_review()
    if closed_since_review >= REVIEW_EVERY_N:
        print(f"[trader] {closed_since_review} trades since last review — running strategy review")
        review = run_strategy_review()
        if review:
            stats = get_stats(last_n=20)
            msg = format_telegram_review(review, stats)
            telegram_messages.append(msg)
            print("[trader] Strategy review complete, notes updated")

    # 4. Fetch market data
    print(f"[trader] Fetching candles for {SYMBOL}...")
    candles = fetch_all_timeframes(SYMBOL)

    # 5. Calculate indicators per timeframe
    tf_signals = {}
    for tf, df in candles.items():
        if df is not None and len(df) >= 50:
            enriched = calculate_indicators(df)
            tf_signals[tf] = extract_signal_data(enriched)
        else:
            tf_signals[tf] = {}
            print(f"[trader] Insufficient data for {tf}")

    # 6. Format indicator summary for LLM
    indicator_text = format_indicators_for_llm(tf_signals, SYMBOL)
    indicator_text += f"\nCurrent price: ${current_price:,.2f}"

    # 7. Check how many positions are open
    open_positions = get_open_positions(SYMBOL)
    open_count = len(open_positions)
    print(f"[trader] Open positions: {open_count}/{MAX_OPEN_POSITIONS}")

    # 8. LLM market analysis
    print(f"[trader] Calling {ANALYSIS_MODEL} for analysis...")
    strategy_notes = load_strategy_notes()
    signal = analyse_market(indicator_text, strategy_notes, open_count)

    direction  = signal.get('direction', 'NONE')
    confidence = signal.get('confidence', 0)
    rr_ratio   = signal.get('rr_ratio') or 0

    print(f"[trader] Signal: {direction} | Confidence: {confidence}% | R:R {rr_ratio:.1f}")

    # 9. Log the signal regardless
    signal_id = log_signal(
        symbol=SYMBOL,
        direction=direction,
        confidence=confidence,
        entry_price=signal.get('entry_price'),
        stop_loss=signal.get('stop_loss'),
        take_profit=signal.get('take_profit'),
        rr_ratio=rr_ratio if rr_ratio else None,
        reasoning=signal.get('reasoning', ''),
        tf_data=tf_signals,
        acted_on=False,
    )

    # 10. Open paper position if signal qualifies
    if (
        direction in ('LONG', 'SHORT')
        and confidence >= MIN_CONFIDENCE
        and rr_ratio >= MIN_RR
        and open_count < MAX_OPEN_POSITIONS
        and signal.get('entry_price')
        and signal.get('stop_loss')
        and signal.get('take_profit')
    ):
        total_positions = open_count + 1  # position number for display
        leverage = signal.get('leverage') or 1
        leverage = max(1, min(int(leverage), 20))
        
        result = open_position(
            signal_id=signal_id,
            symbol=SYMBOL,
            direction=direction,
            entry_price=signal['entry_price'],
            stop_loss=signal['stop_loss'],
            take_profit=signal['take_profit'],
            leverage=leverage,
            strategy_notes=strategy_notes[:500],
        )
        
        if result.get('opened'):
            pos_id = result['id']
            print(f"[trader] Opened position #{pos_id} ({leverage}x leverage, size: ${result['position_size']:,.2f}, margin: ${result['margin_used']:,.2f}, risk: ${result['risk_amount']:,.2f})")
            msg = format_telegram_signal(signal, SYMBOL, result)
            telegram_messages.append(msg)
        else:
            print(f"[trader] Could not open position: {result.get('reason')}")
    else:
        if direction == 'NONE' or confidence < MIN_CONFIDENCE:
            print(f"[trader] No qualifying signal this scan")
        elif rr_ratio < MIN_RR:
            print(f"[trader] Signal R:R {rr_ratio:.1f} below minimum {MIN_RR} — skipped")
        elif open_count >= MAX_OPEN_POSITIONS:
            print(f"[trader] Max positions open — skipped")

    # Send event notifications (position closes, reviews, new trades) first
    if telegram_messages:
        consolidated = "\n\n────────────────────────\n\n".join(telegram_messages)
        notify_telegram(consolidated)
        print(f"[trader] Sent {len(telegram_messages)} event notification(s)")

    # Always send full scan report
    stats = get_stats(last_n=20)
    report = format_telegram_report(
        symbol=SYMBOL,
        current_price=current_price,
        tf_signals=tf_signals,
        signal=signal,
        open_positions=get_open_positions(SYMBOL),
        stats=stats,
    )
    notify_telegram(report)

    print(f"[trader] Scan complete")


if __name__ == '__main__':
    main()
