#!/usr/bin/env python3
"""Hermes Trader Self-Diagnostic Script"""

import os
import re
import sqlite3
from pathlib import Path

# Configuration
TRADER_DIR = Path("/home/agentneo/hermes-trader")
ASSETS = ["BTC", "ETH", "SOL", "LINK"]
SYMBOLS = {"BTC": "BTC/USDT", "ETH": "ETH/USDT", "SOL": "SOL/USDT", "LINK": "LINK/USDT"}
BB_THRESHOLDS = {"BTC": 0.5, "ETH": 0.6, "SOL": 0.7, "LINK": 1.0}

print("="*80)
print("HERMES TRADER SELF-DIAGNOSTIC REPORT")
print("="*80)

# ============================================================================
# CHECK 1: STRATEGY NOTES LOADING
# ============================================================================
print("\n" + "="*80)
print("CHECK 1 — STRATEGY NOTES LOADING")
print("="*80)

check1_results = {}

for asset in ASSETS:
    asset_upper = asset.upper()
    notes_path = TRADER_DIR / f"strategy_notes_{asset_upper}_USDT.md"
    
    print(f"\n--- {asset} ---")
    
    if notes_path.exists():
        print(f"✓ File exists: {notes_path}")
        content = notes_path.read_text()
        first_line = content.split('\n')[0]
        print(f"  First line: '{first_line}'")
        
        if asset_upper in first_line:
            print(f"✓ First line contains correct asset name: {asset_upper}")
            check1_results[asset] = {'exists': True, 'name_correct': True}
        else:
            print(f"✗ First line does NOT contain correct asset name!")
            check1_results[asset] = {'exists': True, 'name_correct': False}
        
        version_match = re.search(r'Version:\s*[\d.]+', content)
        if version_match:
            print(f"✓ Version: {version_match.group(0)}")
            check1_results[asset]['version'] = version_match.group(0)
        else:
            print("✗ No version found in header")
    else:
        print(f"✗ File does NOT exist: {notes_path}")
        check1_results[asset] = {'exists': False, 'name_correct': False}

# ============================================================================
# CHECK 2: SYMBOL CONSISTENCY
# ============================================================================
print("\n" + "="*80)
print("CHECK 2 — SYMBOL CONSISTENCY")
print("="*80)

trader_files = {
    "BTC": TRADER_DIR / "trader.py",
    "ETH": TRADER_DIR / "eth_trader.py",
    "SOL": TRADER_DIR / "sol_trader.py",
    "LINK": TRADER_DIR / "link_trader.py"
}

check2_results = {}

for asset, filepath in trader_files.items():
    print(f"\n--- {asset} ({filepath.name}) ---")
    
    if filepath.exists():
        content = filepath.read_text()
        
        symbol_match = re.search(r'SYMBOL\s*=\s*["\']([^"\']+)["\']', content)
        if symbol_match:
            symbol_value = symbol_match.group(1)
            print(f"  SYMBOL = {symbol_value}")
            if symbol_value == SYMBOLS[asset]:
                print(f"  ✓ SYMBOL matches expected: {SYMBOLS[asset]}")
                check2_results[asset] = {'symbol_ok': True, 'notes_ok': True}
            else:
                print(f"  ✗ SYMBOL MISMATCH! Expected: {SYMBOLS[asset]}")
                check2_results[asset] = {'symbol_ok': False, 'notes_ok': False}
        else:
            print(f"  ✗ No SYMBOL found")
            check2_results[asset] = {'symbol_ok': False, 'notes_ok': False}
        
        notes_match = re.search(r'STRATEGY_NOTES_PATH\s*=\s*["\']([^"\']+)["\']', content)
        if notes_match:
            notes_value = notes_match.group(1)
            print(f"  STRATEGY_NOTES_PATH = {notes_value}")
    else:
        print(f"✗ File does not exist")
        check2_results[asset] = {'symbol_ok': False, 'notes_ok': False}

# Check get_signals.py
print("\n--- get_signals.py (hardcoded symbol check) ---")
signals_file = TRADER_DIR / "get_signals.py"
if signals_file.exists():
    content = signals_file.read_text()
    symbol_refs = re.findall(r'["\']([A-Z]+/USDT)["\']', content)
    if symbol_refs:
        print(f"  Found symbol references: {set(symbol_refs)}")
        if len(set(symbol_refs)) > 1:
            print(f"  ⚠ WARNING: Multiple hardcoded symbols found!")

