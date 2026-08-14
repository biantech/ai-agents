from __future__ import annotations

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIST_PATH = os.path.join(BASE_DIR, "list")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
CACHE_DIR = os.path.join(BASE_DIR, "cache")
CACHE_TTL = 24 * 3600
MAX_RETRY = 3
RETRY_BACKOFF = 1.5
REQUEST_SLEEP = 0.5
DEFAULT_WACC = 8.0

def ensure_dirs() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)
