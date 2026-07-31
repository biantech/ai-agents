# -*- coding: utf-8 -*-
"""Seven-step pipeline orchestration for a single stock and the full batch."""
from __future__ import annotations

import time
from datetime import datetime, timedelta

import pandas as pd

from . import config, data_sources as ds, lynch, metrics


def _recent_close(code: str):
    """Latest close from ~30 days of daily history."""
    start = (datetime.now() - timedelta(days=45)).strftime("%Y%m%d")
    px = ds.get_recent_price(code, start)
    if px is None or px.empty or "收盘" not in px.columns:
        return None, None
    close = metrics.to_float(px.iloc[-1]["收盘"])
    date = str(px.iloc[-1]["日期"])
    return close, date


def analyze_one(code: str, name: str = "", industry_fallback: str = "") -> dict:
    """Run steps 2-7 for one stock, returning a flat record dict.

    ``name`` is placed immediately after ``code`` so downstream CSV/Markdown
    outputs always show 股票代码 + 股票名称 side by side. ``industry_fallback``
    backfills the industry column when the broker report lacks it (Shenzhen only).
    """
    rec: dict = {"code": code, "name": name}

    # Step 2/3/7 raw financials.
    fa = ds.get_financial_abstract(code)
    f = metrics.extract_fundamentals(fa)
    rec.update({
        "roe": f["roe"], "gross_margin": f["gross_margin"],
        "debt_ratio": f["debt_ratio"], "cash_quality": f["cash_quality"],
        "g_profit_annual": f["g_profit_annual"],
        "g_revenue_annual": f["g_revenue_annual"],
        "g_profit_q1": f["g_profit_q1"], "report_period": f["report_period"],
    })

    # Step 3 price + valuation (PE TTM / PB).
    close, price_date = _recent_close(code)
    rec["price"] = close
    rec["price_date"] = price_date

    pe_hist = ds.get_valuation(code, "市盈率(TTM)", config.VAL_PERIOD_LONG)
    pe_stats = metrics.valuation_stats(pe_hist)
    rec["pe_ttm"] = pe_stats["current"]
    rec["pe_percentile"] = pe_stats["percentile"]   # Step 4 percentile

    pb_hist = ds.get_valuation(code, "市净率", config.VAL_PERIOD_LONG)
    pb_stats = metrics.valuation_stats(pb_hist)
    rec["pb"] = pb_stats["current"]
    rec["pb_percentile"] = pb_stats["percentile"]

    # Step 3 dividend yield.
    div = ds.get_dividend_detail(code)
    rec["dividend_yield"] = metrics.dividend_yield(div, close)

    # Step 5 forward growth (broker consensus).
    report = ds.get_research_report(code)
    fw = metrics.forward_growth(report)
    rec["g_forward"] = fw["g_forward"]
    # Industry: broker report first; batch map (Shenzhen) backfills when missing.
    rec["industry"] = metrics.pick_industry(fw["industry"], industry_fallback)
    rec["eps_forecast"] = fw["eps_years"]

    # Step 6 PEG variants. Trailing growth prefers annual profit growth.
    g_trailing = f["g_profit_annual"] if f["g_profit_annual"] is not None else f["g_profit_ttm"]
    peg = metrics.compute_peg(rec["pe_ttm"], g_trailing, fw["g_forward"],
                              rec["dividend_yield"])
    rec.update(peg)

    # Step 7 overlay + Lynch classification + quality score.
    flags = lynch.overlay_flags(f)
    rec["lynch_category"] = lynch.classify(
        f["g_profit_annual"], fw["g_forward"], f["roe"])
    rec["accelerating"] = flags["accelerating"]
    rec["margin_up"] = flags["margin_up"]
    rec["cash_healthy"] = flags["cash_healthy"]
    rec["debt_warn"] = flags["debt_warn"]
    rec["notes"] = "; ".join(flags["notes"])
    rec["quality_score"] = lynch.quality_score(f, flags)
    return rec


def analyze_all(codes: list[str], verbose: bool = True) -> pd.DataFrame:
    """Batch process all stocks with polite throttling."""
    records = []
    total = len(codes)
    # One batch lookup for code -> name mapping (Step 1 enrichment).
    name_map = ds.get_name_map()
    # One batch lookup for code -> industry fallback (Shenzhen coverage only).
    industry_map = ds.get_industry_map()
    for i, code in enumerate(codes, 1):
        name = name_map.get(code, "")
        industry_fallback = industry_map.get(code, "")
        if verbose:
            print(f"[{i}/{total}] analyzing {code} {name} ...")
        try:
            records.append(analyze_one(code, name, industry_fallback))
        except Exception as e:  # noqa: BLE001 - keep batch alive
            print(f"    [error] {code}: {repr(e)[:150]}")
            records.append({"code": code, "name": name,
                            "industry": industry_fallback or "-"})
        time.sleep(config.REQUEST_SLEEP)
    return pd.DataFrame(records)
