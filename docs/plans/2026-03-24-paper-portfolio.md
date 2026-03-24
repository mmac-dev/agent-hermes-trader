# Paper Portfolio ($10,000 Demo Account) Implementation Plan

> **For Hermes:** Execute tasks sequentially using execute_code for changes, commit after each task group.

**Goal:** Add a virtual $10,000 portfolio that sizes positions, tracks balance/equity, calculates dollar P&L, simulates fees, and reports portfolio state in Telegram.

**Architecture:** New `portfolio` table in trade_log.db holds account state. Position sizing uses 1% risk per trade. On close, balance updates with realised P&L minus simulated fees. Drawdown circuit breaker pauses trading at -10%. All changes in existing files — no new modules needed.

**Tech Stack:** SQLite (existing), Python stdlib

**Design Decisions:**
- Starting balance: $10,000
- Risk per trade: 1% of current balance
- Fees: 0.1% per side (entry + exit = 0.2% round trip) — matches Binance spot
- Leverage: None (notional capped at balance — no margin)
- Drawdown circuit breaker: Pause at 10% drawdown from peak
- Reset: Manual function to reset portfolio to $10,000

---

## Task 1: Add portfolio table and init functions

**Objective:** Create the portfolio table schema and initialisation logic.

**Files:**
- Modify: `/home/agentneo/hermes-trader/trade_log.py`

**Step 1: Add portfolio table to `init_db()`**

Add after the `strategy_reviews` CREATE TABLE block:

```python
    # Portfolio state (paper trading account)
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
```

**Step 2: Add `get_portfolio()` function**

```python
def get_portfolio() -> dict:
    """Get current portfolio state. Creates default if not exists."""
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM portfolio WHERE id = 1')
    row = c.fetchone()
    if row is None:
        now = datetime.now(timezone.utc).isoformat()
        c.execute('''
            INSERT INTO portfolio (id, starting_balance, balance, peak_equity,
                                   total_pnl, total_fees, trades_taken, created_at, updated_at)
            VALUES (1, 10000.0, 10000.0, 10000.0, 0.0, 0.0, 0, ?, ?)
        ''', (now, now))
        conn.commit()
        c.execute('SELECT * FROM portfolio WHERE id = 1')
        row = c.fetchone()
    result = dict(row)
    conn.close()
    return result
```

**Step 3: Add `update_portfolio()` function**

```python
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
```

**Step 4: Add `reset_portfolio()` function**

```python
def reset_portfolio(starting_balance: float = 10000.0):
    """Reset portfolio to starting state."""
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    c.execute('DELETE FROM portfolio')
    c.execute('''
        INSERT INTO portfolio (id, starting_balance, balance, peak_equity,
                               total_pnl, total_fees, trades_taken, created_at, updated_at)
        VALUES (1, ?, ?, ?, 0.0, 0.0, 0, ?, ?)
    ''', (starting_balance, starting_balance, starting_balance, now, now))
    conn.commit()
    conn.close()
```

**Verify:** Run `python -c "from trade_log import init_db, get_portfolio; init_db(); print(get_portfolio())"`

**Commit:** `feat: add portfolio table and management functions`

---

## Task 2: Add position sizing columns to positions table

**Objective:** Extend positions table with sizing, fees, and dollar P&L fields.

**Files:**
- Modify: `/home/agentneo/hermes-trader/trade_log.py`

**Step 1: Add columns via migration in `init_db()`**

Add after the existing CREATE TABLE blocks (SQLite ALTER TABLE for new columns):

```python
    # Migration: add portfolio columns to positions (safe to re-run)
    try:
        c.execute('ALTER TABLE positions ADD COLUMN position_size REAL')
    except sqlite3.OperationalError:
        pass  # column already exists
    try:
        c.execute('ALTER TABLE positions ADD COLUMN risk_amount REAL')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('ALTER TABLE positions ADD COLUMN fees REAL DEFAULT 0.0')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('ALTER TABLE positions ADD COLUMN pnl_usd REAL')
    except sqlite3.OperationalError:
        pass
```

**Verify:** Run `python -c "from trade_log import init_db; init_db()"` — no errors.

**Commit:** `feat: add position sizing columns to positions table`

---

## Task 3: Add position sizing calculation

**Objective:** Calculate position size based on portfolio balance and risk %.

**Files:**
- Modify: `/home/agentneo/hermes-trader/trade_log.py`

**Step 1: Add `calculate_position_size()` function**

