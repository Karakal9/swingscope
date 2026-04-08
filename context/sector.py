"""
SwingScope Sector Analyzer
============================
Maps a ticker's sector to its SPDR ETF, fetches ETF data, and runs three
checks: ETF trend, relative strength vs SPY, and momentum (MACD histogram).
Returns a context modifier for the scoring engine.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import pandas as pd
from ta.trend import EMAIndicator, MACD

import config as cfg
from data.fetcher import fetch_ohlcv, get_ticker_info

logger = logging.getLogger(__name__)


@dataclass
class SectorResult:
    """Output of the sector analysis."""

    sector: str
    etf: str
    etf_above_ema50: bool = False
    etf_above_ema200: bool = False
    relative_strength: float = 0.0    # RS Alpha (%)
    rs_market_cond: str = "Unknown"
    rs_label: str = "Unknown"
    macd_positive: bool = False
    verdict: str = "NEUTRAL"          # TAILWIND, NEUTRAL, HEADWIND
    modifier: int = 0                 # pts to add to setup score


def analyze_sector(ticker: str) -> SectorResult:
    """Run sector alignment analysis for *ticker*.

    Fetches the ticker's sector via ``yfinance``, maps it to a SPDR ETF,
    computes EMA trend, relative strength vs SPY, and MACD momentum.

    Parameters
    ----------
    ticker : str
        Stock symbol.

    Returns
    -------
    SectorResult
        Sector context with modifier points.
    """
    info = get_ticker_info(ticker)
    sector = info.get("sector", "Unknown")
    etf_symbol = cfg.SECTOR_ETF_MAP.get(sector)

    if not etf_symbol:
        logger.warning("%s: sector '%s' not in ETF map — returning neutral", ticker, sector)
        return SectorResult(sector=sector, etf="N/A", verdict="NEUTRAL", modifier=0)

    # Fetch ETF and SPY data
    etf_df = fetch_ohlcv(etf_symbol, period="1y", interval="1d")
    spy_df = fetch_ohlcv("SPY", period="1y", interval="1d")

    if etf_df is None or spy_df is None or len(etf_df) < 50:
        logger.warning("%s: failed to fetch ETF/SPY data — returning neutral", ticker)
        return SectorResult(sector=sector, etf=etf_symbol, verdict="NEUTRAL", modifier=0)

    # Compute EMAs on ETF
    ema50 = EMAIndicator(close=etf_df["Close"], window=50, fillna=False)
    ema200 = EMAIndicator(close=etf_df["Close"], window=200, fillna=False)
    etf_df["EMA_50"] = ema50.ema_indicator()
    etf_df["EMA_200"] = ema200.ema_indicator()

    last_etf = etf_df.iloc[-1]
    etf_close = float(last_etf["Close"])
    above_ema50 = etf_close > float(last_etf["EMA_50"]) if pd.notna(last_etf["EMA_50"]) else False
    above_ema200 = etf_close > float(last_etf["EMA_200"]) if pd.notna(last_etf["EMA_200"]) else False

    # Relative Strength: ETF 20-day return / SPY 20-day return (Spread)
    alpha = 0.0
    etf_ret = 0.0
    spy_ret = 0.0
    rs_market_cond = "Unknown"
    rs_label = "Unknown"

    if len(etf_df) >= 20 and len(spy_df) >= 20:
        etf_prev = float(etf_df["Close"].iloc[-20])
        spy_prev = float(spy_df["Close"].iloc[-20])
        etf_ret = (float(etf_df["Close"].iloc[-1]) / etf_prev) - 1 if etf_prev != 0 else 0
        spy_ret = (float(spy_df["Close"].iloc[-1]) / spy_prev) - 1 if spy_prev != 0 else 0
        alpha = etf_ret - spy_ret

        if etf_ret > 0 and spy_ret > 0:
            rs_market_cond = "Broad Bull Market"
            rs_label = "Strong (Outperforming)" if alpha > 0 else "Weak (Underperforming)"
        elif etf_ret < 0 and spy_ret < 0:
            rs_market_cond = "Broad Bear Market"
            rs_label = "Strong (Defensive resilience)" if alpha > 0 else "Weak (Underperforming)"
        elif etf_ret > 0 and spy_ret <= 0:
            rs_market_cond = "Divergence"
            rs_label = "Strongest (Gaining despite market drag)"
        elif etf_ret <= 0 and spy_ret > 0:
            rs_market_cond = "Divergence"
            rs_label = "Weakest (Falling despite market lift)"

    # MACD momentum
    macd_ind = MACD(close=etf_df["Close"], window_slow=26, window_fast=12, window_sign=9, fillna=False)
    macd_positive = False
    macd_diff = macd_ind.macd_diff()
    if macd_diff is not None and len(macd_diff) > 0:
        hist = float(macd_diff.iloc[-1])
        macd_positive = hist > 0

    # Verdict
    if alpha > 0 and above_ema50:
        verdict = "TAILWIND"
        modifier = cfg.MOD_SECTOR_TAILWIND
    elif alpha <= 0 or not above_ema50:
        verdict = "HEADWIND"
        modifier = cfg.MOD_SECTOR_HEADWIND
    else:
        verdict = "NEUTRAL"
        modifier = 0

    result = SectorResult(
        sector=sector,
        etf=etf_symbol,
        etf_above_ema50=above_ema50,
        etf_above_ema200=above_ema200,
        relative_strength=round(alpha * 100, 2),
        rs_market_cond=rs_market_cond,
        rs_label=rs_label,
        macd_positive=macd_positive,
        verdict=verdict,
        modifier=modifier,
    )
    logger.info(
        "Sector: %s (ETF=%s)  Alpha=%.2f%%  EMA50=%s  Verdict=%s  Mod=%+d",
        sector, etf_symbol, alpha*100, above_ema50, verdict, modifier,
    )
    return result
