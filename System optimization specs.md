# SwingScope System Optimization Specification
**Version:** 1.1-draft  
**Derived from:** 18-trade closed log analysis + watchlist cross-reference (April–May 2026)  
**Intended use:** Claude agent implementation guide — Antigravity platform  
**Status:** Data-driven. All recommendations are derived from empirical trade outcomes, not theoretical assumptions.

---

## 1. Critical Issues — Fix Before Anything Else

### 1.1 Scale Ambiguity (Blocker)
The SwingScope internal spec defines a **110-point scale**. All recorded trade scores are on a **0–100 scale**. This is unresolved.

**Agent instruction:** Before processing any score-based logic, confirm which scale is active:
- If scores are **normalised to 100** on output → recalibrate all thresholds (see Section 3.2)
- If scores are **raw 110-point** → identify why no trade has ever exceeded 100 and audit the ceiling logic
- This ambiguity makes all threshold comparisons unreliable until resolved

### 1.2 System Compliance Gap
Of 13 scored closed trades, **7 (54%) were entered below the system's own 55-point invalidation threshold.** The system is being overridden by the trader more than half the time.

**Agent instruction:** Add a pre-entry compliance check. If score < 55 on Fibonacci Pullback or Bull Flag pattern types, block the trade from reaching `Assigned` status. Surface a hard rejection message:
```
REJECTED: Score {score}/100 is below the 55-point validity floor for {pattern_type}. 
Reclassify or obtain manual override with documented justification.
```

---

## 2. Classifier Fixes

### 2.1 EMA Pullback — Broken Pass-Through
**Current behaviour:** When EMA structure is not confirmed, classifier outputs `EMA Pullback` label with score `0/100` and passes the trade to the watchlist.

**Problem:** A score of 0 means the pattern was not found. The classifier is labelling and passing trades it cannot validate.

**Data evidence:**
- VALE: `0/100 EMA Pullback` → WIN +1.76R (won on InvestorPro + sector, not chart pattern)
- STX: `0/100 EMA Pullback` → WIN +1.48R (same — won despite pattern failure)
- AA: `0/100 EMA Pullback` → LOSS -1.32R (no compensating signals)

VALE and STX winning created false confidence that 0/100 EMA Pullbacks are tradeable. They are not — they won for unrelated reasons.

**Required fix:**
```
IF pattern_type == "EMA Pullback" AND score < 40:
    → Run reclassification cascade:
        1. Test for Fibonacci Pullback (50% / 61.8% retracement)
        2. Test for Bull Flag (impulse + controlled consolidation)
        3. Test for VP Reversal (price at POC or HVN shelf)
    → If no pattern scores >= 55: output status = "UNCLASSIFIED — Manual Review Required"
    → NEVER pass score < 40 EMA Pullback to watchlist as a valid setup
```

### 2.2 Setup Type vs Trade Log Mismatch
All 4 EMA Pullback trades were logged as **Trend** setups in the trade journal. The GPT analysis system defines EMA Pullback as a **Bounce** setup (pullback to moving average = mean reversion).

**Required fix:** Add a classifier-to-journal mapping validation:

| SwingScope classifier | Correct journal Setup Type |
|---|---|
| EMA Pullback | Bounce |
| Fibonacci Pullback | Trend |
| Bull Flag / Pennant | Trend |
| Breakout from Base | Breakout |
| VP Reversal | Bounce |

**Agent instruction:** When writing a trade to the watchlist, auto-populate `Setup Type` from the classifier mapping above. Flag any manual override as a discrepancy for review.

### 2.3 Breakout from Base — Unscored Blind Spot
5 breakout trades (NVDA, NN, BE, CRDO, NKTR) have **no SwingScope score recorded.** These represent 28% of total trades with zero scoring data.

**Data evidence:**
- CRDO: gapping into heavy historical resistance (chart grade C in GPT notes) → LOSS -0.26R. A VP Confluence check would likely have flagged this.
- NKTR: false breakout, trader identified failure intraday but held → LOSS -1.09R. A low Trend Alignment score on the weekly would have flagged structural weakness.

**Required fix:** SwingScope must run its `Breakout from Base` classifier on every breakout candidate before it is assigned. Breakout alert systems (RVol scanner, pre-market gap scanner) are sourcing tools only — SwingScope is the validation layer. Source ≠ validation.

---

## 3. Scoring Weight Rebalance

### 3.1 Current vs Recommended Weights

