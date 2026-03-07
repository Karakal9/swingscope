"""
SwingScope Candlestick Pattern Detector
========================================
Detects 14 academically-validated candlestick patterns and cross-references
each detection against structural context (EMA, S/R, VP levels).  Patterns
that do not occur within ``PATTERN_PROXIMITY_ATR`` of a structural level are
marked UNCONFIRMED and do not contribute to the setup score.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd

from config import PATTERN_PROXIMITY_ATR

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Data types
# ──────────────────────────────────────────────────────────────
class PatternSignal(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    INDECISION = "INDECISION"


@dataclass
class PatternMatch:
    """A single detected candlestick pattern."""

    name: str
    signal: PatternSignal
    bar_count: int
    date: pd.Timestamp
    key_price: float          # the pattern's defining price level
    confirmed: bool           # True if near a structural level
    context_level: Optional[str] = None  # e.g. "EMA_21", "SUPPORT @ 150.2"


# ──────────────────────────────────────────────────────────────
# Proximity helper
# ──────────────────────────────────────────────────────────────
def _near_level(
    price: float,
    levels: list[float],
    atr: float,
    proximity: float = PATTERN_PROXIMITY_ATR,
) -> tuple[bool, Optional[str]]:
    """Check if *price* is within *proximity × ATR* of any level.

    Returns (is_near, label_of_nearest_level).
    """
    threshold = proximity * atr
    for lv in levels:
        if abs(price - lv) <= threshold:
            return True, f"{lv:.2f}"
    return False, None


def _body(o: float, c: float) -> float:
    return abs(c - o)


def _upper_shadow(h: float, o: float, c: float) -> float:
    return h - max(o, c)


def _lower_shadow(l: float, o: float, c: float) -> float:
    return min(o, c) - l


def _is_bullish(o: float, c: float) -> bool:
    return c > o


def _is_bearish(o: float, c: float) -> bool:
    return c < o


# ──────────────────────────────────────────────────────────────
# Individual pattern detectors
# ──────────────────────────────────────────────────────────────
def _detect_hammer(row: pd.Series) -> Optional[tuple[str, PatternSignal, float]]:
    """Hammer: small body, long lower shadow ≥ 2× body, tiny upper shadow."""
    o, h, l, c = row["Open"], row["High"], row["Low"], row["Close"]
    body = _body(o, c)
    if body == 0:
        return None
    ls = _lower_shadow(l, o, c)
    us = _upper_shadow(h, o, c)
    if ls >= 2 * body and us <= body * 0.3:
        return ("Hammer", PatternSignal.BULLISH, l)
    return None


def _detect_inverted_hammer(row: pd.Series) -> Optional[tuple[str, PatternSignal, float]]:
    """Inverted Hammer: small body, long upper shadow ≥ 2× body, tiny lower shadow."""
    o, h, l, c = row["Open"], row["High"], row["Low"], row["Close"]
    body = _body(o, c)
    if body == 0:
        return None
    us = _upper_shadow(h, o, c)
    ls = _lower_shadow(l, o, c)
    if us >= 2 * body and ls <= body * 0.3:
        return ("Inverted Hammer", PatternSignal.BULLISH, l)
    return None


def _detect_shooting_star(row: pd.Series, prev: pd.Series) -> Optional[tuple[str, PatternSignal, float]]:
    """Shooting Star: after rally, small body at bottom, long upper shadow."""
    o, h, l, c = row["Open"], row["High"], row["Low"], row["Close"]
    body = _body(o, c)
    if body == 0:
        return None
    us = _upper_shadow(h, o, c)
    ls = _lower_shadow(l, o, c)
    # Must be after a rally (prev close > prev open)
    if _is_bullish(prev["Open"], prev["Close"]) and us >= 2 * body and ls <= body * 0.3 and _is_bearish(o, c):
        return ("Shooting Star", PatternSignal.BEARISH, h)
    return None


def _detect_doji(row: pd.Series) -> Optional[tuple[str, PatternSignal, float]]:
    """Doji at Structure: body ≤ 10% of high-low range."""
    o, h, l, c = row["Open"], row["High"], row["Low"], row["Close"]
    full_range = h - l
    if full_range == 0:
        return None
    body = _body(o, c)
    if body <= 0.10 * full_range:
        return ("Doji at Structure", PatternSignal.INDECISION, (h + l) / 2)
    return None


def _detect_bullish_engulfing(curr: pd.Series, prev: pd.Series) -> Optional[tuple[str, PatternSignal, float]]:
    """Bullish Engulfing: bearish bar followed by bullish bar that engulfs it."""
    if _is_bearish(prev["Open"], prev["Close"]) and _is_bullish(curr["Open"], curr["Close"]):
        if curr["Open"] <= prev["Close"] and curr["Close"] >= prev["Open"]:
            return ("Bullish Engulfing", PatternSignal.BULLISH, curr["Open"])
    return None


def _detect_bearish_engulfing(curr: pd.Series, prev: pd.Series) -> Optional[tuple[str, PatternSignal, float]]:
    """Bearish Engulfing: bullish bar followed by bearish bar that engulfs it."""
    if _is_bullish(prev["Open"], prev["Close"]) and _is_bearish(curr["Open"], curr["Close"]):
        if curr["Open"] >= prev["Close"] and curr["Close"] <= prev["Open"]:
            return ("Bearish Engulfing", PatternSignal.BEARISH, curr["Open"])
    return None


def _detect_piercing_line(curr: pd.Series, prev: pd.Series) -> Optional[tuple[str, PatternSignal, float]]:
    """Piercing Line: bearish bar, then gap-down open that closes above 50% of prev body."""
    if _is_bearish(prev["Open"], prev["Close"]) and _is_bullish(curr["Open"], curr["Close"]):
        mid = (prev["Open"] + prev["Close"]) / 2
        if curr["Open"] < prev["Close"] and curr["Close"] > mid:
            return ("Piercing Line", PatternSignal.BULLISH, curr["Open"])
    return None


def _detect_dark_cloud_cover(curr: pd.Series, prev: pd.Series) -> Optional[tuple[str, PatternSignal, float]]:
    """Dark Cloud Cover: bullish bar, then gap-up open that closes below 50% of prev body."""
    if _is_bullish(prev["Open"], prev["Close"]) and _is_bearish(curr["Open"], curr["Close"]):
        mid = (prev["Open"] + prev["Close"]) / 2
        if curr["Open"] > prev["Close"] and curr["Close"] < mid:
            return ("Dark Cloud Cover", PatternSignal.BEARISH, curr["Open"])
    return None


def _detect_bullish_harami(curr: pd.Series, prev: pd.Series) -> Optional[tuple[str, PatternSignal, float]]:
    """Bullish Harami: large bearish bar, then small bullish bar inside it."""
    if _is_bearish(prev["Open"], prev["Close"]) and _is_bullish(curr["Open"], curr["Close"]):
        if curr["Open"] >= prev["Close"] and curr["Close"] <= prev["Open"]:
            if _body(curr["Open"], curr["Close"]) < _body(prev["Open"], prev["Close"]) * 0.5:
                return ("Bullish Harami", PatternSignal.BULLISH, curr["Open"])
    return None


def _detect_inside_bar(curr: pd.Series, prev: pd.Series) -> Optional[tuple[str, PatternSignal, float]]:
    """Inside Bar: current bar's range is entirely within previous bar."""
    if curr["High"] <= prev["High"] and curr["Low"] >= prev["Low"]:
        return ("Inside Bar", PatternSignal.INDECISION, (curr["High"] + curr["Low"]) / 2)
    return None


