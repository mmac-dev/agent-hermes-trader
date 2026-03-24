## Self-Tuning Framework (v1.0)

### Review Triggers
- After every 5 closed trades on this asset, run a full strategy review
- After any single trade that loses more than 2R, run an immediate mini-review
- After 20 consecutive scans with NONE signal, run a "stale strategy" review to check if thresholds are too restrictive
- Weekly on Sunday: review S/R levels and update based on current 4h chart structure

### Performance Metrics to Track (per review window)
- Win rate (target: >55%)
- Average R per trade (target: >1.0R)
- Max drawdown in the window (alert if >3R cumulative)
- Average trade duration (monitor for drift — getting significantly longer or shorter suggests market regime change)
- Rejection rate (% of scans that returned NONE — if consistently >95% over 50+ scans, thresholds may be too tight)
- Confidence distribution (track average confidence of rejected scans — if averaging 55-64%, you're close to trading and small adjustments may unlock setups)

### Tier 1: Auto-Adjustable Parameters (apply changes directly)
These parameters can be adjusted within the defined bounds WITHOUT human approval. After adjustment, log the change, the reasoning, and the before/after values in the Adaptations Made section.

| Parameter | Min Bound | Max Bound | Step Size |
|-----------|-----------|-----------|-----------|
| BB width trend filter | 0.3% | 1.5% | 0.1% |
| BB width bounce filter | 0.1% | 0.8% | 0.05% |
| BB extreme threshold (lower) | 0.08 | 0.20 | 0.01 |
| BB extreme threshold (upper) | 0.80 | 0.92 | 0.01 |
| ATR stop multiplier | 0.8x | 2.5x | 0.1x |
| Confidence bonus/penalty values | -30% | +15% | 5% |
| Volatility sizing reduction | 20% | 60% | 5% |
| Ranging position size reduction | 30% | 60% | 5% |
| S/R levels | (update freely based on chart structure) | | |

Rules for Tier 1 adjustments:
- Only adjust ONE parameter per review cycle. Changing multiple parameters at once makes it impossible to attribute results.
- Each adjustment must include: which metric triggered it, what the old value was, what the new value is, and what improvement is expected.
- If a parameter change leads to worse performance over the next 5 trades, REVERT it and log the reversion.
- Never adjust a parameter in the same direction twice in a row without at least 5 trades of data between changes.
- If win rate drops below 40% over any 5-trade window, revert ALL Tier 1 changes made in the last 2 review cycles and flag for human review.

### Tier 2: Human Approval Required (propose only, do not apply)
These changes require explicit approval before being applied. Present them as a proposal with supporting data.

Changes that require approval:
- Adding or removing an entire entry setup type (e.g., new "Breakout Setup")
- Changing the Trend Classification Standard
- Modifying the minimum R:R ratio (currently 2.0)
- Changing the minimum confidence threshold (currently 65%)
- Altering the macro trend bias direction or lift/pause levels
- Adding new pre-trade filters or removing existing ones
- Changing the maximum concurrent positions limit
- Any change to the Self-Tuning Framework itself

Format for Tier 2 proposals:
"STRATEGY PROPOSAL — [Asset] — [Date]
Change: [what you want to change]
Reason: [what data supports this]
Expected impact: [what you think will improve]
Risk: [what could go wrong]
Recommendation: [apply / defer / needs more data]"

### Stale Strategy Detection
If the agent produces 20+ consecutive NONE signals:
1. Check if the rejection rate is because confidence is consistently 50-64% — if so, one or more thresholds may be slightly too tight. Identify which threshold is the binding constraint most often and consider a Tier 1 adjustment.
2. Check if the market regime has changed — has the asset moved out of the range where S/R levels are defined? If so, update S/R levels immediately.
3. Check if BB width thresholds are filtering out all setups — compare current BB width readings to the threshold. If BB width is consistently just below the filter, consider lowering the threshold by one step.
4. If none of the above explain the stale period, the market may genuinely have no setups — this is acceptable. Not trading is a valid outcome. Do NOT lower standards just to generate trades.

### Adaptation Log Format
Every change (Tier 1 or Tier 2) must be logged in the Adaptations Made section using this format:
"v[version] ([date]): [Tier 1/2] — [parameter] changed from [old] to [new]. Trigger: [metric]. Reasoning: [1 sentence]. Result after 5 trades: [pending/improved/degraded/reverted]."

### Hard Limits (NEVER adjustable, not even with human approval)
- Minimum confidence to trade: NEVER below 50%
- Minimum R:R ratio: NEVER below 1.5
- Maximum concurrent positions: NEVER above 3
- Stop loss: MUST always be set. No trade without a stop.
- The agent NEVER removes the Self-Tuning Framework section itself
- The agent NEVER adjusts hard limits
