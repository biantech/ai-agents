# PEG-ROIC Agent

基于 AKShare 的 A 股 PEG-ROIC 复合筛选工具。它将 PEG 的增长估值与 ROIC 的资本效率结合，生成 CSV 排名和 Markdown 报告。

## 使用

1. 将 6 位股票代码按行放入 `list/*.txt`；`list/*.csv` 和 `list/*.xls` 从第 5 列读取代码，`list/*.py` 不参与分析。
2. 运行 `python3 run_analysis.py`，每个列表文件独立生成报告。
3. 运行 `python3 run_analysis.py --file 2000cons.xls` 或 `python3 run_analysis.py --file list/2000cons.xls`，仅分析指定文件。
4. 运行 `python3 run_analysis.py 3` 分析合并股票池的前 3 只。
5. 运行 `python3 run_analysis.py --top 20` 生成 Top 20 候选，也可使用 `--top 30`。
6. 运行 `python3 run_analysis.py 50 --top 20` 分析前 50 只股票并输出 Top 20。
7. 长列表分析支持自动断点续跑。进程中断后，重新运行相同命令即可跳过已完成股票。
8. 如需丢弃进度并从头分析，增加 `--restart`，例如 `python3 run_analysis.py --file 2000cons.xls --restart`。
9. 运行 `python3 run_analysis.py --test` 执行离线单元测试。

断点记录保存在 `cache/` 目录，每只股票成功完成后立即更新。只有 CSV 和 Markdown 报告全部生成成功后，断点记录才会删除；失败股票不会被标记为完成，下一次运行会重试。

删除文件时请注意：

- 删除 `cache/analysis_*.checkpoint.pkl` 会清除该任务的分析进度，下次运行将从头分析。
- 删除 `cache/analysis_*.checkpoint.pkl.tmp` 通常不会影响续跑，它只是原子写入时的临时文件。
- 删除 `cache/` 中其他接口缓存只会导致数据重新请求，不会清除分析进度。
- 删除 `output/` 下的报告不会清除检查点，下次运行会继续分析并重新生成报告。

如需彻底重新开始，推荐使用 `--restart`，例如：

```bash
python3 run_analysis.py --file 2000cons.xls --restart
```

Python 依赖：`akshare`、`pandas`、`numpy`、`xlrd`。

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
