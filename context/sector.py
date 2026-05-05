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
    relative_strength: float = 0.0    # RS Alpha 20D (%)
    alpha_10d: float = 0.0            # RS Alpha 10D (%)
    improving: bool = False           # True when 20D negative but 10D positive
    rs_market_cond: str = "Unknown"
    rs_label: str = "Unknown"
    macd_positive: bool = False
    verdict: str = "NEUTRAL"          # TAILWIND, IMPROVING, NEUTRAL, HEADWIND
    modifier: int = 0                 # pts to add to setup score
    rs_direction: str = "Neutral"     # Uptrend, Neutral, Downtrend


def analyze_sector(ticker: str) -> SectorResult:
    """Run sector alignment analysis for *ticker*.

    Fetches the ticker's sector via ``yfinance``, maps it to a SPDR ETF,
    computes EMA trend, relative strength vs SPY, and MACD momentum.

    The verdict uses a dual-timeframe approach:
    - **20-day Alpha** determines the baseline (TAILWIND vs HEADWIND).
    - **10-day Alpha** detects early rotation. If the 20D alpha is negative
      but the 10D alpha is positive, the sector is classified as IMPROVING
      (0 pts) instead of HEADWIND (-10 pts). This prevents the system from
      penalizing stocks in sectors that the market_analyzer already identifies
      as having fresh positive momentum.

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

    # Compute EMAs and SMAs on ETF
    ema50 = EMAIndicator(close=etf_df["Close"], window=50, fillna=False)
    ema200 = EMAIndicator(close=etf_df["Close"], window=200, fillna=False)
    etf_df["EMA_50"] = ema50.ema_indicator()
    etf_df["EMA_200"] = ema200.ema_indicator()
    
    sma20 = etf_df["Close"].rolling(window=20).mean()
    sma50 = etf_df["Close"].rolling(window=50).mean()
    etf_df["SMA_20"] = sma20
    etf_df["SMA_50"] = sma50

    last_etf = etf_df.iloc[-1]
    etf_close = float(last_etf["Close"])
    above_ema50 = etf_close > float(last_etf["EMA_50"]) if pd.notna(last_etf["EMA_50"]) else False
    above_ema200 = etf_close > float(last_etf["EMA_200"]) if pd.notna(last_etf["EMA_200"]) else False
    
    above_sma20 = etf_close > float(last_etf["SMA_20"]) if pd.notna(last_etf["SMA_20"]) else False
    above_sma50_sma = etf_close > float(last_etf["SMA_50"]) if pd.notna(last_etf["SMA_50"]) else False
    
    rs_direction = "Neutral"
    if above_sma20 and above_sma50_sma:
        rs_direction = "Uptrend"
    elif not above_sma20 and not above_sma50_sma:
        rs_direction = "Downtrend"

    # ── Relative Strength: Dual-timeframe Alpha ──────────────
    alpha = 0.0       # 20-day alpha (institutional flow)
    alpha_10d = 0.0   # 10-day alpha (rotation signal)
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

    # 10-day alpha for rotation detection
    if len(etf_df) >= 10 and len(spy_df) >= 10:
        etf_prev_10 = float(etf_df["Close"].iloc[-10])
        spy_prev_10 = float(spy_df["Close"].iloc[-10])
        etf_ret_10 = (float(etf_df["Close"].iloc[-1]) / etf_prev_10) - 1 if etf_prev_10 != 0 else 0
        spy_ret_10 = (float(spy_df["Close"].iloc[-1]) / spy_prev_10) - 1 if spy_prev_10 != 0 else 0
        alpha_10d = etf_ret_10 - spy_ret_10

    # Detect "Improving" state: 20D lagging but 10D outperforming
    improving = alpha <= 0 and alpha_10d > 0

    # MACD momentum
    macd_ind = MACD(close=etf_df["Close"], window_slow=26, window_fast=12, window_sign=9, fillna=False)
    macd_positive = False
    macd_diff = macd_ind.macd_diff()
    if macd_diff is not None and len(macd_diff) > 0:
        hist = float(macd_diff.iloc[-1])
        macd_positive = hist > 0

    # ── Verdict (dual-timeframe) ─────────────────────────────
    # TAILWIND:   20D alpha > 0 AND price above EMA50 → full bonus (+8)
    # IMPROVING:  20D alpha ≤ 0 BUT 10D alpha > 0     → neutral (0)
    #             Sector is in early rotation, don't penalize
    # HEADWIND:   20D alpha ≤ 0, 10D alpha ≤ 0        → penalty (-10)
    #             No sign of rotation, still lagging on all timeframes
    if alpha > 0 and above_ema50:
        verdict = "TAILWIND"
        modifier = cfg.MOD_SECTOR_TAILWIND
    elif improving:
        verdict = "IMPROVING"
        modifier = 0
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
        alpha_10d=round(alpha_10d * 100, 2),
        improving=improving,
        rs_market_cond=rs_market_cond,
        rs_label=rs_label,
        macd_positive=macd_positive,
        verdict=verdict,
        modifier=modifier,
        rs_direction=rs_direction,
    )
    logger.info(
        "Sector: %s (ETF=%s)  Alpha20D=%.2f%%  Alpha10D=%.2f%%  Improving=%s  "
        "EMA50=%s  Verdict=%s  Mod=%+d",
        sector, etf_symbol, alpha*100, alpha_10d*100, improving,
        above_ema50, verdict, modifier,
    )
    return result