```python
RISK_PER_TRADE_PCT = 0.01  # 1% of balance
FEE_RATE = 0.001           # 0.1% per side (Binance spot)
MIN_BALANCE = 500.0        # stop trading below this

def calculate_position_size(
    balance: float,
    entry_price: float,
    stop_loss: float,
) -> dict:
    """
    Calculate position size based on 1% risk rule.
    
    Returns dict with:
        risk_amount: dollars at risk
        position_size: notional position in USD
        quantity: amount of BTC
        entry_fee: fee on entry
        can_trade: whether balance supports this trade
    """
    risk_amount = balance * RISK_PER_TRADE_PCT
    sl_distance_pct = abs(entry_price - stop_loss) / entry_price
    
    if sl_distance_pct == 0:
        return {'can_trade': False, 'reason': 'SL distance is zero'}
    
    # Position size = risk / SL distance
    position_size = risk_amount / sl_distance_pct
    
    # Cap at available balance (no leverage)
    if position_size > balance:
        position_size = balance
        risk_amount = position_size * sl_distance_pct
    
    quantity = position_size / entry_price
    entry_fee = position_size * FEE_RATE
    
    if balance < MIN_BALANCE:
        return {'can_trade': False, 'reason': f'Balance ${balance:.2f} below minimum ${MIN_BALANCE:.2f}'}
    
    return {
        'can_trade': True,
        'risk_amount': round(risk_amount, 2),
        'position_size': round(position_size, 2),
        'quantity': round(quantity, 8),
        'entry_fee': round(entry_fee, 2),
    }
```

**Verify:** Run a quick calculation test:
```python
python -c "
from trade_log import calculate_position_size
r = calculate_position_size(10000, 70000, 69500)
print(r)
# Expected: position_size ~$14,000 (capped to $10,000), risk ~$100
"
```

**Commit:** `feat: add position sizing calculation`

---

## Task 4: Update open_position to use sizing and deduct from balance

**Objective:** When opening a position, calculate size, deduct entry fee, record sizing in DB.

**Files:**
- Modify: `/home/agentneo/hermes-trader/trade_log.py`

**Step 1: Update `open_position()` signature and logic**

```python
def open_position(
    signal_id: int,
    symbol: str,
    direction: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    strategy_notes: str = '',
) -> dict:
    """
    Open a new paper position with portfolio sizing.
    Returns dict with position ID and sizing info, or None if can't trade.
    """
    portfolio = get_portfolio()
    sizing = calculate_position_size(portfolio['balance'], entry_price, stop_loss)
    
    if not sizing['can_trade']:
        return {'opened': False, 'reason': sizing.get('reason', 'Cannot trade')}
    
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        INSERT INTO positions
        (signal_id, opened_at, symbol, direction, entry_price,
         stop_loss, take_profit, status, strategy_notes,
         position_size, risk_amount, fees)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?)
    ''', (
        signal_id,
        datetime.now(timezone.utc).isoformat(),
        symbol, direction,
        entry_price, stop_loss, take_profit,
        strategy_notes,
        sizing['position_size'],
        sizing['risk_amount'],
        sizing['entry_fee'],
    ))
    pos_id = c.lastrowid

    # Mark signal as acted on
    c.execute('UPDATE signals SET acted_on=1 WHERE id=?', (signal_id,))
    conn.commit()
    conn.close()

    # Deduct entry fee from balance
    new_balance = portfolio['balance'] - sizing['entry_fee']
    update_portfolio({'balance': round(new_balance, 2)})

    return {
        'opened': True,
        'id': pos_id,
        'position_size': sizing['position_size'],
        'risk_amount': sizing['risk_amount'],
        'entry_fee': sizing['entry_fee'],
    }
```

**Note:** This changes the return type from `int` to `dict`. trader.py will need updating in Task 6.

**Commit:** `feat: integrate position sizing into open_position`

---

## Task 5: Update close_position to calculate dollar P&L and update balance

**Objective:** On close, calculate dollar P&L, deduct exit fee, update portfolio balance.

**Files:**
- Modify: `/home/agentneo/hermes-trader/trade_log.py`

**Step 1: Update `close_position()` to handle portfolio**

Add after the existing P&L calculation (pnl_pct, pnl_r):

```python
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
```

Update the UPDATE query to include new fields:

```python
    c.execute('''
        UPDATE positions
        SET closed_at=?, exit_price=?, exit_reason=?,
            pnl_pct=?, pnl_r=?, pnl_usd=?, fees=?, status='CLOSED'
        WHERE id=?
    ''', (
        datetime.now(timezone.utc).isoformat(),
        exit_price, exit_reason,
        round(pnl_pct, 4), round(pnl_r, 4),
        round(pnl_usd_net, 2), round(total_fees, 2),
        position_id,
    ))
```

After DB update, update portfolio:

```python
    # Update portfolio balance
    portfolio = get_portfolio()
    new_balance = portfolio['balance'] + pnl_usd_net  # net of exit fee
    new_total_pnl = portfolio['total_pnl'] + pnl_usd_net
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
```

**Commit:** `feat: calculate dollar P&L and update portfolio on close`

---

## Task 6: Update trader.py to use new open_position return type

**Objective:** Handle the dict return from open_position and add drawdown check.

**Files:**
- Modify: `/home/agentneo/hermes-trader/trader.py`

**Step 1: Add config constant**

```python
MAX_DRAWDOWN_PCT = 10.0  # pause trading if drawdown exceeds this
```

**Step 2: Add drawdown check before opening position**

In `main()`, before the position-opening block, add:

