"""AKShare data access with retry and a one-day disk cache."""
from __future__ import annotations

import csv
import hashlib
import logging
import os
import pickle
import time
from datetime import datetime, timedelta
from typing import Callable, Optional

import akshare as ak
import pandas as pd

from . import config

log = logging.getLogger(__name__)


def _cache_path(key: str) -> str:
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    return os.path.join(config.CACHE_DIR, f"{digest}.pkl")


def _cache_get(key: str):
    path = _cache_path(key)
    if not os.path.exists(path) or time.time() - os.path.getmtime(path) >= config.CACHE_TTL:
        return None
    try:
        with open(path, "rb") as handle:
            return pickle.load(handle)
    except Exception:
        return None


def _cache_set(key: str, value) -> None:
    try:
        with open(_cache_path(key), "wb") as handle:
            pickle.dump(value, handle)
    except Exception:
        pass


def _fetch(key: str, fn: Callable[[], pd.DataFrame]) -> Optional[pd.DataFrame]:
    cached = _cache_get(key)
    if cached is not None:
        return cached
    last_error = "empty"
    for attempt in range(1, config.MAX_RETRY + 1):
        try:
            frame = fn()
            if frame is not None and not frame.empty:
                _cache_set(key, frame)
                return frame
        except Exception as exc:  # Keep a batch alive when one provider fails.
            last_error = repr(exc)[:160]
        time.sleep(config.RETRY_BACKOFF * attempt)
    log.warning("Data fetch failed: key=%s error=%s", key, last_error)
    return None


def _unique_codes(values) -> list[str]:
    codes, seen = [], set()
    for value in values:
        code = str(value).strip()
        if len(code) == 6 and code.isdigit() and code not in seen:
            seen.add(code)
            codes.append(code)
    return codes


def _codes_from(path: str) -> list[str]:
    extension = os.path.splitext(path)[1].lower()
    try:
        if extension == ".csv":
            with open(path, "r", encoding="utf-8-sig", newline="") as handle:
                return _unique_codes(row[4] for row in csv.reader(handle) if len(row) >= 5)
        if extension == ".xls":
            frame = pd.read_excel(path, usecols=[4], header=None, dtype=str)
            return _unique_codes(frame.iloc[:, 0])
        with open(path, "r", encoding="utf-8-sig") as handle:
            return _unique_codes(handle)
    except (OSError, UnicodeDecodeError, ValueError):
        return []


def get_codes_from_file(name: str) -> list[str]:
    list_dir = os.path.realpath(config.LIST_DIR)
    path = (os.path.realpath(os.path.join(list_dir, name))
            if os.path.basename(name) == name
            else os.path.realpath(name))
    try:
        if os.path.commonpath((list_dir, path)) != list_dir:
            return []
    except ValueError:
        return []
    if path.lower().endswith(".py") or not os.path.isfile(path):
        return []
    return _codes_from(path)


def get_codes_by_file() -> list[tuple[str, list[str]]]:
    groups = []
    if not os.path.isdir(config.LIST_DIR):
        return groups
    for name in sorted(os.listdir(config.LIST_DIR)):
        if codes := get_codes_from_file(name):
            groups.append((os.path.splitext(name)[0], codes))
    return groups


def get_stock_list() -> list[str]:
    codes, seen = [], set()
    for _, group in get_codes_by_file():
        for code in group:
            if code not in seen:
                seen.add(code)
                codes.append(code)
    return codes


def get_name_map() -> dict[str, str]:
    frame = _fetch("code_name_map", ak.stock_info_a_code_name)
    if frame is None or not {"code", "name"}.issubset(frame.columns):
        return {}
    return {str(row["code"]).zfill(6): str(row["name"]) for _, row in frame.iterrows()}


def get_industry_map() -> dict[str, str]:
    frame = _fetch("industry_map_sz", ak.stock_info_sz_name_code)
    if frame is None or not {"A股代码", "所属行业"}.issubset(frame.columns):
        return {}
    return {str(row["A股代码"]).zfill(6): str(row["所属行业"]).strip()
            for _, row in frame.iterrows() if pd.notna(row["所属行业"])}


def get_financial_abstract(code: str) -> Optional[pd.DataFrame]:
    return _fetch(f"fin_abstract_{code}", lambda: ak.stock_financial_abstract(symbol=code))


def get_valuation(code: str, indicator: str) -> Optional[pd.DataFrame]:
    return _fetch(f"val_{code}_{indicator}_{config.VAL_PERIOD_LONG}",
                  lambda: ak.stock_zh_valuation_baidu(
                      symbol=code, indicator=indicator, period=config.VAL_PERIOD_LONG))


def get_research_report(code: str) -> Optional[pd.DataFrame]:
    return _fetch(f"report_{code}", lambda: ak.stock_research_report_em(symbol=code))


def get_balance_sheet(code: str) -> Optional[pd.DataFrame]:
    symbol = _market_symbol(code).upper()
    return _fetch(f"balance_yearly_{code}",
                  lambda: ak.stock_balance_sheet_by_yearly_em(symbol=symbol))


def get_profit_sheet(code: str) -> Optional[pd.DataFrame]:
    symbol = _market_symbol(code).upper()
    return _fetch(f"profit_yearly_{code}",
                  lambda: ak.stock_profit_sheet_by_yearly_em(symbol=symbol))


def _market_symbol(code: str) -> str:
    if code.startswith("6"):
        return f"sh{code}"
    if code.startswith(("0", "3")):
        return f"sz{code}"
    return f"bj{code}"


def get_recent_price(code: str) -> Optional[pd.DataFrame]:
    start = (datetime.now() - timedelta(days=45)).strftime("%Y%m%d")
    tx = _fetch(f"price_tx_{code}_{start}", lambda: ak.stock_zh_a_hist_tx(
        symbol=_market_symbol(code), start_date=start))
    if tx is not None and "close" in tx.columns:
        return tx.rename(columns={"date": "日期", "close": "收盘"})
    return _fetch(f"price_em_{code}_{start}", lambda: ak.stock_zh_a_hist(
        symbol=code, period="daily", start_date=start, adjust=""))
