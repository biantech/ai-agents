# -*- coding: utf-8 -*-
"""Unit tests for agent.lynch and agent.portfolio pure logic.

Run: python3 -m unittest tests.test_lynch_portfolio
"""
from __future__ import annotations

import unittest

import pandas as pd

from agent import lynch, portfolio


class TestClassify(unittest.TestCase):
    def test_fast_grower(self):
        self.assertEqual(lynch.classify(25.0, 10.0, 12.0), "快速增长")

    def test_stalwart(self):
        self.assertEqual(lynch.classify(15.0, 10.0, 12.0), "稳定增长")

    def test_slow_grower(self):
        self.assertEqual(lynch.classify(5.0, 3.0, 8.0), "缓慢增长")

    def test_turnaround_when_forward_recovers(self):
        # Trailing negative but forward > STALWART_LOW (10) -> 困境反转.
        self.assertEqual(lynch.classify(-20.0, 28.0, 5.0), "困境反转")

    def test_negative_excluded_when_forward_weak(self):
        self.assertEqual(lynch.classify(-20.0, 5.0, 5.0), "负增长(排除)")
        self.assertEqual(lynch.classify(-20.0, None, 5.0), "负增长(排除)")

    def test_uses_forward_when_annual_missing(self):
        self.assertEqual(lynch.classify(None, 25.0, 12.0), "快速增长")

    def test_data_insufficient(self):
        self.assertEqual(lynch.classify(None, None, None), "数据不足")


class TestOverlayFlags(unittest.TestCase):
    def test_acceleration_and_margin_and_debt(self):
        f = {
            "g_profit_q1": 30.0, "g_profit_annual": 20.0,
            "gross_margin": 40.0, "gross_margin_prev": 35.0,
            "cash_quality": 0.5, "debt_ratio": 65.0,
        }
        flags = lynch.overlay_flags(f)
        self.assertTrue(flags["accelerating"])
        self.assertTrue(flags["margin_up"])
        self.assertFalse(flags["cash_healthy"])
        self.assertTrue(flags["debt_warn"])
        self.assertIn("增速加速", flags["notes"])
        self.assertIn("毛利率上升", flags["notes"])
        self.assertIn("现金流质量偏弱", flags["notes"])
        self.assertIn("高负债(>60%)", flags["notes"])

    def test_all_none_no_flags(self):
        flags = lynch.overlay_flags({})
        self.assertIsNone(flags["accelerating"])
        self.assertEqual(flags["notes"], [])


class TestQualityScore(unittest.TestCase):
    def test_high_quality_capped(self):
        f = {"roe": 30.0, "gross_margin": 60.0, "cash_quality": 1.5,
             "g_profit_annual": 40.0}
        flags = {"accelerating": True, "margin_up": True, "debt_warn": False}
        # 30 + 20 + 20 + 10 + 10 + 10 = 100.
        self.assertEqual(lynch.quality_score(f, flags), 100.0)

    def test_debt_penalty_and_floor(self):
        f = {"roe": 0.0, "gross_margin": 0.0, "cash_quality": 0.0}
        flags = {"debt_warn": True}
        # Only penalty -> floored to 0.
        self.assertEqual(lynch.quality_score(f, flags), 0.0)


class TestPegRankingHelpers(unittest.TestCase):
    def test_best_peg_prefers_base(self):
        self.assertEqual(
            portfolio._best_peg({"peg_base": 0.5, "peg_forward": 1.2,
                                 "peg_adjusted": 0.4}), 0.5)

    def test_best_peg_falls_to_forward(self):
        self.assertEqual(
            portfolio._best_peg({"peg_base": None, "peg_forward": 1.2,
                                 "peg_adjusted": 0.4}), 1.2)

    def test_best_peg_none_when_all_missing(self):
        self.assertIsNone(portfolio._best_peg({"peg_base": None}))

    def test_peg_band(self):
        self.assertEqual(portfolio.peg_band(0.5), "极具吸引力")
        self.assertEqual(portfolio.peg_band(1.2), "合理")
        self.assertEqual(portfolio.peg_band(1.8), "略贵")
        self.assertEqual(portfolio.peg_band(3.0), "偏贵")
        self.assertEqual(portfolio.peg_band(None), "-")


def _ranked_frame() -> pd.DataFrame:
    """Six eligible growth stocks + one excluded, with fields buckets need."""
    recs = []
    for i, (code, name, peg, roe, pe, gf, dy, dr, cat) in enumerate([
        ("A01", "甲一", 0.30, 12, 15, 20, 3.0, 40, "快速增长"),
        ("A02", "甲二", 0.45, 18, 18, 40, 2.5, 30, "快速增长"),
        ("A03", "甲三", 0.60, 25, 20, 60, 1.5, 55, "快速增长"),
        ("A04", "甲四", 0.90, 10, 22, 15, 4.5, 20, "稳定增长"),
        ("A05", "甲五", 1.10, 22, 25, 55, 2.0, 65, "困境反转"),
        ("A06", "甲六", 1.30, 15, 28, 30, 3.5, 35, "稳定增长"),
        ("B99", "乙九九", None, 8, 30, -5, 2.0, 45, "负增长(排除)"),
    ]):
        recs.append({
            "code": code, "name": name, "peg_rank_value": peg, "roe": roe,
            "pe_ttm": pe, "pe_percentile": 50, "g_forward": gf,
            "dividend_yield": dy, "debt_ratio": dr, "lynch_category": cat,
            "quality_score": 50 + i,
        })
    return pd.DataFrame(recs)


class TestPortfolio(unittest.TestCase):
    def test_attractive_targets_filter(self):
        df = _ranked_frame()
        att = portfolio.attractive_targets(df)
        self.assertEqual(set(att["code"]), {"A01", "A02", "A03", "A04"})

    def test_build_portfolio_weights_sum_100(self):
        df = _ranked_frame()
        top, buckets = portfolio.build_portfolio(df)
        # Excluded name never enters portfolio.
        self.assertNotIn("B99", set(top["code"]))
        # No duplicates across buckets.
        self.assertTrue(top["code"].is_unique)
        # Weights re-normalise to ~100%.
        self.assertAlmostEqual(top["建议权重%"].sum(), 100.0, delta=0.5)

    def test_core_bucket_picks_lowest_peg(self):
        df = _ranked_frame()
        _, buckets = portfolio.build_portfolio(df)
        self.assertEqual(buckets["核心仓"][0], "A01")

    def test_portfolio_carries_stock_name(self):
        # Stock name must survive into the Top-N table alongside the code.
        df = _ranked_frame()
        top, _ = portfolio.build_portfolio(df)
        self.assertIn("name", top.columns)
        a01 = top[top["code"] == "A01"].iloc[0]
        self.assertEqual(a01["name"], "甲一")


if __name__ == "__main__":
    unittest.main()
