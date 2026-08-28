"""Configuration for the PEG-ROIC analysis agent."""
from __future__ import annotations

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIST_DIR = os.path.join(BASE_DIR, "list")
CACHE_DIR = os.path.join(BASE_DIR, "cache")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

CACHE_TTL = 24 * 3600
MAX_RETRY = 3
RETRY_BACKOFF = 2.0
REQUEST_SLEEP = 0.6
PRICE_SOURCE = "tencent"
VAL_PERIOD_LONG = "近十年"

# WACC is an explicit screening assumption, not a measured company value.
DEFAULT_WACC = 8.0
PEG_ATTRACTIVE = 1.0
ROIC_GOOD = 12.0
ROIC_EXCELLENT = 20.0
SPREAD_GOOD = 4.0
DEBT_WARN = 60.0
CASH_QUALITY_GOOD = 0.8
TOP_N = 20


def ensure_dirs() -> None:
    for path in (LIST_DIR, CACHE_DIR, OUTPUT_DIR):
        os.makedirs(path, exist_ok=True)
