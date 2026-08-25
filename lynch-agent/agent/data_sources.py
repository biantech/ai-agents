# -*- coding: utf-8 -*-
"""Data source layer: wraps AKShare interfaces with retry + disk cache.

Interface selection was validated against this environment (AKShare 1.18.58):
  - stock_financial_abstract (Sina) : raw financials + ROE/margin/debt/growth
  - stock_zh_valuation_baidu (Baidu): PE(TTM)/PB history -> current + percentile
  - stock_research_report_em (EM)   : broker consensus forward EPS (2026E..)
  - stock_zh_a_hist_tx (Tencent)    : recent close price
  - stock_zh_a_hist (EM)            : recent close price
  - stock_history_dividend_detail   : dividend history for dividend yield
EM spot / profit_forecast_em are unstable here, so they are avoided. The recent
close price source is selectable via config.PRICE_SOURCE ("tencent"/"eastmoney"),
with the non-selected interface used as an automatic fallback.
"""
from __future__ import annotations

import csv
import hashlib
import logging
import os
import pickle
import time
import warnings
from typing import Callable, Optional

import akshare as ak
import pandas as pd

from . import config

warnings.filterwarnings("ignore")

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------
def _cache_path(key: str) -> str:
    h = hashlib.md5(key.encode("utf-8")).hexdigest()
    return os.path.join(config.CACHE_DIR, f"{h}.pkl")


def _cache_get(key: str):
    path = _cache_path(key)
    if os.path.exists(path) and (time.time() - os.path.getmtime(path)) < config.CACHE_TTL:
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception:
            return None
    return None


def _cache_set(key: str, value) -> None:
    try:
        with open(_cache_path(key), "wb") as f:
            pickle.dump(value, f)
    except Exception:
        pass


def _extract_url(e: Exception) -> Optional[str]:
    """Best-effort extraction of the full request URL from a requests error.

    requests exceptions usually carry the originating PreparedRequest on
    ``.request`` (with query params already baked into ``.url``). Nested
    ConnectionError/ProtocolError may hide it deeper, so walk the cause chain.
    Returns None when no URL can be recovered.
    """
    cur: Optional[BaseException] = e
    for _ in range(5):  # bounded walk over the __cause__/__context__ chain
        if cur is None:
            break
        req = getattr(cur, "request", None)
        url = getattr(req, "url", None)
        if url:
            return str(url)
        resp = getattr(cur, "response", None)
        url = getattr(resp, "url", None)
        if url:
            return str(url)
        cur = cur.__cause__ or cur.__context__
    return None


def _fetch(key: str, fn: Callable[[], pd.DataFrame]) -> Optional[pd.DataFrame]:
    """Fetch with cache + retry. Returns None on total failure (graceful)."""
    cached = _cache_get(key)
    if cached is not None:
        return cached
    last_err = None
    last_url = None
    for attempt in range(1, config.MAX_RETRY + 1):
        try:
            df = fn()
            if df is not None and len(df) > 0:
                _cache_set(key, df)
                return df
            last_err = "empty"
        except Exception as e:  # noqa: BLE001 - graceful degradation
            last_err = repr(e)[:120]
            last_url = _extract_url(e)
        time.sleep(config.RETRY_BACKOFF * attempt)
    url_info = last_url or "<url unavailable>"
    log.warning(
        "%s failed after %d tries: %s; url: %s",
        key, config.MAX_RETRY, last_err, url_info,
    )
    return None


# ---------------------------------------------------------------------------
# Public data accessors
# ---------------------------------------------------------------------------
def _unique_stocks(rows) -> list[tuple[str, str]]:
    """Return unique code/name pairs while preserving their input order."""
    stocks: list[tuple[str, str]] = []
    indexes: dict[str, int] = {}
    for code_value, name_value in rows:
        code = str(code_value).strip()
        if len(code) != 6 or not code.isdigit():
            continue
        name = str(name_value).strip()
        if name.lower() in ("nan", "none"):
            name = ""
        if code not in indexes:
            indexes[code] = len(stocks)
            stocks.append((code, name))
        elif name and not stocks[indexes[code]][1]:
            stocks[indexes[code]] = (code, name)
    return stocks


