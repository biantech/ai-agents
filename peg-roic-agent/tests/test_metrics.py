from __future__ import annotations

import unittest

import pandas as pd

from agent import metrics


class TestPeg(unittest.TestCase):
    def test_trailing_and_forward(self):
        result = metrics.compute_peg(20.0, 25.0, 40.0)
        self.assertEqual(result["peg_trailing"], 0.8)
        self.assertEqual(result["peg_forward"], 0.5)

    def test_invalid_inputs_are_missing(self):
        result = metrics.compute_peg(20.0, -1.0, None)
        self.assertIsNone(result["peg_trailing"])
        self.assertIsNone(result["peg_forward"])


def balance_rows() -> pd.DataFrame:
    return pd.DataFrame([
        {"REPORT_DATE": "2025-12-31", "TOTAL_EQUITY": 1000,
         "MONETARYFUNDS": 200, "SHORT_LOAN": 200, "LONG_LOAN": 100},
        {"REPORT_DATE": "2024-12-31", "TOTAL_EQUITY": 900,
         "MONETARYFUNDS": 150, "SHORT_LOAN": 180, "LONG_LOAN": 70},
        {"REPORT_DATE": "2023-12-31", "TOTAL_EQUITY": 800,
         "MONETARYFUNDS": 100, "SHORT_LOAN": 150, "LONG_LOAN": 50},
    ])


def profit_rows() -> pd.DataFrame:
    return pd.DataFrame([
        {"REPORT_DATE": "2025-12-31", "TOTAL_PROFIT": 120,
         "FE_INTEREST_EXPENSE": 10, "INCOME_TAX": 30},
        {"REPORT_DATE": "2024-12-31", "TOTAL_PROFIT": 100,
         "FE_INTEREST_EXPENSE": 8, "INCOME_TAX": 20},
    ])


class TestRoic(unittest.TestCase):
    def test_uses_nopat_and_average_invested_capital(self):
        result = metrics.compute_roic(balance_rows(), profit_rows())
        # Capital: 2025=1100, 2024=1000; EBIT=130; tax rate=25%; NOPAT=97.5.
        self.assertEqual(result["invested_capital"], 1050.0)
        self.assertEqual(result["nopat"], 97.5)
        self.assertEqual(result["roic"], 9.29)
        self.assertTrue(result["roic_data_complete"])
        self.assertIsNotNone(result["roic_previous"])

    def test_missing_cash_does_not_invent_roic(self):
        balance = balance_rows().drop(columns=["MONETARYFUNDS"])
        result = metrics.compute_roic(balance, profit_rows())
        self.assertIsNone(result["roic"])
        self.assertFalse(result["roic_data_complete"])

    def test_non_positive_invested_capital_is_rejected(self):
        balance = balance_rows()
        balance["MONETARYFUNDS"] = 5000
        self.assertIsNone(metrics.compute_roic(balance, profit_rows())["roic"])

    def test_tax_rate_is_capped(self):
        profit = profit_rows()
        profit.loc[0, "INCOME_TAX"] = 1000
        result = metrics.compute_roic(balance_rows(), profit)
        # Tax capped at 35%: EBIT 130 * 65% = 84.5.
        self.assertEqual(result["nopat"], 84.5)

    def test_statement_years_are_matched_instead_of_row_positions(self):
        balance = balance_rows()
        profit = profit_rows()
        profit.loc[0, "REPORT_DATE"] = "2026-12-31"
        result = metrics.compute_roic(balance, profit)
        # 2026 cannot be paired; latest valid calculation is 2024 with 2023 capital.
        self.assertEqual(result["roic"], 9.09)


if __name__ == "__main__":
    unittest.main()
