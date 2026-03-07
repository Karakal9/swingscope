"""
SwingScope Chart Builder
=========================
Builds a 4-row Plotly figure (candlestick, volume, MACD, RSI) with all
annotations specified in Section 12 of the build spec.  The chart is
exported as a JSON blob for inline embedding in the HTML report.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from analysis.fibonacci import FibResult
from analysis.patterns import PatternMatch, PatternSignal
from analysis.structure import SRLevel, StructureResult
from analysis.trade_params import TradeParams
from indicators.volume_profile import VolumeProfile

logger = logging.getLogger(__name__)

import pandas as pd


def build_chart(
    df: pd.DataFrame,
    structure: StructureResult,
    patterns: list[PatternMatch],
    vp: Optional[VolumeProfile],
    fib: Optional[FibResult],
    trade: Optional[TradeParams],
    ticker: str,
) -> str:
    """Build the interactive Plotly chart and return it as a JSON string.

    Parameters
    ----------
    df : pd.DataFrame
        Enriched OHLCV + indicator DataFrame.
    structure : StructureResult
        Swing points, trend, and S/R levels.
    patterns : list[PatternMatch]
        Detected candlestick patterns.
    vp : VolumeProfile or None
        Volume profile data.
    fib : FibResult or None
        Fibonacci retracement data.
    trade : TradeParams or None
        Calculated trade parameters.
    ticker : str
        Stock symbol (for titles).

    Returns
    -------
    str
        Plotly figure as a JSON string (for embedded rendering).
    """
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.55, 0.15, 0.15, 0.15],
        subplot_titles=[
            f"{ticker} — Daily",
            "Volume",
            "MACD",
            "RSI",
        ],
    )

    dates = df.index.strftime("%Y-%m-%d").tolist()

    # ── Row 1: Candlestick + overlays ────────────────────────
    fig.add_trace(
        go.Candlestick(
            x=dates,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="OHLC",
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
        ),
        row=1, col=1,
    )

    # EMAs
    ema_styles = {
        "EMA_8": dict(color="rgba(158,158,158,0.5)", width=1),
        "EMA_21": dict(color="#2196f3", width=1.5),
        "EMA_50": dict(color="#ff9800", width=2),
        "EMA_200": dict(color="#f44336", width=2),
    }
    for col_name, style in ema_styles.items():
        if col_name in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=dates, y=df[col_name],
                    mode="lines", name=col_name.replace("_", " "),
                    line=style,
                ),
                row=1, col=1,
            )

    # Bollinger Bands
    if "BB_upper" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=dates, y=df["BB_upper"], mode="lines",
                name="BB Upper", line=dict(color="rgba(156,39,176,0.3)", width=1, dash="dot"),
            ),
            row=1, col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=dates, y=df["BB_lower"], mode="lines",
                name="BB Lower", line=dict(color="rgba(156,39,176,0.3)", width=1, dash="dot"),
                fill="tonexty", fillcolor="rgba(156,39,176,0.05)",
            ),
            row=1, col=1,
        )

    # Volume Profile (POC, VAH, VAL)
    if vp:
        for level, name, color, dash in [
            (vp.poc, "POC", "#ff9800", "solid"),
            (vp.vah, "VAH", "#9c27b0", "dash"),
            (vp.val, "VAL", "#9c27b0", "dash"),
        ]:
            fig.add_hline(
                y=level, row=1, col=1,
                line=dict(color=color, width=1.5, dash=dash),
                annotation_text=f"{name} ${level:.2f}",
                annotation_position="top right",
                annotation_font_size=10,
                annotation_font_color=color,
            )

        # HVN zones
        for hvn in vp.hvns[:5]:  # Limit to 5 to avoid clutter
            fig.add_hrect(
                y0=hvn - 0.5, y1=hvn + 0.5,
                row=1, col=1,
                fillcolor="rgba(33,150,243,0.08)",
                line_width=0,
            )

    # S/R levels
    for sr in structure.support_levels:
        fig.add_hline(
            y=sr.price, row=1, col=1,
            line=dict(color="#4caf50", width=1, dash="dot"),
            annotation_text=f"S ${sr.price:.2f} ({sr.touches}t)",
            annotation_position="top left",
            annotation_font_size=9,
            annotation_font_color="#4caf50",
        )
    for sr in structure.resistance_levels:
        fig.add_hline(
            y=sr.price, row=1, col=1,
            line=dict(color="#f44336", width=1, dash="dot"),
            annotation_text=f"R ${sr.price:.2f} ({sr.touches}t)",
            annotation_position="bottom left",
            annotation_font_size=9,
            annotation_font_color="#f44336",
        )

    # Trade parameter lines
    if trade:
        fig.add_hline(
            y=trade.entry, row=1, col=1,
            line=dict(color="#4caf50", width=2, dash="dash"),
            annotation_text=f"ENTRY ${trade.entry:.2f}",
            annotation_position="top right",
            annotation_font_size=11,
            annotation_font_color="#4caf50",
        )
        fig.add_hline(
            y=trade.stop_loss, row=1, col=1,
            line=dict(color="#f44336", width=2, dash="dash"),
            annotation_text=f"SL ${trade.stop_loss:.2f}",
            annotation_position="bottom right",
            annotation_font_size=11,
            annotation_font_color="#f44336",
        )
        for tp_val, label, rr in [
            (trade.tp1, "TP1", trade.rr_tp1),
            (trade.tp2, "TP2", trade.rr_tp2),
            (trade.tp3, "TP3", trade.rr_tp3),
        ]:
            fig.add_hline(
                y=tp_val, row=1, col=1,
                line=dict(color="#2196f3", width=1.5, dash="dash"),
                annotation_text=f"{label} ${tp_val:.2f} ({rr:.1f}R)",
                annotation_position="top right",
                annotation_font_size=10,
                annotation_font_color="#2196f3",
            )

    # Fibonacci levels
    if fib:
        for lv in fib.levels:
            fig.add_hline(
                y=lv.price, row=1, col=1,
                line=dict(color="rgba(158,158,158,0.5)", width=1, dash="dot"),
                annotation_text=f"Fib {lv.label} ${lv.price:.2f}",
                annotation_position="top left",
                annotation_font_size=9,
                annotation_font_color="rgba(158,158,158,0.8)",
            )

    # Candlestick pattern markers
    for p in patterns:
        if p.confirmed:
            marker_color = "#4caf50" if p.signal == PatternSignal.BULLISH else "#f44336"
            marker_sym = "triangle-up" if p.signal == PatternSignal.BULLISH else "triangle-down"
            y_pos = p.key_price
            fig.add_trace(
                go.Scatter(
                    x=[p.date.strftime("%Y-%m-%d")],
                    y=[y_pos],
                    mode="markers+text",
                    marker=dict(symbol=marker_sym, size=12, color=marker_color),
                    text=[p.name],
                    textposition="top center" if p.signal == PatternSignal.BULLISH else "bottom center",
                    textfont=dict(size=9, color=marker_color),
                    name=p.name,
                    showlegend=False,
                ),
                row=1, col=1,
            )

    # ── Row 2: Volume bars ───────────────────────────────────
    colors = [
        "#26a69a" if c >= o else "#ef5350"
        for c, o in zip(df["Close"], df["Open"])
    ]
    fig.add_trace(
        go.Bar(
            x=dates, y=df["Volume"],
            marker_color=colors, name="Volume",
            showlegend=False,
        ),
        row=2, col=1,
    )
    if "VOL_SMA_20" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=dates, y=df["VOL_SMA_20"],
                mode="lines", name="Vol SMA 20",
                line=dict(color="#ff9800", width=1),
            ),
            row=2, col=1,
        )

    # ── Row 3: MACD ──────────────────────────────────────────
    if "MACD_hist" in df.columns:
        macd_colors = ["#26a69a" if v >= 0 else "#ef5350" for v in df["MACD_hist"]]
        fig.add_trace(
            go.Bar(
                x=dates, y=df["MACD_hist"],
                marker_color=macd_colors, name="MACD Hist",
                showlegend=False,
            ),
            row=3, col=1,
        )
    if "MACD" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=dates, y=df["MACD"],
                mode="lines", name="MACD",
                line=dict(color="#2196f3", width=1.5),
            ),
            row=3, col=1,
        )
    if "MACD_signal" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=dates, y=df["MACD_signal"],
                mode="lines", name="Signal",
                line=dict(color="#ff9800", width=1),
            ),
            row=3, col=1,
        )
    fig.add_hline(y=0, row=3, col=1, line=dict(color="rgba(255,255,255,0.3)", width=0.5))

    # ── Row 4: RSI ───────────────────────────────────────────
    if "RSI_14" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=dates, y=df["RSI_14"],
                mode="lines", name="RSI 14",
                line=dict(color="#ab47bc", width=1.5),
            ),
            row=4, col=1,
        )
        fig.add_hline(y=70, row=4, col=1, line=dict(color="rgba(244,67,54,0.5)", width=1, dash="dash"))
        fig.add_hline(y=30, row=4, col=1, line=dict(color="rgba(76,175,80,0.5)", width=1, dash="dash"))
        fig.add_hline(y=50, row=4, col=1, line=dict(color="rgba(255,255,255,0.2)", width=0.5, dash="dot"))

    # ── Layout ───────────────────────────────────────────────
    fig.update_layout(
        template="plotly_dark",
        height=750,  # Slightly shorter for better mobile aspect ratio
        margin=dict(l=45, r=45, t=40, b=20), # Tight margins so it fills the screen
        xaxis_rangeslider_visible=False,
        showlegend=False, # Disable massive trace legend on mobile
        font=dict(family="Inter, system-ui, sans-serif"),
    )

    # Remove Plotly rangeslider for all x-axes
    for i in range(1, 5):
        fig.update_xaxes(rangeslider_visible=False, row=i, col=1)

    chart_json = fig.to_json()
    logger.info("Chart built: %d traces, %d KB JSON", len(fig.data), len(chart_json) // 1024)
    return chart_json
