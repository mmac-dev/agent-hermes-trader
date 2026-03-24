"""
trade_log.py — SQLite-backed trade log.
Stores signals, paper positions, outcomes, and strategy review history.
"""

import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


DB_PATH = Path.home() / 'hermes-trader' / 'trade_log.db'


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    c = conn.cursor()

    # All generated signals (including ones that didn't meet threshold)
    c.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at  TEXT NOT NULL,
            symbol      TEXT NOT NULL,
            direction   TEXT,          -- LONG / SHORT / NONE
            confidence  INTEGER,       -- 0-100
            entry_price REAL,
            stop_loss   REAL,
            take_profit REAL,
            rr_ratio    REAL,
            reasoning   TEXT,          -- LLM reasoning text
            tf_15m      TEXT,          -- JSON indicator snapshot
            tf_1h       TEXT,
            tf_4h       TEXT,
            acted_on    INTEGER DEFAULT 0  -- 1 if paper trade opened
        )
    ''')

    # Paper portfolio positions
    c.execute('''
        CREATE TABLE IF NOT EXISTS positions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id       INTEGER REFERENCES signals(id),
            opened_at       TEXT NOT NULL,
            closed_at       TEXT,
            symbol          TEXT NOT NULL,
            direction       TEXT NOT NULL,  -- LONG / SHORT
            entry_price     REAL NOT NULL,
            stop_loss       REAL NOT NULL,
            take_profit     REAL NOT NULL,
            exit_price      REAL,
            exit_reason     TEXT,           -- TP_HIT / SL_HIT / MANUAL / TIMEOUT
            pnl_pct         REAL,           -- % gain/loss
            pnl_r           REAL,           -- R multiple (1R = risked amount)
            status          TEXT DEFAULT 'OPEN',  -- OPEN / CLOSED
            strategy_notes  TEXT            -- snapshot of strategy at time of trade
        )
    ''')

    # Migration: add leverage and sizing columns to positions (safe to re-run)
    try:
        c.execute('ALTER TABLE positions ADD COLUMN leverage INTEGER DEFAULT 1')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('ALTER TABLE positions ADD COLUMN margin_used REAL')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('ALTER TABLE positions ADD COLUMN position_size REAL')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('ALTER TABLE positions ADD COLUMN risk_amount REAL')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('ALTER TABLE positions ADD COLUMN pnl_usd REAL DEFAULT 0.0')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('ALTER TABLE positions ADD COLUMN fees REAL DEFAULT 0.0')
    except sqlite3.OperationalError:
        pass

    # Strategy review history
    c.execute('''
        CREATE TABLE IF NOT EXISTS strategy_reviews (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            reviewed_at  TEXT NOT NULL,
            trades_since_last INTEGER,
            win_rate     REAL,
            avg_rr       REAL,
            summary      TEXT,           -- LLM review text
            changes_made TEXT            -- what the agent changed in strategy_notes.md
        )
    ''')

    # Paper portfolio state (singleton row)
    c.execute('''
        CREATE TABLE IF NOT EXISTS portfolio (
            id              INTEGER PRIMARY KEY CHECK (id = 1),  -- singleton row
            starting_balance REAL NOT NULL DEFAULT 10000.0,
            balance         REAL NOT NULL DEFAULT 10000.0,       -- available cash
            peak_equity     REAL NOT NULL DEFAULT 10000.0,       -- for drawdown calc
            total_pnl       REAL NOT NULL DEFAULT 0.0,           -- cumulative realised P&L
            total_fees      REAL NOT NULL DEFAULT 0.0,           -- cumulative fees paid
            trades_taken    INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        )
    ''')

    conn.commit()
    conn.close()
    print(f"DB initialised at {DB_PATH}")


# --- Portfolio methods ---

def get_portfolio() -> dict:
    """Get current portfolio state. Creates default if not exists."""
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM portfolio WHERE id = 1')
    row = c.fetchone()
    if row is None:
        now = datetime.now(timezone.utc).isoformat()
        c.execute('''
            INSERT INTO portfolio
            (id, starting_balance, balance, peak_equity, total_pnl, total_fees,
             trades_taken, created_at, updated_at)
            VALUES (1, 10000.0, 10000.0, 10000.0, 0.0, 0.0, 0, ?, ?)
        ''', (now, now))
        conn.commit()
        c.execute('SELECT * FROM portfolio WHERE id = 1')
        row = c.fetchone()
    result = dict(row)
    conn.close()
    return result


def update_portfolio(updates: dict):
    """Update portfolio fields."""
    conn = get_conn()
    c = conn.cursor()
    updates['updated_at'] = datetime.now(timezone.utc).isoformat()
    set_clause = ', '.join(f'{k} = ?' for k in updates)
    values = list(updates.values())
    c.execute(f'UPDATE portfolio SET {set_clause} WHERE id = 1', values)
    conn.commit()
    conn.close()


def reset_portfolio(starting_balance: float = 10000.0):
    """Reset portfolio to starting state."""
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    c.execute('DELETE FROM portfolio')
    c.execute('''
        INSERT INTO portfolio
        (id, starting_balance, balance, peak_equity, total_pnl, total_fees,
         trades_taken, created_at, updated_at)
        VALUES (1, ?, ?, ?, 0.0, 0.0, 0, ?, ?)
    ''', (starting_balance, starting_balance, starting_balance, now, now))
    conn.commit()
    conn.close()


# --- Position sizing with leverage ---

RISK_PER_TRADE_PCT = 0.01  # 1% of balance
FEE_RATE = 0.001           # 0.1% per side (Binance futures)
MIN_BALANCE = 500.0        # stop trading below this
MAX_LEVERAGE = 20          # hard cap on leverage


def calculate_position_size(
    balance: float,
    entry_price: float,
    stop_loss: float,
    leverage: int = 1,
) -> dict:
    """
    Calculate position size based on 1% risk rule with leverage.
    
    Leverage amplifies position size but not the risk amount.
    E.g. $10k balance, 1% risk = $100 risk. With 5x leverage the
    notional position is larger, but the margin (collateral) used
    is position_size / leverage.
    
    Returns dict with:
        risk_amount: dollars at risk (always 1% of balance)
        position_size: notional position in USD (amplified by leverage)
        margin_used: actual collateral locked (position_size / leverage)
        quantity: amount of BTC
        entry_fee: fee on entry (based on notional)
        leverage: validated leverage used
        can_trade: whether balance supports this trade
    """
    leverage = max(1, min(int(leverage), MAX_LEVERAGE))
    
    risk_amount = balance * RISK_PER_TRADE_PCT
    sl_distance_pct = abs(entry_price - stop_loss) / entry_price
    
    if sl_distance_pct == 0:
        return {'can_trade': False, 'reason': 'SL distance is zero'}
    
    # Position size = risk / SL distance (base sizing from risk)
    position_size = risk_amount / sl_distance_pct
    
    # Apply leverage: allows notional to exceed balance
    # But margin (collateral) must fit within balance
    max_notional = balance * leverage
    if position_size > max_notional:
        position_size = max_notional
        risk_amount = position_size * sl_distance_pct
    
    margin_used = position_size / leverage
    quantity = position_size / entry_price
    entry_fee = position_size * FEE_RATE
    
    # Check margin + fee fits in balance
    if margin_used + entry_fee > balance:
        return {'can_trade': False, 'reason': f'Insufficient margin: need ${margin_used + entry_fee:.2f}, have ${balance:.2f}'}
    
    if balance < MIN_BALANCE:
        return {'can_trade': False, 'reason': f'Balance ${balance:.2f} below minimum ${MIN_BALANCE:.2f}'}
    
    return {
        'can_trade': True,
        'risk_amount': round(risk_amount, 2),
        'position_size': round(position_size, 2),
        'margin_used': round(margin_used, 2),
        'quantity': round(quantity, 8),
        'entry_fee': round(entry_fee, 2),
        'leverage': leverage,
    }


# --- Signal methods ---

def log_signal(
    symbol: str,
    direction: Optional[str],
    confidence: Optional[int],
    entry_price: Optional[float],
    stop_loss: Optional[float],
    take_profit: Optional[float],
    rr_ratio: Optional[float],
    reasoning: str,
    tf_data: dict,
    acted_on: bool = False,
) -> int:
    """Insert a signal record. Returns new signal ID."""
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        INSERT INTO signals
        (created_at, symbol, direction, confidence, entry_price, stop_loss,
         take_profit, rr_ratio, reasoning, tf_15m, tf_1h, tf_4h, acted_on)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        datetime.now(timezone.utc).isoformat(),
        symbol, direction, confidence,
        entry_price, stop_loss, take_profit, rr_ratio,
        reasoning,
        json.dumps(tf_data.get('15m', {})),
        json.dumps(tf_data.get('1h', {})),
        json.dumps(tf_data.get('4h', {})),
        int(acted_on),
    ))
    signal_id = c.lastrowid
    conn.commit()
    conn.close()
    return signal_id


# --- Position methods ---

def open_position(
    signal_id: int,
    symbol: str,
    direction: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    leverage: int = 1,
    strategy_notes: str = '',
) -> dict:
    """
    Open a new paper position with portfolio sizing and leverage.
    Returns dict with position ID and sizing info, or {'opened': False, 'reason': ...}.
    """
    portfolio = get_portfolio()
    sizing = calculate_position_size(portfolio['balance'], entry_price, stop_loss, leverage)
    
    if not sizing['can_trade']:
        return {'opened': False, 'reason': sizing.get('reason', 'Cannot trade')}
    
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        INSERT INTO positions
        (signal_id, opened_at, symbol, direction, entry_price,
         stop_loss, take_profit, status, strategy_notes,
         position_size, risk_amount, fees, leverage, margin_used)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?)
    ''', (
        signal_id,
        datetime.now(timezone.utc).isoformat(),
        symbol, direction,
        entry_price, stop_loss, take_profit,
        strategy_notes,
        sizing['position_size'],
        sizing['risk_amount'],
        sizing['entry_fee'],
        sizing['leverage'],
        sizing['margin_used'],
    ))
    pos_id = c.lastrowid

    # Mark signal as acted on
    c.execute('UPDATE signals SET acted_on=1 WHERE id=?', (signal_id,))
    conn.commit()
    conn.close()

    # Deduct margin + entry fee from balance
    new_balance = portfolio['balance'] - sizing['margin_used'] - sizing['entry_fee']
    update_portfolio({'balance': round(new_balance, 2)})

    return {
        'opened': True,
        'id': pos_id,
        'position_size': sizing['position_size'],
        'margin_used': sizing['margin_used'],
        'risk_amount': sizing['risk_amount'],
        'entry_fee': sizing['entry_fee'],
        'leverage': sizing['leverage'],
    }


