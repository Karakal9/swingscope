"""
SwingScope Earnings Analyzer
==============================
Fetches earnings calendar and history, classifies risk distance, and
checks for post-earnings drift signals.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

import config as cfg
from data.fetcher import get_earnings

logger = logging.getLogger(__name__)


@dataclass
class EarningsResult:
    """Output of the earnings analysis."""

    next_date: Optional[pd.Timestamp] = None
    days_to_earnings: Optional[int] = None
    risk_status: str = "CLEAR"            # CLEAR, WATCH, CAUTION, IMMINENT
    modifier: int = 0
    last_eps_surprise_pct: Optional[float] = None
    post_earnings_drift: bool = False     # surprise > 5% AND day-1 move > 3%
    history_summary: list[dict] = field(default_factory=list)


def analyze_earnings(ticker: str) -> EarningsResult:
    """Run earnings risk analysis for *ticker*.

    Parameters
    ----------
    ticker : str
        Stock symbol.

    Returns
    -------
    EarningsResult
        Earnings context with modifier and risk classification.
    """
    result = EarningsResult()
    earnings_data = get_earnings(ticker)

    result.next_date = earnings_data.get("next_date")
    result.days_to_earnings = earnings_data.get("days_to_earnings")

    # Risk classification
    days = result.days_to_earnings
    if days is not None:
        if days <= 7:
            result.risk_status = "IMMINENT"
            result.modifier = cfg.MOD_EARNINGS_IMMINENT
        elif days <= 21:
            result.risk_status = "CAUTION"
            result.modifier = cfg.MOD_EARNINGS_CAUTION
        elif days <= 45:
            result.risk_status = "WATCH"
            result.modifier = cfg.MOD_EARNINGS_WATCH
        else:
            result.risk_status = "CLEAR"
            result.modifier = 0
    else:
        result.risk_status = "UNKNOWN"
        result.modifier = 0

    # EPS surprise analysis from history
    hist = earnings_data.get("history")
    if hist is not None and not hist.empty:
        try:
            # yfinance earnings_dates has columns like
            # 'EPS Estimate', 'Reported EPS', 'Surprise(%)'
            for _, row in hist.head(4).iterrows():
                entry = {}
                if "Reported EPS" in hist.columns:
                    entry["reported_eps"] = row.get("Reported EPS")
                if "EPS Estimate" in hist.columns:
                    entry["estimated_eps"] = row.get("EPS Estimate")
                if "Surprise(%)" in hist.columns:
                    entry["surprise_pct"] = row.get("Surprise(%)")
                if entry:
                    result.history_summary.append(entry)

            # Last quarter surprise
            if result.history_summary:
                last_q = result.history_summary[0]
                surprise = last_q.get("surprise_pct")
                if surprise is not None and pd.notna(surprise):
                    result.last_eps_surprise_pct = float(surprise)
                    # Post-earnings drift check (simplified — we'd need day-1 price move)
                    if abs(float(surprise)) > 5.0:
                        result.post_earnings_drift = True
        except Exception as exc:
            logger.warning("%s: earnings history parse error — %s", ticker, exc)

    logger.info(
        "Earnings: %s  days=%s  status=%s  mod=%+d  drift=%s",
        ticker,
        result.days_to_earnings,
        result.risk_status,
        result.modifier,
        result.post_earnings_drift,
    )
    return result
