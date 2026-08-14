"""Per-stock and batch orchestration."""
from __future__ import annotations

import logging
import time

import pandas as pd

from . import config, data_sources as ds, metrics

log = logging.getLogger(__name__)


def _recent_close(code: str):
    frame = ds.get_recent_price(code)
    if frame is None or frame.empty or "收盘" not in frame.columns:
        return None, None
    return metrics.to_float(frame.iloc[-1]["收盘"]), str(frame.iloc[-1].get("日期", ""))


def analyze_one(code: str, name: str = "", industry_fallback: str = "") -> dict:
    record = {"code": code, "name": name}
    fundamentals = metrics.extract_abstract(ds.get_financial_abstract(code))
    record.update(fundamentals)

    price, price_date = _recent_close(code)
    record.update({"price": price, "price_date": price_date})

    pe = metrics.valuation_stats(ds.get_valuation(code, "市盈率(TTM)"))
    record.update({"pe_ttm": pe["current"], "pe_percentile": pe["percentile"]})

    forecast = metrics.forward_growth(ds.get_research_report(code))
    record.update({"growth_forward": forecast["growth_forward"],
                   "eps_forecast": forecast["eps_forecast"],
                   "industry": metrics.pick_industry(forecast["industry"], industry_fallback)})
    record.update(metrics.compute_peg(record["pe_ttm"], record["growth_trailing"],
                                      record["growth_forward"]))
    record.update(metrics.compute_roic(ds.get_balance_sheet(code), ds.get_profit_sheet(code)))
    return record


def analyze_all(codes: list[str], verbose: bool = True) -> pd.DataFrame:
    names, industries = ds.get_name_map(), ds.get_industry_map()
    records = []
    for index, code in enumerate(codes, 1):
        if verbose:
            log.info(
                "Analyzing stock: progress=%d/%d code=%s name=%s",
                index, len(codes), code, names.get(code, ""))
        try:
            records.append(analyze_one(code, names.get(code, ""), industries.get(code, "")))
        except Exception:
            log.exception("Stock analysis failed: code=%s", code)
            records.append({"code": code, "name": names.get(code, ""),
                            "industry": industries.get(code, "") or "-"})
        time.sleep(config.REQUEST_SLEEP)
    return pd.DataFrame(records)