# ============================================================================
# CHECK 3: TREND CLASSIFICATION
# ============================================================================
print("\n" + "="*80)
print("CHECK 3 — TREND CLASSIFICATION")
print("="*80)

def extract_tf_summary(filepath):
    content = filepath.read_text()
    func_match = re.search(r'def tf_summary\(.*?\):.*?(?=\ndef |\Z)', content, re.DOTALL)
    return func_match.group(0) if func_match else None

def check_trend_logic(func_code):
    if not func_code:
        return "ERROR", "Function not found"
    
    has_ema_20 = 'ema_20' in func_code
    has_ema_50 = 'ema_50' in func_code
    has_price_comparison = 'price' in func_code and any(op in func_code for op in ['>=', '>', '<=', '<'])
    has_rsi_comparison = 'rsi' in func_code and any(op in func_code for op in ['>=', '>', '<=', '<'])
    has_bullish = 'BULLISH' in func_code
    has_bearish = 'BEARISH' in func_code
    
    has_proper_bullish = all([has_price_comparison, has_ema_20, has_ema_50, has_rsi_comparison])
    is_rsi_only = (has_rsi_comparison and not has_proper_bullish)
    
    if is_rsi_only:
        return "RSI-ONLY", "Uses RSI-only logic (flagged!)"
    elif has_proper_bullish and has_bullish and has_bearish:
        return "3-CONDITION", "Uses proper 3-condition logic"
    else:
        return "PARTIAL", "Partial logic detected"

check3_results = {}

for asset in ASSETS:
    filepath = trader_files[asset]
    print(f"\n--- {asset} ---")
    
    if filepath.exists():
        func_code = extract_tf_summary(filepath)
        status, detail = check_trend_logic(func_code)
        
        print(f"  Status: {status}")
        print(f"  {detail}")
        
        check3_results[asset] = status.lower() == "3-condition"
        
        if status == "RSI-ONLY":
            print(f"  [ACTION REQUIRED] Switch to 3-condition standard!")
    else:
        print(f"✗ File does not exist")
        check3_results[asset] = False

# ============================================================================
# CHECK 4: BB WIDTH FORMAT
# ============================================================================
print("\n" + "="*80)
print("CHECK 4 — BB WIDTH FORMAT")
print("="*80)

indicators_file = TRADER_DIR / "indicators.py"
check4_results = {}

if indicators_file.exists():
    content = indicators_file.read_text()
    
    func_match = re.search(r'def format_indicators_for_llm\(.*?\):.*?(?=\ndef |\Z)', content, re.DOTALL)
    
    if func_match:
        func_code = func_match.group(0)
        print("Found format_indicators_for_llm function")
        
        # Check for percentage formatting
        has_pct_fmt = '%' in func_code and ('.2f%' in func_code or 'f"%' in func_code)
        has_division = '/ middle' in func_code or '/ma' in func_code or 'middle)' in func_code
        
        print(f"\n  BB width calculation: {'✓ Found' if has_division else '✗ Not found'}")
        print(f"  Percentage formatting: {'✓ Yes' if has_pct_fmt else '⚠ Possibly decimal'}")
        
        for asset in ASSETS:
            check4_results[asset] = has_pct_fmt and has_division
        
        print("\n  Strategy threshold requirements:")
        for asset in ASSETS:
            print(f"    {asset}: {BB_THRESHOLDS[asset]}%")
    else:
        print("Could not find format_indicators_for_llm function")
else:
    print("indicators.py not found")

# ============================================================================
# CHECK 5: CANDLE DEPTH
# ============================================================================
print("\n" + "="*80)
print("CHECK 5 — CANDLE DEPTH")
print("="*80)

check5_results = {'candles_ok': False, 'ema200_ok': False}

market_data_file = TRADER_DIR / "market_data.py"
if market_data_file.exists():
    content = market_data_file.read_text()
    
    if '250' in content:
        print("✓ '250' candles reference found")
        check5_results['candles_ok'] = True
    else:
        print("⚠ '250' candles not found")
        # Check for variable
        count_match = re.search(r'count\s*=\s*(\d+)', content)
        if count_match:
            print(f"  Variable found: count = {count_match.group(1)}")

if indicators_file.exists():
    content = indicators_file.read_text()
    
    has_ema200 = 'ema200' in content.lower()
    has_nan_check = 'isna()' in content or 'isnan()' in content or 'pd.isnull' in content
    
    print(f"\n  EMA200 column found: {'✓ Yes' if has_ema200 else '✗ No'}")
    print(f"  NaN/None handling: {'✓ Yes' if has_nan_check else '✗ No'}")
    
    check5_results['ema200_ok'] = has_ema200 and has_nan_check

