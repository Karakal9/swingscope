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
    regime=None,
    force_refresh: bool = False,
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
    # ── Report cache check ───────────────────────────────────
    # If a report for this ticker already exists and was generated
    # within the last 24 hours, return it immediately without re-running.
    if not force_refresh and output_dir:
        existing_report = Path(output_dir) / f"{ticker}_*.html"
        import glob
        matches = sorted(glob.glob(str(existing_report)))
        if matches:
            from datetime import timedelta
            latest = matches[-1]
            mtime  = datetime.fromtimestamp(Path(latest).stat().st_mtime)
            age    = datetime.now() - mtime
            if age < timedelta(hours=24):
                console.print(
                    f"[yellow]↩ {ticker}: report cached ({mtime.strftime('%Y-%m-%d %H:%M')}) "
                    f"— skipping re-run[/yellow]"
                )
                return {
                    "ticker":  ticker,
                    "setup":   "CACHED",
                    "score":   None,
                    "verdict": "CACHED",
                    "rr":      0,
                    "report":  latest,
                    "cached":  True,
                    "cached_at": mtime.strftime("%Y-%m-%d %H:%M"),
                }

    from data.fetcher import fetch_ohlcv, fetch_weekly, get_ticker_info
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

    console.print("[dim]Fetching fundamentals…[/dim]")
    info = get_ticker_info(ticker)
    raw_de = info.get("debtToEquity", 0.0)
    # yfinance returns debtToEquity usually as a percentage
    debt_to_equity = raw_de / 100.0 if raw_de > 10.0 else raw_de

    # Extract swing-trading fundamentals
    short_interest = info.get("shortPercentOfFloat", 0.0) or 0.0
    float_shares = info.get("floatShares", 0) or 0
    current_ratio = info.get("currentRatio", 0.0) or 0.0
    earnings_growth = info.get("earningsGrowth", 0.0) or 0.0

    # ── Step 2: Indicators ───────────────────────────────────
    console.print("[dim]Computing indicators…[/dim]")
    df = add_indicators(df)

    # ── Price Momentum Grade (ADX + ROC) ─────────────────────
    adx_val = float(df["ADX_14"].iloc[-1]) if "ADX_14" in df.columns and not df["ADX_14"].isna().iloc[-1] else 0.0
    roc_val = float(df["ROC_20"].iloc[-1]) if "ROC_20" in df.columns and not df["ROC_20"].isna().iloc[-1] else 0.0

    if roc_val < 0 and adx_val > 25:
        price_momentum_grade = 1  # Strong downtrend
    elif roc_val < 0:
        price_momentum_grade = 2  # Weak / declining
    elif roc_val > 0 and adx_val < 20:
        price_momentum_grade = 3  # Positive but weak trend
    elif roc_val > 5 and adx_val > 20:
        price_momentum_grade = 4  # Strong momentum
    elif roc_val > 10 and adx_val > 25:
        price_momentum_grade = 5  # Excellent momentum
    else:
        price_momentum_grade = 3  # Default neutral

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
        weekly_df=weekly_df,
        debt_to_equity=debt_to_equity,
        price_momentum_grade=price_momentum_grade,
        sector_rs_direction=sector.rs_direction,
    )
    top_setup = setups[0]

    # ── Step 10: Trade Parameters ────────────────────────────
    trade = None
    if top_setup.final_score >= cfg.SCORE_WEAK:
        console.print("[dim]Calculating trade parameters…[/dim]")
        trigger_high = float(last["High"])
        swing_low = structure.swing_lows[-1].price if structure.swing_lows else float(last["Low"])

        trade = calculate_trade_params(
            df=df,
            setup=top_setup,
            trigger_candle_high=trigger_high,
            last_swing_low=swing_low,
            atr=atr,
            resistance_levels=structure.resistance_levels,
            vp=vp,
            account_size=account_size,
        )

        if trade and regime:
            if regime.position_size_adj == "AVOID":
                trade.position_shares   = 0
                trade.position_notional = 0.0
            elif regime.position_size_adj == "HALF":
                trade.position_shares   = trade.position_shares // 2
                trade.position_notional = trade.position_shares * trade.entry

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
        regime=regime,
        output_dir=output_dir,
        debt_to_equity=debt_to_equity,
        price_momentum_grade=price_momentum_grade,
        adx_val=adx_val,
        roc_val=roc_val,
        short_interest=short_interest,
        float_shares=float_shares,
        current_ratio=current_ratio,
        earnings_growth=earnings_growth,
    )

    console.print(f"[green]✓ Report: {report_path}[/green]")

    # Discrete fields for Journal
    journal_setup = cfg.SETUP_JOURNAL_MAPPING.get(top_setup.setup_type.value, "Unknown")
    is_vcp = any(p.name == "VCP" and p.confirmed for p in patterns)

    return {
        "ticker": ticker,
        "setup": top_setup.setup_type.value,
        "journal_setup": journal_setup,
        "score": top_setup.final_score,
        "verdict": top_setup.verdict.value,
        "rr": trade.rr_tp1 if trade else 0,
        "report": str(report_path),
        "discrete_fields": {
            "pattern_type": top_setup.setup_type.value,
            "pattern_score": top_setup.final_score,
            "price_momentum_grade": price_momentum_grade,
            "vcp_valid": "Yes" if is_vcp else "No",
            "weekly_alignment": weekly_trend.name if weekly_trend else "Unknown",
            "rsi_at_entry": top_setup.rsi,
            "atr_at_entry": round(atr, 2),
            "debt_equity": round(debt_to_equity, 2),
            "sector_rs": sector.rs_direction,
            "short_interest": round(short_interest * 100, 2),
            "float_shares": float_shares,
            "current_ratio": round(current_ratio, 2),
            "earnings_growth": round(earnings_growth * 100, 2),
        }
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

    from context.market_regime import analyze_market_regime
    regime = analyze_market_regime()
    console.print(f"[dim]Regime: {regime.label} | VIX={regime.vix} | {regime.detail}[/dim]")

    # Process tickers
    results: list[dict] = []
    for i, ticker in enumerate(args.tickers):
        ticker = ticker.upper().strip()
        try:
            result = analyze_ticker(
                ticker, 
                args.account, 
                output_dir, 
                regime=regime, 
                force_refresh=args.no_cache,
            )
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
            score_display = str(r["score"]) if r["score"] is not None else "—"
            verdict_display = r["verdict"]
            cached_note = f"  [dim](cached {r.get('cached_at','')})[/dim]" if r.get("cached") else ""
        
            style = "dim" if r.get("cached") else (
                "green"  if r["score"] and r["score"] >= cfg.SCORE_HIGH_CONVICTION else
                "blue"   if r["score"] and r["score"] >= cfg.SCORE_VALID else
                "yellow" if r["score"] and r["score"] >= cfg.SCORE_MARGINAL else "red"
            )
        
            table.add_row(
                r["ticker"] + cached_note,
                r["setup"],
                f"[{style}]{score_display}[/{style}]",
                verdict_display,
                f"{r['rr']:.2f}" if r["rr"] else "—",
            )
        console.print(table)
    else:
        console.print("[yellow]No valid results produced.[/yellow]")


if __name__ == "__main__":
    main()
