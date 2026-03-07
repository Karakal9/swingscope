"""
SwingScope Volume Profile Engine
=================================
Custom numpy implementation for computing Volume Profile metrics over a
rolling 60-day lookback.  This is NOT available in pandas-ta and uses
raw numpy for performance.

Outputs
-------
- **POC** — Point of Control (price with highest cumulative volume)
- **VAH** — Value Area High (upper bound of 70 % value area)
- **VAL** — Value Area Low (lower bound of 70 % value area)
- **HVNs** — High Volume Nodes (volume > 1.5× avg)
- **LVNs** — Low Volume Nodes (volume < 0.4× avg)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from scipy.stats import norm

from config import (
    HVN_THRESHOLD,
    LVN_THRESHOLD,
    VP_BINS,
    VP_LOOKBACK_DAYS,
)

logger = logging.getLogger(__name__)


@dataclass
class VolumeProfile:
    """Container for Volume Profile outputs at a single point in time."""

    poc: float
    vah: float
    val: float
    hvns: list[float] = field(default_factory=list)
    lvns: list[float] = field(default_factory=list)


def compute_volume_profile(
    df: pd.DataFrame,
    lookback: int = VP_LOOKBACK_DAYS,
    bins: int = VP_BINS,
) -> Optional[VolumeProfile]:
    """Compute the Volume Profile for the most recent *lookback* bars.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV DataFrame (must contain ``High``, ``Low``, ``Close``,
        ``Volume`` columns).
    lookback : int
        Number of bars to include in the profile (default 60).
    bins : int
        Number of price buckets (default 100).

    Returns
    -------
    VolumeProfile or None
        A ``VolumeProfile`` dataclass, or ``None`` if insufficient data.
    """
    if len(df) < lookback:
        logger.warning(
            "Volume profile: only %d bars available (need %d)", len(df), lookback
        )
        lookback = len(df)
        if lookback < 10:
            return None

    window = df.iloc[-lookback:]

    price_low = float(window["Low"].min())
    price_high = float(window["High"].max())

    if price_high == price_low:
        logger.warning("Volume profile: flat price range — skipping")
        return None

    # Build price bin edges
    bin_edges = np.linspace(price_low, price_high, bins + 1)
    bin_centres = (bin_edges[:-1] + bin_edges[1:]) / 2.0

    # Distribute each bar's volume across the bins its range covers
    vol_profile = np.zeros(bins, dtype=np.float64)

    highs = window["High"].values.astype(np.float64)
    lows = window["Low"].values.astype(np.float64)
    volumes = window["Volume"].values.astype(np.float64)

    for i in range(len(window)):
        bar_low = lows[i]
        bar_high = highs[i]
        bar_vol = volumes[i]

        overlap_mask = (bin_edges[1:] > bar_low) & (bin_edges[:-1] < bar_high)
        n_overlapping = overlap_mask.sum()

        if n_overlapping > 0:
            if bar_high == bar_low:
                vol_profile[overlap_mask] += bar_vol / n_overlapping
            else:
                bar_mean = (bar_low + bar_high) / 2.0
                bar_std  = (bar_high - bar_low) / 4.0

                if bar_std == 0:
                    vol_profile[overlap_mask] += bar_vol / n_overlapping
                else:
                    dist = norm(loc=bar_mean, scale=bar_std)
                    probs = dist.cdf(bin_edges[1:]) - dist.cdf(bin_edges[:-1])
                    if overlap_mask.any():
                        probs_sum = probs[overlap_mask].sum()
                        if probs_sum > 0:
                            probs[overlap_mask] = probs[overlap_mask] / probs_sum
                            vol_profile[overlap_mask] += bar_vol * probs[overlap_mask]
                        else:
                            vol_profile[overlap_mask] += bar_vol / n_overlapping

    # ── POC ──────────────────────────────────────────────────
    poc_idx = int(np.argmax(vol_profile))
    poc = float(bin_centres[poc_idx])

    # ── Value Area (70 %) ────────────────────────────────────
    total_vol = vol_profile.sum()
    target_vol = total_vol * 0.70

    # Expand outward from POC
    va_low_idx = poc_idx
    va_high_idx = poc_idx
    accumulated = vol_profile[poc_idx]

    while accumulated < target_vol:
        expand_down = vol_profile[va_low_idx - 1] if va_low_idx > 0 else 0.0
        expand_up = vol_profile[va_high_idx + 1] if va_high_idx < bins - 1 else 0.0

        if expand_up == 0.0 and expand_down == 0.0:
            break

        if expand_up >= expand_down:
            va_high_idx += 1
            accumulated += expand_up
        else:
            va_low_idx -= 1
            accumulated += expand_down

    vah = float(bin_edges[va_high_idx + 1])  # upper edge of high idx
    val_ = float(bin_edges[va_low_idx])       # lower edge of low idx

    # ── HVN / LVN ───────────────────────────────────────────
    avg_vol = vol_profile.mean()
    hvn_mask = vol_profile > (HVN_THRESHOLD * avg_vol)
    lvn_mask = (vol_profile < (LVN_THRESHOLD * avg_vol)) & (vol_profile > 0)

    hvns = bin_centres[hvn_mask].tolist()
    lvns = bin_centres[lvn_mask].tolist()

    vp = VolumeProfile(poc=poc, vah=vah, val=val_, hvns=hvns, lvns=lvns)
    logger.info(
        "Volume Profile: POC=%.2f  VAH=%.2f  VAL=%.2f  HVNs=%d  LVNs=%d",
        poc, vah, val_, len(hvns), len(lvns),
    )
    return vp
