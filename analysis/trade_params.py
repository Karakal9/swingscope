"""
SwingScope Trade Parameterizer
===============================
Calculates entry, stop loss, profit targets (TP1/TP2/TP3), risk/reward
ratio, and position sizing for a classified setup.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import config as cfg
from analysis.setup_classifier import SetupResult, Verdict
from analysis.structure import SRLevel
from indicators.volume_profile import VolumeProfile

logger = logging.getLogger(__name__)


@dataclass
class TradeParams:
    """Complete trade parameter set for a single setup."""

    entry: float
    stop_loss: float
    risk: float              # entry - stop_loss
    tp1: float               # nearest HVN / S/R above entry
    tp2: float               # 2R
    tp3: float               # 3R
    rr_tp1: float            # R:R to TP1
    rr_tp2: float = 2.0
    rr_tp3: float = 3.0
    position_shares: int = 0
    position_notional: float = 0.0
    risk_pct: float = 0.0    # account risk %
    rr_valid: bool = True    # passes MIN_RR_RATIO gate
    account_size: int = cfg.ACCOUNT_SIZE
    sl_method: str = "STRUCTURAL"
    sl_structural_level: float = 0.0
    atr_cap_triggered: bool = False



def calculate_trade_params(
    setup: SetupResult,
    trigger_candle_high: float,
    last_swing_low: float,
    atr: float,
    resistance_levels: list[SRLevel],
    vp: Optional[VolumeProfile] = None,
    account_size: int = cfg.ACCOUNT_SIZE,
) -> TradeParams:
    """Calculate trade parameters for the given setup.

    Parameters
    ----------
    setup : SetupResult
        The classified setup (used for conviction tier → risk %).
    trigger_candle_high : float
        High of the most recent setup candle.
    last_swing_low : float
        Price of the nearest swing low (for structural stop).
    atr : float
        Current ATR_14 value.
    resistance_levels : list[SRLevel]
        Resistance levels above current price.
    vp : VolumeProfile or None
        Volume profile for HVN-based TP1.
    account_size : int
        Account value for position sizing.

    Returns
    -------
    TradeParams
    """
    # ── Entry ────────────────────────────────────────────────
    entry = trigger_candle_high + (cfg.ENTRY_BUFFER_ATR * atr)

    # ── Stop Loss ────────────────────────────────────────────
    # The stop loss pipeline: structural → liquidity buffer → 2x ATR floor → risk cap

    # 1. Start with structural stop
    sl_base = last_swing_low - (cfg.SL_SWING_BUFFER_ATR * atr)

    # 2. Apply Liquidity Buffer FIRST (odd-cent endings)
    # Never place on round number or exact MA. Use .41, .87, .11, .97
    def _nearest_odd_cent_below(price: float) -> float:
        import math
        price = round(price, 2)
        cents = int(round((price - math.floor(price)) * 100))
        targets = [11, 41, 87, 97]
        lower = [t for t in targets if t < cents]
        if lower:
            return math.floor(price) + (max(lower) / 100.0)
        else:
            return math.floor(price) - 1.0 + (max(targets) / 100.0)

    sl_base = _nearest_odd_cent_below(sl_base)

    # 3. Enforce the 2x ATR Rule (Non-Negotiable)
    # The distance Entry→Stop MUST be at least 2x ATR
    min_risk = 2.0 * atr
    if (entry - sl_base) < min_risk:
        sl_base = entry - min_risk
        # Re-apply buffer after widening
        sl_base = _nearest_odd_cent_below(sl_base)

    # 4. Apply setup-specific risk cap (if risk got too large)
    cap_multiplier = cfg.SL_ATR_CAPS.get(setup.setup_type.value, 2.5)
    max_risk = cap_multiplier * atr

    sl_method = "STRUCTURAL"
    atr_cap_triggered = False

    if (entry - sl_base) > max_risk:
        stop_loss = entry - max_risk
        stop_loss = _nearest_odd_cent_below(stop_loss)
        sl_method = "ATR_CAP"
        atr_cap_triggered = True
    else:
        stop_loss = sl_base

    risk = entry - stop_loss
    if risk <= 0:
        risk = atr  # safety fallback

    # ── Profit Targets ───────────────────────────────────────
    # TP1: nearest HVN or S/R above entry
    tp1_candidates: list[float] = []

    # From resistance levels
    for sr in resistance_levels:
        if sr.price > entry:
            tp1_candidates.append(sr.price)

    # From VP HVNs
    if vp and vp.hvns:
        for hvn in vp.hvns:
            if hvn > entry:
                tp1_candidates.append(hvn)

    if tp1_candidates:
        tp1 = min(tp1_candidates)  # nearest above entry
        # Ensure TP1 provides at least the minimum R:R
        if risk > 0 and (tp1 - entry) / risk < cfg.MIN_RR_RATIO:
            tp1 = entry + cfg.MIN_RR_RATIO * risk
    else:
        tp1 = entry + 1.5 * risk   # fallback to 1.5R

    tp2 = entry + 2.0 * risk
    tp3 = entry + 3.0 * risk

    # ── R:R Validation ───────────────────────────────────────
    rr_tp1 = (tp1 - entry) / risk if risk > 0 else 0
    rr_valid = rr_tp1 >= cfg.MIN_RR_RATIO

    # ── Position Sizing ──────────────────────────────────────
    if setup.verdict == Verdict.HIGH_CONVICTION:
        risk_pct = cfg.RISK_HIGH_CONVICTION
    elif setup.verdict == Verdict.VALID:
        risk_pct = cfg.RISK_VALID
    elif setup.verdict == Verdict.MARGINAL:
        risk_pct = cfg.RISK_MARGINAL
    else:
        risk_pct = 0.0  # no position for WEAK / INVALIDATED

    dollar_risk = min(account_size * risk_pct, cfg.MAX_LOSS_PER_TRADE)
    position_shares = int(dollar_risk / risk) if risk > 0 else 0
    position_notional = position_shares * entry
    max_notional = account_size * cfg.MAX_POSITION_NOTIONAL_PCT
    if position_notional > max_notional:
        position_shares = int(max_notional / entry) if entry > 0 else 0
        position_notional = position_shares * entry
        logger.warning(
            "Position capped by notional limit: %d shares @ $%.2f = $%.0f (max $%.0f)",
            position_shares, entry, position_notional, max_notional,
        )

    params = TradeParams(
        entry=round(entry, 2),
        stop_loss=round(stop_loss, 2),
        risk=round(risk, 2),
        tp1=round(tp1, 2),
        tp2=round(tp2, 2),
        tp3=round(tp3, 2),
        rr_tp1=round(rr_tp1, 2),
        rr_tp2=2.0,
        rr_tp3=3.0,
        position_shares=position_shares,
        position_notional=round(position_notional, 2),
        risk_pct=risk_pct,
        rr_valid=rr_valid,
        account_size=account_size,
        sl_method=sl_method,
        sl_structural_level=round(sl_base, 2),
        atr_cap_triggered=atr_cap_triggered,
    )

    logger.info(
        "Trade params: Entry=%.2f  SL=%.2f  TP1=%.2f  R:R=%.2f  Shares=%d  $%.0f",
        params.entry, params.stop_loss, params.tp1,
        params.rr_tp1, params.position_shares, params.position_notional,
    )
    return params
