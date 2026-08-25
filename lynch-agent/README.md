# Lynch Agent

基于 AKShare 的彼得·林奇式 A 股 PEG 基本面分析工具。程序读取 `list/`
目录中的股票列表，计算估值、增长、财务质量和 PEG 指标，并在 `output/`
目录生成 CSV 排名及 Markdown 报告。

## 环境准备

建议使用 Python 3.10 或更高版本。主要依赖如下：

```bash
python3 -m pip install akshare pandas numpy xlrd
```

其中 `xlrd` 用于读取旧版 `.xls` 文件。

## 股票列表格式

输入文件放在 `list/` 目录中。

| 文件格式 | 股票代码 | 股票名称 | 说明 |
| --- | --- | --- | --- |
| `.csv` | 第 5 列 | 第 6 列 | 名称可为空 |
| `.xls` | 第 5 列 | 第 6 列 | 名称可为空 |
| `.txt` | 第 1 列 | 第 2 列 | 也支持每行只有一个 6 位代码 |
| `.py` | 不读取 | 不读取 | 自动忽略，不参与分析 |

股票代码必须是 6 位数字。重复代码会按首次出现顺序去重；如果文件中已经提供
名称，分析时直接使用该名称。只有存在名称为空的股票时，程序才会调用名称查询
接口补全缺失名称，文件中已有的名称不会被覆盖。

## 使用方法

分析 `list/` 中的所有有效文件，每个文件独立生成一套报告：

```bash
python3 run_analysis.py
```

只分析指定文件。文件名和 `list/文件名` 两种写法都支持：

```bash
python3 run_analysis.py stocks.csv
python3 run_analysis.py list/stocks.csv
python3 run_analysis.py stocks.xls
```

合并所有列表并只分析前 5 只股票，可用于快速检查：

```bash
python3 run_analysis.py 5
```

运行单元测试：

```bash
python3 run_analysis.py --test
```

查看完整命令帮助：

```bash
python3 run_analysis.py --help
```

## 输出文件

报告保存在 `output/` 目录。分析单个 `stocks.csv` 时，文件名会带有
`stocks_` 前缀，例如：

- `stocks_PEG排名表_全样本.csv`
- `stocks_PEG小于1_吸引标的.csv`
- `stocks_Top10组合配置.csv`
- `stocks_林奇PEG分析报告.md`

当筛选结果为空时，对应的“PEG 小于 1”或“Top10”CSV 可能不会生成。

## 中断后继续分析

程序支持自动断点续跑。每只股票成功分析后，进度会立即以原子方式保存到：

```text
cache/analysis_<任务标识>.checkpoint.pkl
```

如果程序被终止，重新执行完全相同的命令即可。程序会读取 checkpoint，跳过已经
完成的股票，并从剩余股票继续。所有报告成功生成后，当前任务的 checkpoint 会
自动删除。

例如分析过程中中断：

```bash
python3 run_analysis.py list/stocks.xls
```

再次执行同一命令即可续跑：

```bash
python3 run_analysis.py list/stocks.xls
```

任务标识由输出前缀和股票代码顺序生成。修改列表中的代码或代码顺序后，会被视为
一个新任务并从头分析。

## 强制重新开始

推荐使用 `--restart` 清除当前命令对应的 checkpoint 并从头分析：

```bash
python3 run_analysis.py stocks.xls --restart
python3 run_analysis.py list/stocks.csv --restart
python3 run_analysis.py 5 --restart
```

`--restart` 只清除当前分析任务的进度，不会删除 AKShare 接口数据缓存。

## 删除临时文件的影响

| 删除内容 | 是否从头分析 | 影响 |
| --- | --- | --- |
| `cache/analysis_*.checkpoint.pkl` | 是 | 对应任务的已完成进度丢失，下次运行从第一只股票开始 |
| 整个 `cache/` 目录中的全部文件 | 是 | 同时删除分析进度和接口缓存，下次运行会从头分析并重新请求数据 |
| `cache/analysis_*.checkpoint.pkl.tmp` | 否 | checkpoint 原子写入的残留临时文件，程序不会读取它 |
| `cache/` 中其他 `.pkl` 文件 | 否 | 这些是 AKShare 接口缓存，删除后相关数据会重新请求 |
| `output/` 中的 CSV 或 Markdown | 通常否 | 不会清除尚存的 checkpoint；续跑完成后会重新生成报告 |
| `__pycache__/` 或 `.pyc` 文件 | 否 | 仅 Python 字节码缓存，不影响分析进度和数据缓存 |

需要注意：完整任务成功后 checkpoint 会自动删除。因此，即使保留 `output/`
报告，再次执行相同命令也会开始一次新的完整分析。删除输出报告本身不会创建或
恢复 checkpoint。

手动清理时，如果只想重新分析某一个任务，优先使用 `--restart`，不要删除整个
`cache/` 目录。

## 常用配置

分析参数集中在 `agent/config.py`，包括：

- `CACHE_TTL`：接口数据缓存有效期，默认 1 天。
- `MAX_RETRY`：单个接口最大重试次数。
- `RETRY_BACKOFF`：接口重试等待时间。
- `REQUEST_SLEEP`：每只股票分析后的请求间隔。
- `PRICE_SOURCE`：近期价格的首选数据源。
- `TOP_N`：最终组合数量，默认 10。

## 免责声明

本工具输出仅用于量化研究和辅助分析，不构成任何投资建议。数据可能因接口延迟、
字段缺失或数据源调整而不完整，使用前应结合原始公告和其他可靠来源复核。
