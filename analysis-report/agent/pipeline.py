from __future__ import annotations
import logging, time
from . import config, data_sources as ds, metrics
log = logging.getLogger(__name__)

def analyze_one(code: str, names: dict[str, str]) -> dict:
    item = {"code": code, "name": names.get(code, "待补充")}
    item.update(metrics.abstract(ds.financial_abstract(code)))
    item["pe"] = metrics.current_value(ds.valuation(code, "市盈率(TTM)"))
    item["pb"] = metrics.current_value(ds.valuation(code, "市净率"))
    item["ps"] = metrics.current_value(ds.valuation(code, "市销率"))
    item["forecast_growth"] = metrics.forecast_growth(ds.research(code))
    item.update(metrics.compute_peg(item.get("pe"), item.get("growth"), item.get("forecast_growth")))
    item.update(metrics.compute_roic(ds.balance(code), ds.profit(code)))
    item.update(metrics.technical(ds.prices(code)))
    return item

def analyze_all(codes: list[str]) -> list[dict]:
    names = ds.name_map(); records = []
    for index, code in enumerate(codes, 1):
        log.info("Analyzing stock: progress=%d/%d code=%s", index, len(codes), code)
        try: records.append(analyze_one(code, names))
        except Exception:
            log.exception("Stock analysis failed: code=%s", code)
            records.append({"code": code, "name": names.get(code, "待补充")})
        time.sleep(config.REQUEST_SLEEP)
    return records
