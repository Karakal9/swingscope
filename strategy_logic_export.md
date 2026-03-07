# SwingScope Analyzer Core Strategy Logic

This document contains the core strategy logic files for SwingScope, compiled for technical review.

## `config.py`

```python
"""
SwingScope Configuration
========================
All constants, thresholds, scoring weights, and keyword lists used throughout
the SwingScope analysis pipeline. Never modify these values without explicit
instruction.
"""

from typing import Final

# ─────────────────────────────────────────────
# Swing / Structure Detection
# ─────────────────────────────────────────────
SWING_LOOKBACK_BARS: Final[int] = 5        # Window each side for swing H/L detection
SR_CLUSTER_PCT: Final[float] = 0.005       # S/R levels within 0.5% are clustered
MAX_SR_LEVELS: Final[int] = 5              # Top N support / resistance levels returned

# ─────────────────────────────────────────────
# Volume Profile
# ─────────────────────────────────────────────
VP_LOOKBACK_DAYS: Final[int] = 60          # Rolling VP window
VP_BINS: Final[int] = 100                  # Price buckets
HVN_THRESHOLD: Final[float] = 1.5          # x avg bucket volume → High Volume Node
LVN_THRESHOLD: Final[float] = 0.4          # x avg bucket volume → Low Volume Node

# ─────────────────────────────────────────────
# Pattern Detection
# ─────────────────────────────────────────────
PATTERN_PROXIMITY_ATR: Final[float] = 0.75 # Max ATR distance for pattern context validity
VP_PROXIMITY_ATR: Final[float] = 0.5       # Max ATR distance for VP confluence scoring

# ─────────────────────────────────────────────
# Trade Parameters
# ─────────────────────────────────────────────
ENTRY_BUFFER_ATR: Final[float] = 0.05      # Entry above trigger candle high
SL_SWING_BUFFER_ATR: Final[float] = 0.10   # SL below last swing low
SL_ATR_CAPS: Final[dict[str, float]] = {
    'EMA Pullback': 2.5,
    'Bull Flag / Pennant': 2.0,
    'Breakout from Base': 2.5,
    'Volume Profile Reversal': 3.0,
    'Fibonacci Pullback': 2.5
}
MIN_RR_RATIO: Final[float] = 1.5           # Minimum acceptable R:R to pass gate
ACCOUNT_SIZE: Final[int] = 50_000         # Default paper trading account
MAX_LOSS_PER_TRADE: Final[float] = 500.0  # Max dollar loss per trade

# Risk per trade by conviction tier
RISK_HIGH_CONVICTION: Final[float] = 0.010  # 1.0%
RISK_VALID: Final[float] = 0.0075           # 0.75%
RISK_MARGINAL: Final[float] = 0.005         # 0.5%

# ─────────────────────────────────────────────
# Rate Limiting & Caching
# ─────────────────────────────────────────────
TICKER_SLEEP_SECS: Final[float] = 0.5      # Delay between tickers in batch mode
CACHE_TTL_HOURS: Final[int] = 24           # Data cache time-to-live
MAX_RETRIES: Final[int] = 3                # Max retry attempts on 429/network error
BACKOFF_BASE_SECS: Final[float] = 2.0      # Exponential backoff base (2, 4, 8 …)

# ─────────────────────────────────────────────
# Scoring Weights (Section 9.1)
# ─────────────────────────────────────────────
SCORE_TREND_MAX: Final[int] = 30
SCORE_PATTERN_MAX: Final[int] = 20
SCORE_RVOL_MAX: Final[int] = 15
SCORE_RSI_MAX: Final[int] = 15
SCORE_OBV_MAX: Final[int] = 10
SCORE_MACD_MAX: Final[int] = 10
SCORE_VP_MAX: Final[int] = 10

# Context modifiers
MOD_SECTOR_TAILWIND: Final[int] = 8
MOD_SECTOR_HEADWIND: Final[int] = -10
MOD_NEWS_BULLISH: Final[int] = 5
MOD_NEWS_BEARISH: Final[int] = -10
MOD_EARNINGS_WATCH: Final[int] = -5        # 21–45 days
MOD_EARNINGS_CAUTION: Final[int] = -10     # 8–21 days
MOD_EARNINGS_IMMINENT: Final[int] = -20    # ≤ 7 days

# Score thresholds
SCORE_HIGH_CONVICTION: Final[int] = 85
SCORE_VALID: Final[int] = 70
SCORE_MARGINAL: Final[int] = 55
SCORE_WEAK: Final[int] = 40

# ─────────────────────────────────────────────
# Setup Classifier Thresholds
# ─────────────────────────────────────────────
# EMA Pullback
EMA_PULLBACK_ATR_PROXIMITY: Final[float] = 1.0
EMA_PULLBACK_RSI_LOW: Final[float] = 40.0
EMA_PULLBACK_RSI_HIGH: Final[float] = 58.0
EMA_PULLBACK_RVOL_MAX: Final[float] = 0.9

# Breakout
BREAKOUT_ATR_CONTRACTION_PCT: Final[float] = 0.30   # ≥ 30% contraction
BREAKOUT_COIL_PCT: Final[float] = 0.03               # within 3% of resistance
BREAKOUT_RVOL_DRY: Final[float] = 0.7
BREAKOUT_RVOL_EXPANSION: Final[float] = 1.5
BREAKOUT_RSI_CEILING: Final[float] = 78.0
BB_SQUEEZE_THRESHOLD: Final[float] = 1.20
BB_SQUEEZE_MIN_BARS: Final[int] = 5

# Bull Flag
FLAG_IMPULSE_MIN_PCT: Final[float] = 0.05            # > 5% gain
FLAG_IMPULSE_MAX_BARS: Final[int] = 5
FLAG_PULLBACK_MAX_FIB: Final[float] = 0.618           # 61.8% Fib
FLAG_PULLBACK_MIN_BARS: Final[int] = 5
FLAG_PULLBACK_MAX_BARS: Final[int] = 15
FLAG_RSI_CEILING: Final[float] = 72.0

# Volume Profile Reversal
VP_REV_RSI_LONG_CEIL: Final[float] = 35.0
VP_REV_RSI_SHORT_FLOOR: Final[float] = 65.0
VP_REV_RVOL_MIN: Final[float] = 1.3

# Fibonacci Pullback
FIB_RSI_LOW: Final[float] = 42.0
FIB_RSI_HIGH: Final[float] = 58.0
FIB_MAX_RETRACEMENT: Final[float] = 0.786             # 78.6%

# ─────────────────────────────────────────────
# Sector ETF Map (Section 11.1)
# ─────────────────────────────────────────────
SECTOR_ETF_MAP: Final[dict[str, str]] = {
    "Technology":              "XLK",
    "Financial Services":      "XLF",
    "Healthcare":              "XLV",
    "Consumer Cyclical":       "XLY",
    "Consumer Defensive":      "XLP",
    "Industrials":             "XLI",
    "Energy":                  "XLE",
    "Basic Materials":         "XLB",
    "Real Estate":             "XLRE",
    "Utilities":               "XLU",
    "Communication Services":  "XLC",
}

# ─────────────────────────────────────────────
# News Keyword Sentiment Lists (Section 11.3)
# ─────────────────────────────────────────────
NEWS_BULLISH_KEYWORDS: Final[list[str]] = [
    "beat", "raised guidance", "buyback", "partnership",
    "upgraded", "record revenue", "new contract",
    "fda approval", "strong demand",
    "soaring", "winners", "win big", "rearmament", "contract win",
    "secures contract", "quadruple production", "record output",
    "geopolitical tailwind", "crack spread",
]

NEWS_BEARISH_KEYWORDS: Final[list[str]] = [
    "miss", "lowered guidance", "downgraded", "investigation",
    "lawsuit", "recall", "layoffs", "disappointing",
    "guidance cut", "sec probe",
]

NEWS_WATCH_KEYWORDS: Final[list[str]] = [
    "earnings", "results", "analyst day", "merger",
    "split", "ceo", "cfo", "conference",
]

# Yahoo RSS template
NEWS_RSS_URL: Final[str] = (
    "https://feeds.finance.yahoo.com/rss/2.0/headline"
    "?s={ticker}&region=US&lang=en-US"
)

```

