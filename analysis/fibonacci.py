"""
SwingScope Fibonacci Retracement Calculator
=============================================
Auto-detects the most recent significant swing leg and computes standard
Fibonacci retracement levels (23.6 %, 38.2 %, 50 %, 61.8 %, 78.6 %).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from analysis.structure import get_major_swings, StructureResult

logger = logging.getLogger(__name__)

# Standard Fibonacci retracement ratios
FIB_RATIOS: list[float] = [0.236, 0.382, 0.500, 0.618, 0.786]


@dataclass
class FibLevel:
    """A single Fibonacci retracement level."""

    ratio: float
    price: float
    label: str  # e.g. "38.2%"


@dataclass
class FibResult:
    """Output of the Fibonacci retracement calculation."""

    swing_high: float
    swing_low: float
    direction: str         # "UP" (retrace from high) or "DOWN" (retrace from low)
    levels: list[FibLevel] = field(default_factory=list)


def compute_fibonacci(
    df: pd.DataFrame,
    structure: StructureResult,
    current_price: float,
) -> Optional[FibResult]:
    """Compute Fibonacci retracement levels from the most recent major swing leg.

    The function identifies the most recent major swing high and
    swing low, determines the direction of the leg, and maps standard
    Fibonacci ratios onto the price range.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV DataFrame with ATR for major swing filtering.
    structure : StructureResult
        Output of structure analysis.
    current_price : float
        Latest close price (used to determine retracement direction).

    Returns
    -------
    FibResult or None
        Fibonacci levels, or ``None`` if insufficient swing data.
    """
    major_highs, major_lows = get_major_swings(df, structure, atr_mult=1.5)

    if not major_highs or not major_lows:
        logger.warning("Fibonacci: insufficient major swing points")
        return None

    # Use the most recent major swing high and major swing low
    latest_high = major_highs[-1]
    latest_low = major_lows[-1]

    sh_price = latest_high.price
    sl_price = latest_low.price

    if sh_price == sl_price:
        logger.warning("Fibonacci: swing high == swing low — skipping")
        return None

    # Determine direction: if swing high came AFTER swing low → uptrend leg
    # (we're retracing DOWN from the high). Otherwise → downtrend leg
    # (retracing UP from the low).
    if latest_high.idx > latest_low.idx:
        direction = "UP"  # uptrend leg, retracing downward
        diff = sh_price - sl_price
        levels = [
            FibLevel(
                ratio=r,
                price=sh_price - diff * r,
                label=f"{r * 100:.1f}%",
            )
            for r in FIB_RATIOS
        ]
    else:
        direction = "DOWN"  # downtrend leg, retracing upward
        diff = sh_price - sl_price
        levels = [
            FibLevel(
                ratio=r,
                price=sl_price + diff * r,
                label=f"{r * 100:.1f}%",
            )
            for r in FIB_RATIOS
        ]

    result = FibResult(
        swing_high=sh_price,
        swing_low=sl_price,
        direction=direction,
        levels=levels,
    )
    logger.info(
        "Fibonacci: %s leg  H=%.2f  L=%.2f  levels=%s",
        direction,
        sh_price,
        sl_price,
        [f"{lv.label}@{lv.price:.2f}" for lv in levels],
    )
    return result
