from __future__ import annotations

import unittest

from agent import scoring


class TestScoring(unittest.TestCase):
    def test_forward_peg_is_preferred(self):
        self.assertEqual(scoring.best_peg({"peg_forward": 0.8, "peg_trailing": 0.5}), 0.8)

    def test_preferred_requires_cheap_growth_and_value_creation(self):
        result = scoring.evaluate({
            "peg_forward": 0.8, "roic": 15.0, "cash_quality": 1.0,
            "debt_ratio": 30.0,
        })
        self.assertEqual(result["roic_wacc_spread"], 7.0)
        self.assertEqual(result["grade"], "优选")

    def test_roic_below_wacc_is_not_value_creating(self):
        result = scoring.evaluate({"peg_forward": 0.5, "roic": 6.0})
        self.assertEqual(result["grade"], "未创造超额回报")

    def test_missing_roic_is_data_insufficient(self):
        result = scoring.evaluate({"peg_forward": 0.5, "roic": None})
        self.assertEqual(result["grade"], "数据不足")

    def test_ranking_orders_by_composite_score(self):
        frame = scoring.build_ranking([
            {"code": "A", "peg_forward": 1.4, "roic": 10.0},
            {"code": "B", "peg_forward": 0.7, "roic": 20.0},
        ])
        self.assertEqual(frame.iloc[0]["code"], "B")
        self.assertEqual(frame.iloc[0]["排名"], 1)

    def test_top_targets_uses_requested_limit(self):
        ranking = scoring.build_ranking([
            {"code": str(index), "peg_forward": 1.2, "roic": 12.0}
            for index in range(30)
        ])
        self.assertEqual(len(scoring.top_targets(ranking, 20)), 20)
        self.assertEqual(len(scoring.top_targets(ranking, 30)), 30)


if __name__ == "__main__":
    unittest.main()
