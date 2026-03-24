# -*- coding: utf-8 -*-
"""
indicators.py -- Technical indicator calculations using the `ta` library.
Python 3.11 compatible. No TA-Lib compile required. ARM/Nano safe.
"""

import pandas as pd
import ta
from typing import Optional


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate full indicator suite on a candle DataFrame.
    Adds columns in-place and returns the enriched DataFrame.
    """
    if df is None or len(df) < 50:
        return df

    close = df['close']
    high  = df['high']
    low   = df['low']
    vol   = df['volume']

    # --- Trend: EMAs ---
    df['ema_9']   = ta.trend.ema_indicator(close, window=9)
    df['ema_20']  = ta.trend.ema_indicator(close, window=20)
    df['ema_50']  = ta.trend.ema_indicator(close, window=50)
    df['ema_200'] = ta.trend.ema_indicator(close, window=200)

    # --- Momentum: RSI ---
    df['rsi'] = ta.momentum.rsi(close, window=14)

    # --- Momentum: MACD ---
    macd_obj          = ta.trend.MACD(close, window_slow=26, window_fast=12, window_sign=9)
    df['macd']        = macd_obj.macd()
    df['macd_signal'] = macd_obj.macd_signal()
    df['macd_hist']   = macd_obj.macd_diff()

    # --- Volatility: Bollinger Bands ---
    bb             = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    df['bb_upper'] = bb.bollinger_hband()
    df['bb_mid']   = bb.bollinger_mavg()
    df['bb_lower'] = bb.bollinger_lband()
    df['bb_width'] = bb.bollinger_wband()

    # --- Volatility: ATR ---
    df['atr'] = ta.volatility.average_true_range(high, low, close, window=14)

    # --- Volume: OBV ---
    df['obv'] = ta.volume.on_balance_volume(close, vol)

    # --- Volume: VWAP (rolling proxy) ---
    df['vwap'] = ta.volume.volume_weighted_average_price(high, low, close, vol, window=14)

    # --- Structure: swing highs/lows ---
    window = 5
    df['swing_high'] = df['high'].where(df['high'] == df['high'].rolling(window, center=True).max())
    df['swing_low']  = df['low'].where(df['low']  == df['low'].rolling(window, center=True).min())

    return df


def extract_signal_data(df: pd.DataFrame) -> dict:
    """
    Extract latest indicator values into a flat dict for LLM consumption.
    Uses the most recent completed candle.
    """
    if df is None or df.empty:
        return {}

    row  = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else row

    def safe(col, default=None):
        try:
            val = row.get(col)
            return round(float(val), 4) if pd.notna(val) else default
        except Exception:
            return default

    def safe_prev(col, default=None):
        try:
            val = prev.get(col)
            return round(float(val), 4) if pd.notna(val) else default
        except Exception:
            return default

    price  = safe('close')
    ema20  = safe('ema_20')
    ema50  = safe('ema_50')
    ema200 = safe('ema_200')

    # EMA cross detection (EMA9 vs EMA20)
    ema_cross_up   = (safe_prev('ema_9') or 0) < (safe_prev('ema_20') or 0) and \
                     (safe('ema_9') or 0) > (safe('ema_20') or 0)
    ema_cross_down = (safe_prev('ema_9') or 0) > (safe_prev('ema_20') or 0) and \
                     (safe('ema_9') or 0) < (safe('ema_20') or 0)

    # MACD histogram cross
    macd_cross_up   = (safe_prev('macd_hist') or 0) < 0 and (safe('macd_hist') or 0) > 0
    macd_cross_down = (safe_prev('macd_hist') or 0) > 0 and (safe('macd_hist') or 0) < 0

    # BB position (0 = lower band, 1 = upper band)
    bbl = safe('bb_lower')
    bbu = safe('bb_upper')
    bb_position = None
    if price and bbl and bbu and (bbu - bbl) > 0:
        bb_position = round((price - bbl) / (bbu - bbl), 3)

    # Trend bias — 3-condition standard (consistent with strategy notes)
    # BULLISH: price > EMA50 AND EMA20 > EMA50 AND RSI > 50
    # BEARISH: price < EMA50 AND EMA20 < EMA50 AND RSI < 50
    # NEUTRAL: everything else
    rsi = safe('rsi')
    trend = 'neutral'
    if price and ema20 and ema50 and rsi:
        if price > ema50 and ema20 > ema50 and rsi > 50:
            trend = 'bullish'
        elif price < ema50 and ema20 < ema50 and rsi < 50:
            trend = 'bearish'

    return {
        'price':           price,
        'ema_9':           safe('ema_9'),
        'ema_20':          ema20,
        'ema_50':          ema50,
        'ema_200':         ema200,
        'trend_bias':      trend,
        'ema_cross_up':    ema_cross_up,
        'ema_cross_down':  ema_cross_down,
        'rsi':             safe('rsi'),
        'macd':            safe('macd'),
        'macd_signal':     safe('macd_signal'),
        'macd_hist':       safe('macd_hist'),
        'macd_cross_up':   macd_cross_up,
        'macd_cross_down': macd_cross_down,
        'bb_lower':        bbl,
        'bb_upper':        bbu,
        'bb_mid':          safe('bb_mid'),
        'bb_position':     bb_position,
        'bb_width':        safe('bb_width'),
        'atr':             safe('atr'),
        'obv':             safe('obv'),
        'vwap':            safe('vwap'),
        'volume':          safe('volume'),
        'prev_volume':     safe_prev('volume'),
        'volume_surge':    (safe('volume') or 0) > (safe_prev('volume') or 1) * 1.5,
        'candle_high':     safe('high'),
        'candle_low':      safe('low'),
        'timestamp':       str(row.get('timestamp', '')),
    }


def format_indicators_for_llm(signals: dict, symbol: str) -> str:
    """
    Format multi-timeframe indicator data into a compact,
    token-efficient string for the LLM analysis prompt.
    """
    lines = [f"=== {symbol} INDICATOR SNAPSHOT ===\n"]

    for tf, data in signals.items():
        if not data:
            lines.append(f"[{tf}] No data\n")
            continue

        lines.append(f"[{tf}] @ {data.get('timestamp', 'N/A')}")

        price = data.get('price')
        lines.append(f"  Price: ${price:,.2f}" if price else "  Price: N/A")
        lines.append(f"  Trend: {data.get('trend_bias', 'N/A').upper()}")

        e9, e20, e50, e200 = data.get('ema_9'), data.get('ema_20'), data.get('ema_50'), data.get('ema_200')
        if all([e9, e20, e50, e200]):
            lines.append(f"  EMA 9/20/50/200: {e9:.0f} / {e20:.0f} / {e50:.0f} / {e200:.0f}")
        else:
            lines.append("  EMA: partial data")

        rsi = data.get('rsi')
        if rsi:
            if rsi > 70:   rsi_note = ' (OVERBOUGHT)'
            elif rsi < 30: rsi_note = ' (OVERSOLD)'
            elif rsi > 60: rsi_note = ' (bullish momentum)'
            elif rsi < 40: rsi_note = ' (bearish momentum)'
            else:          rsi_note = ''
            lines.append(f"  RSI(14): {rsi:.1f}{rsi_note}")
        else:
            lines.append("  RSI: N/A")

        macd_h = data.get('macd_hist')
        if macd_h is not None:
            note = 'above zero (bullish)' if macd_h > 0 else 'below zero (bearish)'
            lines.append(f"  MACD hist: {macd_h:.2f} -- {note}")
        else:
            lines.append("  MACD: N/A")

        bb_pos = data.get('bb_position')
        bb_w   = data.get('bb_width')
        if bb_pos is not None:
            if bb_pos > 0.8:   bb_note = ' (near upper band)'
            elif bb_pos < 0.2: bb_note = ' (near lower band)'
            else:              bb_note = ' (mid-range)'
            lines.append(f"  BB position: {bb_pos:.2f}{bb_note}")
        else:
            lines.append("  BB position: N/A")
        if bb_w is not None:
            if bb_w < 0.3:    bw_note = ' (EXTREME COMPRESSION)'
            elif bb_w < 0.8:  bw_note = ' (consolidating)'
            elif bb_w > 1.5:  bw_note = ' (expanding — trend confirmation)'
            else:             bw_note = ''
            lines.append(f"  BB width: {bb_w:.2f}%{bw_note}")
        else:
            lines.append("  BB width: N/A")

        atr = data.get('atr')
        lines.append(f"  ATR(14): {atr:.2f}" if atr else "  ATR: N/A")
        lines.append(f"  Volume surge: {'YES' if data.get('volume_surge') else 'No'}")

        crosses = []
        if data.get('ema_cross_up'):    crosses.append('EMA9 crossed above EMA20')
        if data.get('ema_cross_down'):  crosses.append('EMA9 crossed below EMA20')
        if data.get('macd_cross_up'):   crosses.append('MACD bullish cross')
        if data.get('macd_cross_down'): crosses.append('MACD bearish cross')
        if crosses:
            lines.append(f"  Signals: {' | '.join(crosses)}")

        lines.append("")

    return '\n'.join(lines)
