from __future__ import annotations
import logging
from dataclasses import dataclass
import yfinance as yf

logger = logging.getLogger(__name__)

@dataclass
class MarketRegime:
    label:             str   # BULL | CAUTION | BEAR
    spy_vs_ema50:      str   # ABOVE | BELOW
    spy_vs_ema200:     str   # ABOVE | BELOW
    vix:               float
    vix_state:         str   # LOW | ELEVATED | SPIKING
    position_size_adj: str   # FULL | HALF | AVOID
    detail:            str

def analyze_market_regime() -> MarketRegime:
    try:
        spy = yf.Ticker("SPY").history(period="3mo", interval="1d")
        vix = yf.Ticker("^VIX").history(period="5d",  interval="1d")
    except Exception as e:
        logger.warning("Regime fetch failed: %s", e)
        return MarketRegime("UNKNOWN","UNKNOWN","UNKNOWN",0.0,"UNKNOWN","FULL","Could not fetch SPY/VIX")

    spy_close  = float(spy["Close"].iloc[-1])
    spy_ema50  = float(spy["Close"].ewm(span=50).mean().iloc[-1])
    spy_ema200 = float(spy["Close"].ewm(span=200).mean().iloc[-1])
    spy_vs_50  = "ABOVE" if spy_close > spy_ema50  else "BELOW"
    spy_vs_200 = "ABOVE" if spy_close > spy_ema200 else "BELOW"

    vix_val   = float(vix["Close"].iloc[-1]) if len(vix) > 0 else 15.0
    vix_state = "LOW" if vix_val < 20 else "ELEVATED" if vix_val < 25 else "SPIKING"

    if spy_vs_50 == "ABOVE" and vix_state == "LOW":
        label, adj  = "BULL", "FULL"
        detail = f"SPY above EMA50, VIX={vix_val:.1f} — favorable"
    elif spy_vs_200 == "BELOW" or vix_state == "SPIKING":
        label, adj  = "BEAR", "AVOID"
        detail = f"SPY below EMA200 or VIX={vix_val:.1f} spiking — avoid longs"
    else:
        label, adj  = "CAUTION", "HALF"
        detail = f"SPY below EMA50, VIX={vix_val:.1f} — reduce size 50%"

    return MarketRegime(label, spy_vs_50, spy_vs_200, round(vix_val,1), vix_state, adj, detail)