| Factor | Current pts | Current % | Recommended pts | Recommended % | Rationale |
|---|---|---|---|---|---|
| Trend Alignment (EMA stack) | 30 | 27% | 20 | 18% | Overweighted — producing identical 0-outputs across different chart structures, lowest discrimination of any factor |
| Candlestick Pattern | 20 | 18% | 20 | 18% | Maintain — insufficient data to challenge |
| Volume / RVol | 15 | 14% | 15 | 14% | Maintain — justified by breakout data (NKTR high RVol but false breakout → RVol alone insufficient, confirms role as one factor among many) |
| RSI Context | 15 | 14% | 15 | 14% | Maintain — RSI reset zone (40–58) is confirmed predictor in winning trend trades |
| VP Confluence | 10 | 9% | 20 | 18% | Underweighted — best winning trades (IMOS 100, NN 91, ASX 80) all occurred near confirmed volume shelves. Most directly connected to institutional price levels. |
| OBV Conviction | 10 | 9% | 10 | 9% | Maintain — accumulation confirmation is sound in principle |
| MACD Confluence | 10 | 9% | 10 | 9% | Maintain but see Section 3.3 for setup-specific weighting |
| **Total** | **110** | | **110** | | |

### 3.2 Recalibrated Thresholds (If Normalising to 100)
If the 110-point scale is being normalised to 100 on output, current thresholds must be adjusted:

| Tier | Current threshold (110pt) | Normalised threshold (100pt) | Position size |
|---|---|---|---|
| High Conviction | 85+ | 77+ | Full |
| Valid Setup | 70–84 | 64–76 | Standard |
| Marginal | 55–69 | 50–63 | Reduced / avoid |
| Invalidated | <55 | <50 | Do not trade |

### 3.3 Setup-Type-Specific Factor Weighting
The current system applies identical factor weights to all pattern types. The data supports differentiated weighting:

**EMA Pullback setups — recommended adjustments:**
- Increase MACD Confluence weight (+5pts): MACD histogram turning positive at the MA level is direct confirmation of mean-reversion validity — more signal-relevant for this pattern than for trend-following setups
- Increase VP Confluence weight (+5pts): price bouncing off a POC or HVN shelf validates the EMA level structurally

**Breakout from Base setups — recommended adjustments:**
- Increase Volume / RVol weight (+5pts): breakout validity is volume-dependent more than any other pattern type
- Reduce Candlestick Pattern weight (-5pts): candlestick reversal patterns are less relevant to range-expansion breakouts

**Agent instruction:** Implement a `pattern_weight_override` config block per classifier. If not yet implemented, log this as a v1.2 roadmap item and apply uniform weights for now.

---

## 4. Contextual Gating Layer — Additions Required

### 4.1 D/E Ratio Gate (New — Not Currently in System)
**Data evidence:** D/E ratio below 0.50 produced 5W/1L (83% win rate) across matched trades. D/E above 1.0 produced 1W/4L (20% win rate) excluding the STX structural outlier.

**Required addition:** Add D/E ratio as a contextual gate in the Fundamental Gating layer:

```
IF debt_to_equity > 1.0:
    → Apply score penalty: -8 points
    → Add warning flag: "HIGH LEVERAGE — elevated structural risk"
IF debt_to_equity > 2.0:
    → Hard gate: REJECT unless VP Confluence >= 8/10 AND Trend Alignment >= 25/30
```

### 4.2 InvestorPro Health Grade Gate (Formalise Existing Signal)
The InvestorPro health signal is currently entered as free text in notes. It needs to be a discrete scored input.

**Data evidence:**
- Explicitly weak / unscored Inv.Pro: 0W/4L → cost -$2,236 (55% of all gross losses)
- Explicitly strong / fair Inv.Pro: 7W/3L

**Required addition:** Add `invpro_health_grade` as a required watchlist field with discrete values:
```
5 = Excellent  → +5 score bonus
4 = Strong     → +3 score bonus  
3 = Fair       → 0 (neutral)
2 = Weak       → -5 score penalty + warning flag
1 = Very Weak  → Hard gate: REJECT on Trend setups
```

### 4.3 Sector RS Validation (Formalise Existing Correlation)
**Data evidence:** Technology sector: 5W/2L. Energy: 0W/2L. Utilities: 0W/1L. Communication Services: 0W/1L. Sector is the single variable that split identical setups (ADI vs LUNR — same score 68, same tier, same fund rating, different sector → different outcome).

The system spec mentions sector ETF correlation (XLK, XLE etc.) but this is not surfaced as a discrete scored field in the watchlist.

**Required addition:** Add `sector_rs_direction` as a required field:
```
Confirmed uptrend  → +5 score bonus
Neutral / mixed    → 0
Confirmed downtrend → -10 score penalty
```

**Agent instruction:** Auto-populate `sector_rs_direction` by comparing the ticker's sector ETF (XLK, XLE, XLB, XLU etc.) to its 20-day and 50-day SMA at time of watchlist entry.

---

## 5. Journal Data Quality Fixes

### 5.1 Required Discrete Fields (Currently Free Text)
The following signals exist in trade notes as free text but need to be discrete columns for reliable analysis:

