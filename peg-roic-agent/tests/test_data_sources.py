from __future__ import annotations

import csv
import os
import tempfile
import unittest
from unittest import mock

import pandas as pd

from agent import data_sources


class TestStockLists(unittest.TestCase):
    def test_csv_uses_fifth_column(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "stocks.csv")
            with open(path, "w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["000001", "", "", "", "code"])
                writer.writerow(["", "", "", "", "000011"])
                writer.writerow(["", "", "", "", "000014"])

            self.assertEqual(data_sources._codes_from(path), ["000011", "000014"])

    @mock.patch("agent.data_sources.pd.read_excel")
    def test_xls_uses_fifth_column(self, read_excel):
        read_excel.return_value = pd.DataFrame(["code", "000011", "000014"])

        self.assertEqual(data_sources._codes_from("stocks.xls"), ["000011", "000014"])
        read_excel.assert_called_once_with(
            "stocks.xls", usecols=[4], header=None, dtype=str)

    def test_python_files_are_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            with open(os.path.join(directory, "stocks.py"), "w", encoding="utf-8") as handle:
                handle.write("000011\n")
            with open(os.path.join(directory, "stocks.txt"), "w", encoding="utf-8") as handle:
                handle.write("000014\n")

            with mock.patch("agent.data_sources.config.LIST_DIR", directory):
                self.assertEqual(data_sources.get_codes_by_file(), [("stocks", ["000014"])])

    def test_single_file_is_read_from_list_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "stocks.txt")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("000014\n")

            with mock.patch("agent.data_sources.config.LIST_DIR", directory):
                self.assertEqual(data_sources.get_codes_from_file("stocks.txt"), ["000014"])
                self.assertEqual(data_sources.get_codes_from_file(path), ["000014"])
                self.assertEqual(data_sources.get_codes_from_file("stocks.py"), [])
                self.assertEqual(data_sources.get_codes_from_file("../stocks.txt"), [])


if __name__ == "__main__":
    unittest.main()
