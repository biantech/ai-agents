import tempfile
import unittest
from pathlib import Path
from agent.data_sources import read_codes

class TestReadCodes(unittest.TestCase):
    def test_bom_header_and_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "list.txt"
            path.write_text("\ufeff信息\n001229\n001229\n002106,foo\ninvalid\n", encoding="utf-8")
            self.assertEqual(read_codes(str(path)), ["001229", "002106"])