| Signal | Current state | Required field name | Values |
|---|---|---|---|
| Pattern type | Embedded in notes | `pattern_type` | EMA Pullback / Fibonacci Pullback / Bull Flag / Breakout from Base / VP Reversal |
| Pattern score | Embedded in notes | `pattern_score` | 0–100 integer |
| InvestorPro health | Free text | `invpro_health` | 1–5 integer |
| VCP validity | Not recorded | `vcp_valid` | Yes / No / Partial |
| Weekly alignment | Not recorded | `weekly_alignment` | Aligned / Divergent / Neutral |
| RSI at analysis | Not recorded | `rsi_at_entry` | Float |
| ATR at analysis | Not recorded | `atr_at_entry` | Float (dollar value) |
| D/E ratio | Watchlist only | `debt_equity` | Float |
| Sector RS | Not recorded | `sector_rs` | Uptrend / Neutral / Downtrend |

### 5.2 Recycled Trade Tracking
3 trades were re-entered after pre-entry stop hits (BKR once, LUNR twice). All lost. There is no field tracking this.

**Required addition:** Add `recycled` boolean field. Any trade where price hit the stop level before entry triggers must set `recycled = true`. 

**Agent instruction:** Flag all `recycled = true` trades for post-trade review. Aggregate recycled trade win rate monthly — if it falls below 40%, implement a hard block on recycled entries for that setup type.

### 5.3 Intraday Exit Rule (NKTR Finding)
NKTR trade notes explicitly state: *"I should have closed it on the day of trading when I saw it wasn't breaking ORB."* This is a real-time observation that was ignored.

**Required addition:** Add a breakout-specific intraday rule to the execution engine:
```
IF setup_type == "Breakout" AND price fails to hold ORH within 45 minutes of trigger:
    → Generate alert: "BREAKOUT FAILURE — price back inside range. Exit at market?"
    → Log: intraday_exit_triggered = true
```

---

## 6. GPT Analysis Integration

### 6.1 What the GPT System Produces vs What Gets Recorded
The GPT analysis system (per the system prompt) generates the following outputs. Only some are currently captured in the watchlist:

| GPT output | Currently recorded | Should be recorded |
|---|---|---|
| Tier (A/B/REJECT) | Yes — `GPT Grade` | Yes |
| Setup type | Yes — `GPT Setup` | Yes |
| Entry / Stop / Target | Yes | Yes |
| VCP validity | No | Yes → `vcp_valid` |
| Multi-timeframe divergence | No | Yes → `weekly_alignment` |
| RSI at analysis | No | Yes → `rsi_at_entry` |
| ATR at analysis | No | Yes → `atr_at_entry` |
| Sector momentum assessment | No | Yes → `sector_rs` |

**Agent instruction:** Parse GPT analysis output and auto-populate all fields above into the watchlist row at time of entry. The GPT system is generating this data — it is being discarded before it reaches the journal.

### 6.2 B-TIER Interpretation Rule
B-TIER is not a lower quality signal — it is a **specific structural warning**. Current usage treats B-TIER as a quality downgrade. Correct interpretation:

```
B-TIER = valid daily setup + identified weekly structural risk
Action  = reduce position size by 30%, require additional confirmation trigger before entry
NOT     = avoid the trade
```

---

## 7. Implementation Priority

| Priority | Item | Section | Effort |
|---|---|---|---|
| P0 — Blocker | Resolve 110pt vs 100pt scale | 1.1 | Low |
| P0 — Blocker | Hard gate: no sub-55 entries on Fib/Bull Flag | 1.2 | Low |
| P1 — Critical | Fix EMA Pullback classifier pass-through | 2.1 | Medium |
| P1 — Critical | Add Setup Type auto-mapping from classifier | 2.2 | Low |
| P1 — Critical | Run SwingScope on all breakout candidates | 2.3 | Medium |
| P2 — High | Rebalance factor weights (Trend -10, VP +10) | 3.1 | Medium |
| P2 — High | Add D/E ratio gate to scoring | 4.1 | Low |
| P2 — High | Formalise InvestorPro health as scored input | 4.2 | Low |
| P2 — High | Add sector RS as discrete field + auto-populate | 4.3 | Medium |
| P3 — Standard | Add all discrete journal fields | 5.1 | Medium |
| P3 — Standard | Add recycled trade tracking and block logic | 5.2 | Low |
| P3 — Standard | Add breakout intraday exit alert | 5.3 | Medium |
| P3 — Standard | Auto-parse GPT outputs into watchlist fields | 6.1 | High |
| P4 — Optimise | Setup-type-specific factor weighting | 3.3 | High |

---

## 8. Success Metrics

Track the following after each implementation phase to validate improvements:

| Metric | Current baseline | Target |
|---|---|---|
| Win rate (all trades) | 43.8% | >55% |
| Win rate (scored trades above threshold) | 57% | >65% |
| Avg loss R | -0.53R | < -0.40R |
| Expectancy per trade | +0.37R | >+0.60R |
| % trades entered below 55-point threshold | 54% | <10% |
| Recycled trade win rate | 0% (3 trades) | Track only — enforce block if <40% over 20 trades |
| EMA Pullback 0/100 pass-through rate | 100% | 0% |
| Breakout trades with SwingScope score | 0% | 100% |

---

*Document generated from 18-trade empirical analysis. Recommendations are evidence-based and specific to observed patterns in this trading log. Re-evaluate all thresholds after 50+ additional scored trades.*