def _stocks_from(path: str) -> list[tuple[str, str]]:
    """Read stock codes and available names from one supported list file."""
    extension = os.path.splitext(path)[1].lower()
    try:
        if extension == ".csv":
            with open(path, "r", encoding="utf-8-sig", newline="") as handle:
                rows = csv.reader(handle)
                return _unique_stocks(
                    (row[4], row[5] if len(row) > 5 else "")
                    for row in rows if len(row) >= 5
                )
        if extension == ".xls":
            frame = pd.read_excel(path, usecols=[4, 5], header=None, dtype=str)
            return _unique_stocks(frame.itertuples(index=False, name=None))
        with open(path, "r", encoding="utf-8-sig", newline="") as handle:
            rows = csv.reader(handle)
            return _unique_stocks(
                (row[0], row[1] if len(row) > 1 else "")
                for row in rows if row
            )
    except Exception as exc:  # noqa: BLE001 - skip malformed list files
        log.warning("Unable to read list file %s: %s", path, exc)
        return []


def _codes_from(path: str) -> list[str]:
    """Read only stock codes from one supported list file."""
    return [code for code, _ in _stocks_from(path)]


def _resolve_list_path(name: str) -> Optional[str]:
    """Resolve a filename or list-relative path without leaving LIST_DIR."""
    list_dir = os.path.realpath(config.LIST_DIR)
    if os.path.isabs(name):
        path = os.path.realpath(name)
    elif os.path.basename(name) == name:
        path = os.path.realpath(os.path.join(list_dir, name))
    else:
        path = os.path.realpath(os.path.join(config.BASE_DIR, name))
    try:
        if os.path.commonpath((list_dir, path)) != list_dir:
            return None
    except ValueError:
        return None
    return path


def get_codes_from_file(name: str) -> list[str]:
    """Read codes from one file in LIST_DIR, accepting name or list/name."""
    return [code for code, _ in get_stocks_from_file(name)]


def get_stocks_from_file(name: str) -> list[tuple[str, str]]:
    """Read code/name pairs from one file in LIST_DIR."""
    path = _resolve_list_path(name)
    if path is None or path.lower().endswith(".py") or not os.path.isfile(path):
        return []
    return _stocks_from(path)


def get_stock_entries() -> list[tuple[str, str]]:
    """Collect unique code/name pairs from all supported list files."""
    stocks: list[tuple[str, str]] = []
    indexes: dict[str, int] = {}
    for _, file_stocks in get_stocks_by_file():
        for code, name in file_stocks:
            if code not in indexes:
                indexes[code] = len(stocks)
                stocks.append((code, name))
            elif name and not stocks[indexes[code]][1]:
                stocks[indexes[code]] = (code, name)
    return stocks


def get_stock_list() -> list[str]:
    """Collect unique six-digit codes from all supported files in LIST_DIR."""
    return [code for code, _ in get_stock_entries()]


def get_stocks_by_file() -> list[tuple[str, list[tuple[str, str]]]]:
    """Collect code/name pairs grouped by their source file."""
    groups: list[tuple[str, list[tuple[str, str]]]] = []
    if not os.path.isdir(config.LIST_DIR):
        return groups
    for name in sorted(os.listdir(config.LIST_DIR)):
        if stocks := get_stocks_from_file(name):
            stem = os.path.splitext(name)[0]
            groups.append((stem, stocks))
    return groups


def get_codes_by_file() -> list[tuple[str, list[str]]]:
    """Collect 6-digit codes grouped by their source file under LIST_DIR.

    Returns a list of (filename_stem, codes) pairs, one per readable file that
    yields at least one code. Codes are de-duplicated within each file (order
    preserved) but NOT across files, so callers can produce isolated per-file
    reports. The stem (name without extension) is intended as an output prefix.
    """
    return [
        (stem, [code for code, _ in stocks])
        for stem, stocks in get_stocks_by_file()
    ]


def get_name_map() -> dict:
    """Return a {6-digit code: stock name} map for the whole A-share market.

    Uses one stable batch call (stock_info_a_code_name) instead of per-stock
    lookups. Degrades gracefully to an empty map on failure.
    """
    df = _fetch("code_name_map", lambda: ak.stock_info_a_code_name())
    if df is None or "code" not in df.columns or "name" not in df.columns:
        return {}
    return {str(r["code"]).zfill(6): str(r["name"]) for _, r in df.iterrows()}


