"""
SwingScope Setup Classifier
=============================
Evaluates the current market state against 5 swing trading setup types,
scores each setup using the 7-factor validity system (Section 9), applies
hard invalidation gates and context modifiers, and returns a ranked list
of ``SetupResult`` objects.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd
from scipy.stats import linregress

import config as cfg
from analysis.fibonacci import FibResult
from analysis.patterns import PatternMatch, PatternSignal
from analysis.structure import SRLevel, StructureResult, SwingPoint, Trend
from indicators.volume_profile import VolumeProfile

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Data types
# ──────────────────────────────────────────────────────────────
class SetupType(str, Enum):
    EMA_PULLBACK = "EMA Pullback"
    BREAKOUT = "Breakout from Base"
    BULL_FLAG = "Bull Flag / Pennant"
    VP_REVERSAL = "Volume Profile Reversal"
    FIB_PULLBACK = "Fibonacci Pullback"


class Verdict(str, Enum):
    HIGH_CONVICTION = "HIGH CONVICTION"
    VALID = "VALID SETUP"
    MARGINAL = "MARGINAL"
    WEAK = "WEAK"
    INVALIDATED = "INVALIDATED"


@dataclass
class ScoreFactor:
    """One row in the 7-factor scoring table."""
    name: str
    max_pts: int
    earned: int
    detail: str = ""


@dataclass
class SetupResult:
    """Complete output for one evaluated setup."""
    setup_type: SetupType
    direction: str = "LONG"
    raw_score: int = 0
    context_modifier: int = 0
    final_score: int = 0
    verdict: Verdict = Verdict.INVALIDATED
    factors: list[ScoreFactor] = field(default_factory=list)
    invalidation_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    hard_invalidated: bool = False

    # Thesis variables
    rvol_avg: float = 1.0
    rsi: float = 50.0
    macd_state: str = "flattening"


# ──────────────────────────────────────────────────────────────
# Shared scoring helpers
# ──────────────────────────────────────────────────────────────
def _score_trend(trend: Trend) -> ScoreFactor:
    """Score factor 1 — Trend Alignment (max 30)."""
    mapping = {
        Trend.STRONG_UPTREND: (20, "10/20/50 SMAs stacked & rising"),
        Trend.UPTREND:        (15, "Above SMA50 rising"),
        Trend.WEAK_UPTREND:   (8, "Above SMA50 flat/falling"),
        Trend.RANGE:          (3,  "Mixed / ranging"),
        Trend.DOWNTREND:      (0,  "Below SMA50 — HARD STOP"),
    }
    pts, detail = mapping.get(trend, (0, "Unknown"))
    return ScoreFactor("Trend Alignment", cfg.SCORE_TREND_MAX, pts, detail)


def _score_pattern(patterns: list[PatternMatch]) -> ScoreFactor:
    """Score factor 2 — Candlestick Pattern (max 20)."""
    confirmed = [p for p in patterns if p.confirmed]
    if confirmed:
        return ScoreFactor("Candlestick Pattern", cfg.SCORE_PATTERN_MAX, 20,
                           f"{confirmed[0].name} at structure")
    if patterns:
        return ScoreFactor("Candlestick Pattern", cfg.SCORE_PATTERN_MAX, 10,
                           f"{patterns[0].name} — weak context")
    return ScoreFactor("Candlestick Pattern", cfg.SCORE_PATTERN_MAX, 0, "No pattern")


def _score_rvol(df: pd.DataFrame) -> ScoreFactor:
    """Score factor 3 — Volume RVol (max 15)."""
    if "RVOL" not in df.columns or len(df) < 3:
        return ScoreFactor("Volume — RVol", cfg.SCORE_RVOL_MAX, 0, "No RVol data")

    rvol_last = float(df["RVOL"].iloc[-1])
    # Check pullback dryness (prior bars) and reversal spike (last bar)
    rvol_prior = df["RVOL"].iloc[-4:-1].mean() if len(df) >= 4 else rvol_last
    dry = rvol_prior < 0.8
    spike = rvol_last > 1.3

    if dry and spike:
        return ScoreFactor("Volume — RVol", cfg.SCORE_RVOL_MAX, 15,
                           f"Dry pullback ({rvol_prior:.2f}) + spike ({rvol_last:.2f})")
    if dry or spike:
        detail = f"Dry pullback ({rvol_prior:.2f})" if dry else f"Spike ({rvol_last:.2f})"
        return ScoreFactor("Volume — RVol", cfg.SCORE_RVOL_MAX, 8, detail)
    return ScoreFactor("Volume — RVol", cfg.SCORE_RVOL_MAX, 0,
                       f"No confirmation (prior={rvol_prior:.2f}, last={rvol_last:.2f})")


def score_rsi_context(rsi: float, direction: str = "LONG") -> tuple[int, str, bool, str]:
    """Returns (points, label, is_invalid, warning_flag)."""
    if rsi < 35:
        return 0, "INVALIDATED_OVERSOLD", True, ""
    elif 35 <= rsi < 40:
        return 7, "DEEP_FLUSH", False, "DEEP_FLUSH_RSI"
    elif 40 <= rsi <= 58:
        return 15, "IDEAL_RESET", False, ""
    elif 58 < rsi <= 65:
        return 5, "INSUFFICIENT_RESET", False, ""
    else:
        return 0, "INVALIDATED_OVERBOUGHT", True, ""


def _score_rsi(df: pd.DataFrame) -> ScoreFactor:
    """Score factor 4 — RSI Context (max 15)."""
    if "RSI_14" not in df.columns:
        return ScoreFactor("RSI Context", cfg.SCORE_RSI_MAX, 0, "No RSI")
    rsi = float(df["RSI_14"].iloc[-1])
    pts, label, _, _ = score_rsi_context(rsi, "LONG")
    return ScoreFactor("RSI Context", cfg.SCORE_RSI_MAX, pts, f"{label} ({rsi:.1f})")


def _score_obv(df: pd.DataFrame) -> ScoreFactor:
    """Score factor 5 — OBV Conviction (max 10)."""
    if "OBV" not in df.columns or len(df) < 20:
        return ScoreFactor("OBV Conviction", cfg.SCORE_OBV_MAX, 0, "No OBV data")

    obv = df["OBV"].iloc[-20:]
    obv_trend = np.polyfit(range(len(obv)), obv.values, 1)[0]

    # Check for bearish divergence: price up but OBV down
    price_trend = np.polyfit(range(len(obv)), df["Close"].iloc[-20:].values, 1)[0]
    divergence = price_trend > 0 and obv_trend < 0

    if divergence:
        return ScoreFactor("OBV Conviction", cfg.SCORE_OBV_MAX, 0,
                           "Bearish divergence ⚠")
    if obv_trend > 0:
        return ScoreFactor("OBV Conviction", cfg.SCORE_OBV_MAX, 10, "OBV trending up")
    return ScoreFactor("OBV Conviction", cfg.SCORE_OBV_MAX, 5, "Flat / neutral")


def get_macd_histogram_state(df: pd.DataFrame) -> str:
    """Returns the MACD histogram momentum state."""
    if "MACD_hist" not in df.columns or len(df) < 3:
        return "UNKNOWN"
        
    hist_now = float(df["MACD_hist"].iloc[-1])
    hist_prev = float(df["MACD_hist"].iloc[-2])
    hist_prev2 = float(df["MACD_hist"].iloc[-3])
    
    # CONFIRMED_BOTTOM: Negative, but slope has been increasing for 2+ bars
    if hist_now < 0 and hist_now > hist_prev and hist_prev > hist_prev2:
        return "CONFIRMED_BOTTOM"
        
    # ZERO_CROSS: Crossed from negative to positive on this bar
    if hist_now >= 0 and hist_prev < 0:
        return "ZERO_CROSS"
        
    # EARLY_TURN: Negative, turned up on this bar (1 bar only)
    if hist_now < 0 and hist_now > hist_prev and hist_prev <= hist_prev2:
        return "EARLY_TURN"
        
    # STILL_FALLING: Negative and slope is decreasing/flat
    if hist_now < 0 and hist_now <= hist_prev:
        return "STILL_FALLING"
        
    if hist_now >= 0:
        return "POSITIVE"
        
    return "UNKNOWN"

def _score_macd(df: pd.DataFrame) -> ScoreFactor:
    """Score factor 6 — MACD Confluence (max 10)."""
    state = get_macd_histogram_state(df)
    
    if state in ("CONFIRMED_BOTTOM", "ZERO_CROSS", "POSITIVE"):
        return ScoreFactor("MACD Confluence", cfg.SCORE_MACD_MAX, 10, state)
    elif state == "EARLY_TURN":
        return ScoreFactor("MACD Confluence", cfg.SCORE_MACD_MAX, 5, state)
    else:
        return ScoreFactor("MACD Confluence", cfg.SCORE_MACD_MAX, 0, state)


def _score_vp_confluence(
    current_price: float,
    vp: Optional[VolumeProfile],
    atr: float,
) -> ScoreFactor:
    """Score factor 7 — VP Confluence (max 10)."""
    if vp is None or atr <= 0:
        return ScoreFactor("VP Confluence", cfg.SCORE_VP_MAX, 0, "No VP data")

    key_levels = [vp.poc, vp.vah, vp.val] + vp.hvns
    near_thresh = cfg.VP_PROXIMITY_ATR * atr
    far_thresh = 1.0 * atr

    for lv in key_levels:
        dist = abs(current_price - lv)
        if dist <= near_thresh:
            return ScoreFactor("VP Confluence", cfg.SCORE_VP_MAX, 20,
                               f"At VP level ({lv:.2f})")
        if dist <= far_thresh:
            return ScoreFactor("VP Confluence", cfg.SCORE_VP_MAX, 10,
                               f"Near VP level ({lv:.2f})")

    return ScoreFactor("VP Confluence", cfg.SCORE_VP_MAX, 0, "No VP proximity")


# ──────────────────────────────────────────────────────────────
# Setup-specific requirement checks
# ──────────────────────────────────────────────────────────────
def get_pullback_window(df: pd.DataFrame, structure: StructureResult) -> int:
    """Returns count of consecutive bars since last swing high."""
    if not structure.swing_highs:
        return min(len(df), 10)
    last_high_idx = structure.swing_highs[-1].idx
    bars_since = len(df) - 1 - last_high_idx
    return max(1, bars_since)

def check_pullback_volume(df: pd.DataFrame, structure: StructureResult, threshold: float = 0.90) -> tuple[bool, float]:
    """Calculates avg RVol over the full pullback window (not just last bar)."""
    window = get_pullback_window(df, structure)
    if "RVOL" not in df.columns or len(df) < window + 1:
        return False, 1.0
    if window > 1:
        avg_rvol = float(df["RVOL"].iloc[-(window+1):-1].mean())
    else:
        avg_rvol = float(df["RVOL"].iloc[-1])
    return avg_rvol <= threshold, avg_rvol

def check_bb_squeeze(df: pd.DataFrame) -> tuple[bool, int, float]:
    """Returns (is_squeeze, squeeze_duration_bars, width_ratio)."""
    if "BB_width" not in df.columns or len(df) < 60:
        return False, 0, 999.0
    
    bb_width_now = float(df["BB_width"].iloc[-1])
    bb_width_min = float(df["BB_width"].iloc[-60:].min())
    width_ratio = bb_width_now / bb_width_min if bb_width_min > 0 else 999.0
    is_squeeze = width_ratio <= cfg.BB_SQUEEZE_THRESHOLD
    
    squeeze_duration = 0
    if is_squeeze:
        threshold_val = bb_width_min * cfg.BB_SQUEEZE_THRESHOLD
        for width in reversed(df["BB_width"].iloc[-60:].values):
            if width <= threshold_val:    
                squeeze_duration += 1
            else:
                break
                
    return is_squeeze, squeeze_duration, width_ratio

def check_flag_volume_declining(df: pd.DataFrame, flag_length: int) -> tuple[bool, float]:
    """Returns (is_declining, slope_pct) using linear regression over flag period."""
    if "RVOL" not in df.columns or len(df) < flag_length:
        return False, 0.0
    
    rvol_data = df["RVOL"].iloc[-flag_length:].values
    slope, _, _, _, _ = linregress(range(flag_length), rvol_data)
    
    is_declining = slope < 0
    return is_declining, float(slope)

def _check_ema_pullback(df: pd.DataFrame, patterns: list[PatternMatch], structure: StructureResult) -> tuple[bool, list[str], list[str], list[str]]:
    """Return (is_valid, hard_reasons, soft_reasons, warnings) for Setup 1."""
    hard_reasons, soft_reasons, warnings = [], [], []
    last = df.iloc[-1]
    close, ema50, ema200 = float(last["Close"]), float(last["EMA_50"]), float(last["EMA_200"])
    if close < ema50:
        hard_reasons.append("Close below EMA50")
    if close < ema200:
        hard_reasons.append("Close below EMA200")

    rsi = float(last["RSI_14"]) if "RSI_14" in df.columns else 50
    _, rsi_label, is_invalid, rsi_warn = score_rsi_context(rsi, "LONG")
    if is_invalid:
        hard_reasons.append(f"RSI {rsi_label} ({rsi:.1f})")
    elif rsi_label == "INSUFFICIENT_RESET":
        soft_reasons.append(f"RSI INSUFFICIENT_RESET ({rsi:.1f})")
    if rsi_warn:
        warnings.append(rsi_warn)

    macd_state = get_macd_histogram_state(df)
    if macd_state == "STILL_FALLING":
        hard_reasons.append("MACD histogram STILL_FALLING")

    confirmed_patterns = [p for p in patterns if p.confirmed]
    if not confirmed_patterns:
        hard_reasons.append("No confirmed candlestick reversal pattern")

    # Proximity to EMA21 or EMA50 (scored via factor, not binary killed here)
    atr = float(last["ATR_14"]) if "ATR_14" in df.columns else 1
    ema21 = float(last["EMA_21"])
    near = min(abs(close - ema21), abs(close - ema50)) <= cfg.EMA_PULLBACK_ATR_PROXIMITY * atr
    if not near:
        soft_reasons.append("Not near EMA21/EMA50")

    rvol = float(last["RVOL"]) if "RVOL" in df.columns else 1
    if rvol > cfg.EMA_PULLBACK_RVOL_MAX:
        # Check if high-vol through EMA (invalidation)
        if close < ema21:
            hard_reasons.append(f"High volume through EMA (RVol={rvol:.2f})")
            
    is_dry, avg_rvol = check_pullback_volume(df, structure, threshold=0.90)
    if not is_dry:
        soft_reasons.append(f"Pullback volume not dry (avg RVol={avg_rvol:.2f})")

    return len(hard_reasons) == 0, hard_reasons, soft_reasons, warnings


def _check_breakout(df: pd.DataFrame, structure: StructureResult, vp: Optional[VolumeProfile]) -> tuple[bool, list[str], list[str], list[str]]:
    """Return (is_valid, hard_reasons, soft_reasons, warnings) for Setup 2."""
    hard_reasons, soft_reasons, warnings = [], [], []
    last = df.iloc[-1]
    atr = float(last["ATR_14"]) if "ATR_14" in df.columns else 1

    # ATR contraction
    if len(df) >= 20 and "ATR_14" in df.columns:
        atr_now = float(df["ATR_14"].iloc[-1])
        atr_past = float(df["ATR_14"].iloc[-20])
        if atr_past > 0:
            contraction = 1.0 - (atr_now / atr_past)
            if contraction < cfg.BREAKOUT_ATR_CONTRACTION_PCT:
                soft_reasons.append(f"ATR contraction only {contraction:.0%}")

    # Price near resistance
    if structure.resistance_levels:
        nearest_r = min(structure.resistance_levels, key=lambda x: abs(x.price - float(last["Close"])))
        dist_pct = abs(float(last["Close"]) - nearest_r.price) / nearest_r.price if nearest_r.price != 0 else 0
        if dist_pct > cfg.BREAKOUT_COIL_PCT:
            soft_reasons.append(f"Not coiling near resistance ({dist_pct:.1%} away)")

    # ── VCP Audit (Tightening & Volume Dry-up) ───────────────
    vcp_valid, vcp_detail = check_vcp_validity(df, structure)
    if not vcp_valid:
        soft_reasons.append(f"VCP Audit Failed: {vcp_detail}")
    else:
        warnings.append(f"VCP_VALID: {vcp_detail}")

    rvol = float(last["RVOL"]) if "RVOL" in df.columns else 1
    if rvol < cfg.BREAKOUT_RVOL_EXPANSION:
        hard_reasons.append(f"Breakout on low volume (RVol={rvol:.2f})")

    # Bollinger Band Squeeze (Coiling)
    if "BB_width" in df.columns and len(df) >= 60:
        is_squeeze, squeeze_duration, _ = check_bb_squeeze(df)
        if not is_squeeze:
            soft_reasons.append("Bollinger Band width not tightly squeezed")
        elif squeeze_duration < cfg.BB_SQUEEZE_MIN_BARS:
            warnings.append("SQUEEZE_YOUNG")

    if "MACD" in df.columns:
        macd_val = float(last["MACD"])
        if macd_val <= 0:
            hard_reasons.append(f"MACD below zero ({macd_val:.2f})")

    rsi = float(last["RSI_14"]) if "RSI_14" in df.columns else 50
    if rsi > cfg.BREAKOUT_RSI_CEILING:
        hard_reasons.append(f"RSI too high ({rsi:.1f})")

    # Major HVN above
    if vp and vp.hvns:
        close = float(last["Close"])
        hvns_above = [h for h in vp.hvns if h > close and abs(h - close) < 2 * atr]
        if hvns_above:
            hard_reasons.append(f"Major HVN immediately above ({hvns_above[0]:.2f})")

    return len(hard_reasons) == 0, hard_reasons, soft_reasons, warnings


def _check_bull_flag(df: pd.DataFrame) -> tuple[bool, list[str], list[str], list[str]]:
    """Return (is_valid, hard_reasons, soft_reasons, warnings) for Setup 3."""
    hard_reasons, soft_reasons, warnings = [], [], []
    if len(df) < 25:
        hard_reasons.append("Insufficient data for flag detection")
        return False, hard_reasons, soft_reasons, warnings

    last = df.iloc[-1]
    close = float(last["Close"])

    # Look for impulse leg in the last 25 bars
    found_flag = False
    flag_length = 5
    for start_idx in range(len(df) - 25, len(df) - 10):
        if start_idx < 0:
            continue
        for end_idx in range(start_idx + 1, min(start_idx + cfg.FLAG_IMPULSE_MAX_BARS + 1, len(df) - 5)):
            start_price = float(df["Close"].iloc[start_idx])
            end_price = float(df["Close"].iloc[end_idx])
            if start_price == 0:
                continue
            gain = (end_price - start_price) / start_price
            if gain >= cfg.FLAG_IMPULSE_MIN_PCT:
                # Found impulse — check pullback
                remaining_bars = len(df) - 1 - end_idx
                if cfg.FLAG_PULLBACK_MIN_BARS <= remaining_bars <= cfg.FLAG_PULLBACK_MAX_BARS:
                    pullback_low = float(df["Low"].iloc[end_idx:].min())
                    retracement = (end_price - pullback_low) / (end_price - start_price) if end_price != start_price else 1
                    if retracement <= cfg.FLAG_PULLBACK_MAX_FIB:
                        found_flag = True
                        flag_length = remaining_bars
                        break
        if found_flag:
            break

    if not found_flag:
        hard_reasons.append("No valid flag pattern detected")
        return False, hard_reasons, soft_reasons, warnings

    ema21 = float(last["EMA_21"]) if "EMA_21" in df.columns else close
    if close < ema21:
        hard_reasons.append("Price below EMA21 during flag")

    if "MACD_hist" in df.columns and "MACD" in df.columns and "MACD_signal" in df.columns:
        macd_val = float(last["MACD"])
        signal_val = float(last["MACD_signal"])
        hist_val = float(last["MACD_hist"])
        if macd_val <= signal_val:
            hard_reasons.append("MACD below signal line")
        if hist_val <= 0:
            hard_reasons.append("MACD histogram negative")

    if len(df) >= flag_length:
        is_declining, slope = check_flag_volume_declining(df, flag_length)
        if not is_declining:
            soft_reasons.append(f"Volume expanding in pullback (slope={slope:.3f})")

    rsi = float(last["RSI_14"]) if "RSI_14" in df.columns else 50
    if rsi > cfg.FLAG_RSI_CEILING:
        hard_reasons.append(f"RSI too high at entry ({rsi:.1f})")

    return len(hard_reasons) == 0, hard_reasons, soft_reasons, warnings


def _check_vp_reversal(
    df: pd.DataFrame,
    vp: Optional[VolumeProfile],
    patterns: list[PatternMatch],
    fib: Optional[FibResult],
    weekly_trend: Optional[Trend],
) -> tuple[bool, list[str], list[str], list[str]]:
    """Return (is_valid, hard_reasons, soft_reasons, warnings) for Setup 4."""
    hard_reasons, soft_reasons, warnings = [], [], []
    if vp is None:
        hard_reasons.append("No volume profile data")
        return False, hard_reasons, soft_reasons, warnings

    last = df.iloc[-1]
    close = float(last["Close"])
    atr = float(last["ATR_14"]) if "ATR_14" in df.columns else 1

    # Price at VP level
    key_vp = [vp.poc, vp.vah, vp.val] + vp.hvns
    near = any(abs(close - lv) <= cfg.VP_PROXIMITY_ATR * atr for lv in key_vp)
    if not near:
        soft_reasons.append("Not at a VP key level")

    # Reversal candlestick
    confirmed_patterns = [p for p in patterns if p.confirmed]
    if not confirmed_patterns:
        hard_reasons.append("No confirmed candlestick at VP level")

    # RSI extreme
    rsi = float(last["RSI_14"]) if "RSI_14" in df.columns else 50
    if not (rsi <= cfg.VP_REV_RSI_LONG_CEIL or rsi >= cfg.VP_REV_RSI_SHORT_FLOOR):
        soft_reasons.append(f"RSI not at extreme ({rsi:.1f})")

    # RVol spike
    rvol = float(last["RVOL"]) if "RVOL" in df.columns else 1
    if rvol < cfg.VP_REV_RVOL_MIN:
        soft_reasons.append(f"No RVol spike ({rvol:.2f})")

    # LVN check (price in void = no support)
    if vp.lvns:
        in_lvn = any(abs(close - lv) <= 0.3 * atr for lv in vp.lvns)
        if in_lvn:
            hard_reasons.append("Price in LVN void — no support")

    # Fibonacci confluence
    if fib:
        has_fib_confluence = False
        for lv in fib.levels:
            if lv.ratio in (0.382, 0.500, 0.618):
                if abs(close - lv.price) <= 1.0 * atr:
                    has_fib_confluence = True
                    break
        if not has_fib_confluence:
            soft_reasons.append("No Fibonacci confluence at VP level")
    else:
        soft_reasons.append("No Fibonacci data for confluence check")

    # Weekly trend opposing
    if weekly_trend in (Trend.DOWNTREND,):
        hard_reasons.append("Weekly trend opposing")

    return len(hard_reasons) == 0, hard_reasons, soft_reasons, warnings


def _check_fib_pullback(
    df: pd.DataFrame,
    fib: Optional[FibResult],
    vp: Optional[VolumeProfile],
    weekly_trend: Optional[Trend],
) -> tuple[bool, list[str], list[str], list[str]]:
    """Return (is_valid, hard_reasons, soft_reasons, warnings) for Setup 5."""
    hard_reasons, soft_reasons, warnings = [], [], []
    if fib is None:
        hard_reasons.append("No Fibonacci data")
        return False, hard_reasons, soft_reasons, warnings

    last = df.iloc[-1]
    close = float(last["Close"])
    atr = float(last["ATR_14"]) if "ATR_14" in df.columns else 1

    # Check if price is at a Fibonacci level
    at_fib = False
    for lv in fib.levels:
        if lv.ratio in (0.382, 0.500, 0.618):
            if abs(close - lv.price) <= 1.0 * atr:
                at_fib = True
                break
    if not at_fib:
        soft_reasons.append("Not at a key Fibonacci level")

    # Check for VP/EMA confluence
    has_confluence = False
    if vp:
        for vp_lv in [vp.poc, vp.vah, vp.val] + vp.hvns:
            if abs(close - vp_lv) <= 1.0 * atr:
                has_confluence = True
                break
    ema21 = float(last["EMA_21"]) if "EMA_21" in df.columns else close
    ema50 = float(last["EMA_50"]) if "EMA_50" in df.columns else close
    if abs(close - ema21) <= 1.0 * atr or abs(close - ema50) <= 1.0 * atr:
        has_confluence = True
    if not has_confluence:
        soft_reasons.append("No VP/EMA confluence at Fib level")

    # RSI zone
    rsi = float(last["RSI_14"]) if "RSI_14" in df.columns else 50
    if not (cfg.FIB_RSI_LOW <= rsi <= cfg.FIB_RSI_HIGH):
        soft_reasons.append(f"RSI out of zone ({rsi:.1f})")

    # Max retracement check
    retracement = abs(close - fib.swing_high) / abs(fib.swing_high - fib.swing_low) if fib.swing_high != fib.swing_low else 1
    if retracement > cfg.FIB_MAX_RETRACEMENT:
        hard_reasons.append(f"Retracement too deep ({retracement:.1%})")

    # MACD histogram state
    macd_state = get_macd_histogram_state(df)
    if macd_state == "STILL_FALLING":
        hard_reasons.append("MACD histogram STILL_FALLING")

    # Weekly trend
    if weekly_trend in (Trend.DOWNTREND,):
        hard_reasons.append("Weekly trend opposing")

    return len(hard_reasons) == 0, hard_reasons, soft_reasons, warnings


def check_vcp_validity(
    df: pd.DataFrame,
    structure: StructureResult,
    min_waves: int = 2,
) -> tuple[bool, str]:
    """Detect Volatility Contraction Patterns (VCP).

    Checks for:
    1. Tightening price ranges from left to right (decreasing wave amplitude).
    2. Volume dry-up on the right side of the base.

    Returns (is_vcp_valid, detail_string).
    """
    # Merge all swings and sort chronologically
    all_swings = structure.swing_highs + structure.swing_lows
    all_swings.sort(key=lambda s: s.idx)

    if len(all_swings) < 4:
        return False, "Insufficient swings for VCP audit"

    # Extract wave amplitudes: distance between consecutive opposite swings
    waves = []
    for i in range(1, len(all_swings)):
        if all_swings[i].kind != all_swings[i - 1].kind:
            amp = abs(all_swings[i].price - all_swings[i - 1].price)
            waves.append(amp)

    if len(waves) < min_waves:
        return False, f"Only {len(waves)} wave(s) — need {min_waves}+"

    # Check recent waves for tightening (each <= 110% of the previous, i.e. decreasing)
    recent = waves[-min(4, len(waves)):]
    is_tightening = all(recent[i] <= recent[i - 1] * 1.10 for i in range(1, len(recent)))

    # Check volume dry-up on the right side of the base
    vol_dry = False
    if len(df) >= 10 and "Volume" in df.columns:
        vol_right = float(df["Volume"].iloc[-5:].mean())
        vol_left = float(df["Volume"].iloc[-10:-5].mean())
        vol_dry = vol_left > 0 and vol_right < vol_left

    wave_str = ", ".join([f"{w:.2f}" for w in recent])
    if is_tightening and vol_dry:
        return True, f"Tightening waves ({wave_str}) + Vol dry-up"
    elif is_tightening:
        return True, f"Price tightening ({wave_str}), vol not yet dry"

    return False, f"Erratic ranges ({wave_str})"


# ──────────────────────────────────────────────────────────────
# Guardrail helpers
# ──────────────────────────────────────────────────────────────
def check_weekly_distribution_wicks(
    weekly_df: Optional[pd.DataFrame],
    lookback: int = 8,
    wick_ratio_threshold: float = 0.60,
    min_occurrences: int = 2,
) -> tuple[bool, int]:
    """Detect heavy upper wicks on the weekly chart (institutional distribution).

    Returns (is_distribution, count_of_heavy_wick_bars).
    A wick is "heavy" when the upper wick is >= wick_ratio_threshold of the
    total candle range (High - Low).
    """
    if weekly_df is None or len(weekly_df) < lookback:
        return False, 0

    recent = weekly_df.iloc[-lookback:]
    count = 0
    for _, bar in recent.iterrows():
        rng = float(bar["High"]) - float(bar["Low"])
        if rng <= 0:
            continue
        upper_wick = float(bar["High"]) - max(float(bar["Open"]), float(bar["Close"]))
        if upper_wick / rng >= wick_ratio_threshold:
            count += 1

    return count >= min_occurrences, count


def check_ema_whipsaw(
    df: pd.DataFrame,
    lookback: int = 15,
    threshold: int = 5,
) -> tuple[bool, int]:
    """Count how many times price crossed EMA_21 in the last *lookback* bars.

    Returns (is_chaotic, cross_count).  Chaotic if cross_count >= threshold.
    """
    if "EMA_21" not in df.columns or len(df) < lookback + 1:
        return False, 0

    recent = df.iloc[-(lookback + 1):]
    crosses = 0
    for i in range(1, len(recent)):
        prev_close = float(recent["Close"].iloc[i - 1])
        curr_close = float(recent["Close"].iloc[i])
        prev_ema = float(recent["EMA_21"].iloc[i - 1])
        curr_ema = float(recent["EMA_21"].iloc[i])
        # A cross occurs when the close changes side relative to EMA
        if (prev_close >= prev_ema and curr_close < curr_ema) or \
           (prev_close < prev_ema and curr_close >= curr_ema):
            crosses += 1

    return crosses >= threshold, crosses


def check_rsi_slope(
    df: pd.DataFrame,
    lookback: int = 5,
) -> tuple[bool, float]:
    """Check if RSI is rising over the last *lookback* bars.

    Returns (is_rising, slope).  Slope > 0 means momentum is returning.
    """
    if "RSI_14" not in df.columns or len(df) < lookback:
        return True, 0.0  # Default to True if no data

    rsi_data = df["RSI_14"].iloc[-lookback:].values
    slope = float(np.polyfit(range(lookback), rsi_data, 1)[0])
    return slope > 0, slope


# ──────────────────────────────────────────────────────────────
# Verdict mapper
# ──────────────────────────────────────────────────────────────
def _map_verdict(score: int) -> Verdict:
    if score >= cfg.SCORE_HIGH_CONVICTION:
        return Verdict.HIGH_CONVICTION
    if score >= cfg.SCORE_VALID:
        return Verdict.VALID
    if score >= cfg.SCORE_MARGINAL:
        return Verdict.MARGINAL
    if score >= cfg.SCORE_WEAK:
        return Verdict.WEAK
    return Verdict.INVALIDATED


# ──────────────────────────────────────────────────────────────
# Main classifier
# ──────────────────────────────────────────────────────────────
def classify_setups(
    df: pd.DataFrame,
    structure: StructureResult,
    patterns: list[PatternMatch],
    vp: Optional[VolumeProfile],
    fib: Optional[FibResult],
    context_modifier: int = 0,
    weekly_trend: Optional[Trend] = None,
    weekly_df: Optional[pd.DataFrame] = None,
    debt_to_equity: float = 0.0,
    price_momentum_grade: int = 3,
    sector_rs_direction: str = "Neutral",
) -> list[SetupResult]:
    """Evaluate all 5 setups and return ranked results.

    Hard invalidation gates (Section 9.4) are checked **first**.  If any
    gate fires, the setup is immediately marked ``INVALIDATED``.

    Parameters
    ----------
    df : pd.DataFrame
        Enriched OHLCV DataFrame.
    structure : StructureResult
        Output of ``analyze_structure``.
    patterns : list[PatternMatch]
        Detected candlestick patterns.
    vp : VolumeProfile or None
        Volume profile data.
    fib : FibResult or None
        Fibonacci retracement data.
    context_modifier : int
        Sum of all context modifiers (sector + earnings + news).
    weekly_trend : Trend or None
        Weekly timeframe trend for multi-TF checks.

    Returns
    -------
    list[SetupResult]
        All 5 setup evaluations, sorted by final score descending.
    """
    last = df.iloc[-1]
    current_price = float(last["Close"])
    atr = float(last["ATR_14"]) if "ATR_14" in df.columns else 1.0

    # ── Universal hard invalidation gates ────────────────────
    hard_gates: list[str] = []
    if structure.trend == Trend.DOWNTREND:
        hard_gates.append(f"Price below EMA50 — NO LONG SETUP")
        
    # Sector RS Validation
    if sector_rs_direction == "Uptrend":
        context_modifier += 5
    elif sector_rs_direction == "Downtrend":
        context_modifier -= 10
        
    # D/E Ratio Gate
    if debt_to_equity > 2.0:
        # Check if exceptional VP and Trend
        # Note: We don't have the scores yet, so we will append to hard gates later if condition fails.
        # But we can just enforce the penalty for now, and apply the hard gate check after scores are computed.
        pass
    elif debt_to_equity > 1.0:
        context_modifier -= 8
        
    # Price Momentum Grade Gate
    if price_momentum_grade == 5:
        context_modifier += 5
    elif price_momentum_grade == 4:
        context_modifier += 3
    elif price_momentum_grade == 2:
        context_modifier -= 5

    # OBV divergence (computed in scorer, but we flag it here too)
    if "OBV" in df.columns and len(df) >= 20:
        obv_slope = np.polyfit(range(20), df["OBV"].iloc[-20:].values, 1)[0]
        price_slope = np.polyfit(range(20), df["Close"].iloc[-20:].values, 1)[0]
        if price_slope > 0 and obv_slope < 0:
            hard_gates.append("OBV bearish divergence detected")

    # ── Guardrail: Weekly Distribution Wicks ──────────────────
    is_distribution, wick_count = check_weekly_distribution_wicks(weekly_df)
    if is_distribution:
        context_modifier -= 15
        logger.info("GUARDRAIL: Weekly distribution wicks detected (%d bars) → -15 pts", wick_count)

    # ── Guardrail: EMA Whipsaw Detector ───────────────────────
    is_chaotic, cross_count = check_ema_whipsaw(df)
    if is_chaotic:
        context_modifier -= 10
        logger.info("GUARDRAIL: EMA whipsaw detected (%d crosses in 15 bars) → -10 pts", cross_count)

    # ── Guardrail: RSI Slope Gate ─────────────────────────────
    rsi_val_current = float(last.get("RSI_14", 50.0))
    rsi_rising, rsi_slope = check_rsi_slope(df)
    if not rsi_rising and 40 <= rsi_val_current <= 58:
        # RSI is in the "ideal reset" zone but momentum is still falling
        context_modifier -= 5
        logger.info("GUARDRAIL: RSI in reset zone but slope negative (%.2f) → -5 pts", rsi_slope)

    # ── Deterministic Thesis Variables ────────────────────────
    rsi_val = float(last.get("RSI_14", 50.0))
    macd_state_val = get_macd_histogram_state(df)
    
    # We want the exact pullback volume calculation for the thesis text,
    # falling back to average rvol if check_pullback_volume is irrelevant/fails.
    try:
        _, rvol_avg_val = check_pullback_volume(df, structure)
    except Exception:
        # Fallback to general rvol
        rvol_avg_val = float(df["RVOL"].iloc[-4:-1].mean()) if len(df) >= 4 else float(last.get("RVOL", 1.0))

    # ── Common scoring factors ───────────────────────────────
    f_trend = _score_trend(structure.trend)
    f_pattern = _score_pattern(patterns)
    f_rvol = _score_rvol(df)
    f_rsi = _score_rsi(df)
    f_obv = _score_obv(df)
    f_macd = _score_macd(df)
    f_vp = _score_vp_confluence(current_price, vp, atr)
    common_factors = [f_trend, f_pattern, f_rvol, f_rsi, f_obv, f_macd, f_vp]
    raw = sum(f.earned for f in common_factors)

    # Post-scoring Fundamental Gates
    if debt_to_equity > 2.0:
        if f_vp.earned < 16 or f_trend.earned < 15:
            hard_gates.append(f"HIGH LEVERAGE (D/E={debt_to_equity:.2f}) without exceptional VP/Trend")
        else:
            context_modifier -= 8
            
    if debt_to_equity > 1.0 and debt_to_equity <= 2.0:
        pass # Penalty already applied above, will add warning in per-setup evaluation
        
    # ── Per-setup evaluation ─────────────────────────────────
    setup_checks = {
        SetupType.EMA_PULLBACK: lambda: _check_ema_pullback(df, patterns, structure),
        SetupType.BREAKOUT: lambda: _check_breakout(df, structure, vp),
        SetupType.BULL_FLAG: lambda: _check_bull_flag(df),
        SetupType.VP_REVERSAL: lambda: _check_vp_reversal(df, vp, patterns, fib, weekly_trend),
        SetupType.FIB_PULLBACK: lambda: _check_fib_pullback(df, fib, vp, weekly_trend),
    }

    results = []
    for setup_type, checker in setup_checks.items():
        is_valid, hard_reasons, soft_reasons, checker_warnings = checker()
        all_reasons = hard_gates + hard_reasons + soft_reasons

        factors = [ScoreFactor(f.name, f.max_pts, f.earned, f.detail) for f in common_factors]
        final = max(0, min(100, raw + context_modifier))

        warnings: list[str] = list(checker_warnings)
        hard_inv = len(hard_gates) > 0 or len(hard_reasons) > 0

        # Hard kills: zero the score
        if hard_inv:
            final = 0
        # Soft kills: cap based on number of soft reasons
        elif soft_reasons:
            n = len(soft_reasons)
            if n >= 3:
                final = min(final, cfg.SCORE_WEAK - 1)
            elif n == 2:
                final = min(final, cfg.SCORE_MARGINAL - 1)
            elif n == 1:
                final = min(final, cfg.SCORE_VALID - 1)

        # Fundamental Warnings & Setup-specific Gates
        if debt_to_equity > 1.0:
            warnings.append(f"HIGH LEVERAGE (D/E={debt_to_equity:.2f}) — elevated structural risk")
        if price_momentum_grade == 2:
            warnings.append("Weak Price Momentum (Grade 2/5)")
        if price_momentum_grade == 1 and setup_type in (SetupType.FIB_PULLBACK, SetupType.BULL_FLAG, SetupType.EMA_PULLBACK):
            hard_reasons.append("Price Momentum Grade 1 — Strong downtrend, Trend Setup Rejected")
            final = 0
            hard_inv = True

        # Guardrail warnings (for report visibility)
        if is_distribution:
            warnings.append(f"WEEKLY DISTRIBUTION: {wick_count} heavy upper-wick bars — overhead supply")
        if is_chaotic:
            warnings.append(f"CHAOTIC ACTION: Price crossed EMA21 {cross_count}x in 15 bars — no clean trend")
        if not rsi_rising and 40 <= rsi_val_current <= 58:
            warnings.append(f"RSI FALLING IN RESET ZONE (slope={rsi_slope:.2f}) — momentum not returning")

        # Cap breakout on low RVol
        if setup_type == SetupType.BREAKOUT:
            rvol = float(last["RVOL"]) if "RVOL" in df.columns else 1
            if rvol < 0.5:
                final = min(final, 50)
                warnings.append(f"FALSE BREAKOUT warning — RVol={rvol:.2f}")
                
        # EMA Pullback Pass-Through Fix
        if setup_type == SetupType.EMA_PULLBACK and final < 40:
            hard_reasons.append(f"EMA Pullback score < 40 ({final}) — Pattern not validated")
            final = 0
            hard_inv = True
            
        # Compliance Gap Hard Gate
        if setup_type in (SetupType.FIB_PULLBACK, SetupType.BULL_FLAG) and final < 50:
            hard_reasons.append(f"REJECTED: Score {final}/100 is below the 50-point validity floor for {setup_type.value}.")
            final = 0
            hard_inv = True

        verdict = _map_verdict(final)

        results.append(SetupResult(
            setup_type=setup_type,
            direction="LONG",
            raw_score=raw,
            context_modifier=context_modifier,
            final_score=final,
            verdict=verdict,
            factors=factors,
            invalidation_reasons=all_reasons,
            warnings=warnings,
            hard_invalidated=hard_inv,
            
            # Thesis variables precisely calculated from setup engine
            rvol_avg=rvol_avg_val,
            rsi=rsi_val,
            macd_state=macd_state_val.lower().replace("_", " "),
        ))

    results.sort(key=lambda r: r.final_score, reverse=True)
    logger.info(
        "Setup classification: top=%s (score=%d, verdict=%s)",
        results[0].setup_type.value if results else "NONE",
        results[0].final_score if results else 0,
        results[0].verdict.value if results else "N/A",
    )
    return results
