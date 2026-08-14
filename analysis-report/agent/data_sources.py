from __future__ import annotations

import hashlib
import logging
import os
import pickle
import time
from datetime import datetime, timedelta
from typing import Callable

import pandas as pd

from . import config

log = logging.getLogger(__name__)
try:
    import akshare as ak
except ImportError:  # Allows report formatting and tests without the optional provider.
    ak = None

def _cache_path(key: str) -> str:
    return os.path.join(config.CACHE_DIR, hashlib.md5(key.encode()).hexdigest() + ".pkl")

def _fetch(key: str, fn: Callable[[], pd.DataFrame]):
    path = _cache_path(key)
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < config.CACHE_TTL:
        try:
            with open(path, "rb") as handle:
                return pickle.load(handle)
        except Exception:
            pass
    if ak is None:
        log.warning("AKShare is unavailable: key=%s", key)
        return None
    for attempt in range(1, config.MAX_RETRY + 1):
        try:
            frame = fn()
            if frame is not None and not frame.empty:
                with open(path, "wb") as handle:
                    pickle.dump(frame, handle)
                return frame
        except Exception as exc:
            log.warning("Data fetch failed: key=%s attempt=%d error=%s", key, attempt, exc)
            time.sleep(config.RETRY_BACKOFF * attempt)
    return None

def read_codes(path: str = config.LIST_PATH) -> list[str]:
    paths = []
    if os.path.isfile(path):
        paths = [path]
    elif os.path.isdir(path):
        paths = [os.path.join(path, n) for n in sorted(os.listdir(path))]
    codes, seen = [], set()
    for file_path in paths:
        if not os.path.isfile(file_path):
            continue
        try:
            with open(file_path, encoding="utf-8-sig") as handle:
                for line in handle:
                    code = line.strip().split(",")[0]
                    if len(code) == 6 and code.isdigit() and code not in seen:
                        seen.add(code); codes.append(code)
        except (OSError, UnicodeError):
            log.warning("Unable to read stock list: %s", file_path)
    return codes

def _market(code: str) -> str:
    return ("sh" if code.startswith("6") else "sz" if code.startswith(("0", "3")) else "bj") + code

def name_map() -> dict[str, str]:
    frame = _fetch("names", lambda: ak.stock_info_a_code_name())
    return {} if frame is None or not {"code", "name"}.issubset(frame.columns) else {str(r.code).zfill(6): str(r.name) for r in frame.itertuples()}

def financial_abstract(code): return _fetch("abstract_" + code, lambda: ak.stock_financial_abstract(symbol=code))
def valuation(code, indicator): return _fetch("valuation_" + code + indicator, lambda: ak.stock_zh_valuation_baidu(symbol=code, indicator=indicator, period="近十年"))
def research(code): return _fetch("research_" + code, lambda: ak.stock_research_report_em(symbol=code))
def balance(code): return _fetch("balance_" + code, lambda: ak.stock_balance_sheet_by_yearly_em(symbol=_market(code).upper()))
def profit(code): return _fetch("profit_" + code, lambda: ak.stock_profit_sheet_by_yearly_em(symbol=_market(code).upper()))
def prices(code):
    start = (datetime.now() - timedelta(days=380)).strftime("%Y%m%d")
    frame = _fetch("price_" + code + start, lambda: ak.stock_zh_a_hist_tx(symbol=_market(code), start_date=start))
    return frame.rename(columns={"date": "日期", "close": "收盘", "high": "最高", "low": "最低", "volume": "成交量"}) if frame is not None else None
