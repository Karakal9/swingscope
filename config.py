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
MAX_POSITION_NOTIONAL_PCT: Final[float] = 0.20 # Max % of account per open position

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