def _detect_tweezer_bottom(curr: pd.Series, prev: pd.Series) -> Optional[tuple[str, PatternSignal, float]]:
    """Tweezer Bottom: two bars with roughly equal lows (within 0.1% of each other)."""
    if abs(curr["Low"] - prev["Low"]) / max(prev["Low"], 0.01) <= 0.001:
        if _is_bearish(prev["Open"], prev["Close"]) and _is_bullish(curr["Open"], curr["Close"]):
            return ("Tweezer Bottom", PatternSignal.BULLISH, curr["Low"])
    return None


def _detect_morning_star(
    c0: pd.Series, c1: pd.Series, c2: pd.Series,
) -> Optional[tuple[str, PatternSignal, float]]:
    """Morning Star: bearish, small-body, bullish — reversal."""
    if not _is_bearish(c0["Open"], c0["Close"]):
        return None
    body1 = _body(c1["Open"], c1["Close"])
    range1 = c1["High"] - c1["Low"]
    if range1 == 0 or body1 > 0.3 * range1:
        return None
    if not _is_bullish(c2["Open"], c2["Close"]):
        return None
    if c2["Close"] > (c0["Open"] + c0["Close"]) / 2:
        return ("Morning Star", PatternSignal.BULLISH, c1["Low"])
    return None


def _detect_evening_star(
    c0: pd.Series, c1: pd.Series, c2: pd.Series,
) -> Optional[tuple[str, PatternSignal, float]]:
    """Evening Star: bullish, small-body, bearish — reversal."""
    if not _is_bullish(c0["Open"], c0["Close"]):
        return None
    body1 = _body(c1["Open"], c1["Close"])
    range1 = c1["High"] - c1["Low"]
    if range1 == 0 or body1 > 0.3 * range1:
        return None
    if not _is_bearish(c2["Open"], c2["Close"]):
        return None
    if c2["Close"] < (c0["Open"] + c0["Close"]) / 2:
        return ("Evening Star", PatternSignal.BEARISH, c1["High"])
    return None


