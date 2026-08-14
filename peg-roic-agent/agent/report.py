"""CSV and Markdown output for PEG-ROIC analysis."""
from __future__ import annotations

import os
from datetime import datetime

import pandas as pd

from . import config


RANK_COLUMNS = [
    ("排名", "排名"), ("code", "代码"), ("name", "名称"), ("industry", "行业"),
    ("pe_ttm", "PE(TTM)"), ("growth_trailing", "历史增速%"),
    ("growth_forward", "前瞻增速%"), ("peg_rank_value", "排名PEG"),
    ("roic", "ROIC%"), ("roic_wacc_spread", "ROIC-WACC%"),
    ("cash_quality", "现金流/净利润"), ("debt_ratio", "负债率%"),
    ("composite_score", "复合分"), ("grade", "结论"),
]


def _fmt(value, digits=2):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "-"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (int,)):
        return str(value)
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _table(frame: pd.DataFrame, columns=RANK_COLUMNS) -> list[str]:
    lines = ["| " + " | ".join(label for _, label in columns) + " |",
             "| " + " | ".join("---" for _ in columns) + " |"]
    for _, row in frame.iterrows():
        lines.append("| " + " | ".join(_fmt(row.get(key), 3 if "peg" in key else 2)
                                         for key, _ in columns) + " |")
    return lines


def save_csv(frame: pd.DataFrame, filename: str) -> str:
    path = os.path.join(config.OUTPUT_DIR, filename)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def build_markdown(ranking: pd.DataFrame, preferred: pd.DataFrame,
                   top: pd.DataFrame, top_n: int = config.TOP_N) -> str:
    complete = int(ranking.get("roic_data_complete", pd.Series(dtype=bool)).fillna(False).sum())
    lines = ["# PEG-ROIC 复合分析报告", "",
             f"> 生成时间：{datetime.now():%Y-%m-%d %H:%M} | 样本：{len(ranking)} | "
             f"ROIC数据完整：{complete}/{len(ranking)} | WACC假设：{config.DEFAULT_WACC:.1f}%", ""]

    lines += ["## 一、复合排名", ""]
    lines += _table(ranking) if not ranking.empty else ["_无可用数据。_"]

    lines += ["", f"## 二、优选池（{len(preferred)} 只）", ""]
    lines += _table(preferred) if not preferred.empty else ["_无同时满足 PEG < 1 且 ROIC-WACC >= 4% 的标的。_"]

    lines += ["", f"## 三、Top {top_n} 候选", ""]
    lines += _table(top) if not top.empty else ["_无数据完整的优选或观察标的。_"]

    lines += ["", "## 四、方法和口径", "",
              "- PEG 优先采用券商一致预期增速，缺失时使用最新年度归母净利润增速。",
              "- NOPAT = (利润总额 + 利息费用) x (1 - 有效税率)；有效税率限制在 0%~35%。",
              "- 投入资本 = 股东权益 + 短期借款 + 一年内到期非流动负债 + 长期借款 + 应付债券 + 租赁负债 - 货币资金。",
              "- ROIC = NOPAT / 平均投入资本；资产负债表字段不完整时不估算 ROIC。",
              f"- ROIC-WACC 使用统一 {config.DEFAULT_WACC:.1f}% WACC 假设，用于横向初筛，不是公司精确资本成本。",
              "- 复合分权重：PEG 40、ROIC 25、ROIC-WACC 15、现金流质量 10、负债约束 10。",
              "- 银行、保险、券商等金融企业的负债与投入资本含义不同，不建议直接与实体企业横向比较。",
              "- 本报告是量化初筛结果，不构成投资建议。", ""]
    return "\n".join(lines)


def save_markdown(text: str, filename: str) -> str:
    path = os.path.join(config.OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path
