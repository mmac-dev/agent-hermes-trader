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
from get_signals import get_signals as analyse_market
from trade_log import (
    init_db, log_signal, open_position, check_and_close_positions,
    get_open_positions, get_closed_trades, get_stats,
    count_closed_since_last_review, log_strategy_review,
    get_portfolio, get_available_margin,
)

# Import config from shared module
from config import (
    OPENROUTER_API_KEY, ANALYSIS_MODEL, REVIEW_MODEL,
    SYMBOL, MIN_RR, MIN_CONFIDENCE, MAX_OPEN_POSITIONS,
    REVIEW_EVERY_N, POSITION_TIMEOUT_HOURS,
    STRATEGY_NOTES_PATH, TELEGRAM_NOTIFY_PATH,
    llm_call,
)

# Override SYMBOL and strategy notes path for this specific asset
SYMBOL = 'ETH/USDT'
STRATEGY_NOTES_PATH = TRADER_DIR / 'strategy_notes_ETH_USDT.md'

# Load strategy notes once
def load_strategy_notes() -> str:
    content = []
    if STRATEGY_NOTES_PATH.exists():
        content.append(STRATEGY_NOTES_PATH.read_text())
    else:
        content.append("No strategy notes yet. Use common technical analysis principles.")
    
    framework_path = TRADER_DIR / 'self_tuning_framework.md'
    if framework_path.exists():
        content.append(framework_path.read_text())
    else:
        content.append("No self-tuning framework available.")
    
    return '\n\n---\n\n'.join(content)


def save_strategy_notes(content: str):
    STRATEGY_NOTES_PATH.write_text(content)


def notify_telegram(text: str):
    """Send notification via this asset's dedicated Telegram bot."""
    from config import TELEGRAM_BOTS
    import requests

    bot = TELEGRAM_BOTS.get(SYMBOL, {})
    bot_token = bot.get('token', '')
    chat_id = bot.get('chat_id', '')

    if bot_token and chat_id:
        try:
            resp = requests.post(
                f'https://api.telegram.org/bot{bot_token}/sendMessage',
                json={'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'},
                timeout=30,
            )
            if resp.status_code == 200:
                print(f"[trader] Sent Telegram message via {SYMBOL} bot")
                return
            else:
                print(f"[trader] Telegram error {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            print(f"[trader] Telegram API call failed: {e}")

    # Fallback to file
    TELEGRAM_NOTIFY_PATH.write_text(text)
    print(f"[trader] Wrote to {TELEGRAM_NOTIFY_PATH}")


def _get_strategy_version() -> str:
    """Simple version counter based on strategy notes hash."""
    notes = load_strategy_notes()
    return f"v{abs(hash(notes)) % 1000:03d}"


def run_strategy_review() -> dict:
    """Run strategy review after N closed trades."""
    trades = get_closed_trades(limit=20, symbol=SYMBOL)
    if not trades:
        return None
    
    stats = get_stats(last_n=20, symbol=SYMBOL)
    current_notes = load_strategy_notes()
    
    trades_text = "\n".join([
        f"Trade #{t['id']} {t['direction']} @ ${t['entry_price']:,.2f} -> ${t['exit_price']:,.2f} "
        f"({t['pnl_r']:.2f}R) - {t['exit_reason']}"
        for t in trades[-5:]
    ])
    
    system = """You are an expert crypto swing trader reviewing your recent performance.
Analyze what worked, what failed, and suggest concrete improvements to your strategy.

Return valid JSON with this schema:
{
  "review_summary": "string",
  "what_worked": ["string", ...],
  "what_failed": ["string", ...],
  "recommended_changes": ["string", ...],
  "updated_strategy_notes": "FULL updated strategy_notes.md content"
}
Respond with valid JSON only."""
    
    user = f"""RECENT TRADE DATA:
{trades_text}

PERFORMANCE STATS:
{json.dumps(stats, indent=2)}

CURRENT STRATEGY NOTES:
{current_notes}

Review performance and produce updated strategy notes."""
    
    raw = llm_call(REVIEW_MODEL, system, user, max_tokens=3000)
    
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
        symbol=SYMBOL,
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
    portfolio: dict = None,
) -> str:
    """Format a full scan report for Telegram — sent every 5 minutes."""
    
    def tf_summary(tf_data):
        if not tf_data:
            return "No data"
        signals = []
        for tf, indicators in tf_data.items():
            rsi = indicators.get('rsi', 0)
            price = indicators.get('close', 0)
            ema50 = indicators.get('ema_50', 0)
            ema20 = indicators.get('ema_20', 0)
            if price and ema50 and ema20:
                if price > ema50 and ema20 > ema50 and rsi > 50:
                    trend = "bullish"
                elif price < ema50 and ema20 < ema50 and rsi < 50:
                    trend = "bearish"
                else:
                    trend = "neutral"
            else:
                trend = "neutral"
            signals.append(f"{tf}: {trend}")
        return ', '.join(signals)
    
    direction    = signal.get('direction', 'NONE')
    confidence   = signal.get('confidence', 0)
    deferred     = signal.get('deferred', False)
    setup_conf   = signal.get('setup_confidence', 0)
    entry        = signal.get('entry_price', 'N/A')
    reasoning    = signal.get('reasoning', '') or "N/A"
    if direction != 'NONE':
        signal_status = f"{direction} @ {confidence}%"
    elif deferred and setup_conf > 0:
        signal_status = f"NONE (DEFERRED) — setup quality: {setup_conf}%"
    else:
        signal_status = f"NONE @ {confidence}%"
    no_trade_line = (
        f"⏳ Deferred — setup quality {setup_conf}% (pre-trade filter blocking)"
        if deferred and setup_conf > 0
        else "No trade this scan"
    )
    
    open_text = "None"
    if open_positions:
        open_lines = [f"#{p['id']} {p['direction']} ${p['entry_price']:,.2f}" for p in open_positions[:3]]
        open_text = '\n'.join(open_lines)
        if len(open_positions) > 3:
            open_text += f"\n+{len(open_positions)-3} more"
    
    portfolio_text = ""
    if portfolio:
        balance = portfolio.get('balance', 0)
        total_pnl = portfolio.get('total_pnl', 0)
        portfolio_text = f"""
💰 *Portfolio:*
Balance: ${balance:,.2f}
Total P&L: ${total_pnl:+,.2f}
Trades: {portfolio.get('trades_taken', 0)}"""

    return f"""📊 *{symbol} SCAN REPORT*
━━━━━━━━━━━━━━━━━━━━━
Current Price: ${current_price:,.2f}

🤖 *LLM Analysis:*
Signal: {signal_status}
{f"Entry Target: ${entry:,.2f}" if direction != 'NONE' else no_trade_line}
Reasoning: {reasoning}

📈 *Multi-Timeframe:*
{tf_summary(tf_signals)}

📦 *Open Positions:*
{open_text}{portfolio_text}

📉 *Recent Stats (last 20):*
Total: {stats.get('total', 0)} | Win Rate: {stats.get('win_rate', 0):.1f}%
Avg R: {stats.get('avg_r', 0):.2f}R | Best: {stats.get('best_r', 0):.2f}R | Worst: {stats.get('worst_r', 0):.2f}R
Max DD: {stats.get('max_drawdown_r', 0):.2f}R | Duration: {stats.get('avg_duration', 0):.1f}h avg

Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"""