def _detect_three_white_soldiers(
    c0: pd.Series, c1: pd.Series, c2: pd.Series,
) -> Optional[tuple[str, PatternSignal, float]]:
    """Three White Soldiers: three consecutive bullish bars, each closing higher."""
    if (
        _is_bullish(c0["Open"], c0["Close"])
        and _is_bullish(c1["Open"], c1["Close"])
        and _is_bullish(c2["Open"], c2["Close"])
    ):
        if c1["Close"] > c0["Close"] and c2["Close"] > c1["Close"]:
            # Each opens within previous body
            if c1["Open"] >= c0["Open"] and c2["Open"] >= c1["Open"]:
                return ("Three White Soldiers", PatternSignal.BULLISH, c0["Low"])
    return None


# ──────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────
def detect_patterns(
    df: pd.DataFrame,
    structural_levels: list[float],
    atr: float,
) -> list[PatternMatch]:
    """Scan the last 5 bars for all 14 candlestick patterns.

    Each detected pattern is validated against *structural_levels* using
    the ATR-proximity rule (Section 7.2).  Patterns outside the proximity
    threshold are still returned but marked ``confirmed=False``.

    Parameters
    ----------
    df : pd.DataFrame
        Enriched OHLCV DataFrame (at least 5 recent bars needed).
    structural_levels : list[float]
        Candidate S/R, EMA, POC, VAH, VAL levels for context check.
    atr : float
        Current ATR_14 value.

    Returns
    -------
    list[PatternMatch]
        All detected patterns (most recent first).
    """
    if len(df) < 5 or atr <= 0:
        return []

    matches: list[PatternMatch] = []

    # Scan last 5 bars for 1-bar patterns, last 4 pairs for 2-bar, last 3 triples for 3-bar
    for offset in range(min(5, len(df))):
        i = len(df) - 1 - offset
        row = df.iloc[i]

        # 1-bar patterns
        for detector in (_detect_hammer, _detect_inverted_hammer, _detect_doji):
            result = detector(row)
            if result:
                name, signal, key_price = result
                near, ctx = _near_level(key_price, structural_levels, atr)
                matches.append(PatternMatch(
                    name=name, signal=signal, bar_count=1,
                    date=df.index[i], key_price=key_price,
                    confirmed=near, context_level=ctx,
                ))

        # 2-bar patterns (need previous bar)
        if i >= 1:
            prev = df.iloc[i - 1]
            for detector in (
                _detect_bullish_engulfing,
                _detect_bearish_engulfing,
                _detect_piercing_line,
                _detect_dark_cloud_cover,
                _detect_bullish_harami,
                _detect_inside_bar,
                _detect_tweezer_bottom,
            ):
                result = detector(row, prev)
                if result:
                    name, signal, key_price = result
                    near, ctx = _near_level(key_price, structural_levels, atr)
                    matches.append(PatternMatch(
                        name=name, signal=signal, bar_count=2,
                        date=df.index[i], key_price=key_price,
                        confirmed=near, context_level=ctx,
                    ))

            # Shooting star needs rally context
            result = _detect_shooting_star(row, prev)
            if result:
                name, signal, key_price = result
                near, ctx = _near_level(key_price, structural_levels, atr)
                matches.append(PatternMatch(
                    name=name, signal=signal, bar_count=1,
                    date=df.index[i], key_price=key_price,
                    confirmed=near, context_level=ctx,
                ))

        # 3-bar patterns
        if i >= 2:
            c0 = df.iloc[i - 2]
            c1 = df.iloc[i - 1]
            c2 = df.iloc[i]
            for detector in (
                _detect_morning_star,
                _detect_evening_star,
                _detect_three_white_soldiers,
            ):
                result = detector(c0, c1, c2)
                if result:
                    name, signal, key_price = result
                    near, ctx = _near_level(key_price, structural_levels, atr)
                    matches.append(PatternMatch(
                        name=name, signal=signal, bar_count=3,
                        date=df.index[i], key_price=key_price,
                        confirmed=near, context_level=ctx,
                    ))

    # De-duplicate by (name, date) — keep first occurrence
    seen: set[tuple[str, pd.Timestamp]] = set()
    unique: list[PatternMatch] = []
    for m in matches:
        key = (m.name, m.date)
        if key not in seen:
            seen.add(key)
            unique.append(m)

    logger.info("Patterns detected: %d (%d confirmed)", len(unique), sum(1 for m in unique if m.confirmed))
    return unique
