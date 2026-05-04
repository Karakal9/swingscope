"""
SwingScope Report Renderer
============================
Renders the final self-contained HTML report from analysis results using
the Jinja2 template.  Includes deterministic trade thesis and invalidation
risk auto-generation (Section 13.2).
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader

import config as cfg
from analysis.setup_classifier import SetupResult, SetupType, Verdict
from analysis.trade_params import TradeParams
from context.earnings import EarningsResult
from context.news import NewsResult
from context.sector import SectorResult

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


# ──────────────────────────────────────────────────────────────
# Thesis templates (deterministic, per setup type)
# ──────────────────────────────────────────────────────────────
_THESIS_TEMPLATES: dict[SetupType, str] = {
    SetupType.EMA_PULLBACK: (
        "{ticker} pulled back to the {ema_level} on declining volume "
        "({rvol_avg:.1f}x avg) after a strong prior leg. RSI reset to {rsi:.0f}. "
        "MACD histogram {macd_state}. {pattern} confirms buyer absorption "
        "at the {ema_level} level."
    ),
    SetupType.BREAKOUT: (
        "{ticker} is coiling near resistance at ${resistance:.2f} with "
        "ATR contraction and Bollinger Band squeeze. Volume dried up in the "
        "base ({rvol_avg:.1f}x avg). A break above resistance on expanding "
        "volume would confirm the breakout setup."
    ),
    SetupType.BULL_FLAG: (
        "{ticker} posted a strong impulse leg followed by an orderly "
        "pullback holding above the EMA21. Volume declined during the "
        "flag consolidation ({rvol_avg:.1f}x avg). RSI at {rsi:.0f} with room "
        "to expand. MACD {macd_state}."
    ),
    SetupType.VP_REVERSAL: (
        "{ticker} is testing a key Volume Profile level at ${vp_level:.2f}. "
        "{pattern} detected with RVol spike ({rvol_avg:.1f}x). RSI at {rsi:.0f} "
        "suggests {rsi_condition}. Fibonacci confluence adds confirmation."
    ),
    SetupType.FIB_PULLBACK: (
        "{ticker} retraced to the {fib_level} Fibonacci level at ${fib_price:.2f}, "
        "which aligns with {confluence}. RSI reset to {rsi:.0f}. "
        "MACD histogram {macd_state}."
    ),
}


def _generate_thesis(
    ticker: str,
    setup: SetupResult,
    vp=None,
    fib=None,
    patterns=None,
) -> str:
    # Pattern name
    pattern = "No pattern"
    if patterns:
        confirmed = [p for p in patterns if p.confirmed]
        if confirmed:
            pattern = confirmed[0].name
        elif patterns:
            pattern = patterns[0].name

    template = _THESIS_TEMPLATES.get(setup.setup_type, "{ticker} shows a potential setup.")

    # Build kwargs with safe defaults
    kwargs = dict(
        ticker=ticker,
        ema_level="EMA21", # Default
        rvol_avg=setup.rvol_avg,
        rsi=setup.rsi,
        macd_state=setup.macd_state,
        pattern=pattern,
        resistance=vp.vah if vp else 0, # Placeholder
        vp_level=vp.poc if vp else 0,
        rsi_condition="oversold reversal" if setup.rsi < 35 else "neutral zone",
        fib_level="50.0%",
        fib_price=0,
        confluence="EMA and VP levels",
    )

    # Refine EMA level from factors if present (specifically for EMA pullbacks)
    for f in setup.factors:
        if f.name == "EMA Respect":
            if "EMA50" in f.detail:
                kwargs["ema_level"] = "EMA50"
            elif "EMA21" in f.detail:
                kwargs["ema_level"] = "EMA21"
            break

    # Fib refinement
    if fib and fib.levels:
        for lv in fib.levels:
            if lv.ratio in (0.382, 0.500, 0.618):
                kwargs["fib_level"] = lv.label
                kwargs["fib_price"] = lv.price
                break

    try:
        return template.format(**kwargs)
    except (KeyError, ValueError):
        return f"{ticker} presents a {setup.setup_type.value} setup with a score of {setup.final_score}/100."


def _generate_invalidation_risks(
    setup: SetupResult,
    earnings: Optional[EarningsResult] = None,
) -> list[str]:
    """Generate invalidation risk bullets from setup state."""
    risks: list[str] = []

    # OBV divergence
    for w in setup.warnings:
        risks.append(w)

    for reason in setup.invalidation_reasons:
        if reason not in risks:
            risks.append(reason)

    # Earnings
    if earnings and earnings.days_to_earnings and earnings.days_to_earnings <= 45:
        dt_str = earnings.next_date.strftime("%Y-%m-%d") if earnings.next_date else "TBD"
        risks.append(
            f"Earnings in {earnings.days_to_earnings} days — plan exit before {dt_str}"
        )

    return risks


# ──────────────────────────────────────────────────────────────
# Score class / color helpers
# ──────────────────────────────────────────────────────────────
def _score_class(verdict: Verdict) -> str:
    return {
        Verdict.HIGH_CONVICTION: "score-high",
        Verdict.VALID: "score-valid",
        Verdict.MARGINAL: "score-marginal",
        Verdict.WEAK: "score-weak",
        Verdict.INVALIDATED: "score-invalid",
    }.get(verdict, "score-weak")


def _score_color(verdict: Verdict) -> str:
    return {
        Verdict.HIGH_CONVICTION: "#3fb950",
        Verdict.VALID: "#58a6ff",
        Verdict.MARGINAL: "#d29922",
        Verdict.WEAK: "#8b949e",
        Verdict.INVALIDATED: "#f85149",
    }.get(verdict, "#8b949e")


# ──────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────
def render_report(
    ticker: str,
    df,
    setup: SetupResult,
    trade: Optional[TradeParams],
    chart_json: str,
    sector: SectorResult,
    earnings: EarningsResult,
    news: NewsResult,
    vp=None,
    fib=None,
    patterns=None,
    regime=None,
    cached_at=None,
    output_dir: Optional[Path] = None,
    debt_to_equity: float = 0.0,
    price_momentum_grade: int = 3,
    adx_val: float = 0.0,
    roc_val: float = 0.0,
    short_interest: float = 0.0,
    float_shares: int = 0,
    current_ratio: float = 0.0,
    earnings_growth: float = 0.0,
) -> Path:
    """Render the complete HTML report and write to disk.

    Parameters
    ----------
    ticker : str
        Stock symbol.
    df : pd.DataFrame
        Enriched OHLCV DataFrame.
    setup : SetupResult
        Top-ranked setup result.
    trade : TradeParams or None
        Calculated trade parameters.
    chart_json : str
        Plotly chart as JSON string.
    sector : SectorResult
        Sector analysis output.
    earnings : EarningsResult
        Earnings analysis output.
    news : NewsResult
        News analysis output.
    vp, fib, patterns :
        Optional analysis objects for thesis generation.
    output_dir : Path or None
        Directory to write the report (default: ``reports/``).

    Returns
    -------
    Path
        Absolute path to the generated HTML file.
    """
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent.parent / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"{ticker}_{date_str}.html"
    output_path = output_dir / filename

    # Get company name
    try:
        from data.fetcher import get_ticker_info
        info = get_ticker_info(ticker)
        company_name = info.get("name", ticker)
    except Exception:
        company_name = ticker

    # Generate thesis and risks
    thesis = _generate_thesis(ticker, setup, vp, fib, patterns)
    invalidation_risks = _generate_invalidation_risks(setup, earnings)

    # ATR
    atr = float(df["ATR_14"].iloc[-1]) if "ATR_14" in df.columns else 0

    # Template context
    ctx = dict(
        ticker=ticker,
        company_name=company_name,
        date=datetime.now().strftime("%Y-%m-%d"),
        regime=regime,
        cached_at=cached_at,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        setup_type=setup.setup_type.value,
        direction=setup.direction,
        final_score=setup.final_score,
        verdict=setup.verdict.value,
        score_class=_score_class(setup.verdict),
        score_color=_score_color(setup.verdict),
        factors=setup.factors,
        chart_json=chart_json,
        # Sector
        sector=sector.sector,
        sector_etf=sector.etf,
        sector_above_ema50=sector.etf_above_ema50,
        sector_alpha=sector.relative_strength,
        sector_rs_market_cond=sector.rs_market_cond,
        sector_rs_label=sector.rs_label,
        sector_macd_positive=sector.macd_positive,
        sector_verdict=sector.verdict,
        sector_modifier=sector.modifier,
        # Earnings
        next_earnings_date=earnings.next_date.strftime("%Y-%m-%d") if earnings.next_date else None,
        days_to_earnings=earnings.days_to_earnings,
        earnings_risk=earnings.risk_status,
        earnings_imminent=earnings.risk_status == "IMMINENT",
        last_eps_surprise=earnings.last_eps_surprise_pct,
        post_earnings_drift=earnings.post_earnings_drift,
        # News
        news_sentiment=news.overall_sentiment,
        news_modifier=news.modifier,
        headlines=news.headlines,
        # Trade
        trade=trade,
        atr=atr,
        min_rr=cfg.MIN_RR_RATIO,
        # Thesis / Risks
        thesis=thesis,
        invalidation_risks=invalidation_risks,
        debt_to_equity=debt_to_equity,
        price_momentum_grade=price_momentum_grade,
        adx_val=adx_val,
        roc_val=roc_val,
        short_interest=short_interest,
        float_shares=float_shares,
        current_ratio=current_ratio,
        earnings_growth=earnings_growth,
    )

    # Render
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=False,
    )
    template = env.get_template("report.html.j2")
    html = template.render(**ctx)

    output_path.write_text(html, encoding="utf-8")
    logger.info("Report written: %s (%d KB)", output_path, len(html) // 1024)
    return output_path
