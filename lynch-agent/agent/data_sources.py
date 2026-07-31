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

import hashlib
import os
import pickle
import time
import warnings
from typing import Callable, Optional

import akshare as ak
import pandas as pd

from . import config

warnings.filterwarnings("ignore")


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
    print(f"    [warn] {key} failed after {config.MAX_RETRY} tries: {last_err}")
    print(f"           url: {url_info}")
    return None


# ---------------------------------------------------------------------------
# Public data accessors
# ---------------------------------------------------------------------------
def get_stock_list() -> list[str]:
    """Collect 6-digit codes from every text file under LIST_DIR.

    Walks all files in the list directory, extracts lines that are exactly a
    6-digit code (BOM headers / category titles are skipped), and de-duplicates
    while preserving first-seen order. This removes the need to manually merge or
    rename source files into a single out.txt.
    """
    codes: list[str] = []
    seen: set[str] = set()
    if not os.path.isdir(config.LIST_DIR):
        return codes
    for name in sorted(os.listdir(config.LIST_DIR)):
        path = os.path.join(config.LIST_DIR, name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                for line in f:
                    s = line.strip()
                    if len(s) == 6 and s.isdigit() and s not in seen:
                        seen.add(s)
                        codes.append(s)
        except (OSError, UnicodeDecodeError):
            # Skip unreadable / non-text files gracefully.
            continue
    return codes


def get_codes_by_file() -> list[tuple[str, list[str]]]:
    """Collect 6-digit codes grouped by their source file under LIST_DIR.

    Returns a list of (filename_stem, codes) pairs, one per readable file that
    yields at least one code. Codes are de-duplicated within each file (order
    preserved) but NOT across files, so callers can produce isolated per-file
    reports. The stem (name without extension) is intended as an output prefix.
    """
    groups: list[tuple[str, list[str]]] = []
    if not os.path.isdir(config.LIST_DIR):
        return groups
    for name in sorted(os.listdir(config.LIST_DIR)):
        path = os.path.join(config.LIST_DIR, name)
        if not os.path.isfile(path):
            continue
        codes: list[str] = []
        seen: set[str] = set()
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                for line in f:
                    s = line.strip()
                    if len(s) == 6 and s.isdigit() and s not in seen:
                        seen.add(s)
                        codes.append(s)
        except (OSError, UnicodeDecodeError):
            # Skip unreadable / non-text files gracefully.
            continue
        if codes:
            stem = os.path.splitext(name)[0]
            groups.append((stem, codes))
    return groups


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
