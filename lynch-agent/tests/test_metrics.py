# -*- coding: utf-8 -*-
"""Unit tests for agent.metrics pure functions.

Run: python3 -m unittest tests.test_metrics
"""
from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from agent import metrics


def _abstract(rows: dict, cols: list[str]) -> pd.DataFrame:
    """Build a stock_financial_abstract-like frame: index '指标' + date cols."""
    data = {"指标": list(rows.keys())}
    for c in cols:
        data[c] = [rows[ind].get(c) for ind in rows]
    return pd.DataFrame(data)


class TestToFloat(unittest.TestCase):
    def test_none_and_placeholders(self):
        for v in (None, "--", "-", "", "None", "nan", "NaN"):
            self.assertIsNone(metrics.to_float(v))

    def test_nan_float(self):
        self.assertIsNone(metrics.to_float(float("nan")))

    def test_strips_comma_and_percent(self):
        self.assertEqual(metrics.to_float("1,234.5"), 1234.5)
        self.assertEqual(metrics.to_float("12.03%"), 12.03)

    def test_numeric_passthrough(self):
        self.assertEqual(metrics.to_float(7), 7.0)
        self.assertEqual(metrics.to_float(3.14), 3.14)

    def test_garbage_returns_none(self):
        self.assertIsNone(metrics.to_float("abc"))


class TestExtractFundamentals(unittest.TestCase):
    def test_empty_inputs(self):
        self.assertIsNone(metrics.extract_fundamentals(None)["roe"])
        self.assertIsNone(metrics.extract_fundamentals(pd.DataFrame())["roe"])

    def test_roe_uses_latest_annual_not_q1(self):
        # Latest column is Q1 (0331) with a low value; annual (1231) is higher.
        cols = ["20260331", "20251231", "20241231"]
        fa = _abstract({
            "净资产收益率(ROE)": {"20260331": "1.82", "20251231": "12.03",
                                   "20241231": "5.21"},
            "毛利率": {"20260331": "40", "20251231": "38", "20241231": "35"},
            "归属母公司净利润增长率": {"20260331": "5", "20251231": "30",
                                        "20241231": "10"},
        }, cols)
        f = metrics.extract_fundamentals(fa)
        # ROE must pick the annual 12.03, not the Q1 1.82.
        self.assertEqual(f["roe"], 12.03)
        # Annual profit growth prefers year-end row.
        self.assertEqual(f["g_profit_annual"], 30.0)
        # Q1 growth captured separately.
        self.assertEqual(f["g_profit_q1"], 5.0)
        # report_period is newest column.
        self.assertEqual(f["report_period"], "20260331")
        # gross margin latest + previous year-end.
        self.assertEqual(f["gross_margin"], 40.0)
        self.assertEqual(f["gross_margin_prev"], 35.0)

    def test_roe_falls_back_to_any_col_without_annual(self):
        cols = ["20260331", "20260930"]
        fa = _abstract({
            "净资产收益率(ROE)": {"20260331": "1.82", "20260930": "3.76"},
        }, cols)
        f = metrics.extract_fundamentals(fa)
        # No 1231 available -> use newest column (dates sorted desc: 0930 wins).
        self.assertEqual(f["roe"], 3.76)

    def test_cash_quality_ratio(self):
        cols = ["20251231"]
        fa = _abstract({
            "归母净利润": {"20251231": "100"},
            "经营现金流量净额": {"20251231": "80"},
        }, cols)
        f = metrics.extract_fundamentals(fa)
        self.assertAlmostEqual(f["cash_quality"], 0.8)

    def test_cash_quality_zero_profit_guard(self):
        cols = ["20251231"]
        fa = _abstract({
            "归母净利润": {"20251231": "0"},
            "经营现金流量净额": {"20251231": "80"},
        }, cols)
        self.assertIsNone(metrics.extract_fundamentals(fa)["cash_quality"])


