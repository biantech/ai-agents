from __future__ import annotations

import unittest
from unittest import mock

import run_analysis


class TestArguments(unittest.TestCase):
    def test_file_argument(self):
        args = run_analysis.parse_args(
            ["--file", "stocks.csv", "--top", "20", "--restart"])

        self.assertEqual(args.file, "stocks.csv")
        self.assertEqual(args.top, 20)
        self.assertTrue(args.restart)

    def test_file_and_limit_are_mutually_exclusive(self):
        with self.assertRaises(SystemExit):
            run_analysis.parse_args(["10", "--file", "stocks.csv"])

    @mock.patch("run_analysis.analyze_and_report")
    @mock.patch("run_analysis.data_sources.get_codes_from_file")
    @mock.patch("run_analysis.config.ensure_dirs")
    def test_main_analyzes_only_requested_file(self, ensure_dirs, get_codes, analyze):
        get_codes.return_value = ["000011", "000014"]

        with mock.patch("sys.argv", ["run_analysis.py", "--file", "list/stocks.csv"]):
            run_analysis.main()

        ensure_dirs.assert_called_once_with()
        get_codes.assert_called_once_with("list/stocks.csv")
        analyze.assert_called_once_with(
            ["000011", "000014"], "stocks_", run_analysis.config.TOP_N, False)

    @mock.patch("run_analysis.report.save_markdown", side_effect=OSError("disk full"))
    @mock.patch("run_analysis.report.save_csv")
    @mock.patch("run_analysis.scoring.top_targets")
    @mock.patch("run_analysis.scoring.preferred_targets")
    @mock.patch("run_analysis.scoring.build_ranking")
    @mock.patch("run_analysis.pipeline.analyze_all")
    @mock.patch("run_analysis.pipeline.clear_checkpoint")
    def test_report_failure_keeps_checkpoint(
            self, clear_checkpoint, analyze_all, build_ranking, preferred_targets,
            top_targets, save_csv, save_markdown):
        with self.assertRaises(OSError):
            run_analysis.analyze_and_report(["000001"])

        clear_checkpoint.assert_not_called()


if __name__ == "__main__":
    unittest.main()