## `analyze.py`

```python
#!/usr/bin/env python3
"""
SwingScope — Swing Trading Analysis System
============================================
CLI entry point.  Accepts one or more tickers, runs the full deterministic
analysis pipeline, and outputs self-contained interactive HTML reports.

Usage
-----
    python analyze.py AAPL
    python analyze.py AAPL NVDA MSFT --account 50000
    python analyze.py AAPL --no-cache
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.logging import RichHandler

import config as cfg

# ── Configure logging ────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True, show_time=False)],
)
logger = logging.getLogger("swingscope")
console = Console()


def analyze_ticker(
    ticker: str,
    account_size: int = cfg.ACCOUNT_SIZE,
    output_dir: Optional[Path] = None,
) -> Optional[dict]:
    """Run the full analysis pipeline for a single ticker.

    Parameters
    ----------
    ticker : str
        Stock symbol.
    account_size : int
        Account value for position sizing.
    output_dir : Path or None
        Report output directory.

    Returns
    -------
    dict or None
        Summary dict with ticker, setup, score, R:R; or None on failure.
    """
    from data.fetcher import fetch_ohlcv, fetch_weekly
    from indicators.engine import add_indicators
    from indicators.volume_profile import compute_volume_profile
    from analysis.structure import analyze_structure, classify_trend
    from analysis.patterns import detect_patterns
    from analysis.fibonacci import compute_fibonacci
    from analysis.setup_classifier import classify_setups
    from analysis.trade_params import calculate_trade_params
    from context.sector import analyze_sector
    from context.earnings import analyze_earnings
    from context.news import analyze_news
    from report.chart_builder import build_chart
    from report.renderer import render_report

    console.rule(f"[bold cyan]{ticker}[/bold cyan]")

    # ── Step 1: Data ─────────────────────────────────────────
    console.print("[dim]Fetching data…[/dim]")
    df = fetch_ohlcv(ticker)
    if df is None or len(df) < 50:
        console.print(f"[red]✗ {ticker}: insufficient data — skipping[/red]")
        return None

    # ── Step 2: Indicators ───────────────────────────────────
    console.print("[dim]Computing indicators…[/dim]")
    df = add_indicators(df)

    # ── Step 3: Volume Profile ───────────────────────────────
    console.print("[dim]Building volume profile…[/dim]")
    vp = compute_volume_profile(df)

    # ── Step 4: Structure ────────────────────────────────────
    console.print("[dim]Analyzing structure…[/dim]")
    structure = analyze_structure(df)

    # ── Step 5: Patterns ─────────────────────────────────────
    console.print("[dim]Detecting candlestick patterns…[/dim]")
    atr = float(df["ATR_14"].iloc[-1]) if "ATR_14" in df.columns else 1.0
    structural_levels = (
        [s.price for s in structure.support_levels]
        + [s.price for s in structure.resistance_levels]
    )
    # Add EMA levels
    last = df.iloc[-1]
    for ema_col in ("EMA_21", "EMA_50", "EMA_200"):
        if ema_col in df.columns and not df[ema_col].isna().iloc[-1]:
            structural_levels.append(float(last[ema_col]))
    # Add VP levels
    if vp:
        structural_levels.extend([vp.poc, vp.vah, vp.val])

    patterns = detect_patterns(df, structural_levels, atr)

    # ── Step 6: Fibonacci ────────────────────────────────────
    console.log("Computing Fibonacci levels…")
    fib = compute_fibonacci(
        df,
        structure,
        float(df["Close"].iloc[-1])
    )

    # ── Step 7: Context ──────────────────────────────────────
    console.print("[dim]Analyzing sector…[/dim]")
    sector = analyze_sector(ticker)

    console.print("[dim]Checking earnings…[/dim]")
    earnings = analyze_earnings(ticker)

    console.print("[dim]Scanning news…[/dim]")
    news = analyze_news(ticker)

    context_modifier = sector.modifier + earnings.modifier + news.modifier

    # ── Step 8: Weekly trend (for multi-TF checks) ───────────
    weekly_trend = None
    weekly_df = fetch_weekly(ticker)
    if weekly_df is not None and len(weekly_df) >= 50:
        from indicators.engine import add_indicators as add_weekly_ind
        weekly_df = add_weekly_ind(weekly_df)
        weekly_trend = classify_trend(weekly_df)

    # ── Step 9: Setup Classification ─────────────────────────
    console.print("[dim]Classifying setups…[/dim]")
    setups = classify_setups(
        df, structure, patterns, vp, fib,
        context_modifier=context_modifier,
        weekly_trend=weekly_trend,
    )
    top_setup = setups[0]

    # ── Step 10: Trade Parameters ────────────────────────────
    trade = None
    if top_setup.final_score >= cfg.SCORE_WEAK:
        console.print("[dim]Calculating trade parameters…[/dim]")
        trigger_high = float(last["High"])
        swing_low = structure.swing_lows[-1].price if structure.swing_lows else float(last["Low"])

        trade = calculate_trade_params(
            setup=top_setup,
            trigger_candle_high=trigger_high,
            last_swing_low=swing_low,
            atr=atr,
            resistance_levels=structure.resistance_levels,
            vp=vp,
            account_size=account_size,
        )

    # ── Step 11: Chart ───────────────────────────────────────
    console.print("[dim]Building chart…[/dim]")
    chart_json = build_chart(df, structure, patterns, vp, fib, trade, ticker)

    # ── Step 12: Report ──────────────────────────────────────
    console.print("[dim]Rendering report…[/dim]")
    report_path = render_report(
        ticker=ticker,
        df=df,
        setup=top_setup,
        trade=trade,
        chart_json=chart_json,
        sector=sector,
        earnings=earnings,
        news=news,
        vp=vp,
        fib=fib,
        patterns=patterns,
        output_dir=output_dir,
    )

    console.print(f"[green]✓ Report: {report_path}[/green]")

    return {
        "ticker": ticker,
        "setup": top_setup.setup_type.value,
        "score": top_setup.final_score,
        "verdict": top_setup.verdict.value,
        "rr": trade.rr_tp1 if trade else 0,
        "report": str(report_path),
    }


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="swingscope",
        description="SwingScope — Swing Trading Analysis System",
    )
    parser.add_argument(
        "tickers",
        nargs="+",
        type=str,
        help="One or more stock ticker symbols (e.g. AAPL NVDA MSFT)",
    )
    parser.add_argument(
        "--account",
        type=int,
        default=cfg.ACCOUNT_SIZE,
        help=f"Account size for position sizing (default: {cfg.ACCOUNT_SIZE:,})",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Force fresh data fetch (ignore cache)",
    )
    args = parser.parse_args()

    # Clear cache if requested
    if args.no_cache:
        cache_dir = Path(__file__).resolve().parent / "data" / "cache"
        if cache_dir.exists():
            for f in cache_dir.glob("*.parquet"):
                f.unlink()
            console.print("[yellow]Cache cleared[/yellow]")

    # Determine output directory
    is_batch = len(args.tickers) > 1
    if is_batch:
        date_str = datetime.now().strftime("%Y%m%d")
        output_dir = Path(__file__).resolve().parent / "reports" / f"batch_{date_str}"
    else:
        output_dir = Path(__file__).resolve().parent / "reports"

    # Process tickers
    results: list[dict] = []
    for i, ticker in enumerate(args.tickers):
        ticker = ticker.upper().strip()
        try:
            result = analyze_ticker(ticker, args.account, output_dir)
            if result:
                results.append(result)
        except Exception as exc:
            console.print(f"[red]✗ {ticker}: {exc}[/red]")
            logger.exception("Error analyzing %s", ticker)

        # Rate limiting between tickers
        if i < len(args.tickers) - 1:
            time.sleep(cfg.TICKER_SLEEP_SECS)

    # Summary table
    if results:
        console.print()
        table = Table(
            title="SwingScope Summary",
            show_header=True,
            header_style="bold cyan",
            border_style="dim",
        )
        table.add_column("Ticker", style="bold")
        table.add_column("Setup")
        table.add_column("Score", justify="right")
        table.add_column("Verdict")
        table.add_column("R:R", justify="right")

        for r in results:
            score = r["score"]
            if score >= cfg.SCORE_HIGH_CONVICTION:
                style = "green"
            elif score >= cfg.SCORE_VALID:
                style = "blue"
            elif score >= cfg.SCORE_MARGINAL:
                style = "yellow"
            else:
                style = "red"

            table.add_row(
                r["ticker"],
                r["setup"],
                f"[{style}]{score}[/{style}]",
                r["verdict"],
                f"{r['rr']:.2f}",
            )
        console.print(table)
    else:
        console.print("[yellow]No valid results produced.[/yellow]")


if __name__ == "__main__":
    main()

```

