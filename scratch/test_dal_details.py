import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent))

import config as cfg
from analyze import analyze_ticker
from indicators.engine import add_indicators
from data.fetcher import fetch_ohlcv, get_ticker_info, fetch_weekly
from analysis.structure import analyze_structure
from analysis.patterns import detect_patterns
from indicators.volume_profile import compute_volume_profile
from analysis.fibonacci import compute_fibonacci
from context.sector import analyze_sector
from context.earnings import analyze_earnings
from context.news import analyze_news
from analysis.setup_classifier import classify_setups, Trend

def test_dal():
    ticker = "DAL"
    df = fetch_ohlcv(ticker)
    df = add_indicators(df)
    info = get_ticker_info(ticker)
    raw_de = info.get("debtToEquity", 0.0)
    debt_to_equity = raw_de / 100.0 if raw_de > 10.0 else raw_de
    
    vp = compute_volume_profile(df)
    structure = analyze_structure(df)
    atr = float(df["ATR_14"].iloc[-1])
    structural_levels = [s.price for s in structure.support_levels] + [s.price for s in structure.resistance_levels]
    patterns = detect_patterns(df, structural_levels, atr)
    fib = compute_fibonacci(df, structure, float(df["Close"].iloc[-1]))
    
    sector = analyze_sector(ticker)
    earnings = analyze_earnings(ticker)
    news = analyze_news(ticker)
    
    context_modifier = sector.modifier + earnings.modifier + news.modifier
    
    weekly_df = fetch_weekly(ticker)
    weekly_trend = None
    if weekly_df is not None:
        from indicators.engine import add_indicators as add_weekly_ind
        weekly_df = add_weekly_ind(weekly_df)
        from analysis.structure import classify_trend
        weekly_trend = classify_trend(weekly_df)

    adx_val = float(df["ADX_14"].iloc[-1])
    roc_val = float(df["ROC_20"].iloc[-1])
    if roc_val < 0 and adx_val > 25: price_momentum_grade = 1
    elif roc_val < 0: price_momentum_grade = 2
    elif roc_val > 0 and adx_val < 20: price_momentum_grade = 3
    elif roc_val > 5 and adx_val > 20: price_momentum_grade = 4
    elif roc_val > 10 and adx_val > 25: price_momentum_grade = 5
    else: price_momentum_grade = 3

    results = classify_setups(
        df, structure, patterns, vp, fib,
        context_modifier=context_modifier,
        weekly_trend=weekly_trend,
        debt_to_equity=debt_to_equity,
        price_momentum_grade=price_momentum_grade,
        sector_rs_direction=sector.rs_direction
    )
    
    top = results[0]
    print(f"Top Setup: {top.setup_type.value}")
    print(f"Final Score: {top.final_score}")
    print(f"Context Modifier: {top.context_modifier}")
    print(f"Raw Score: {top.raw_score}")
    print("\nFactors:")
    for f in top.factors:
        print(f"  {f.name}: {f.earned}/{f.max_pts} ({f.detail})")
    print("\nWarnings:")
    for w in top.warnings:
        print(f"  {w}")

if __name__ == "__main__":
    test_dal()
