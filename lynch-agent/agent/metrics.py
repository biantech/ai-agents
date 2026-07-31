# -*- coding: utf-8 -*-
"""Metric computation: parse financials, compute PEG variants, percentiles.

All heavy numeric logic lives here so pipeline.py stays a thin orchestrator.
Values from stock_financial_abstract are strings; growth/ratio rows are in %.
"""
from __future__ import annotations

import re
from typing import Optional

import numpy as np
import pandas as pd

from . import config


# ---------------------------------------------------------------------------
# Low-level parsing helpers
# ---------------------------------------------------------------------------
def to_float(x) -> Optional[float]:
    """Robust conversion: handle None, '--', commas, percent signs."""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return None if (isinstance(x, float) and np.isnan(x)) else float(x)
    s = str(x).strip().replace(",", "").replace("%", "")
    if s in ("", "--", "-", "None", "nan", "NaN"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _date_cols(df: pd.DataFrame) -> list[str]:
    """Return report-date columns (YYYYMMDD) sorted descending (newest first)."""
    cols = [c for c in df.columns if re.fullmatch(r"\d{8}", str(c))]
    return sorted(cols, reverse=True)


def _annual_cols(cols: list[str]) -> list[str]:
    """Keep only year-end (1231) reports, newest first."""
    return [c for c in cols if str(c).endswith("1231")]


def _row_value(df: pd.DataFrame, indicator: str, col: str) -> Optional[float]:
    """Fetch a single metric value by indicator name at a given report column."""
    sub = df[df["指标"] == indicator]
    if sub.empty or col not in df.columns:
        return None
    return to_float(sub.iloc[0][col])


def _latest_value(df: pd.DataFrame, indicator: str, cols: list[str]) -> Optional[float]:
    """First non-null value of indicator scanning newest->oldest columns."""
    for c in cols:
        v = _row_value(df, indicator, c)
        if v is not None:
            return v
    return None


# ---------------------------------------------------------------------------
# Financial fundamentals extraction (Steps 2 & 3 & 7)
# ---------------------------------------------------------------------------
def extract_fundamentals(fa: Optional[pd.DataFrame]) -> dict:
    """Extract ROE, gross margin, debt ratio, growth, cash quality from abstract."""
    out: dict = {
        "roe": None, "gross_margin": None, "debt_ratio": None,
        "g_profit_annual": None, "g_revenue_annual": None,
        "g_profit_ttm": None, "cash_quality": None,
        "gross_margin_prev": None, "g_profit_q1": None,
        "report_period": None, "net_profit": None,
    }
    if fa is None or fa.empty or "指标" not in fa.columns:
        return out
    cols = _date_cols(fa)
    if not cols:
        return out
    annual = _annual_cols(cols)
    out["report_period"] = cols[0]

    # ROE is a flow/return metric: use the latest ANNUAL value so a Q1-only
    # figure (e.g. 1.8%) does not understate a full-year 12% return.
    out["roe"] = _latest_value(fa, "净资产收益率(ROE)", annual or cols)
    out["gross_margin"] = _latest_value(fa, "毛利率", cols)
    out["debt_ratio"] = _latest_value(fa, "资产负债率", cols)
    out["net_profit"] = _latest_value(fa, "归母净利润", cols)

    # Annual growth: prefer latest year-end growth rows.
    out["g_profit_annual"] = _latest_value(fa, "归属母公司净利润增长率", annual or cols)
    out["g_revenue_annual"] = _latest_value(fa, "营业总收入增长率", annual or cols)
    # TTM / most-recent-period profit growth (any period).
    out["g_profit_ttm"] = _latest_value(fa, "归属母公司净利润增长率", cols)

    # Gross margin one-year-ago (previous year-end) for trend.
    if len(annual) >= 2:
        out["gross_margin_prev"] = _row_value(fa, "毛利率", annual[1])

    # Q1 profit growth: latest column ending 0331.
    q1_cols = [c for c in cols if str(c).endswith("0331")]
    if q1_cols:
        out["g_profit_q1"] = _row_value(fa, "归属母公司净利润增长率", q1_cols[0])

    # Cash quality = operating cashflow / net profit (latest period both present).
    ocf = _latest_value(fa, "经营现金流量净额", cols)
    npf = out["net_profit"]
    if ocf is not None and npf not in (None, 0):
        out["cash_quality"] = round(ocf / npf, 3)
    return out


# ---------------------------------------------------------------------------
# Valuation + historical percentile (Steps 3 & 4)
# ---------------------------------------------------------------------------
def valuation_stats(hist: Optional[pd.DataFrame]) -> dict:
    """From a Baidu valuation series (date,value) -> current value + percentile."""
    out = {"current": None, "percentile": None}
    if hist is None or hist.empty or "value" not in hist.columns:
        return out
    vals = pd.to_numeric(hist["value"], errors="coerce").dropna()
    if vals.empty:
        return out
    cur = float(vals.iloc[-1])
    out["current"] = round(cur, 2)
    # Percentile: share of history below current value (only positive PE valid).
    valid = vals[vals > 0] if cur > 0 else vals
    if not valid.empty:
        out["percentile"] = round(float((valid < cur).mean()) * 100, 1)
    return out


# ---------------------------------------------------------------------------
# Forward growth from broker consensus (Step 5)
# ---------------------------------------------------------------------------
def forward_growth(report: Optional[pd.DataFrame]) -> dict:
    """Median forward EPS growth across broker reports (year N -> N+1)."""
    out = {"g_forward": None, "industry": None, "eps_years": {}}
    if report is None or report.empty:
        return out
    if "行业" in report.columns and not report["行业"].dropna().empty:
        out["industry"] = str(report["行业"].dropna().iloc[0])
    # Locate consensus EPS columns like "2026-盈利预测-收益".
    eps_cols = {}
    for c in report.columns:
        m = re.match(r"(\d{4})-盈利预测-收益", str(c))
        if m:
            eps_cols[int(m.group(1))] = c
    if len(eps_cols) < 2:
        return out
    years = sorted(eps_cols)
    medians = {}
    for y in years:
        series = pd.to_numeric(report[eps_cols[y]], errors="coerce").dropna()
        series = series[series != 0]
        if not series.empty:
            medians[y] = float(series.median())
    out["eps_years"] = {y: round(v, 3) for y, v in medians.items()}
    # Average YoY growth across consecutive available years.
    growths = []
    ys = sorted(medians)
    for i in range(len(ys) - 1):
        prev, nxt = medians[ys[i]], medians[ys[i + 1]]
        if prev and prev > 0:
            growths.append((nxt - prev) / prev * 100.0)
    if growths:
        out["g_forward"] = round(sum(growths) / len(growths), 2)
    return out


# ---------------------------------------------------------------------------
# Dividend yield (Step 3)
# ---------------------------------------------------------------------------
def dividend_yield(div: Optional[pd.DataFrame], price: Optional[float]) -> Optional[float]:
    """TTM dividend yield %: sum of last-12-month per-share cash dividend / price.

    A-share '派息' is cash per 10 shares, so divide by 10.
    """
    if div is None or div.empty or not price or price <= 0:
        return None
    if "派息" not in div.columns or "除权除息日" not in div.columns:
        return None
    d = div.copy()
    d["_ex"] = pd.to_datetime(d["除权除息日"], errors="coerce")
    d = d.dropna(subset=["_ex"])
    if d.empty:
        return None
    cutoff = d["_ex"].max() - pd.Timedelta(days=365)
    recent = d[d["_ex"] > cutoff]
    total = pd.to_numeric(recent["派息"], errors="coerce").fillna(0).sum()
    per_share = total / 10.0
    return round(per_share / price * 100.0, 2)


# ---------------------------------------------------------------------------
# PEG variants (Step 6)
# ---------------------------------------------------------------------------
def _safe_peg(pe: Optional[float], g: Optional[float]) -> Optional[float]:
    """PEG = PE / G(%). Guards: need positive PE and positive growth."""
    if pe is None or g is None or pe <= 0 or g <= 0:
        return None
    return round(pe / g, 3)


def compute_peg(pe_ttm: Optional[float], g_trailing: Optional[float],
                g_forward: Optional[float], div_yield: Optional[float]) -> dict:
    """Base / adjusted / forward PEG per analysis-step.md Step 6."""
    base = _safe_peg(pe_ttm, g_trailing)
    dv = div_yield or 0.0
    adj_g = None if g_trailing is None else g_trailing + dv
    adjusted = _safe_peg(pe_ttm, adj_g)
    forward = _safe_peg(pe_ttm, g_forward)
    return {"peg_base": base, "peg_adjusted": adjusted, "peg_forward": forward}


def pick_industry(report_industry, fallback) -> str:
    """Choose the industry label: broker report first, batch map as fallback.

    A broker-report value that is None/empty/placeholder ("-", "nan") is treated
    as missing and replaced by ``fallback`` when the latter is meaningful.
    Returns "-" when neither source provides a usable value.
    """
    def _clean(v):
        if v is None:
            return ""
        s = str(v).strip()
        return "" if s.lower() in ("", "-", "none", "nan") else s

    primary = _clean(report_industry)
    if primary:
        return primary
    alt = _clean(fallback)
    return alt if alt else "-"
