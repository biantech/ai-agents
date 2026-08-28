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

## Top N 如何排序并写入报告

程序先对全部已完成分析的股票计算复合分，再按以下步骤生成 Top N：

1. 只保留结论为“优选”或“观察”的股票；“数据不足”“未创造超额回报”“估值偏高”不会进入候选池。
2. 候选按 `composite_score` 从高到低排序。
3. 复合分相同时，先按 `roic_wacc_spread`（ROIC-WACC）从高到低，再按 `peg_rank_value`（PEG）从低到高；缺失值排在最后。
4. 排序完成后取前 `N` 条（`N` 由 `--top N` 或 `agent/config.py` 的 `TOP_N` 决定）。候选不足 N 条时，报告只写入实际候选数量。

完整排序结果写入 `*PEG-ROIC排名_全样本.csv`，筛选后的优选池写入 `*PEG-ROIC优选池.csv`，最终 Top N 写入 `*PEG-ROIC_TopN.csv`，三者的 Markdown 汇总同时写入 `*PEG-ROIC复合分析报告.md`。报告第三节“Top N 候选”就是最终截取的记录，并保留排名、PEG、ROIC、现金流质量、负债率和复合分等字段。

## 复合分如何计算

复合分满分 100 分，先分别计算五项分数，再相加并四舍五入到 1 位小数：

| 项目 | 满分 | 计算方式 |
| --- | ---: | --- |
| PEG | 40 | `min(40, 40 / max(PEG, 1))`；PEG 缺失或非正数记 0 分，PEG 越低分越高，PEG 不高于 1 时该项为 40 分 |
| ROIC | 25 | `clip(ROIC, 0, 20) / 20 * 25`；缺失记 0 分 |
| ROIC-WACC | 15 | `clip(ROIC - WACC, 0, 12) / 12 * 15`；WACC 默认 8%，缺失或低于 WACC 的部分记 0 分 |
| 现金流质量 | 10 | `clip(现金流/净利润, 0, 1.2) / 1.2 * 10`；缺失记 0 分 |
| 负债约束 | 10 | `max(0, 1 - 负债率/100) * 10`；负债率越低分越高，缺失记 0 分 |

其中 `clip(x, low, high)` 表示把数值限制在上下限内。PEG 优先使用前瞻 PEG，缺失时使用历史 PEG；ROIC 需要完整的资产负债表和利润表字段，无法可靠计算时保留缺失，不做估算。

## 如何调整增长和价值权重

权重目前集中写在 `agent/scoring.py` 的 `evaluate()` 中，默认分配为：PEG 40、ROIC 25、ROIC-WACC 15、现金流质量 10、负债约束 10。修改后应保持总分仍为 100，并同步检查报告中的权重说明。

- **增长/估值侧更重要**：提高 PEG 的 40 分上限，例如改为 PEG 50；可从现金流质量和负债约束各减少 5 分，形成 `50/25/15/5/5`。PEG 越低代表相对增长的估值越便宜，因此该调整会更明显地拉开低 PEG 股票的排名。
- **价值/资本效率侧更重要**：提高 ROIC 与 ROIC-WACC 两项，例如改为 `PEG 30、ROIC 30、ROIC-WACC 20、现金流质量 10、负债约束 10`。这样高 ROIC、且明显高于 WACC 的股票会获得更大排序优势。

调整权重后，重新运行分析即可生成新的全样本排名和 Top N；已有 CSV 若只需按原复合分重新截取，可使用 `rerank_results.py`，但它不会重新计算权重或财务数据。

## 已有结果重新排序

已有 Top CSV 可以直接重新排序和截取，不会重新获取或计算财务数据：

```bash
python3 rerank_results.py output/2000cons_PEG-ROIC_Top50.csv --top 30
```

默认输出为同目录下的 `2000cons_PEG-ROIC_Top30.csv`。也可以指定输出路径：

```bash
python3 rerank_results.py output/2000cons_PEG-ROIC_Top50.csv --top 20 \
  --output output/my_top20.csv
```

## 核心规则

- PEG 优先使用券商一致预期增速，缺失时使用年度归母净利润增速。
- ROIC 使用 NOPAT 和平均投入资本计算。资产负债表字段不完整时保留缺失值，不做伪精确估算。
- 统一使用 8% WACC 作为横向初筛假设。
- 优选条件：`PEG < 1` 且 `ROIC - WACC >= 4%`。