# ============================================================================
# CHECK 6: SCHEMA FIELDS
# ============================================================================
print("\n" + "="*80)
print("CHECK 6 — SCHEMA FIELDS")
print("="*80)

check6_results = False

if signals_file.exists():
    content = signals_file.read_text()
    
    schema_matches = re.findall(r'(schema\s*=\s*[\{\[].*?[\}\]]|Schema\(.*?\))', content, re.DOTALL)
    
    if schema_matches:
        has_deferred = False
        has_confidence = False
        
        for match in schema_matches:
            if '"deferred"' in match or "'deferred'" in match:
                has_deferred = True
            if '"setup_confidence"' in match or "'setup_confidence'" in match:
                has_confidence = True
        
        print(f"  Contains 'deferred': {'✓' if has_deferred else '✗'}")
        print(f"  Contains 'setup_confidence': {'✓' if has_confidence else '✗'}")
        
        check6_results = has_deferred and has_confidence
        
        if has_deferred and has_confidence:
            print("  ✓ Both required fields present!")
        else:
            print("  ✗ Missing required fields!")

# ============================================================================
# CHECK 7: STRATEGY NOTES SIZE
# ============================================================================
print("\n" + "="*80)
print("CHECK 7 — STRATEGY NOTES SIZE")
print("="*80)

check7_results = {}

for asset in ASSETS:
    asset_upper = asset.upper()
    notes_path = TRADER_DIR / f"strategy_notes_{asset_upper}_USDT.md"
    
    print(f"\n--- {asset} ---")
    
    if notes_path.exists():
        content = notes_path.read_text()
        char_count = len(content)
        print(f"Character count: {char_count:,}")
        
        if char_count > 12000:
            print(f"  ✗ OVER 12,000 characters! [ACTION REQUIRED]")
            check7_results[asset] = False
        else:
            print(f"  ✓ Under 12,000 characters")
            check7_results[asset] = True
    else:
        print(f"✗ File does not exist")
        check7_results[asset] = False

# ============================================================================
# CHECK 8: PARSE ERROR HISTORY
# ============================================================================
print("\n" + "="*80)
print("CHECK 8 — PARSE ERROR HISTORY")
print("="*80)

check8_results = {}

db_path = TRADER_DIR / "trade_log.db"
if db_path.exists():
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    for asset in ASSETS:
        query = '''
        SELECT reasoning 
        FROM signals 
        WHERE symbol = ? 
        ORDER BY timestamp DESC 
        LIMIT 20
        '''
        cursor.execute(query, (f"{asset}/USDT",))
        results = cursor.fetchall()
        
        if results:
            parse_errors = sum(1 for row in results if row[0] == 'Parse error')
            rate = (parse_errors / 20 * 100) if results else 0
            
            print(f"\n{asset}/USDT: {parse_errors}/20 parse errors ({rate:.1f}%)")
            
            if parse_errors > 2:
                print(f"  ✗ HIGH ERROR RATE! [ACTION REQUIRED]")
                check8_results[asset] = False
            else:
                print(f"  ✓ Acceptable error rate")
                check8_results[asset] = True
        else:
            print(f"\n{asset}/USDT: No signals found")
            check8_results[asset] = False
    
    conn.close()
else:
    print(f"Database not found: {db_path}")

# ============================================================================
# CHECK 9: PRE-TRADE FILTER DATA
# ============================================================================
print("\n" + "="*80)
print("CHECK 9 — PRE-TRADE FILTER DATA")
print("="*80)

check9_results = {'extract': True, 'format': True}

