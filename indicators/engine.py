"""
SwingScope Indicator Engine
============================
Computes the full indicator suite using the ``ta`` library (Technical
Analysis) and appends all computed columns to the OHLCV DataFrame.
This module is the **only** place where indicator calculations happen —
analysis modules consume, never compute.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import ta as ta_lib
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import AverageTrueRange, BollingerBands
from ta.volume import OnBalanceVolumeIndicator

logger = logging.getLogger(__name__)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Enrich an OHLCV DataFrame with the full SwingScope indicator suite.

    All indicators are appended as new columns and the enriched DataFrame
    is returned.  The input DataFrame is **not** modified in place.

    Parameters
    ----------
    df : pd.DataFrame
        Clean OHLCV DataFrame as returned by ``data.fetcher.fetch_ohlcv``.

    Returns
    -------
    pd.DataFrame
        The same DataFrame with ~20 new indicator columns appended.
    """
    df = df.copy()

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"].astype(float)

    # ── Trend: EMAs ──────────────────────────────────────────
    for length in (8, 21, 50, 200):
        col = f"EMA_{length}"
        ema = EMAIndicator(close=close, window=length, fillna=False)
        df[col] = ema.ema_indicator()

    # ── Trend: VWAP (session-anchored approximation) ─────────
    df["VWAP"] = _rolling_vwap(df, length=20)

    # ── Momentum: MACD (12, 26, 9) ───────────────────────────
    macd = MACD(close=close, window_slow=26, window_fast=12, window_sign=9, fillna=False)
    df["MACD"] = macd.macd()
    df["MACD_signal"] = macd.macd_signal()
    df["MACD_hist"] = macd.macd_diff()

    # ── Momentum: RSI (14) ───────────────────────────────────
    rsi = RSIIndicator(close=close, window=14, fillna=False)
    df["RSI_14"] = rsi.rsi()

    # ── Momentum: Stochastic (14, 3, 3) ──────────────────────
    stoch = StochasticOscillator(
        high=high, low=low, close=close,
        window=14, smooth_window=3, fillna=False,
    )
    df["STOCH_k"] = stoch.stoch()
    df["STOCH_d"] = stoch.stoch_signal()

    # ── Volatility: ATR (14) ─────────────────────────────────
    atr = AverageTrueRange(high=high, low=low, close=close, window=14, fillna=False)
    df["ATR_14"] = atr.average_true_range()

    # ── Volatility: Bollinger Bands (20, 2σ) ─────────────────
    bb = BollingerBands(close=close, window=20, window_dev=2, fillna=False)
    df["BB_upper"] = bb.bollinger_hband()
    df["BB_mid"] = bb.bollinger_mavg()
    df["BB_lower"] = bb.bollinger_lband()
    df["BB_width"] = bb.bollinger_wband()

    # ── Volume: OBV ──────────────────────────────────────────
    obv = OnBalanceVolumeIndicator(close=close, volume=volume, fillna=False)
    df["OBV"] = obv.on_balance_volume()

    # ── Volume: Relative Volume (RVol) ───────────────────────
    vol_sma = volume.rolling(window=20).mean()
    df["VOL_SMA_20"] = vol_sma
    df["RVOL"] = volume / vol_sma.replace(0, float("nan"))

    logger.info("Indicators added: %d columns total", len(df.columns))
    return df


# ──────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────
def _rolling_vwap(df: pd.DataFrame, length: int = 20) -> pd.Series:
    """Compute a rolling VWAP proxy for daily data.

    Since daily bars don't have session boundaries, we use a rolling
    window of *length* bars as the anchor.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV DataFrame.
    length : int
        Rolling window size (default 20).
    """
    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3.0
    tp_vol = typical_price * df["Volume"]
    return tp_vol.rolling(length).sum() / df["Volume"].rolling(length).sum()
