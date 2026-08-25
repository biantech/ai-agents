from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

from agent import pipeline


class TestCheckpointResume(unittest.TestCase):
    @mock.patch("agent.pipeline.time.sleep")
    @mock.patch("agent.pipeline.ds.get_industry_map", return_value={})
    @mock.patch("agent.pipeline.ds.get_name_map", return_value={})
    def test_resume_skips_completed_stocks(self, get_names, get_industries, sleep):
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = os.path.join(directory, "analysis.pkl")
            with mock.patch("agent.pipeline.analyze_one",
                            side_effect=[{"code": "000001", "pe_ttm": 10.0},
                                         KeyboardInterrupt()]):
                with self.assertRaises(KeyboardInterrupt):
                    pipeline.analyze_all(["000001", "000002"], checkpoint_path=checkpoint)

            with mock.patch("agent.pipeline.analyze_one",
                            return_value={"code": "000002", "pe_ttm": 20.0}) as analyze:
                result = pipeline.analyze_all(
                    ["000001", "000002"], checkpoint_path=checkpoint)

            analyze.assert_called_once_with("000002", "", "")
            self.assertEqual(result["code"].tolist(), ["000001", "000002"])
            self.assertEqual(result["pe_ttm"].tolist(), [10.0, 20.0])

    @mock.patch("agent.pipeline.time.sleep")
    @mock.patch("agent.pipeline.ds.get_industry_map", return_value={})
    @mock.patch("agent.pipeline.ds.get_name_map", return_value={})
    @mock.patch("agent.pipeline.analyze_one", return_value={"code": "000002"})
    def test_failed_stock_is_retried_after_interruption(
            self, analyze, get_names, get_industries, sleep):
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = os.path.join(directory, "analysis.pkl")
            pipeline._save_checkpoint(
                checkpoint, [{"code": "000001"}])

            result = pipeline.analyze_all(
                ["000001", "000002"], checkpoint_path=checkpoint)

            analyze.assert_called_once_with("000002", "", "")
            self.assertEqual(result["code"].tolist(), ["000001", "000002"])


if __name__ == "__main__":
    unittest.main()