## `analysis/setup_classifier.py`

```python
"""
SwingScope Setup Classifier
=============================
Evaluates the current market state against 5 swing trading setup types,
scores each setup using the 7-factor validity system (Section 9), applies
hard invalidation gates and context modifiers, and returns a ranked list
of ``SetupResult`` objects.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd
from scipy.stats import linregress

import config as cfg
from analysis.fibonacci import FibResult
from analysis.patterns import PatternMatch, PatternSignal
from analysis.structure import SRLevel, StructureResult, SwingPoint, Trend
from indicators.volume_profile import VolumeProfile

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Data types
# ──────────────────────────────────────────────────────────────
class SetupType(str, Enum):
    EMA_PULLBACK = "EMA Pullback"
    BREAKOUT = "Breakout from Base"
    BULL_FLAG = "Bull Flag / Pennant"
    VP_REVERSAL = "Volume Profile Reversal"
    FIB_PULLBACK = "Fibonacci Pullback"


class Verdict(str, Enum):
    HIGH_CONVICTION = "HIGH CONVICTION"
    VALID = "VALID SETUP"
    MARGINAL = "MARGINAL"
    WEAK = "WEAK"
    INVALIDATED = "INVALIDATED"


@dataclass
class ScoreFactor:
    """One row in the 7-factor scoring table."""
    name: str
    max_pts: int
    earned: int
    detail: str = ""


@dataclass
class SetupResult:
    """Complete output for one evaluated setup."""
    setup_type: SetupType
    direction: str = "LONG"
    raw_score: int = 0
    context_modifier: int = 0
    final_score: int = 0
    verdict: Verdict = Verdict.INVALIDATED
    factors: list[ScoreFactor] = field(default_factory=list)
    invalidation_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    hard_invalidated: bool = False

    # Thesis variables
    rvol_avg: float = 1.0
    rsi: float = 50.0
    macd_state: str = "flattening"


# ──────────────────────────────────────────────────────────────
# Shared scoring helpers
# ──────────────────────────────────────────────────────────────
def _score_trend(trend: Trend) -> ScoreFactor:
    """Score factor 1 — Trend Alignment (max 30)."""
    mapping = {
        Trend.STRONG_UPTREND: (30, "All EMAs stacked & rising"),
        Trend.UPTREND:        (22, "EMA50 + EMA200 aligned"),
        Trend.WEAK_UPTREND:   (12, "EMA50 only"),
        Trend.RANGE:          (5,  "Mixed / ranging"),
        Trend.DOWNTREND:      (0,  "Below EMA50 — HARD STOP"),
    }
    pts, detail = mapping.get(trend, (0, "Unknown"))
    return ScoreFactor("Trend Alignment", cfg.SCORE_TREND_MAX, pts, detail)


def _score_pattern(patterns: list[PatternMatch]) -> ScoreFactor:
    """Score factor 2 — Candlestick Pattern (max 20)."""
    confirmed = [p for p in patterns if p.confirmed]
    if confirmed:
        return ScoreFactor("Candlestick Pattern", cfg.SCORE_PATTERN_MAX, 20,
                           f"{confirmed[0].name} at structure")
    if patterns:
        return ScoreFactor("Candlestick Pattern", cfg.SCORE_PATTERN_MAX, 10,
                           f"{patterns[0].name} — weak context")
    return ScoreFactor("Candlestick Pattern", cfg.SCORE_PATTERN_MAX, 0, "No pattern")


def _score_rvol(df: pd.DataFrame) -> ScoreFactor:
    """Score factor 3 — Volume RVol (max 15)."""
    if "RVOL" not in df.columns or len(df) < 3:
        return ScoreFactor("Volume — RVol", cfg.SCORE_RVOL_MAX, 0, "No RVol data")

    rvol_last = float(df["RVOL"].iloc[-1])
    # Check pullback dryness (prior bars) and reversal spike (last bar)
    rvol_prior = df["RVOL"].iloc[-4:-1].mean() if len(df) >= 4 else rvol_last
    dry = rvol_prior < 0.8
    spike = rvol_last > 1.3

    if dry and spike:
        return ScoreFactor("Volume — RVol", cfg.SCORE_RVOL_MAX, 15,
                           f"Dry pullback ({rvol_prior:.2f}) + spike ({rvol_last:.2f})")
    if dry or spike:
        detail = f"Dry pullback ({rvol_prior:.2f})" if dry else f"Spike ({rvol_last:.2f})"
        return ScoreFactor("Volume — RVol", cfg.SCORE_RVOL_MAX, 8, detail)
    return ScoreFactor("Volume — RVol", cfg.SCORE_RVOL_MAX, 0,
                       f"No confirmation (prior={rvol_prior:.2f}, last={rvol_last:.2f})")


def score_rsi_context(rsi: float, direction: str = "LONG") -> tuple[int, str, bool, str]:
    """Returns (points, label, is_invalid, warning_flag)."""
    if rsi < 35:
        return 0, "INVALIDATED_OVERSOLD", True, ""
    elif 35 <= rsi < 40:
        return 7, "DEEP_FLUSH", False, "DEEP_FLUSH_RSI"
    elif 40 <= rsi <= 58:
        return 15, "IDEAL_RESET", False, ""
    elif 58 < rsi <= 65:
        return 5, "INSUFFICIENT_RESET", False, ""
    else:
        return 0, "INVALIDATED_OVERBOUGHT", True, ""


def _score_rsi(df: pd.DataFrame) -> ScoreFactor:
    """Score factor 4 — RSI Context (max 15)."""
    if "RSI_14" not in df.columns:
        return ScoreFactor("RSI Context", cfg.SCORE_RSI_MAX, 0, "No RSI")
    rsi = float(df["RSI_14"].iloc[-1])
    pts, label, _, _ = score_rsi_context(rsi, "LONG")
    return ScoreFactor("RSI Context", cfg.SCORE_RSI_MAX, pts, f"{label} ({rsi:.1f})")


def _score_obv(df: pd.DataFrame) -> ScoreFactor:
    """Score factor 5 — OBV Conviction (max 10)."""
    if "OBV" not in df.columns or len(df) < 20:
        return ScoreFactor("OBV Conviction", cfg.SCORE_OBV_MAX, 0, "No OBV data")

    obv = df["OBV"].iloc[-20:]
    obv_trend = np.polyfit(range(len(obv)), obv.values, 1)[0]

    # Check for bearish divergence: price up but OBV down
    price_trend = np.polyfit(range(len(obv)), df["Close"].iloc[-20:].values, 1)[0]
    divergence = price_trend > 0 and obv_trend < 0

    if divergence:
        return ScoreFactor("OBV Conviction", cfg.SCORE_OBV_MAX, 0,
                           "Bearish divergence ⚠")
    if obv_trend > 0:
        return ScoreFactor("OBV Conviction", cfg.SCORE_OBV_MAX, 10, "OBV trending up")
    return ScoreFactor("OBV Conviction", cfg.SCORE_OBV_MAX, 5, "Flat / neutral")


def get_macd_histogram_state(df: pd.DataFrame) -> str:
    """Returns the MACD histogram momentum state."""
    if "MACD_hist" not in df.columns or len(df) < 3:
        return "UNKNOWN"
        
    hist_now = float(df["MACD_hist"].iloc[-1])
    hist_prev = float(df["MACD_hist"].iloc[-2])
    hist_prev2 = float(df["MACD_hist"].iloc[-3])
    
    # CONFIRMED_BOTTOM: Negative, but slope has been increasing for 2+ bars
    if hist_now < 0 and hist_now > hist_prev and hist_prev > hist_prev2:
        return "CONFIRMED_BOTTOM"
        
    # ZERO_CROSS: Crossed from negative to positive on this bar
    if hist_now >= 0 and hist_prev < 0:
        return "ZERO_CROSS"
        
    # EARLY_TURN: Negative, turned up on this bar (1 bar only)
    if hist_now < 0 and hist_now > hist_prev and hist_prev <= hist_prev2:
        return "EARLY_TURN"
        
    # STILL_FALLING: Negative and slope is decreasing/flat
    if hist_now < 0 and hist_now <= hist_prev:
        return "STILL_FALLING"
        
    if hist_now >= 0:
        return "POSITIVE"
        
    return "UNKNOWN"

def _score_macd(df: pd.DataFrame) -> ScoreFactor:
    """Score factor 6 — MACD Confluence (max 10)."""
    state = get_macd_histogram_state(df)
    
    if state in ("CONFIRMED_BOTTOM", "ZERO_CROSS", "POSITIVE"):
        return ScoreFactor("MACD Confluence", cfg.SCORE_MACD_MAX, 10, state)
    elif state == "EARLY_TURN":
        return ScoreFactor("MACD Confluence", cfg.SCORE_MACD_MAX, 5, state)
    else:
        return ScoreFactor("MACD Confluence", cfg.SCORE_MACD_MAX, 0, state)


def _score_vp_confluence(
    current_price: float,
    vp: Optional[VolumeProfile],
    atr: float,
) -> ScoreFactor:
    """Score factor 7 — VP Confluence (max 10)."""
    if vp is None or atr <= 0:
        return ScoreFactor("VP Confluence", cfg.SCORE_VP_MAX, 0, "No VP data")

    key_levels = [vp.poc, vp.vah, vp.val] + vp.hvns
    near_thresh = cfg.VP_PROXIMITY_ATR * atr
    far_thresh = 1.0 * atr

    for lv in key_levels:
        dist = abs(current_price - lv)
        if dist <= near_thresh:
            return ScoreFactor("VP Confluence", cfg.SCORE_VP_MAX, 10,
                               f"At VP level ({lv:.2f})")
        if dist <= far_thresh:
            return ScoreFactor("VP Confluence", cfg.SCORE_VP_MAX, 5,
                               f"Near VP level ({lv:.2f})")

    return ScoreFactor("VP Confluence", cfg.SCORE_VP_MAX, 0, "No VP proximity")


# ──────────────────────────────────────────────────────────────
# Setup-specific requirement checks
# ──────────────────────────────────────────────────────────────
def get_pullback_window(df: pd.DataFrame, structure: StructureResult) -> int:
    """Returns count of consecutive bars since last swing high."""
    if not structure.swing_highs:
        return min(len(df), 10)
    last_high_idx = structure.swing_highs[-1].idx
    bars_since = len(df) - 1 - last_high_idx
    return max(1, bars_since)

def check_pullback_volume(df: pd.DataFrame, structure: StructureResult, threshold: float = 0.90) -> tuple[bool, float]:
    """Calculates avg RVol over the full pullback window (not just last bar)."""
    window = get_pullback_window(df, structure)
    if "RVOL" not in df.columns or len(df) < window + 1:
        return False, 1.0
    if window > 1:
        avg_rvol = float(df["RVOL"].iloc[-(window+1):-1].mean())
    else:
        avg_rvol = float(df["RVOL"].iloc[-1])
    return avg_rvol <= threshold, avg_rvol

def check_bb_squeeze(df: pd.DataFrame) -> tuple[bool, int, float]:
    """Returns (is_squeeze, squeeze_duration_bars, width_ratio)."""
    if "BB_width" not in df.columns or len(df) < 60:
        return False, 0, 999.0
    
    bb_width_now = float(df["BB_width"].iloc[-1])
    bb_width_min = float(df["BB_width"].iloc[-60:].min())
    width_ratio = bb_width_now / bb_width_min if bb_width_min > 0 else 999.0
    is_squeeze = width_ratio <= cfg.BB_SQUEEZE_THRESHOLD
    
    squeeze_duration = 0
    if is_squeeze:
        threshold_val = bb_width_min * cfg.BB_SQUEEZE_THRESHOLD
        for width in reversed(df["BB_width"].iloc[-60:].values):
            if width <= threshold_val:    
                squeeze_duration += 1
            else:
                break
                
    return is_squeeze, squeeze_duration, width_ratio

def check_flag_volume_declining(df: pd.DataFrame, flag_length: int) -> tuple[bool, float]:
    """Returns (is_declining, slope_pct) using linear regression over flag period."""
    if "RVOL" not in df.columns or len(df) < flag_length:
        return False, 0.0
    
    rvol_data = df["RVOL"].iloc[-flag_length:].values
    slope, _, _, _, _ = linregress(range(flag_length), rvol_data)
    
    is_declining = slope < 0
    return is_declining, float(slope)

def _check_ema_pullback(df: pd.DataFrame, patterns: list[PatternMatch], structure: StructureResult) -> tuple[bool, list[str], list[str]]:
    """Return (is_valid, invalidation_reasons, warnings) for Setup 1."""
    reasons = []
    warnings = []
    last = df.iloc[-1]
    close, ema50, ema200 = float(last["Close"]), float(last["EMA_50"]), float(last["EMA_200"])
    if close < ema50:
        reasons.append("Close below EMA50")
    if close < ema200:
        reasons.append("Close below EMA200")

    rsi = float(last["RSI_14"]) if "RSI_14" in df.columns else 50
    _, rsi_label, is_invalid, rsi_warn = score_rsi_context(rsi, "LONG")
    if is_invalid:
        reasons.append(f"RSI {rsi_label} ({rsi:.1f})")
    if rsi_warn:
        warnings.append(rsi_warn)

    macd_state = get_macd_histogram_state(df)
    if macd_state == "STILL_FALLING":
        reasons.append("MACD histogram STILL_FALLING")

    confirmed_patterns = [p for p in patterns if p.confirmed]
    if not confirmed_patterns:
        reasons.append("No confirmed candlestick reversal pattern")

    # Proximity to EMA21 or EMA50
    atr = float(last["ATR_14"]) if "ATR_14" in df.columns else 1
    ema21 = float(last["EMA_21"])
    near_ema = min(abs(close - ema21), abs(close - ema50)) <= cfg.EMA_PULLBACK_ATR_PROXIMITY * atr
    if not near_ema:
        reasons.append("Not near EMA21/EMA50")

    rvol = float(last["RVOL"]) if "RVOL" in df.columns else 1
    if rvol > cfg.EMA_PULLBACK_RVOL_MAX:
        # Check if high-vol through EMA (invalidation)
        if close < ema21:
            reasons.append(f"High volume through EMA (RVol={rvol:.2f})")
            
    is_dry, avg_rvol = check_pullback_volume(df, structure, threshold=0.90)
    if not is_dry:
        reasons.append(f"Pullback volume not dry (avg RVol={avg_rvol:.2f})")

    return len(reasons) == 0, reasons, warnings


def _check_breakout(df: pd.DataFrame, structure: StructureResult, vp: Optional[VolumeProfile]) -> tuple[bool, list[str], list[str]]:
    """Return (is_valid, invalidation_reasons, warnings) for Setup 2."""
    reasons = []
    warnings = []
    last = df.iloc[-1]
    atr = float(last["ATR_14"]) if "ATR_14" in df.columns else 1

    # ATR contraction
    if len(df) >= 20 and "ATR_14" in df.columns:
        atr_now = float(df["ATR_14"].iloc[-1])
        atr_past = float(df["ATR_14"].iloc[-20])
        if atr_past > 0:
            contraction = 1.0 - (atr_now / atr_past)
            if contraction < cfg.BREAKOUT_ATR_CONTRACTION_PCT:
                reasons.append(f"ATR contraction only {contraction:.0%}")

    # Price near resistance
    if structure.resistance_levels:
        nearest_r = min(structure.resistance_levels, key=lambda x: abs(x.price - float(last["Close"])))
        dist_pct = abs(float(last["Close"]) - nearest_r.price) / nearest_r.price
        if dist_pct > cfg.BREAKOUT_COIL_PCT:
            reasons.append(f"Not coiling near resistance ({dist_pct:.1%} away)")

    rvol = float(last["RVOL"]) if "RVOL" in df.columns else 1
    if rvol < cfg.BREAKOUT_RVOL_EXPANSION:
        reasons.append(f"Breakout on low volume (RVol={rvol:.2f})")

    if len(df) >= 6:
        base_rvol = float(df["RVOL"].iloc[-6:-1].mean())
        if base_rvol > cfg.BREAKOUT_RVOL_DRY:
            reasons.append(f"Base volume not dry (avg RVol={base_rvol:.2f})")

    if "BB_width" in df.columns and len(df) >= 60:
        is_squeeze, squeeze_duration, _ = check_bb_squeeze(df)
        if not is_squeeze:
            reasons.append("Bollinger Band width not tightly squeezed")
        elif squeeze_duration < cfg.BB_SQUEEZE_MIN_BARS:
            warnings.append("SQUEEZE_YOUNG")

    if "MACD" in df.columns:
        macd_val = float(last["MACD"])
        if macd_val <= 0:
            reasons.append(f"MACD below zero ({macd_val:.2f})")

    rsi = float(last["RSI_14"]) if "RSI_14" in df.columns else 50
    if rsi > cfg.BREAKOUT_RSI_CEILING:
        reasons.append(f"RSI too high ({rsi:.1f})")

    # Major HVN above
    if vp and vp.hvns:
        close = float(last["Close"])
        hvns_above = [h for h in vp.hvns if h > close and abs(h - close) < 2 * atr]
        if hvns_above:
            reasons.append(f"Major HVN immediately above ({hvns_above[0]:.2f})")

    return len(reasons) == 0, reasons, warnings


def _check_bull_flag(df: pd.DataFrame) -> tuple[bool, list[str], list[str]]:
    """Return (is_valid, invalidation_reasons, warnings) for Setup 3."""
    reasons = []
    warnings = []
    if len(df) < 25:
        reasons.append("Insufficient data for flag detection")
        return False, reasons, warnings

    last = df.iloc[-1]
    close = float(last["Close"])

    # Look for impulse leg in the last 25 bars
    found_flag = False
    flag_length = 5
    for start_idx in range(len(df) - 25, len(df) - 10):
        if start_idx < 0:
            continue
        for end_idx in range(start_idx + 1, min(start_idx + cfg.FLAG_IMPULSE_MAX_BARS + 1, len(df) - 5)):
            start_price = float(df["Close"].iloc[start_idx])
            end_price = float(df["Close"].iloc[end_idx])
            if start_price == 0:
                continue
            gain = (end_price - start_price) / start_price
            if gain >= cfg.FLAG_IMPULSE_MIN_PCT:
                # Found impulse — check pullback
                remaining_bars = len(df) - 1 - end_idx
                if cfg.FLAG_PULLBACK_MIN_BARS <= remaining_bars <= cfg.FLAG_PULLBACK_MAX_BARS:
                    pullback_low = float(df["Low"].iloc[end_idx:].min())
                    retracement = (end_price - pullback_low) / (end_price - start_price) if end_price != start_price else 1
                    if retracement <= cfg.FLAG_PULLBACK_MAX_FIB:
                        found_flag = True
                        flag_length = remaining_bars
                        break
        if found_flag:
            break

    if not found_flag:
        reasons.append("No valid flag pattern detected")
        return False, reasons, warnings

    ema21 = float(last["EMA_21"]) if "EMA_21" in df.columns else close
    if close < ema21:
        reasons.append("Price below EMA21 during flag")

    if "MACD_hist" in df.columns and "MACD" in df.columns and "MACD_signal" in df.columns:
        macd_val = float(last["MACD"])
        signal_val = float(last["MACD_signal"])
        hist_val = float(last["MACD_hist"])
        if macd_val <= signal_val:
            reasons.append("MACD below signal line")
        if hist_val <= 0:
            reasons.append("MACD histogram negative")

    if len(df) >= flag_length:
        is_declining, slope = check_flag_volume_declining(df, flag_length)
        if not is_declining:
            reasons.append(f"Volume expanding in pullback (slope={slope:.3f})")

    rsi = float(last["RSI_14"]) if "RSI_14" in df.columns else 50
    if rsi > cfg.FLAG_RSI_CEILING:
        reasons.append(f"RSI too high at entry ({rsi:.1f})")

    return len(reasons) == 0, reasons, warnings


def _check_vp_reversal(
    df: pd.DataFrame,
    vp: Optional[VolumeProfile],
    patterns: list[PatternMatch],
    fib: Optional[FibResult],
    weekly_trend: Optional[Trend],
) -> tuple[bool, list[str], list[str]]:
    """Return (is_valid, invalidation_reasons, warnings) for Setup 4."""
    reasons = []
    warnings = []
    if vp is None:
        reasons.append("No volume profile data")
        return False, reasons, warnings

    last = df.iloc[-1]
    close = float(last["Close"])
    atr = float(last["ATR_14"]) if "ATR_14" in df.columns else 1

    # Price at VP level
    key_vp = [vp.poc, vp.vah, vp.val] + vp.hvns
    near = any(abs(close - lv) <= cfg.VP_PROXIMITY_ATR * atr for lv in key_vp)
    if not near:
        reasons.append("Not at a VP key level")

    # Reversal candlestick
    confirmed_patterns = [p for p in patterns if p.confirmed]
    if not confirmed_patterns:
        reasons.append("No confirmed candlestick at VP level")

    # RSI extreme
    rsi = float(last["RSI_14"]) if "RSI_14" in df.columns else 50
    if not (rsi <= cfg.VP_REV_RSI_LONG_CEIL or rsi >= cfg.VP_REV_RSI_SHORT_FLOOR):
        reasons.append(f"RSI not at extreme ({rsi:.1f})")

    # RVol spike
    rvol = float(last["RVOL"]) if "RVOL" in df.columns else 1
    if rvol < cfg.VP_REV_RVOL_MIN:
        reasons.append(f"No RVol spike ({rvol:.2f})")

    # LVN check (price in void = no support)
    if vp.lvns:
        in_lvn = any(abs(close - lv) <= 0.3 * atr for lv in vp.lvns)
        if in_lvn:
            reasons.append("Price in LVN void — no support")

    # Fibonacci confluence
    if fib:
        has_fib_confluence = False
        for lv in fib.levels:
            if lv.ratio in (0.382, 0.500, 0.618):
                if abs(close - lv.price) <= 1.0 * atr:
                    has_fib_confluence = True
                    break
        if not has_fib_confluence:
            reasons.append("No Fibonacci confluence at VP level")
    else:
        reasons.append("No Fibonacci data for confluence check")

    # Weekly trend opposing
    if weekly_trend in (Trend.DOWNTREND,):
        reasons.append("Weekly trend opposing")

    return len(reasons) == 0, reasons, warnings


def _check_fib_pullback(
    df: pd.DataFrame,
    fib: Optional[FibResult],
    vp: Optional[VolumeProfile],
    weekly_trend: Optional[Trend],
) -> tuple[bool, list[str], list[str]]:
    """Return (is_valid, invalidation_reasons, warnings) for Setup 5."""
    reasons = []
    warnings = []
    if fib is None:
        reasons.append("No Fibonacci data")
        return False, reasons, warnings

    last = df.iloc[-1]
    close = float(last["Close"])
    atr = float(last["ATR_14"]) if "ATR_14" in df.columns else 1

    # Check if price is at a Fibonacci level
    at_fib = False
    for lv in fib.levels:
        if lv.ratio in (0.382, 0.500, 0.618):
            if abs(close - lv.price) <= 1.0 * atr:
                at_fib = True
                break
    if not at_fib:
        reasons.append("Not at a key Fibonacci level")

    # Check for VP/EMA confluence
    has_confluence = False
    if vp:
        for vp_lv in [vp.poc, vp.vah, vp.val] + vp.hvns:
            if abs(close - vp_lv) <= 1.0 * atr:
                has_confluence = True
                break
    ema21 = float(last["EMA_21"]) if "EMA_21" in df.columns else close
    ema50 = float(last["EMA_50"]) if "EMA_50" in df.columns else close
    if abs(close - ema21) <= 1.0 * atr or abs(close - ema50) <= 1.0 * atr:
        has_confluence = True
    if not has_confluence:
        reasons.append("No VP/EMA confluence at Fib level")

    # RSI zone
    rsi = float(last["RSI_14"]) if "RSI_14" in df.columns else 50
    if not (cfg.FIB_RSI_LOW <= rsi <= cfg.FIB_RSI_HIGH):
        reasons.append(f"RSI out of zone ({rsi:.1f})")

    # Max retracement check
    retracement = abs(close - fib.swing_high) / abs(fib.swing_high - fib.swing_low) if fib.swing_high != fib.swing_low else 1
    if retracement > cfg.FIB_MAX_RETRACEMENT:
        reasons.append(f"Retracement too deep ({retracement:.1%})")

    # MACD histogram state
    macd_state = get_macd_histogram_state(df)
    if macd_state == "STILL_FALLING":
        reasons.append("MACD histogram STILL_FALLING")

    # Weekly trend
    if weekly_trend in (Trend.DOWNTREND,):
        reasons.append("Weekly trend opposing")

    return len(reasons) == 0, reasons, warnings


# ──────────────────────────────────────────────────────────────
# Verdict mapper
# ──────────────────────────────────────────────────────────────
def _map_verdict(score: int) -> Verdict:
    if score >= cfg.SCORE_HIGH_CONVICTION:
        return Verdict.HIGH_CONVICTION
    if score >= cfg.SCORE_VALID:
        return Verdict.VALID
    if score >= cfg.SCORE_MARGINAL:
        return Verdict.MARGINAL
    if score >= cfg.SCORE_WEAK:
        return Verdict.WEAK
    return Verdict.INVALIDATED


# ──────────────────────────────────────────────────────────────
# Main classifier
# ──────────────────────────────────────────────────────────────
def classify_setups(
    df: pd.DataFrame,
    structure: StructureResult,
    patterns: list[PatternMatch],
    vp: Optional[VolumeProfile],
    fib: Optional[FibResult],
    context_modifier: int = 0,
    weekly_trend: Optional[Trend] = None,
) -> list[SetupResult]:
    """Evaluate all 5 setups and return ranked results.

    Hard invalidation gates (Section 9.4) are checked **first**.  If any
    gate fires, the setup is immediately marked ``INVALIDATED``.

    Parameters
    ----------
    df : pd.DataFrame
        Enriched OHLCV DataFrame.
    structure : StructureResult
        Output of ``analyze_structure``.
    patterns : list[PatternMatch]
        Detected candlestick patterns.
    vp : VolumeProfile or None
        Volume profile data.
    fib : FibResult or None
        Fibonacci retracement data.
    context_modifier : int
        Sum of all context modifiers (sector + earnings + news).
    weekly_trend : Trend or None
        Weekly timeframe trend for multi-TF checks.

    Returns
    -------
    list[SetupResult]
        All 5 setup evaluations, sorted by final score descending.
    """
    last = df.iloc[-1]
    current_price = float(last["Close"])
    atr = float(last["ATR_14"]) if "ATR_14" in df.columns else 1.0

    # ── Universal hard invalidation gates ────────────────────
    hard_gates: list[str] = []
    if structure.trend == Trend.DOWNTREND:
        hard_gates.append(f"Price below EMA50 — NO LONG SETUP")

    # OBV divergence (computed in scorer, but we flag it here too)
    if "OBV" in df.columns and len(df) >= 20:
        obv_slope = np.polyfit(range(20), df["OBV"].iloc[-20:].values, 1)[0]
        price_slope = np.polyfit(range(20), df["Close"].iloc[-20:].values, 1)[0]
        if price_slope > 0 and obv_slope < 0:
            hard_gates.append("OBV bearish divergence detected")

    # ── Deterministic Thesis Variables ────────────────────────
    rsi_val = float(last.get("RSI_14", 50.0))
    macd_state_val = get_macd_histogram_state(df)
    
    # We want the exact pullback volume calculation for the thesis text,
    # falling back to average rvol if check_pullback_volume is irrelevant/fails.
    try:
        from analysis.setup_classifier import check_pullback_volume
        _, rvol_avg_val = check_pullback_volume(df, structure)
    except Exception:
        # Fallback to general rvol
        rvol_avg_val = float(df["RVOL"].iloc[-4:-1].mean()) if len(df) >= 4 else float(last.get("RVOL", 1.0))

    # ── Common scoring factors ───────────────────────────────
    f_trend = _score_trend(structure.trend)
    f_pattern = _score_pattern(patterns)
    f_rvol = _score_rvol(df)
    f_rsi = _score_rsi(df)
    f_obv = _score_obv(df)
    f_macd = _score_macd(df)
    f_vp = _score_vp_confluence(current_price, vp, atr)
    common_factors = [f_trend, f_pattern, f_rvol, f_rsi, f_obv, f_macd, f_vp]
    raw = sum(f.earned for f in common_factors)

    # ── Per-setup evaluation ─────────────────────────────────
    setup_checks = {
        SetupType.EMA_PULLBACK: lambda: _check_ema_pullback(df, patterns, structure),
        SetupType.BREAKOUT: lambda: _check_breakout(df, structure, vp),
        SetupType.BULL_FLAG: lambda: _check_bull_flag(df),
        SetupType.VP_REVERSAL: lambda: _check_vp_reversal(df, vp, patterns, fib, weekly_trend),
        SetupType.FIB_PULLBACK: lambda: _check_fib_pullback(df, fib, vp, weekly_trend),
    }

    results: list[SetupResult] = []
    for setup_type, checker in setup_checks.items():
        is_valid, inv_reasons, checker_warnings = checker()
        all_reasons = hard_gates + inv_reasons

        factors = [ScoreFactor(f.name, f.max_pts, f.earned, f.detail) for f in common_factors]
        final = max(0, min(100, raw + context_modifier))

        warnings: list[str] = list(checker_warnings)
        hard_inv = len(hard_gates) > 0

        if not is_valid or hard_inv:
            final = min(final, cfg.SCORE_WEAK - 1)
            if hard_inv:
                final = 0

        # Cap breakout on low RVol
        if setup_type == SetupType.BREAKOUT:
            rvol = float(last["RVOL"]) if "RVOL" in df.columns else 1
            if rvol < 0.5:
                final = min(final, 50)
                warnings.append(f"FALSE BREAKOUT warning — RVol={rvol:.2f}")

        verdict = _map_verdict(final)

        results.append(SetupResult(
            setup_type=setup_type,
            direction="LONG",
            raw_score=raw,
            context_modifier=context_modifier,
            final_score=final,
            verdict=verdict,
            factors=factors,
            invalidation_reasons=all_reasons,
            warnings=warnings,
            hard_invalidated=hard_inv,
            
            # Thesis variables precisely calculated from setup engine
            rvol_avg=rvol_avg_val,
            rsi=rsi_val,
            macd_state=macd_state_val.lower().replace("_", " "),
        ))

    results.sort(key=lambda r: r.final_score, reverse=True)
    logger.info(
        "Setup classification: top=%s (score=%d, verdict=%s)",
        results[0].setup_type.value if results else "NONE",
        results[0].final_score if results else 0,
        results[0].verdict.value if results else "N/A",
    )
    return results

```