class TestValuationStats(unittest.TestCase):
    def test_empty(self):
        self.assertIsNone(metrics.valuation_stats(None)["current"])
        self.assertIsNone(metrics.valuation_stats(pd.DataFrame())["current"])

    def test_percentile_share_below_current(self):
        # History 10,20,30,40,50 (current=last=50): 4 of 5 below -> 80%.
        hist = pd.DataFrame({"value": [10, 20, 30, 40, 50]})
        out = metrics.valuation_stats(hist)
        self.assertEqual(out["current"], 50.0)
        self.assertEqual(out["percentile"], 80.0)

    def test_positive_pe_filter(self):
        # Negative PEs excluded from the valid base when current is positive.
        hist = pd.DataFrame({"value": [-5, 10, 20, 30]})
        out = metrics.valuation_stats(hist)
        self.assertEqual(out["current"], 30.0)
        # valid = [10,20,30]; below 30 -> 2/3 = 66.7%.
        self.assertEqual(out["percentile"], 66.7)


class TestForwardGrowth(unittest.TestCase):
    def test_empty(self):
        self.assertIsNone(metrics.forward_growth(None)["g_forward"])

    def test_median_eps_growth(self):
        rep = pd.DataFrame({
            "行业": ["消费电子", "消费电子"],
            "2026-盈利预测-收益": [1.0, 1.0],
            "2027-盈利预测-收益": [1.2, 1.4],
        })
        out = metrics.forward_growth(rep)
        self.assertEqual(out["industry"], "消费电子")
        # medians: 2026=1.0, 2027=1.3 -> growth 30%.
        self.assertEqual(out["g_forward"], 30.0)

    def test_single_year_insufficient(self):
        rep = pd.DataFrame({"2026-盈利预测-收益": [1.0, 1.2]})
        self.assertIsNone(metrics.forward_growth(rep)["g_forward"])


class TestDividendYield(unittest.TestCase):
    def test_none_or_bad_price(self):
        self.assertIsNone(metrics.dividend_yield(None, 10))
        self.assertIsNone(metrics.dividend_yield(pd.DataFrame(), 0))

    def test_ttm_yield_divides_by_ten(self):
        # 派息 is per 10 shares: 2.0/10 = 0.2 per share; price 10 -> 2.0%.
        div = pd.DataFrame({
            "除权除息日": ["2026-05-01", "2020-05-01"],
            "派息": [2.0, 5.0],
        })
        y = metrics.dividend_yield(div, 10.0)
        self.assertEqual(y, 2.0)


class TestComputePeg(unittest.TestCase):
    def test_three_variants(self):
        out = metrics.compute_peg(pe_ttm=13.76, g_trailing=32.77,
                                  g_forward=4.29, div_yield=3.43)
        self.assertAlmostEqual(out["peg_base"], round(13.76 / 32.77, 3))
        self.assertAlmostEqual(out["peg_adjusted"],
                               round(13.76 / (32.77 + 3.43), 3))
        self.assertAlmostEqual(out["peg_forward"], round(13.76 / 4.29, 3))

    def test_negative_growth_yields_none(self):
        out = metrics.compute_peg(20.0, -5.0, None, 2.0)
        self.assertIsNone(out["peg_base"])
        self.assertIsNone(out["peg_adjusted"])
        self.assertIsNone(out["peg_forward"])

    def test_none_pe_guard(self):
        out = metrics.compute_peg(None, 20.0, 20.0, 1.0)
        self.assertIsNone(out["peg_base"])


class TestPickIndustry(unittest.TestCase):
    def test_report_industry_wins(self):
        # Broker report present -> fallback ignored.
        self.assertEqual(metrics.pick_industry("消费电子", "C 制造业"), "消费电子")

    def test_fallback_when_report_missing(self):
        # None / empty / placeholder report values fall back to the batch map.
        for missing in (None, "", "  ", "-", "nan", "None"):
            self.assertEqual(metrics.pick_industry(missing, "C 制造业"),
                             "C 制造业")

    def test_dash_when_both_missing(self):
        # Neither source usable -> canonical "-".
        for missing in (None, "", "-", "nan"):
            self.assertEqual(metrics.pick_industry(missing, missing), "-")

    def test_report_missing_fallback_missing_returns_dash(self):
        self.assertEqual(metrics.pick_industry(None, ""), "-")

    def test_values_are_trimmed(self):
        self.assertEqual(metrics.pick_industry("  半导体  ", ""), "半导体")
        self.assertEqual(metrics.pick_industry(None, "  C 制造业 "), "C 制造业")


if __name__ == "__main__":
    unittest.main()
