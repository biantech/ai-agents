from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

import rerank_results


class TestRerankResults(unittest.TestCase):
    def test_reranks_existing_csv_and_preserves_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "sample_Top50.csv"
            pd.DataFrame([
                {"排名": 1, "code": "000001", "composite_score": 90,
                 "roic_wacc_spread": 12, "peg_rank_value": 1.2},
                {"排名": 2, "code": "000002", "composite_score": 91,
                 "roic_wacc_spread": 8, "peg_rank_value": 0.9},
                {"排名": 3, "code": "000003", "composite_score": 90,
                 "roic_wacc_spread": 12, "peg_rank_value": 0.8},
            ]).to_csv(source, index=False, encoding="utf-8-sig")

            target = rerank_results.rerank_results(source, 2)
            result = pd.read_csv(target, dtype={"code": str})

            self.assertEqual(target.name, "sample_Top2.csv")
            self.assertEqual(result["code"].tolist(), ["000002", "000003"])
            self.assertEqual(result["排名"].tolist(), [1, 2])

    def test_rejects_missing_sort_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "sample.csv"
            pd.DataFrame([{"code": "000001"}]).to_csv(source, index=False)

            with self.assertRaisesRegex(ValueError, "Missing required columns"):
                rerank_results.rerank_results(source, 1)


if __name__ == "__main__":
    unittest.main()