if indicators_file.exists():
    content = indicators_file.read_text()
    
    extract_match = re.search(r'def extract_signal_data\(.*?\):.*?(?=\ndef |\Z)', content, re.DOTALL)
    format_match = re.search(r'def format_indicators_for_llm\(.*?\):.*?(?=\ndef |\Z)', content, re.DOTALL)
    
    if extract_match:
        extract_code = extract_match.group(0)
        has_bb = 'bb_position' in extract_code
        has_vol = 'volume' in extract_code
        has_atr = 'atr' in extract_code
        has_btc = 'btc' in extract_code.lower()
        
        print("extract_signal_data():")
        print(f"  bb_position (1h): {'✓' if has_bb else '✗'}")
        print(f"  volume: {'✓' if has_vol else '✗'}")
        print(f"  atr: {'✓' if has_atr else '✗'}")
        print(f"  BTC price: {'✓' if has_btc else '✗'}")
        
        check9_results['extract'] = has_bb and has_vol and has_atr
    else:
        print("extract_signal_data() not found")
        check9_results['extract'] = False
    
    if format_match:
        format_code = format_match.group(0)
        has_bb = 'bb_position' in format_code
        has_vol = 'volume' in format_code
        has_atr = 'atr' in format_code
        has_btc = 'btc' in format_code.lower()
        
        print("\nformat_indicators_for_llm():")
        print(f"  bb_position (1h): {'✓' if has_bb else '✗'}")
        print(f"  volume: {'✓' if has_vol else '✗'}")
        print(f"  atr: {'✓' if has_atr else '✗'}")
        print(f"  BTC price: {'✓' if has_btc else '✗'}")
        
        check9_results['format'] = has_bb and has_vol and has_atr
    else:
        print("format_indicators_for_llm() not found")
        check9_results['format'] = False

# ============================================================================
# CHECK 10: SELF-TUNING FRAMEWORK
# ============================================================================
print("\n" + "="*80)
print("CHECK 10 — SELF-TUNING FRAMEWORK")
print("="*80)

check10_results = {}

for asset in ASSETS:
    asset_upper = asset.upper()
    notes_path = TRADER_DIR / f"strategy_notes_{asset_upper}_USDT.md"
    
    print(f"\n--- {asset} ---")
    
    if notes_path.exists():
        content = notes_path.read_text()
        
        if 'Self-Tuning Framework' in content:
            print("✓ Self-Tuning Framework section found")
            
            match = re.search(r'Self-Tuning Framework.*?(?=##|\Z)', content, re.DOTALL)
            if match:
                lines = match.group(0).split('\n')
                print(f"  Section length: {len(lines)} lines")
            
            check10_results[asset] = True
        else:
            print("✗ Self-Tuning Framework NOT FOUND! [ACTION REQUIRED]")
            check10_results[asset] = False
    else:
        print(f"✗ File does not exist")
        check10_results[asset] = False

# ============================================================================
# SUMMARY TABLE
# ============================================================================
print("\n" + "="*80)
print("SUMMARY TABLE")
print("="*80)

print(f"\n{'Asset':<8} | {'Notes':<7} | {'Symbol':<8} | {'Trend':<8} | {'BB fmt':<8} | {'Candles':<9} | {'Schema':<8} | {'Notes Size':<12} | {'Parse Errors':<15} | {'Filters':<9} | {'STF':<6}")
print("-"*125)

for asset in ASSETS:
    notes_check = "✓" if check1_results.get(asset, {}).get('exists', False) and check1_results.get(asset, {}).get('name_correct', False) else "✗"
    symbol_check = "✓" if check2_results.get(asset, {}).get('symbol_ok', False) else "✗"
    trend_check = "✓" if check3_results.get(asset, False) else "✗"
    bb_check = "✓" if check4_results.get(asset, True) else "✗"
    candles_check = "✓" if check5_results.get('candles_ok', False) else "✗"
    schema_check = "✓" if check6_results else "✗"
    
    # Get notes size
    if TRADER_DIR.exists():
        notes_path = TRADER_DIR / f"strategy_notes_{asset}_USDT.md"
        if notes_path.exists():
            notes_size = len(notes_path.read_text())
        else:
            notes_size = 0
    else:
        notes_size = 0
    
    # Get parse errors
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute('SELECT reasoning FROM signals WHERE symbol = ? ORDER BY timestamp DESC LIMIT 20', (f"{asset}/USDT",))
        results = cursor.fetchall()
        parse_errors = sum(1 for row in results if row[0] == 'Parse error') if results else 0
        conn.close()
    else:
        parse_errors = 0
    
    parse_str = f"{parse_errors}/20"
    filters_check = "✓" if check9_results.get('extract', False) and check9_results.get('format', False) else "✗"
    stf_check = "✓" if check10_results.get(asset, False) else "✗"
    
    print(f"{asset:<8} | {notes_check:<7} | {symbol_check:<8} | {trend_check:<8} | {bb_check:<8} | {candles_check:<9} | {schema_check:<8} | {notes_size:<12} | {parse_str:<15} | {filters_check:<9} | {stf_check:<6}")

print("\n" + "="*80)
print("DIAGNOSTIC COMPLETE")
print("="*80)
