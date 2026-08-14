# 股票投资价值分析报告生成器

本项目按照 `analysis-framework.md` 的九个章节，为 `list` 文件或 `list/` 目录中的每个六位 A 股代码生成一份 Markdown 报告。数据接口采用 AKShare，参考 `peg-roic-agent` 的缓存、重试和逐只处理方式。

## 使用

```bash
python3 -m pip install -r requirements.txt
python3 run_analysis.py
```

报告输出到 `output/`，缓存保存到 `cache/`。当前仓库的 `list` 是带 BOM/CRLF 的单文件，首行表头会自动跳过；也支持将多个 `.txt` 文件放入 `list/` 目录。

无网络或只想检查报告版式时：

```bash
python3 run_analysis.py --offline --limit 2
```

所有缺少或无法验证的数据会显示为“数据缺失”，不会用猜测值填充。报告中的行业、股权结构、重大事件、现金流明细、DCF 和风险事项仍应结合年报、公告及交易所披露人工复核。

## 验证

```bash
python3 -m unittest discover -s tests -v
```