```python
    # Check portfolio health
    from trade_log import get_portfolio
    portfolio = get_portfolio()
    drawdown = 0
    if portfolio['peak_equity'] > 0:
        drawdown = (portfolio['peak_equity'] - portfolio['balance']) / portfolio['peak_equity'] * 100
    
    if drawdown >= MAX_DRAWDOWN_PCT:
        print(f"[trader] CIRCUIT BREAKER: {drawdown:.1f}% drawdown exceeds {MAX_DRAWDOWN_PCT}% limit — no new trades")
```

**Step 3: Update the position-opening block**

Change from:
```python
pos_id = open_position(...)
```
To:
```python
result = open_position(...)
if result.get('opened'):
    pos_id = result['id']
    print(f"[trader] Opened paper position #{pos_id} (size: ${result['position_size']:,.2f}, risk: ${result['risk_amount']:,.2f})")
    msg = format_telegram_signal(signal, SYMBOL, pos_id)
    telegram_messages.append(msg)
else:
    print(f"[trader] Could not open position: {result.get('reason')}")
```

**Verify:** Run a manual scan and check output includes sizing info.

**Commit:** `feat: add drawdown circuit breaker and position sizing to trader`

---

## Task 7: Add portfolio section to Telegram report

**Objective:** Show portfolio state in every 5-minute report.

**Files:**
- Modify: `/home/agentneo/hermes-trader/trader.py`

**Step 1: Update `format_telegram_report()` signature**

Add `portfolio: dict` parameter.

**Step 2: Add portfolio section to report template**

```python
    # Portfolio section
    balance = portfolio.get('balance', 10000)
    starting = portfolio.get('starting_balance', 10000)
    total_pnl = portfolio.get('total_pnl', 0)
    total_fees = portfolio.get('total_fees', 0)
    peak = portfolio.get('peak_equity', balance)
    return_pct = ((balance - starting) / starting) * 100
    drawdown = ((peak - balance) / peak) * 100 if peak > 0 else 0

    portfolio_text = (
        f"Balance: ${balance:,.2f} ({'+' if return_pct >= 0 else ''}{return_pct:.1f}%)\n"
        f"P&L: ${'+' if total_pnl >= 0 else ''}{total_pnl:,.2f} | Fees: ${total_fees:,.2f}\n"
        f"Drawdown: {drawdown:.1f}% | Peak: ${peak:,.2f}"
    )
```

Add to the report string:

```
💰 PORTFOLIO:
{portfolio_text}
```

**Step 3: Update `main()` to pass portfolio to report**

```python
    portfolio = get_portfolio()
    report = format_telegram_report(
        ...,
        portfolio=portfolio,
    )
```

**Verify:** Check Telegram report includes portfolio section.

**Commit:** `feat: add portfolio stats to Telegram report`

---

## Task 8: Add enhanced stats functions

**Objective:** Add max drawdown, average trade duration, and streak tracking.

**Files:**
- Modify: `/home/agentneo/hermes-trader/trade_log.py`

**Step 1: Enhance `get_stats()` to include new metrics**

Add to the existing stats dict:

```python
    # Average trade duration
    durations = []
    for t in trades:
        if t.get('opened_at') and t.get('closed_at'):
            opened = datetime.fromisoformat(t['opened_at'])
            closed = datetime.fromisoformat(t['closed_at'])
            durations.append((closed - opened).total_seconds() / 3600)
    
    # Win/loss streak
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
    
    # Add to return dict
    stats['avg_duration_hours'] = round(sum(durations) / len(durations), 1) if durations else 0
    stats['current_streak'] = f"{streak} {'win' if streak_type == 'win' else 'loss'}" if streak_type else 'N/A'
    stats['total_pnl_usd'] = round(sum(t.get('pnl_usd') or 0 for t in trades), 2)
```

**Commit:** `feat: add enhanced trade stats (duration, streaks, dollar P&L)`

---

## Task 9: Final integration and commit

**Objective:** Test end-to-end, clean up, push.

**Steps:**

1. Run `python -c "from trade_log import init_db, get_portfolio; init_db(); print(get_portfolio())"` — verify portfolio initialises at $10,000
2. Run `python trader.py` — verify scan completes with portfolio in report
3. Check Telegram for report with portfolio section
4. `git add -A && git commit -m "feat: paper portfolio with $10k demo account"`
5. `git push` (from Jetson terminal)

**Verify checklist:**
- [ ] Portfolio starts at $10,000
- [ ] Position sizing uses 1% risk
- [ ] Fees deducted on open and close
- [ ] Balance updates on trade close
- [ ] Drawdown circuit breaker works at 10%
- [ ] Telegram report shows portfolio section
- [ ] Stats include dollar P&L and duration

---

## Summary of Changes

| File | Changes |
|------|---------|
| `trade_log.py` | New portfolio table, get/update/reset functions, position sizing, dollar P&L on close, enhanced stats |
| `trader.py` | Drawdown circuit breaker, new open_position return handling, portfolio in Telegram report |

**Total estimated effort:** 9 tasks, ~45 minutes implementation time.
