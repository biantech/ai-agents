# PEG-ROIC Agent

基于 AKShare 的 A 股 PEG-ROIC 复合筛选工具。它将 PEG 的增长估值与 ROIC 的资本效率结合，生成 CSV 排名和 Markdown 报告。

## 使用

1. 将 6 位股票代码按行放入 `list/*.txt`。
2. 运行 `python3 run_analysis.py`，每个列表文件独立生成报告。
3. 运行 `python3 run_analysis.py 3` 分析合并股票池的前 3 只。
4. 运行 `python3 run_analysis.py --top 20` 生成 Top 20 候选，也可使用 `--top 30`。
5. 运行 `python3 run_analysis.py 50 --top 20` 分析前 50 只股票并输出 Top 20。
6. 运行 `python3 run_analysis.py --test` 执行离线单元测试。

Python 依赖：`akshare`、`pandas`、`numpy`。

## Top N 设置

默认候选数量在 `agent/config.py` 中设置：

```python
TOP_N = 10
```

如果希望默认生成 Top 20，可以修改为：

```python
TOP_N = 20
```

更推荐在运行时使用 `--top` 临时指定，无需修改代码：

```bash
python3 run_analysis.py --top 20
python3 run_analysis.py --top 30
```

`--top` 的优先级高于 `agent/config.py` 中的 `TOP_N`。未传入 `--top` 时，才使用 `TOP_N` 的默认值。

## 核心规则

- PEG 优先使用券商一致预期增速，缺失时使用年度归母净利润增速。
- ROIC 使用 NOPAT 和平均投入资本计算。资产负债表字段不完整时保留缺失值，不做伪精确估算。
- 统一使用 8% WACC 作为横向初筛假设。
- 优选条件：`PEG < 1` 且 `ROIC - WACC >= 4%`。
