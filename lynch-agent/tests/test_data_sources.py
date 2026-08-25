from __future__ import annotations

import csv
import os
import tempfile
import unittest
from unittest import mock

import pandas as pd

from agent import data_sources


class TestStockLists(unittest.TestCase):
    def test_csv_uses_fifth_column_and_sixth_column_name(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "stocks.csv")
            with open(path, "w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["000001", "", "", "", "code", "name"])
                writer.writerow(["", "", "", "", "000011", "深物业A"])
                writer.writerow(["", "", "", "", "000014", "沙河股份"])

            self.assertEqual(data_sources._codes_from(path), ["000011", "000014"])
            self.assertEqual(
                data_sources._stocks_from(path),
                [("000011", "深物业A"), ("000014", "沙河股份")],
            )

    @mock.patch("agent.data_sources.pd.read_excel")
    def test_xls_uses_fifth_column_and_sixth_column_name(self, read_excel):
        read_excel.return_value = pd.DataFrame([
            ["code", "name"],
            ["000011", "深物业A"],
            ["000014", "沙河股份"],
        ])

        self.assertEqual(data_sources._codes_from("stocks.xls"), ["000011", "000014"])
        self.assertEqual(
            data_sources._stocks_from("stocks.xls"),
            [("000011", "深物业A"), ("000014", "沙河股份")],
        )
        read_excel.assert_called_with(
            "stocks.xls", usecols=[4, 5], header=None, dtype=str,
        )

    def test_txt_reads_code_and_name(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "stocks.txt")
            with open(path, "w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["代码", "名称"])
                writer.writerow(["000011", "深物业A"])
                writer.writerow(["000014", "沙河股份"])

            self.assertEqual(
                data_sources._stocks_from(path),
                [("000011", "深物业A"), ("000014", "沙河股份")],
            )

    def test_python_files_are_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            with open(os.path.join(directory, "stocks.py"), "w", encoding="utf-8") as handle:
                handle.write("000011\n")
            with open(os.path.join(directory, "stocks.txt"), "w", encoding="utf-8") as handle:
                handle.write("000014\n")

            with mock.patch("agent.data_sources.config.LIST_DIR", directory):
                self.assertEqual(data_sources.get_codes_by_file(), [("stocks", ["000014"])])

    def test_single_file_accepts_name_and_list_path(self):
        with tempfile.TemporaryDirectory() as base_dir:
            list_dir = os.path.join(base_dir, "list")
            os.mkdir(list_dir)
            path = os.path.join(list_dir, "stocks.txt")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("000014\n")

            with mock.patch("agent.data_sources.config.BASE_DIR", base_dir), \
                    mock.patch("agent.data_sources.config.LIST_DIR", list_dir):
                self.assertEqual(data_sources.get_codes_from_file("stocks.txt"), ["000014"])
                self.assertEqual(data_sources.get_codes_from_file("list/stocks.txt"), ["000014"])
                self.assertEqual(data_sources.get_codes_from_file("../stocks.txt"), [])


if __name__ == "__main__":
    unittest.main()
