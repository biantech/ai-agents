"""Pure financial calculations for the PEG-ROIC framework."""
from __future__ import annotations

import re
from typing import Iterable, Optional

import numpy as np
import pandas as pd


def to_float(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float, np.number)):
        return None if pd.isna(value) else float(value)
    text = str(value).strip().replace(",", "").replace("%", "")
    if text.lower() in ("", "--", "-", "none", "nan"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _date_cols(frame: pd.DataFrame) -> list[str]:
    return sorted((str(c) for c in frame.columns if re.fullmatch(r"\d{8}", str(c))),
                  reverse=True)


def _annual_cols(frame: pd.DataFrame) -> list[str]:
    return [c for c in _date_cols(frame) if c.endswith("1231")]


def _indicator_value(frame: pd.DataFrame, names: Iterable[str], column: str):
    if frame is None or frame.empty or "指标" not in frame.columns or column not in frame.columns:
        return None
    for name in names:
        rows = frame[frame["指标"] == name]
        if not rows.empty and (value := to_float(rows.iloc[0][column])) is not None:
            return value
    return None


def extract_abstract(frame: Optional[pd.DataFrame]) -> dict:
    out = {"roe": None, "gross_margin": None, "debt_ratio": None,
           "cash_quality": None, "growth_trailing": None,
           "report_period": None}
    if frame is None or frame.empty or "指标" not in frame.columns:
        return out
    dates, annual = _date_cols(frame), _annual_cols(frame)
    if not dates:
        return out
    latest, annual_latest = dates[0], (annual or dates)[0]
    out["report_period"] = latest
    out["roe"] = _indicator_value(frame, ["净资产收益率(ROE)", "净资产收益率_平均"], annual_latest)
    out["gross_margin"] = _indicator_value(frame, ["毛利率"], latest)
    out["debt_ratio"] = _indicator_value(frame, ["资产负债率"], latest)
    out["growth_trailing"] = _indicator_value(
        frame, ["归属母公司净利润增长率"], annual_latest)
    profit = _indicator_value(frame, ["归母净利润", "净利润"], latest)
    cash = _indicator_value(frame, ["经营现金流量净额"], latest)
    if cash is not None and profit not in (None, 0):
        out["cash_quality"] = round(cash / profit, 3)
    return out


def valuation_stats(frame: Optional[pd.DataFrame]) -> dict:
    out = {"current": None, "percentile": None}
    if frame is None or frame.empty or "value" not in frame.columns:
        return out
    values = pd.to_numeric(frame["value"], errors="coerce").dropna()
    if values.empty:
        return out
    current = float(values.iloc[-1])
    valid = values[values > 0] if current > 0 else values
    out["current"] = round(current, 2)
    if not valid.empty:
        out["percentile"] = round(float((valid < current).mean()) * 100, 1)
    return out


def forward_growth(report: Optional[pd.DataFrame]) -> dict:
    out = {"growth_forward": None, "industry": None, "eps_forecast": {}}
    if report is None or report.empty:
        return out
    if "行业" in report.columns and not report["行业"].dropna().empty:
        out["industry"] = str(report["行业"].dropna().iloc[0])
    columns = {}
    for column in report.columns:
        match = re.match(r"(\d{4})-盈利预测-收益", str(column))
        if match:
            columns[int(match.group(1))] = column
    medians = {}
    for year, column in columns.items():
        values = pd.to_numeric(report[column], errors="coerce").dropna()
        values = values[values > 0]
        if not values.empty:
            medians[year] = float(values.median())
    out["eps_forecast"] = {year: round(value, 3) for year, value in medians.items()}
    growth = []
    years = sorted(medians)
    for previous, current in zip(years, years[1:]):
        growth.append((medians[current] / medians[previous] - 1) * 100)
    if growth:
        out["growth_forward"] = round(sum(growth) / len(growth), 2)
    return out


def compute_peg(pe: Optional[float], growth_trailing: Optional[float],
                growth_forward: Optional[float]) -> dict:
    def divide(growth):
        if pe is None or growth is None or pe <= 0 or growth <= 0:
            return None
        return round(pe / growth, 3)
    return {"peg_trailing": divide(growth_trailing),
            "peg_forward": divide(growth_forward)}


def _statement_columns(frame: Optional[pd.DataFrame]) -> tuple[Optional[str], Optional[str]]:
    if frame is None or frame.empty:
        return None, None
    date_col = next((c for c in ("REPORT_DATE", "REPORTDATE", "报告日期")
                     if c in frame.columns), None)
    return date_col, "SECURITY_CODE" if "SECURITY_CODE" in frame.columns else None


def _sorted_statement(frame: Optional[pd.DataFrame]) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    date_col, _ = _statement_columns(frame)
    result = frame.copy()
    if date_col:
        result["_report_date"] = pd.to_datetime(result[date_col], errors="coerce")
        result = result.sort_values("_report_date", ascending=False)
    return result.reset_index(drop=True)


def _row_number(row: pd.Series, aliases: Iterable[str], default=None):
    for alias in aliases:
        if alias in row.index and (value := to_float(row[alias])) is not None:
            return value
    return default


DEBT_FIELDS = (
    ("SHORT_LOAN", "短期借款"), ("NONCURRENT_LIAB_1YEAR", "一年内到期的非流动负债"),
    ("LONG_LOAN", "长期借款"), ("BOND_PAYABLE", "应付债券"),
    ("LEASE_LIAB", "租赁负债"),
)


def _invested_capital(row: pd.Series) -> Optional[float]:
    equity = _row_number(row, ("TOTAL_EQUITY", "TOTAL_PARENT_EQUITY", "股东权益合计"))
    cash = _row_number(row, ("MONETARYFUNDS", "MONETARY_FUNDS", "货币资金"))
    if equity is None or cash is None:
        return None
    debt = sum(_row_number(row, aliases, 0.0) for aliases in DEBT_FIELDS)
    capital = equity + debt - cash
    return capital if capital > 0 else None


def compute_roic(balance: Optional[pd.DataFrame], profit: Optional[pd.DataFrame]) -> dict:
    """Compute annual ROIC using NOPAT / average invested capital.

    NOPAT = EBIT * (1 - effective tax rate), where effective tax is constrained
    to 0..35%. Invested capital = equity + interest-bearing debt - cash.
    """
    out = {"roic": None, "roic_previous": None, "roic_stability": None,
           "nopat": None, "invested_capital": None, "roic_data_complete": False}
    balances, profits = _sorted_statement(balance), _sorted_statement(profit)
    if len(balances) < 2 or profits.empty:
        return out

    balance_by_year = {
        int(row["_report_date"].year): row
        for _, row in balances.iterrows() if pd.notna(row.get("_report_date"))
    }
    annual_values = []
    for _, prow in profits.iterrows():
        report_date = prow.get("_report_date")
        if pd.isna(report_date):
            continue
        year = int(report_date.year)
        if year not in balance_by_year or year - 1 not in balance_by_year:
            continue
        current_capital = _invested_capital(balance_by_year[year])
        previous_capital = _invested_capital(balance_by_year[year - 1])
        pretax_profit = _row_number(prow, ("TOTAL_PROFIT", "利润总额"))
        interest = _row_number(prow, ("FE_INTEREST_EXPENSE", "INTEREST_EXPENSE",
                                      "利息费用"), 0.0)
        tax = _row_number(prow, ("INCOME_TAX", "所得税费用"), 0.0)
        if None in (current_capital, previous_capital, pretax_profit) or pretax_profit <= 0:
            continue
        ebit = pretax_profit + interest
        tax_rate = min(max(tax / pretax_profit, 0.0), 0.35)
        nopat = ebit * (1 - tax_rate)
        average_capital = (current_capital + previous_capital) / 2
        annual_values.append((year, nopat / average_capital * 100, nopat, average_capital))

    if not annual_values:
        return out
    annual_values.sort(key=lambda item: item[0], reverse=True)
    out["roic"] = round(annual_values[0][1], 2)
    out["nopat"] = round(annual_values[0][2], 2)
    out["invested_capital"] = round(annual_values[0][3], 2)
    out["roic_data_complete"] = True
    if len(annual_values) > 1:
        out["roic_previous"] = round(annual_values[1][1], 2)
        out["roic_stability"] = round(abs(annual_values[0][1] - annual_values[1][1]), 2)
    return out


def pick_industry(primary, fallback) -> str:
    for value in (primary, fallback):
        text = "" if value is None else str(value).strip()
        if text.lower() not in ("", "-", "none", "nan"):
            return text
    return "-"
