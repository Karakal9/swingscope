"""
SwingScope Data Fetcher
=======================
Single source of truth for all market data. Fetches daily OHLCV via yfinance,
caches locally as Parquet with 24-hour TTL, and returns clean, validated
DataFrames.  All network calls include exponential backoff for 429s.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

from config import (
    BACKOFF_BASE_SECS,
    CACHE_TTL_HOURS,
    MAX_RETRIES,
)

logger = logging.getLogger(__name__)

# Resolve cache directory relative to project root
_CACHE_DIR = Path(__file__).resolve().parent / "cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ──────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────
def _cache_path(ticker: str, interval: str) -> Path:
    """Return the Parquet cache file path for a given ticker/interval."""
    return _CACHE_DIR / f"{ticker.upper()}_{interval}.parquet"


def _cache_is_fresh(path: Path) -> bool:
    """Return True if *path* exists and was modified within CACHE_TTL_HOURS."""
    if not path.exists():
        return False
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    return datetime.now() - mtime < timedelta(hours=CACHE_TTL_HOURS)


def _clean_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalise an OHLCV DataFrame.

    * Keeps only required columns.
    * Ensures correct dtypes.
    * Sorts ascending by date.
    * Drops rows where *all* of OHLCV are NaN.
    """
    required = ["Open", "High", "Low", "Close", "Volume"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    df = df[required].copy()
    df.index = pd.to_datetime(df.index)
    df.index.name = "Date"

    for col in ["Open", "High", "Low", "Close"]:
        df[col] = df[col].astype(np.float64)
    df["Volume"] = df["Volume"].astype(np.int64)

    df.sort_index(inplace=True)
    df.dropna(subset=required, how="all", inplace=True)
    return df


def _fetch_with_retry(
    ticker_obj: yf.Ticker,
    period: str,
    interval: str,
) -> Optional[pd.DataFrame]:
    """Download history with exponential backoff on failure/429."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            df = ticker_obj.history(period=period, interval=interval)
            if df is not None and not df.empty:
                return df
            logger.warning(
                "%s: empty response (attempt %d/%d)",
                ticker_obj.ticker, attempt, MAX_RETRIES,
            )
        except Exception as exc:
            logger.warning(
                "%s: fetch error '%s' (attempt %d/%d)",
                ticker_obj.ticker, exc, attempt, MAX_RETRIES,
            )
        if attempt < MAX_RETRIES:
            wait = BACKOFF_BASE_SECS ** attempt
            logger.info("Backing off %.1fs …", wait)
            time.sleep(wait)
    return None


# ──────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────
def fetch_ohlcv(
    ticker: str,
    period: str = "1y",
    interval: str = "1d",
) -> Optional[pd.DataFrame]:
    """Fetch daily OHLCV data for *ticker*.

    Returns a clean DataFrame or ``None`` on failure.  Results are cached
    as Parquet with a 24-hour TTL.

    Parameters
    ----------
    ticker:
        Stock symbol, e.g. ``'AAPL'``.
    period:
        yfinance period string (default ``'1y'``).
    interval:
        yfinance interval string (default ``'1d'``).
    """
    cache = _cache_path(ticker, interval)

    if _cache_is_fresh(cache):
        logger.info("%s: loading from cache (%s)", ticker, cache)
        try:
            return pd.read_parquet(cache)
        except Exception as exc:
            logger.warning("%s: cache read failed (%s), re-fetching", ticker, exc)

    logger.info("%s: fetching from yfinance (period=%s, interval=%s)", ticker, period, interval)
    t = yf.Ticker(ticker)
    raw = _fetch_with_retry(t, period, interval)

    if raw is None:
        logger.error("%s: failed to fetch OHLCV after %d retries", ticker, MAX_RETRIES)
        return None

    try:
        df = _clean_ohlcv(raw)
    except ValueError as exc:
        logger.error("%s: data validation failed — %s", ticker, exc)
        return None

    df.to_parquet(cache)
    logger.info("%s: cached → %s", ticker, cache)
    return df


def fetch_weekly(ticker: str) -> Optional[pd.DataFrame]:
    """Fetch 2-year weekly OHLCV for broader trend context.

    Parameters
    ----------
    ticker:
        Stock symbol.
    """
    return fetch_ohlcv(ticker, period="2y", interval="1wk")


def fetch_sector_etf(etf: str) -> Optional[pd.DataFrame]:
    """Fetch 1-year daily OHLCV for a sector ETF (e.g. ``'XLK'``).

    Parameters
    ----------
    etf:
        ETF symbol from the SECTOR_ETF_MAP.
    """
    return fetch_ohlcv(etf, period="1y", interval="1d")


def get_ticker_info(ticker: str) -> dict:
    """Return basic info dict (sector, industry, shortName).

    Falls back to an empty dict on failure so downstream code can
    degrade gracefully.

    Parameters
    ----------
    ticker:
        Stock symbol.
    """
    try:
        info = yf.Ticker(ticker).info or {}
        return {
            "sector": info.get("sector", "Unknown"),
            "industry": info.get("industry", "Unknown"),
            "name": info.get("shortName", ticker),
            "debtToEquity": info.get("debtToEquity", 0.0),
            # Swing-trading fundamentals
            "shortPercentOfFloat": info.get("shortPercentOfFloat", 0.0),
            "floatShares": info.get("floatShares", 0),
            "currentRatio": info.get("currentRatio", 0.0),
            "earningsGrowth": info.get("earningsGrowth", 0.0),
            "revenueGrowth": info.get("revenueGrowth", 0.0),
        }
    except Exception as exc:
        logger.warning("%s: failed to get ticker info — %s", ticker, exc)
        return {
            "sector": "Unknown", "industry": "Unknown", "name": ticker,
            "debtToEquity": 0.0, "shortPercentOfFloat": 0.0,
            "floatShares": 0, "currentRatio": 0.0,
            "earningsGrowth": 0.0, "revenueGrowth": 0.0,
        }


def get_earnings(ticker: str) -> dict:
    """Return earnings info: next earnings date, history, days away.

    Returns a dict with keys ``next_date``, ``days_to_earnings``, and
    ``history`` (DataFrame of past quarters).  All values may be ``None``
    if the data is unavailable.

    Parameters
    ----------
    ticker:
        Stock symbol.
    """
    result: dict = {
        "next_date": None,
        "days_to_earnings": None,
        "history": None,
    }
    try:
        t = yf.Ticker(ticker)

        # Next earnings date
        cal = t.calendar
        if cal is not None:
            if isinstance(cal, pd.DataFrame) and "Earnings Date" in cal.columns:
                dates = cal["Earnings Date"]
                if len(dates) > 0:
                    next_dt = pd.Timestamp(dates.iloc[0])
                    result["next_date"] = next_dt
                    result["days_to_earnings"] = (next_dt - pd.Timestamp.now()).days
            elif isinstance(cal, dict):
                ed = cal.get("Earnings Date")
                if ed is not None:
                    if isinstance(ed, list) and len(ed) > 0:
                        next_dt = pd.Timestamp(ed[0])
                    else:
                        next_dt = pd.Timestamp(ed)
                    result["next_date"] = next_dt
                    result["days_to_earnings"] = (next_dt - pd.Timestamp.now()).days

        # Earnings history
        try:
            hist = t.earnings_dates
            if hist is not None and not hist.empty:
                result["history"] = hist.head(8)  # last ~4 quarters (2 rows each)
        except Exception:
            pass

    except Exception as exc:
        logger.warning("%s: earnings lookup failed — %s", ticker, exc)

    return result