def get_open_positions(symbol: Optional[str] = None) -> list:
    """Return all open paper positions, optionally filtered by symbol."""
    conn = get_conn()
    c = conn.cursor()
    if symbol:
        c.execute('SELECT * FROM positions WHERE status=? AND symbol=?', ('OPEN', symbol))
    else:
        c.execute('SELECT * FROM positions WHERE status=?', ('OPEN',))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_available_margin() -> float:
    """Calculate available margin across all positions for portfolio-based sizing."""
    portfolio = get_portfolio()
    balance = portfolio['balance']
    
    # Sum margin used by all open positions
    open_positions = get_open_positions(symbol=None)  # All symbols
    total_margin = sum(p.get('margin_used', 0) or 0 for p in open_positions)
    
    return balance - total_margin


def close_position(
    position_id: int,
    exit_price: float,
    exit_reason: str,
) -> dict:
    """
    Close a paper position. Calculates P&L in dollars and updates portfolio.
    Returns the closed position dict.
    """
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM positions WHERE id=?', (position_id,))
    pos = dict(c.fetchone())

    entry = pos['entry_price']
    sl    = pos['stop_loss']
    risk  = abs(entry - sl)

    if pos['direction'] == 'LONG':
        pnl_pct = (exit_price - entry) / entry * 100
        pnl_r   = (exit_price - entry) / risk if risk > 0 else 0
    else:  # SHORT
        pnl_pct = (entry - exit_price) / entry * 100
        pnl_r   = (entry - exit_price) / risk if risk > 0 else 0

    # Dollar P&L calculation
    position_size = pos.get('position_size') or 0
    if position_size > 0:
        if pos['direction'] == 'LONG':
            pnl_usd = position_size * (exit_price - entry) / entry
        else:
            pnl_usd = position_size * (entry - exit_price) / entry
        
        exit_fee = position_size * FEE_RATE
        pnl_usd_net = pnl_usd - exit_fee
        total_fees = (pos.get('fees') or 0) + exit_fee
    else:
        # Legacy positions without sizing
        pnl_usd = 0
        exit_fee = 0
        pnl_usd_net = 0
        total_fees = pos.get('fees') or 0

    c.execute('''
        UPDATE positions
        SET closed_at=?, exit_price=?, exit_reason=?,
            pnl_pct=?, pnl_r=?, pnl_usd=?, fees=?, status='CLOSED'
        WHERE id=?
    ''', (
        datetime.now(timezone.utc).isoformat(),
        exit_price, exit_reason,
        round(pnl_pct, 4), round(pnl_r, 4),
        round(pnl_usd, 2), round(total_fees, 2),
        position_id,
    ))
    conn.commit()
    conn.close()

    pos.update({
        'exit_price': exit_price,
        'exit_reason': exit_reason,
        'pnl_pct': round(pnl_pct, 4),
        'pnl_r': round(pnl_r, 4),
        'pnl_usd': round(pnl_usd, 2),  # Gross P&L (exit fee subtracted)
        'fees': round(total_fees, 2),
        'status': 'CLOSED',
    })

    # Update portfolio balance: return margin + apply net P&L
    margin_used = pos.get('margin_used') or 0
    portfolio = get_portfolio()
    new_balance = portfolio['balance'] + margin_used + pnl_usd_net
    new_total_pnl = portfolio['total_pnl'] + pnl_usd  # Gross P&L
    new_total_fees = portfolio['total_fees'] + total_fees
    new_trades = portfolio['trades_taken'] + 1
    new_peak = max(portfolio['peak_equity'], new_balance)

    update_portfolio({
        'balance': round(new_balance, 2),
        'total_pnl': round(new_total_pnl, 2),
        'total_fees': round(new_total_fees, 2),
        'trades_taken': new_trades,
        'peak_equity': round(new_peak, 2),
    })

    return pos


