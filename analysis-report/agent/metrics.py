from __future__ import annotations
import re
import numpy as np
import pandas as pd

def number(value):
    if value is None or (isinstance(value, (float, np.number)) and pd.isna(value)): return None
    try: return float(str(value).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError): return None

def _cols(frame): return sorted([str(c) for c in frame.columns if re.fullmatch(r"\d{8}", str(c))], reverse=True)
def _value(frame, names, col):
    if frame is None or frame.empty or "指标" not in frame.columns or col not in frame.columns: return None
    for name in names:
        rows = frame[frame["指标"] == name]
        if not rows.empty and (v := number(rows.iloc[0][col])) is not None: return v
    return None

def abstract(frame):
    out = {"report_period": None, "revenue": None, "profit": None, "growth": None, "gross_margin": None, "net_margin": None, "roe": None, "debt_ratio": None, "cash_quality": None}
    if frame is None or frame.empty or "指标" not in frame.columns: return out
    cols = _cols(frame)
    if not cols: return out
    latest, annual = cols[0], next((c for c in cols if c.endswith("1231")), cols[0])
    out.update(report_period=latest, revenue=_value(frame, ["营业收入"], latest), profit=_value(frame, ["归母净利润", "净利润"], latest), growth=_value(frame, ["归属母公司净利润增长率", "净利润增长率"], annual), gross_margin=_value(frame, ["毛利率"], latest), roe=_value(frame, ["净资产收益率(ROE)", "净资产收益率_平均"], annual), debt_ratio=_value(frame, ["资产负债率"], latest))
    out["net_margin"] = None if not out["revenue"] or out["profit"] is None else out["profit"] / out["revenue"] * 100
    cash = _value(frame, ["经营现金流量净额"], latest)
    out["cash_quality"] = None if cash is None or not out["profit"] else cash / out["profit"]
    return out

def current_value(frame):
    if frame is None or frame.empty or "value" not in frame.columns: return None
    vals = pd.to_numeric(frame["value"], errors="coerce").dropna()
    return None if vals.empty else float(vals.iloc[-1])

def forecast_growth(frame):
    if frame is None or frame.empty: return None
    vals = {}
    for col in frame.columns:
        if re.match(r"\d{4}-盈利预测-收益", str(col)):
            series = pd.to_numeric(frame[col], errors="coerce").dropna(); series = series[series > 0]
            if not series.empty: vals[int(str(col)[:4])] = float(series.median())
    growth = [(vals[y] / vals[p] - 1) * 100 for p, y in zip(sorted(vals), sorted(vals)[1:]) if vals[p] > 0]
    return sum(growth) / len(growth) if growth else None

def compute_peg(pe, trailing_growth, forward_growth):
    def divide(growth):
        return None if pe is None or growth is None or pe <= 0 or growth <= 0 else round(pe / growth, 3)
    return {"peg_trailing": divide(trailing_growth), "peg_forward": divide(forward_growth)}

def compute_roic(balance, profit):
    """Return latest ROIC when the required annual statement fields are present."""
    out = {"roic": None, "nopat": None, "invested_capital": None}
    if balance is None or profit is None or balance.empty or profit.empty: return out
    def rows(frame):
        date = next((c for c in ("REPORT_DATE", "REPORTDATE", "报告日期") if c in frame), None)
        if not date: return {}
        result = {}
        for _, row in frame.iterrows():
            year = pd.to_datetime(row[date], errors="coerce")
            if not pd.isna(year): result[int(year.year)] = row
        return result
    balances, profits = rows(balance), rows(profit)
    if not profits: return out
    def field(row, names, default=None):
        for name in names:
            if name in row.index and (value := number(row[name])) is not None: return value
        return default
    for year in sorted(profits, reverse=True):
        current, previous = balances.get(year), balances.get(year - 1)
        if current is None or previous is None: continue
        def capital(row):
            equity = field(row, ("TOTAL_EQUITY", "TOTAL_PARENT_EQUITY", "股东权益合计"))
            cash = field(row, ("MONETARYFUNDS", "MONETARY_FUNDS", "货币资金"))
            if equity is None or cash is None: return None
            debt = sum(field(row, names, 0) for names in (("SHORT_LOAN",), ("NONCURRENT_LIAB_1YEAR",), ("LONG_LOAN",), ("BOND_PAYABLE",), ("LEASE_LIAB",)))
            value = equity + debt - cash
            return value if value > 0 else None
        cur_cap, prev_cap = capital(current), capital(previous)
        pretax = field(profits[year], ("TOTAL_PROFIT", "利润总额"))
        if cur_cap is None or prev_cap is None or pretax is None or pretax <= 0: continue
        interest = field(profits[year], ("FE_INTEREST_EXPENSE", "INTEREST_EXPENSE", "利息费用"), 0)
        tax = field(profits[year], ("INCOME_TAX", "所得税费用"), 0)
        nopat = (pretax + interest) * (1 - min(max(tax / pretax, 0), 0.35))
        invested = (cur_cap + prev_cap) / 2
        out.update(nopat=round(nopat, 2), invested_capital=round(invested, 2), roic=round(nopat / invested * 100, 2))
        break
    return out

def technical(frame):
    if frame is None or frame.empty or "收盘" not in frame.columns: return {}
    close = pd.to_numeric(frame["收盘"], errors="coerce").dropna()
    if close.empty: return {}
    return {"price": float(close.iloc[-1]), **{f"ma{n}": float(close.tail(n).mean()) for n in (5, 20, 60, 120, 250) if len(close) >= n}, "price_date": str(frame.iloc[-1].get("日期", ""))}