def get_industry_map() -> dict:
    """Return a {6-digit code: industry} map as a fallback for the industry column.

    Uses the stable Shenzhen batch call (stock_info_sz_name_code) which carries
    an industry column. Coverage is Shenzhen-only (codes starting with 0/3);
    Shanghai codes (starting with 6) are absent here and keep the broker-report
    industry (or "-" when that is missing too). Degrades to an empty map on failure.
    """
    df = _fetch("industry_map_sz", lambda: ak.stock_info_sz_name_code())
    if df is None or "A股代码" not in df.columns or "所属行业" not in df.columns:
        return {}
    out: dict = {}
    for _, r in df.iterrows():
        code = str(r["A股代码"]).zfill(6)
        ind = str(r["所属行业"]).strip()
        if ind and ind.lower() != "nan":
            out[code] = ind
    return out


def get_financial_abstract(code: str) -> Optional[pd.DataFrame]:
    return _fetch(f"fin_abstract_{code}", lambda: ak.stock_financial_abstract(symbol=code))


def get_valuation(code: str, indicator: str, period: str) -> Optional[pd.DataFrame]:
    key = f"val_{code}_{indicator}_{period}"
    return _fetch(key, lambda: ak.stock_zh_valuation_baidu(
        symbol=code, indicator=indicator, period=period))


def get_research_report(code: str) -> Optional[pd.DataFrame]:
    return _fetch(f"report_{code}", lambda: ak.stock_research_report_em(symbol=code))


def _tx_symbol(code: str) -> str:
    """Prefix a 6-digit code with sh/sz/bj for the Tencent interface."""
    if code.startswith("6"):
        return f"sh{code}"
    if code.startswith(("0", "3")):
        return f"sz{code}"
    return f"bj{code}"


def _price_from_tencent(code: str, start_date: str) -> Optional[pd.DataFrame]:
    """Recent daily bars from Tencent, normalised to the EM column naming."""
    tx = _fetch(f"price_tx_{code}_{start_date}", lambda: ak.stock_zh_a_hist_tx(
        symbol=_tx_symbol(code), start_date=start_date))
    if tx is not None and "close" in tx.columns:
        return tx.rename(columns={"date": "日期", "close": "收盘"})
    return None


def _price_from_eastmoney(code: str, start_date: str) -> Optional[pd.DataFrame]:
    """Recent daily bars from East Money."""
    df = _fetch(f"price_{code}_{start_date}", lambda: ak.stock_zh_a_hist(
        symbol=code, period="daily", start_date=start_date, adjust=""))
    if df is not None and "收盘" in df.columns:
        return df
    return None


# Registry mapping a config.PRICE_SOURCE value to its provider function.
_PRICE_PROVIDERS = {
    "tencent": _price_from_tencent,
    "eastmoney": _price_from_eastmoney,
}


def get_recent_price(code: str, start_date: str) -> Optional[pd.DataFrame]:
    """Latest daily bars from the configured source, with automatic fallback.

    config.PRICE_SOURCE selects the primary interface ("tencent" or
    "eastmoney"); the other is tried when the primary yields nothing. Tencent
    (stock_zh_a_hist_tx) is generally more stable here, while the EM endpoint
    (push2his.eastmoney.com) is occasionally refused with RemoteDisconnected.

    Returns a frame normalised to have '日期' and '收盘' columns.
    """
    primary = (getattr(config, "PRICE_SOURCE", "tencent") or "tencent").strip().lower()
    if primary not in _PRICE_PROVIDERS:
        primary = "tencent"
    order = [primary] + [k for k in _PRICE_PROVIDERS if k != primary]
    for name in order:
        df = _PRICE_PROVIDERS[name](code, start_date)
        if df is not None:
            return df
    return None


def get_dividend_detail(code: str) -> Optional[pd.DataFrame]:
    key = f"div_{code}"
    return _fetch(key, lambda: ak.stock_history_dividend_detail(symbol=code, indicator="分红"))
