# -*- coding: utf-8 -*-
"""Peter Lynch style fundamental analysis agent - configuration.

Holds all paths, thresholds, portfolio weights and network retry params so
that the rest of the modules stay free of magic numbers.
"""
from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# Project root = the parent of this agent package. Resolved from __file__ so it
# stays correct regardless of the root folder name (e.g. after renaming to
# "lingqi-agent").
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIST_DIR = os.path.join(BASE_DIR, "list")
CACHE_DIR = os.path.join(BASE_DIR, "cache")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# Cache time-to-live in seconds (1 day). Financial data changes slowly.
CACHE_TTL = 24 * 3600

# ---------------------------------------------------------------------------
# Price data source selection
# ---------------------------------------------------------------------------
# Which interface provides the recent close price. The other one is used as an
# automatic fallback when the primary yields nothing.
#   "tencent"   -> stock_zh_a_hist_tx (Tencent / 腾讯), stable in most environments
#   "eastmoney" -> stock_zh_a_hist    (East Money / 东方财富)
PRICE_SOURCE = "tencent"

# ---------------------------------------------------------------------------
# Network retry / throttle
# ---------------------------------------------------------------------------
MAX_RETRY = 3            # attempts per interface call
RETRY_BACKOFF = 2.0      # seconds, multiplied by attempt index
REQUEST_SLEEP = 0.6      # polite pause between stocks to avoid rate limiting

# ---------------------------------------------------------------------------
# Valuation history window (Baidu valuation supports "近十年"/"近五年"/"近一年")
# ---------------------------------------------------------------------------
VAL_PERIOD_LONG = "近十年"   # for percentile calculation
VAL_PERIOD_SHORT = "近一年"  # fallback when 10y unavailable

# ---------------------------------------------------------------------------
# Lynch classification growth thresholds (annual profit growth, %)
# ---------------------------------------------------------------------------
FAST_GROWTH = 20.0       # >=20% -> Fast Grower
STALWART_LOW = 10.0      # 10%~20% -> Stalwart
# <10% (positive) -> Slow Grower; <0 with positive forward -> Turnaround

# ---------------------------------------------------------------------------
# Quality / risk thresholds (Step 7 overlay)
# ---------------------------------------------------------------------------
DEBT_WARN = 60.0         # debt ratio > 60% -> caution flag
ROE_GOOD = 15.0          # ROE >= 15% -> quality
GROSS_GOOD = 30.0        # gross margin >= 30% -> pricing power
CASH_QUALITY_GOOD = 0.8  # operating cashflow / net profit >= 0.8 -> healthy

# ---------------------------------------------------------------------------
# PEG interpretation bands (Step 6)
# ---------------------------------------------------------------------------
PEG_ATTRACTIVE = 1.0     # < 1.0 -> attractive
PEG_FAIR = 1.5           # 1.0~1.5 -> fair; >2 -> expensive
PEG_EXPENSIVE = 2.0

# ---------------------------------------------------------------------------
# Percentile bands for valuation cheap/expensive judgement
# ---------------------------------------------------------------------------
PCT_CHEAP = 30.0         # PE percentile < 30% -> cheap
PCT_EXPENSIVE = 70.0     # > 70% -> expensive

# ---------------------------------------------------------------------------
# Portfolio bucket weights (Step 7)
# ---------------------------------------------------------------------------
PORTFOLIO_WEIGHTS = {
    "核心仓": 0.35,   # lowest PEG + strongest fundamentals
    "进攻仓": 0.25,   # high elasticity + turnaround
    "价值仓": 0.20,   # lowest PE + margin of safety
    "质量仓": 0.15,   # brand power + platform, high ROE
    "防守仓": 0.05,   # low PE + low debt + high dividend
}

# Top-N final portfolio size
TOP_N = 10


def ensure_dirs() -> None:
    """Create cache/output dirs if missing."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
