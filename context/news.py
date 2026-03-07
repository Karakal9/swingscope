"""
SwingScope News Analyzer
=========================
Fetches the latest headlines via Yahoo Finance RSS (no API key required)
and classifies sentiment using deterministic keyword matching.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import config as cfg

logger = logging.getLogger(__name__)

try:
    import feedparser
except ImportError:
    feedparser = None  # type: ignore
    logger.warning("feedparser not installed — news analysis disabled")


@dataclass
class NewsHeadline:
    """A single parsed news headline."""

    title: str
    published: Optional[str] = None
    link: Optional[str] = None
    sentiment: str = "NEUTRAL"          # BULLISH, BEARISH, WATCH, NEUTRAL
    matched_keywords: list[str] = field(default_factory=list)


@dataclass
class NewsResult:
    """Output of the news analysis."""

    headlines: list[NewsHeadline] = field(default_factory=list)
    overall_sentiment: str = "NEUTRAL"  # BULLISH, BEARISH, NEUTRAL
    modifier: int = 0
    bullish_count: int = 0
    bearish_count: int = 0


def _classify_headline(title: str) -> tuple[str, list[str]]:
    """Classify a headline by keyword matching.

    Returns (sentiment, matched_keywords).
    """
    title_lower = title.lower()
    matched: list[str] = []

    for kw in cfg.NEWS_BULLISH_KEYWORDS:
        if kw in title_lower:
            matched.append(kw)

    if matched:
        return "BULLISH", matched

    matched = []
    for kw in cfg.NEWS_BEARISH_KEYWORDS:
        if kw in title_lower:
            # Guard against false negatives in defense/production
            if "quadruple" in title_lower:
                continue
            if kw == "miss" and "missile" in title_lower:
                continue
            matched.append(kw)

    if matched:
        return "BEARISH", matched

    for kw in cfg.NEWS_WATCH_KEYWORDS:
        if kw in title_lower:
            return "WATCH", [kw]

    return "NEUTRAL", []


def analyze_news(ticker: str) -> NewsResult:
    """Fetch and classify recent news for *ticker* via Yahoo RSS.

    Parameters
    ----------
    ticker : str
        Stock symbol.

    Returns
    -------
    NewsResult
        Headlines with per-item sentiment and an overall score modifier.
    """
    result = NewsResult()

    if feedparser is None:
        logger.warning("feedparser unavailable — returning empty news result")
        return result

    url = cfg.NEWS_RSS_URL.format(ticker=ticker)

    try:
        feed = feedparser.parse(url)
    except Exception as exc:
        logger.warning("%s: RSS fetch failed — %s", ticker, exc)
        return result

    if not feed.entries:
        logger.info("%s: no RSS entries found", ticker)
        return result

    for entry in feed.entries[:8]:
        title = entry.get("title", "")
        sentiment, keywords = _classify_headline(title)

        headline = NewsHeadline(
            title=title,
            published=entry.get("published"),
            link=entry.get("link"),
            sentiment=sentiment,
            matched_keywords=keywords,
        )
        result.headlines.append(headline)

        if sentiment == "BULLISH":
            result.bullish_count += 1
        elif sentiment == "BEARISH":
            result.bearish_count += 1

    # Overall sentiment
    if result.bullish_count > result.bearish_count and result.bullish_count >= 2:
        result.overall_sentiment = "BULLISH"
        result.modifier = cfg.MOD_NEWS_BULLISH
    elif result.bearish_count > result.bullish_count and result.bearish_count >= 1:
        result.overall_sentiment = "BEARISH"
        result.modifier = cfg.MOD_NEWS_BEARISH
    else:
        result.overall_sentiment = "NEUTRAL"
        result.modifier = 0

    logger.info(
        "News: %s  headlines=%d  bull=%d  bear=%d  mod=%+d",
        ticker,
        len(result.headlines),
        result.bullish_count,
        result.bearish_count,
        result.modifier,
    )
    return result
