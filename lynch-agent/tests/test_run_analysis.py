from __future__ import annotations

import unittest
from unittest import mock

import run_analysis


class TestArguments(unittest.TestCase):
    def test_file_argument(self):
        args = run_analysis.parse_args(["list/stocks.csv"])

        self.assertEqual(args.target, "list/stocks.csv")
        self.assertFalse(args.restart)

    def test_restart_argument(self):
        args = run_analysis.parse_args(["stocks.csv", "--restart"])

        self.assertEqual(args.target, "stocks.csv")
        self.assertTrue(args.restart)

    @mock.patch("run_analysis._analyze_and_report")
    @mock.patch("run_analysis.ds.get_stocks_from_file")
    @mock.patch("run_analysis.config.ensure_dirs")
    def test_main_analyzes_only_requested_file(self, ensure_dirs, get_stocks, analyze):
        get_stocks.return_value = [("000011", "深物业A"), ("000014", "沙河股份")]

        with mock.patch("sys.argv", ["run_analysis.py", "list/stocks.csv"]):
            run_analysis.main()

        ensure_dirs.assert_called_once_with()
        get_stocks.assert_called_once_with("list/stocks.csv")
        analyze.assert_called_once_with(
            ["000011", "000014"], prefix="stocks_",
            provided_names={"000011": "深物业A", "000014": "沙河股份"},
            restart=False,
        )


if __name__ == "__main__":
    unittest.main()