## `analysis/structure.py`

```python
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

    Requires ``EMA_21``, ``EMA_50``, ``EMA_200`` columns (from
    ``indicators.engine.add_indicators``).

    Parameters
    ----------
    df : pd.DataFrame
        Enriched OHLCV DataFrame.
    """
    if len(df) < 2:
        return Trend.RANGE

    last = df.iloc[-1]
    prev = df.iloc[-2]
    close = float(last["Close"])
    ema21 = float(last["EMA_21"])
    ema50 = float(last["EMA_50"])
    ema200 = float(last["EMA_200"])

    ema21_prev = float(prev["EMA_21"])
    ema50_prev = float(prev["EMA_50"])
    ema200_prev = float(prev["EMA_200"])

    all_rising = ema21 > ema21_prev and ema50 > ema50_prev and ema200 > ema200_prev

    # STRONG_UPTREND: Close > EMA21 > EMA50 > EMA200, ALL rising
    if close > ema21 > ema50 > ema200 and all_rising:
        return Trend.STRONG_UPTREND

    # UPTREND: Close > EMA50 > EMA200
    if close > ema50 > ema200:
        return Trend.UPTREND

    # WEAK_UPTREND: Close > EMA50 but below EMA200
    if close > ema50 and close < ema200:
        return Trend.WEAK_UPTREND

    # DOWNTREND: Close < EMA50 < EMA200
    if close < ema50 < ema200:
        return Trend.DOWNTREND

    # Default: RANGE
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

```

