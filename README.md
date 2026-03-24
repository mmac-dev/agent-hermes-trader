# Hermes Trading Agent

Autonomous BTC/USDT swing trade scanner. Runs as a Hermes cron job every 5 minutes on the Jetson Nano.

## What It Does

- Fetches live candle data (15m, 1h, 4h) via Binance public API (no key needed)
- Calculates full indicator suite: EMA 9/20/50/200, RSI, MACD, Bollinger Bands, ATR, OBV, VWAP
- Sends indicator data to Qwen3.5-35b-a3b (cheap, £~0.01/scan) for analysis
- Opens paper positions when confidence ≥ 65% and R:R ≥ 2.0
- Auto-closes positions when TP or SL is hit
- Fires Telegram alerts for: new signals, position closes, strategy reviews
- Every 5 closed trades → MiniMax M2.1 reviews performance and updates strategy_notes.md

## File Structure

```
~/hermes-trader/
├── trader.py               # Main orchestration — called by Hermes cron
├── market_data.py          # OHLCV fetcher (ccxt + Binance public)
├── indicators.py           # pandas-ta indicator suite
├── trade_log.py            # SQLite DB layer (signals, positions, reviews)
├── strategy_notes.md       # Agent's evolving strategy doc (auto-updated)
├── market-scan.yaml        # Hermes cron config (copy to ~/.hermes/cron/)
├── crypto-trader-skill.md  # Hermes skill (copy to ~/.hermes/skills/)
├── setup.sh                # One-shot setup script
└── trade_log.db            # SQLite DB (auto-created on first run)
```

## Quick Start

```bash
cd ~/hermes-trader
chmod +x setup.sh
./setup.sh
```

## Telegram Alert Examples

**New signal:**
```
🟢 BTC/USDT — LONG SETUP
Entry:       $105,200.00
Stop Loss:   $103,800.00  (-1.3%)
Take Profit: $108,900.00  (+3.5%)
Risk/Reward: 2.7R
Timeframes: 15m ⚠️  1h ✅  4h ✅
Confidence: 74%
```

**Position closed:**
```
✅ BTC/USDT LONG CLOSED
🎯 Take profit hit
Exit: $108,900.00
P&L: +3.52% (+2.70R)
```

**Strategy review (every 5 trades):**
```
🔬 STRATEGY REVIEW
Win rate: 60.0%
Avg R: 1.82R
✅ Working: EMA crossovers on 1h...
❌ Failing: 15m RSI signals in ranging markets...
🔧 Changes made: Raised min confidence to 70%...
```

## Cost Estimate

- ~288 scans/day (every 5 mins)
- ~80% scans → NONE signal (Qwen only)
- ~20% scans with signal processing
- Qwen3.5-35b @ $0.07/$0.30 per 1M tokens
- Estimated: **£1-3/month** for scans alone
- Strategy reviews (MiniMax M2.1): rare, ~£0.10 per review

## Expanding to More Pairs

Edit `trader.py` — change `SYMBOL = 'BTC/USDT'` to a list and loop.
Each additional pair adds ~£0.50-1/month to costs.

## RAM Usage

Peak ~150MB during a scan. Well within 2GB Nano envelope.
If OOM: reduce `limit` in `market_data.py` fetch calls (100 → 50).
