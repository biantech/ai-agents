import unittest
from agent.report import build_markdown

class TestReport(unittest.TestCase):
    def test_framework_sections_exist(self):
        text = build_markdown({"code": "001229", "name": "测试"})
        for title in ("1. 公司基本面概述", "2. 行业与竞争格局分析", "3. 财务分析", "4. 估值分析", "7. 投资结论与建议", "9. 分析原则"):
            self.assertIn(title, text)
