from __future__ import annotations

import os
import pickle
import tempfile
import unittest
from unittest import mock

from agent import pipeline


class TestAnalyzeAll(unittest.TestCase):
    @mock.patch("agent.pipeline.time.sleep")
    @mock.patch("agent.pipeline.analyze_one")
    @mock.patch("agent.pipeline.ds.get_industry_map", return_value={})
    @mock.patch("agent.pipeline.ds.get_name_map")
    def test_complete_provided_names_skip_name_lookup(
            self, get_name_map, _get_industry_map, analyze_one, _sleep):
        analyze_one.side_effect = lambda code, name, industry: {
            "code": code, "name": name,
        }

        result = pipeline.analyze_all(
            ["000011", "000014"], verbose=False,
            provided_names={"000011": "深物业A", "000014": "沙河股份"},
        )

        get_name_map.assert_not_called()
        self.assertEqual(result["name"].tolist(), ["深物业A", "沙河股份"])

    @mock.patch("agent.pipeline.time.sleep")
    @mock.patch("agent.pipeline.analyze_one")
    @mock.patch("agent.pipeline.ds.get_industry_map", return_value={})
    @mock.patch("agent.pipeline.ds.get_name_map")
    def test_missing_name_uses_lookup_without_overwriting_provided_name(
            self, get_name_map, _get_industry_map, analyze_one, _sleep):
        get_name_map.return_value = {"000011": "远程名称", "000014": "沙河股份"}
        analyze_one.side_effect = lambda code, name, industry: {
            "code": code, "name": name,
        }

        result = pipeline.analyze_all(
            ["000011", "000014"], verbose=False,
            provided_names={"000011": "本地名称"},
        )

        get_name_map.assert_called_once_with()
        self.assertEqual(result["name"].tolist(), ["本地名称", "沙河股份"])

    @mock.patch("agent.pipeline.time.sleep")
    @mock.patch("agent.pipeline.analyze_one")
    @mock.patch("agent.pipeline.ds.get_industry_map", return_value={})
    @mock.patch("agent.pipeline.ds.get_name_map", return_value={})
    def test_checkpoint_resumes_completed_stocks(
            self, get_name_map, _get_industry_map, analyze_one, _sleep):
        analyze_one.side_effect = lambda code, name, industry: {
            "code": code, "name": name,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "analysis.checkpoint.pkl")
            pipeline._save_checkpoint(path, [{"code": "000011", "name": "已完成"}])

            result = pipeline.analyze_all(
                ["000011", "000014"], verbose=False, checkpoint_path=path,
            )

        analyze_one.assert_called_once_with("000014", "", "")
        get_name_map.assert_called_once_with()
        self.assertEqual(result["code"].tolist(), ["000011", "000014"])

    @mock.patch("agent.pipeline.ds.get_industry_map")
    @mock.patch("agent.pipeline.ds.get_name_map")
    def test_complete_checkpoint_skips_lookup_apis(
            self, get_name_map, get_industry_map):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "analysis.checkpoint.pkl")
            pipeline._save_checkpoint(path, [{"code": "000011", "name": "已完成"}])

            result = pipeline.analyze_all(
                ["000011"], verbose=False, checkpoint_path=path,
            )

        get_name_map.assert_not_called()
        get_industry_map.assert_not_called()
        self.assertEqual(result["name"].tolist(), ["已完成"])

    @mock.patch("agent.pipeline.time.sleep")
    @mock.patch("agent.pipeline.ds.get_industry_map", return_value={})
    @mock.patch("agent.pipeline.ds.get_name_map", return_value={})
    def test_interruption_keeps_completed_progress(
            self, _get_name_map, _get_industry_map, _sleep):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "analysis.checkpoint.pkl")
            with mock.patch(
                    "agent.pipeline.analyze_one",
                    side_effect=[{"code": "000011", "name": ""}, KeyboardInterrupt],
            ):
                with self.assertRaises(KeyboardInterrupt):
                    pipeline.analyze_all(
                        ["000011", "000014"], verbose=False,
                        checkpoint_path=path,
                    )

            with open(path, "rb") as handle:
                records = pickle.load(handle)

        self.assertEqual(records, [{"code": "000011", "name": ""}])


if __name__ == "__main__":
    unittest.main()