def main():
    """Main trading loop — runs every 5 minutes via cron."""
    # Ensure DB is initialized
    init_db()
    
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
    closed_since_review = count_closed_since_last_review(symbol=SYMBOL)
    if closed_since_review >= REVIEW_EVERY_N:
        print(f"[trader] {closed_since_review} trades since last review — running strategy review")
        review = run_strategy_review()
        if review:
            stats = get_stats(last_n=20, symbol=SYMBOL)
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
    
    # 6. Fetch BTC 4h data for correlation check
    try:
        from market_data import fetch_candles
        
        btc_df = fetch_candles('BTC/USDT', '4h', limit=250)
        btc_current = get_current_price('BTC/USDT')
        btc_rsi = btc_ema = btc_macd = btc_bb = None
        
        if btc_df is not None and len(btc_df) >= 50:
            btc_enriched = calculate_indicators(btc_df)
            btc_rsi = btc_enriched.iloc[-1].get('rsi')
            btc_ema9 = btc_enriched.iloc[-1].get('ema_9')
            btc_ema50 = btc_enriched.iloc[-1].get('ema_50')
            btc_macd = btc_enriched.iloc[-1].get('macd')
            btc_macd_signal = btc_enriched.iloc[-1].get('macd_signal')
            btc_bb_position = btc_enriched.iloc[-1].get('bb_position') if 'bb_position' in btc_enriched.columns else None
    except Exception as e:
        print(f"[trader] BTC data fetch failed: {e}")
        btc_current = btc_rsi = btc_ema = btc_macd = btc_bb = None
    
    # 7. Format indicator summary for LLM
    indicator_text = format_indicators_for_llm(tf_signals, SYMBOL)
    indicator_text += f"\nCurrent price: ${current_price:,.2f}"
    
    # Add BTC correlation data
    if btc_current:
        indicator_text += f"\n\n=== BTC/USDT 4h CORRELATION DATA ===\n"
        indicator_text += f"Current: ${btc_current:,.2f}\n"
        if btc_rsi:
            indicator_text += f"RSI(14): {btc_rsi:.1f}"
            if btc_rsi > 75: indicator_text += " (OVERBOUGHT)"
            elif btc_rsi < 25: indicator_text += " (OVERSOLD)"
            indicator_text += "\n"
        if btc_ema9 and btc_ema50:
            indicator_text += f"EMA: {btc_ema9:.0f} / {btc_ema50:.0f} ({'BULLISH' if btc_ema9 > btc_ema50 else 'BEARISH'})\n"
        if btc_macd is not None and btc_macd_signal is not None:
            indicator_text += f"MACD: {btc_macd:.2f} / Signal: {btc_macd_signal:.2f} ({'BULLISH' if btc_macd > btc_macd_signal else 'BEARISH'})\n"
        indicator_text += "Major S/R levels: $60k, $65k, $70k, $75k\n"
        btc_near_level = any(abs(btc_current - lvl) / lvl < 0.01 for lvl in [60000, 65000, 70000, 75000])
        indicator_text += f"BTC within 1% of major level: {'YES' if btc_near_level else 'NO'}\n"
    
    # 8. Check how many positions are open
    open_positions = get_open_positions(SYMBOL)
    open_count = len(open_positions)
    print(f"[trader] Open positions: {open_count}/{MAX_OPEN_POSITIONS}")
    
    # 8. LLM market analysis
    print(f"[trader] Calling {ANALYSIS_MODEL} for analysis...")
    strategy_notes = load_strategy_notes()
    signal = analyse_market(indicator_text, strategy_notes, open_count, symbol=SYMBOL)
    
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
    stats = get_stats(last_n=20, symbol=SYMBOL)
    portfolio = get_portfolio()
    report = format_telegram_report(
        symbol=SYMBOL,
        current_price=current_price,
        tf_signals=tf_signals,
        signal=signal,
        open_positions=get_open_positions(SYMBOL),
        stats=stats,
        portfolio=portfolio,
    )
    notify_telegram(report)
    
    print(f"[trader] Scan complete")


if __name__ == '__main__':
    main()