## `indicators/volume_profile.py`

```python
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

        # Find bins that overlap with this bar's range
        overlap_mask = (bin_edges[1:] > bar_low) & (bin_edges[:-1] < bar_high)
        n_overlapping = overlap_mask.sum()
        if n_overlapping > 0:
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

```

## `indicators/engine.py`

```python
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

```

## `analysis/patterns.py`

```python
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

```

## `analysis/trade_params.py`

```python
"""
SwingScope Trade Parameterizer
===============================
Calculates entry, stop loss, profit targets (TP1/TP2/TP3), risk/reward
ratio, and position sizing for a classified setup.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import config as cfg
from analysis.setup_classifier import SetupResult, Verdict
from analysis.structure import SRLevel
from indicators.volume_profile import VolumeProfile

logger = logging.getLogger(__name__)


@dataclass
class TradeParams:
    """Complete trade parameter set for a single setup."""

    entry: float
    stop_loss: float
    risk: float              # entry - stop_loss
    tp1: float               # nearest HVN / S/R above entry
    tp2: float               # 2R
    tp3: float               # 3R
    rr_tp1: float            # R:R to TP1
    rr_tp2: float = 2.0
    rr_tp3: float = 3.0
    position_shares: int = 0
    position_notional: float = 0.0
    risk_pct: float = 0.0    # account risk %
    rr_valid: bool = True    # passes MIN_RR_RATIO gate
    account_size: int = cfg.ACCOUNT_SIZE
    sl_method: str = "STRUCTURAL"
    sl_structural_level: float = 0.0
    atr_cap_triggered: bool = False



def calculate_trade_params(
    setup: SetupResult,
    trigger_candle_high: float,
    last_swing_low: float,
    atr: float,
    resistance_levels: list[SRLevel],
    vp: Optional[VolumeProfile] = None,
    account_size: int = cfg.ACCOUNT_SIZE,
) -> TradeParams:
    """Calculate trade parameters for the given setup.

    Parameters
    ----------
    setup : SetupResult
        The classified setup (used for conviction tier → risk %).
    trigger_candle_high : float
        High of the most recent setup candle.
    last_swing_low : float
        Price of the nearest swing low (for structural stop).
    atr : float
        Current ATR_14 value.
    resistance_levels : list[SRLevel]
        Resistance levels above current price.
    vp : VolumeProfile or None
        Volume profile for HVN-based TP1.
    account_size : int
        Account value for position sizing.

    Returns
    -------
    TradeParams
    """
    # ── Entry ────────────────────────────────────────────────
    entry = trigger_candle_high + (cfg.ENTRY_BUFFER_ATR * atr)

    # ── Stop Loss ────────────────────────────────────────────
    sl_structural = last_swing_low - (cfg.SL_SWING_BUFFER_ATR * atr)
    
    cap_multiplier = cfg.SL_ATR_CAPS.get(setup.setup_type.value, 2.5)
    max_risk = cap_multiplier * atr
    
    # Calculate the risk if we used the structural stop
    structural_risk = entry - sl_structural
    
    sl_method = "STRUCTURAL"
    atr_cap_triggered = False
    stop_loss = sl_structural
    
    # Fallback: If structural stop enforces absurd risk, use setup-specific ATR cap
    if structural_risk > max_risk:
        stop_loss = entry - max_risk
        sl_method = "ATR_CAP"
        atr_cap_triggered = True

    risk = entry - stop_loss
    if risk <= 0:
        risk = atr  # fallback to 1 ATR

    # ── Profit Targets ───────────────────────────────────────
    # TP1: nearest HVN or S/R above entry
    tp1_candidates: list[float] = []

    # From resistance levels
    for sr in resistance_levels:
        if sr.price > entry:
            tp1_candidates.append(sr.price)

    # From VP HVNs
    if vp and vp.hvns:
        for hvn in vp.hvns:
            if hvn > entry:
                tp1_candidates.append(hvn)

    if tp1_candidates:
        tp1 = min(tp1_candidates)  # nearest above entry
        # Ensure TP1 provides at least the minimum R:R
        if risk > 0 and (tp1 - entry) / risk < cfg.MIN_RR_RATIO:
            tp1 = entry + cfg.MIN_RR_RATIO * risk
    else:
        tp1 = entry + 1.5 * risk   # fallback to 1.5R

    tp2 = entry + 2.0 * risk
    tp3 = entry + 3.0 * risk

    # ── R:R Validation ───────────────────────────────────────
    rr_tp1 = (tp1 - entry) / risk if risk > 0 else 0
    rr_valid = rr_tp1 >= cfg.MIN_RR_RATIO

    # ── Position Sizing ──────────────────────────────────────
    if setup.verdict == Verdict.HIGH_CONVICTION:
        risk_pct = cfg.RISK_HIGH_CONVICTION
    elif setup.verdict == Verdict.VALID:
        risk_pct = cfg.RISK_VALID
    elif setup.verdict == Verdict.MARGINAL:
        risk_pct = cfg.RISK_MARGINAL
    else:
        risk_pct = 0.0  # no position for WEAK / INVALIDATED

    dollar_risk = min(account_size * risk_pct, cfg.MAX_LOSS_PER_TRADE)
    position_shares = int(dollar_risk / risk) if risk > 0 else 0
    position_notional = position_shares * entry

    params = TradeParams(
        entry=round(entry, 2),
        stop_loss=round(stop_loss, 2),
        risk=round(risk, 2),
        tp1=round(tp1, 2),
        tp2=round(tp2, 2),
        tp3=round(tp3, 2),
        rr_tp1=round(rr_tp1, 2),
        rr_tp2=2.0,
        rr_tp3=3.0,
        position_shares=position_shares,
        position_notional=round(position_notional, 2),
        risk_pct=risk_pct,
        rr_valid=rr_valid,
        account_size=account_size,
        sl_method=sl_method,
        sl_structural_level=round(sl_structural, 2),
        atr_cap_triggered=atr_cap_triggered,
    )

    logger.info(
        "Trade params: Entry=%.2f  SL=%.2f  TP1=%.2f  R:R=%.2f  Shares=%d  $%.0f",
        params.entry, params.stop_loss, params.tp1,
        params.rr_tp1, params.position_shares, params.position_notional,
    )
    return params

```