def check_and_close_positions(current_prices: dict, position_timeout_hours: int = None) -> list:
    """
    Check all open positions against current prices.
    Auto-close if TP or SL hit, or if timeout exceeded.
    Returns list of positions that were closed.
    """
    from datetime import datetime, timezone, timedelta
    
    closed = []
    for pos in get_open_positions():
        symbol = pos['symbol']
        price = current_prices.get(symbol)
        
        # Parse open time
        open_dt = datetime.fromisoformat(pos['opened_at'].replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        hours_open = (now - open_dt).total_seconds() / 3600
        
        # Check timeout first
        timeout_hours = position_timeout_hours or 48
        if hours_open > timeout_hours:
            # Use the average of entry and stop for timeout exit (midpoint)
            exit_price = (pos['entry_price'] + pos['stop_loss']) / 2
            closed.append(close_position(pos['id'], exit_price, 'TIMEOUT'))
            continue
        
        # If no price available, skip price-based checks
        if price is None:
            continue
        
        hit = None
        if pos['direction'] == 'LONG':
            if price >= pos['take_profit']:
                hit = ('TP_HIT', pos['take_profit'])
            elif price <= pos['stop_loss']:
                hit = ('SL_HIT', pos['stop_loss'])
        else:  # SHORT
            if price <= pos['take_profit']:
                hit = ('TP_HIT', pos['take_profit'])
            elif price >= pos['stop_loss']:
                hit = ('SL_HIT', pos['stop_loss'])

        if hit:
            reason, exit_price = hit
            closed.append(close_position(pos['id'], exit_price, reason))

    return closed


# --- Stats methods ---

def get_closed_trades(limit: int = 50, symbol: str = None) -> list:
    """Return recent closed positions, optionally filtered by symbol."""
    conn = get_conn()
    c = conn.cursor()
    if symbol:
        c.execute('''
            SELECT p.*, s.reasoning, s.confidence, s.tf_1h
            FROM positions p
            LEFT JOIN signals s ON p.signal_id = s.id
            WHERE p.status = 'CLOSED' AND p.symbol = ?
            ORDER BY p.closed_at DESC
            LIMIT ?
        ''', (symbol, limit))
    else:
        c.execute('''
            SELECT p.*, s.reasoning, s.confidence, s.tf_1h
            FROM positions p
            LEFT JOIN signals s ON p.signal_id = s.id
            WHERE p.status = 'CLOSED'
            ORDER BY p.closed_at DESC
            LIMIT ?
        ''', (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_stats(last_n: int = 20, symbol: str = None) -> dict:
    """Calculate win rate, avg R, streak, max drawdown for last N closed trades."""
    trades = get_closed_trades(limit=last_n, symbol=symbol)
    if not trades:
        return {'total': 0}

    wins   = [t for t in trades if (t['pnl_r'] or 0) > 0]
    losses = [t for t in trades if (t['pnl_r'] or 0) <= 0]
    pnl_rs = [t['pnl_r'] or 0 for t in trades]

    # Average trade duration
    durations = []
    for t in trades:
        if t.get('opened_at') and t.get('closed_at'):
            try:
                opened = datetime.fromisoformat(t['opened_at'].replace('Z', '+00:00'))
                closed = datetime.fromisoformat(t['closed_at'].replace('Z', '+00:00'))
                durations.append((closed - opened).total_seconds() / 3600)
            except (ValueError, TypeError):
                pass

    # Win/loss streak (consecutive)
    streak = 0
    streak_type = None
    for t in trades:
        r = t.get('pnl_r') or 0
        if streak_type is None:
            streak_type = 'win' if r > 0 else 'loss'
            streak = 1
        elif (r > 0 and streak_type == 'win') or (r <= 0 and streak_type == 'loss'):
            streak += 1
        else:
            break

    # Max drawdown in R terms (peak-to-trough)
    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for r in pnl_rs:
        cumulative += r
        if cumulative > peak:
            peak = cumulative
        drawdown = peak - cumulative
        if drawdown > max_drawdown:
            max_drawdown = drawdown

    # Dollar P&L totals
    total_pnl_usd = sum(t.get('pnl_usd') or 0 for t in trades)

    return {
        'total':          len(trades),
        'wins':           len(wins),
        'losses':         len(losses),
        'win_rate':       round(len(wins) / len(trades) * 100, 1),
        'avg_r':          round(sum(pnl_rs) / len(pnl_rs), 3),
        'total_r':        round(sum(pnl_rs), 3),
        'best_r':         round(max(pnl_rs), 3),
        'worst_r':        round(min(pnl_rs), 3),
        'avg_duration':   round(sum(durations) / len(durations), 1) if durations else 0,
        'current_streak': f"{streak} {'win' if streak_type == 'win' else 'loss'}" if streak_type else 'N/A',
        'max_drawdown_r': round(max_drawdown, 3),
        'total_pnl_usd':  round(total_pnl_usd, 2),
    }


def count_closed_since_last_review(symbol: str = 'BTC/USDT') -> int:
    """Count trades closed after the last strategy review for this symbol."""
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        'SELECT reviewed_at FROM strategy_reviews WHERE symbol=? ORDER BY reviewed_at DESC LIMIT 1',
        (symbol,)
    )
    row = c.fetchone()
    last_review = row['reviewed_at'] if row else '1970-01-01'
    
    c.execute(
        "SELECT COUNT(*) as cnt FROM positions WHERE status='CLOSED' AND symbol=? AND closed_at > ?",
        (symbol, last_review)
    )
    cnt = c.fetchone()['cnt']
    conn.close()
    return cnt


def log_strategy_review(
    trades_reviewed: int,
    win_rate: float,
    avg_rr: float,
    summary: str,
    changes_made: str,
    symbol: str = 'BTC/USDT',
):
    """Log a strategy review for a specific symbol."""
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        INSERT INTO strategy_reviews
        (reviewed_at, trades_since_last, win_rate, avg_rr, summary, changes_made, symbol)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        datetime.now(timezone.utc).isoformat(),
        trades_reviewed, win_rate, avg_rr,
        summary, changes_made, symbol,
    ))
    conn.commit()
    conn.close()


if __name__ == '__main__':
    init_db()
