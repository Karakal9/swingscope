"""
SwingScope Structure Analysis
==============================
Detects swing highs / lows, classifies the market trend regime, and maps
support / resistance levels with touch-count scoring and clustering.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd

from config import MAX_SR_LEVELS, SR_CLUSTER_PCT, SWING_LOOKBACK_BARS

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Enums / data classes
# ──────────────────────────────────────────────────────────────
class Trend(str, Enum):
    """Market trend regime labels (Section 6.2)."""

    STRONG_UPTREND = "STRONG_UPTREND"
    UPTREND = "UPTREND"
    WEAK_UPTREND = "WEAK_UPTREND"
    RANGE = "RANGE"
    DOWNTREND = "DOWNTREND"


@dataclass
class SwingPoint:
    """A single detected swing high or low."""

    date: pd.Timestamp
    price: float
    kind: str  # "high" or "low"
    idx: int   # positional index in the DataFrame


@dataclass
class SRLevel:
    """A support / resistance price level with metadata."""

    price: float
    touches: int
    role: str  # "SUPPORT" or "RESISTANCE"


@dataclass
class StructureResult:
    """Complete output of the structure analysis pass."""

    swing_highs: list[SwingPoint] = field(default_factory=list)
    swing_lows: list[SwingPoint] = field(default_factory=list)
    trend: Trend = Trend.RANGE
    support_levels: list[SRLevel] = field(default_factory=list)
    resistance_levels: list[SRLevel] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────
# Swing High / Low Detection
# ──────────────────────────────────────────────────────────────
def detect_swings(
    df: pd.DataFrame,
    lookback: int = SWING_LOOKBACK_BARS,
) -> tuple[list[SwingPoint], list[SwingPoint]]:
    """Detect swing highs and swing lows using a symmetric lookback.

    A **swing high** is a bar whose ``High`` exceeds the ``High`` of the
    *lookback* bars on each side.  A **swing low** is defined analogously
    on ``Low``.  Returns the last 10 of each.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV + indicator DataFrame.
    lookback : int
        Number of bars on each side (default from ``config.SWING_LOOKBACK_BARS``).
    """
    highs: list[SwingPoint] = []
    lows: list[SwingPoint] = []

    high_arr = df["High"].values.astype(np.float64)
    low_arr = df["Low"].values.astype(np.float64)
    dates = df.index

    for i in range(lookback, len(df) - lookback):
        # Swing high: higher than N bars on each side
        if high_arr[i] == np.max(high_arr[i - lookback : i + lookback + 1]):
            highs.append(
                SwingPoint(date=dates[i], price=float(high_arr[i]), kind="high", idx=i)
            )
        # Swing low: lower than N bars on each side
        if low_arr[i] == np.min(low_arr[i - lookback : i + lookback + 1]):
            lows.append(
                SwingPoint(date=dates[i], price=float(low_arr[i]), kind="low", idx=i)
            )

    return highs[-10:], lows[-10:]


# ──────────────────────────────────────────────────────────────
# Trend Classification
# ──────────────────────────────────────────────────────────────
def classify_trend(df: pd.DataFrame) -> Trend:
    """Classify the current trend regime from the latest bar.

    Uses the 10, 20, and 50 SMA stack for high-probability trend analysis.

    Parameters
    ----------
    df : pd.DataFrame
        Enriched OHLCV DataFrame.
    """
    if len(df) < 2:
        return Trend.RANGE

    last, prev = df.iloc[-1], df.iloc[-2]
    close  = float(last["Close"])
    sma10  = float(last["SMA_10"])
    sma20  = float(last["SMA_20"])
    sma50  = float(last["SMA_50"])

    sma10_rising = sma10 > float(prev["SMA_10"])
    sma20_rising = sma20 > float(prev["SMA_20"])
    sma50_rising = sma50 > float(prev["SMA_50"])

    # All stacked AND all rising (Core Trend Setup criteria)
    if close > sma10 > sma20 > sma50 and sma10_rising and sma20_rising and sma50_rising:
        return Trend.STRONG_UPTREND

    # Stacked but maybe not all rising
    if close > sma20 > sma50 and sma50_rising:
        return Trend.UPTREND

    # Above SMA50 but weak structure
    if close > sma50:
        if sma50_rising:
            return Trend.UPTREND
        else:
            return Trend.WEAK_UPTREND

    if close < sma50:
        return Trend.DOWNTREND

    return Trend.RANGE


# ──────────────────────────────────────────────────────────────
# S/R Level Mapping
# ──────────────────────────────────────────────────────────────
def map_sr_levels(
    swing_highs: list[SwingPoint],
    swing_lows: list[SwingPoint],
    current_price: float,
    cluster_pct: float = SR_CLUSTER_PCT,
    max_levels: int = MAX_SR_LEVELS,
) -> tuple[list[SRLevel], list[SRLevel]]:
    """Cluster swing points into S/R levels and classify vs current price.

    Levels within *cluster_pct* of each other are merged (mean price,
    summed touches).  The top *max_levels* support and resistance levels
    are returned, sorted by number of touches descending.

    Parameters
    ----------
    swing_highs, swing_lows:
        As returned by ``detect_swings``.
    current_price:
        Latest close price.
    cluster_pct:
        Max % difference to merge levels (default 0.5 %).
    max_levels:
        Maximum number of each type to return (default 5).
    """
    raw_prices = [sp.price for sp in swing_highs] + [sp.price for sp in swing_lows]
    if not raw_prices:
        return [], []

    # Sort and cluster
    raw_prices.sort()
    clusters: list[list[float]] = [[raw_prices[0]]]
    for p in raw_prices[1:]:
        if abs(p - clusters[-1][-1]) / clusters[-1][-1] <= cluster_pct:
            clusters[-1].append(p)
        else:
            clusters.append([p])

    # Build SRLevel objects
    sr: list[SRLevel] = []
    for cluster in clusters:
        avg_price = float(np.mean(cluster))
        touches = len(cluster)
        role = "SUPPORT" if avg_price < current_price else "RESISTANCE"
        sr.append(SRLevel(price=avg_price, touches=touches, role=role))

    supports = sorted(
        [s for s in sr if s.role == "SUPPORT"], key=lambda x: x.touches, reverse=True
    )[:max_levels]
    resistances = sorted(
        [s for s in sr if s.role == "RESISTANCE"], key=lambda x: x.touches, reverse=True
    )[:max_levels]

    return supports, resistances


def get_major_swings(
    df: pd.DataFrame,
    structure: StructureResult,
    atr_mult: float = 1.5,
) -> tuple[list[SwingPoint], list[SwingPoint]]:
    """Filter structure.swing_highs and lows to only those >= atr_mult * ATR from opposite swing."""
    if "ATR_14" not in df.columns:
        return structure.swing_highs, structure.swing_lows

    major_highs = []
    major_lows = []
    atr = float(df["ATR_14"].iloc[-1])
    min_move = atr * atr_mult
    
    all_swings = structure.swing_highs + structure.swing_lows
    all_swings.sort(key=lambda s: s.idx)
    
    if not all_swings:
        return [], []
        
    for i, swing in enumerate(all_swings):
        is_major = False
        if i > 0 and abs(swing.price - all_swings[i-1].price) >= min_move:
            is_major = True
        if i < len(all_swings) - 1 and abs(swing.price - all_swings[i+1].price) >= min_move:
            is_major = True
        
        if len(all_swings) == 1:
            is_major = True
            
        if is_major:
            if swing.kind == "high":
                major_highs.append(swing)
            else:
                major_lows.append(swing)
                
    return major_highs, major_lows

# ──────────────────────────────────────────────────────────────
# Top-level entry
# ──────────────────────────────────────────────────────────────
def analyze_structure(df: pd.DataFrame) -> StructureResult:
    """Run the full structure analysis pass.

    Parameters
    ----------
    df : pd.DataFrame
        Enriched OHLCV DataFrame (with EMA columns).

    Returns
    -------
    StructureResult
        Swing points, trend label, and S/R level maps.
    """
    swing_highs, swing_lows = detect_swings(df)
    trend = classify_trend(df)
    current_price = float(df["Close"].iloc[-1])
    supports, resistances = map_sr_levels(swing_highs, swing_lows, current_price)

    result = StructureResult(
        swing_highs=swing_highs,
        swing_lows=swing_lows,
        trend=trend,
        support_levels=supports,
        resistance_levels=resistances,
    )
    logger.info(
        "Structure: trend=%s  swing_H=%d  swing_L=%d  S=%d  R=%d",
        trend.value,
        len(swing_highs),
        len(swing_lows),
        len(supports),
        len(resistances),
    )
    return result
