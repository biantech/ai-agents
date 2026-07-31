# -*- coding: utf-8 -*-
"""Render analysis outputs: CSV files + a Markdown report."""
from __future__ import annotations

import os
from datetime import datetime

import pandas as pd

from . import config, portfolio


def _fmt(v, nd=2):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "-"
    if isinstance(v, bool):
        return "是" if v else "否"
    # Integer-valued numbers (e.g. rank) render without decimals.
    if isinstance(v, (int,)) or (isinstance(v, float) and float(v).is_integer()):
        return str(int(v))
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


def save_csv(df: pd.DataFrame, name: str) -> str:
    path = os.path.join(config.OUTPUT_DIR, name)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


# Columns shown in the Markdown PEG ranking table.
RANK_COLS = [
    ("排名", "排名"), ("code", "代码"), ("name", "名称"), ("industry", "行业"),
    ("lynch_category", "林奇分类"), ("pe_ttm", "PE(TTM)"),
    ("pe_percentile", "PE分位%"), ("roe", "ROE%"),
    ("dividend_yield", "股息率%"), ("g_profit_annual", "年增速%"),
    ("g_forward", "前瞻增速%"), ("peg_base", "基础PEG"),
    ("peg_adjusted", "调整PEG"), ("peg_forward", "前瞻PEG"),
]


def _md_table(df: pd.DataFrame, cols) -> list[str]:
    header = "| " + " | ".join(h for _, h in cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    lines = [header, sep]
    for _, r in df.iterrows():
        cells = []
        for key, _ in cols:
            v = r.get(key)
            cells.append(_fmt(v, 3 if "PEG" in key or key.startswith("peg") else 2))
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def build_markdown(ranking: pd.DataFrame, attractive: pd.DataFrame,
                   top: pd.DataFrame, buckets: dict) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    md = [f"# 彼得·林奇式 PEG 基本面分析报告", "",
          f"> 生成时间：{ts}　|　样本：{len(ranking)} 只成份股　|　"
          f"数据源：AKShare（新浪财务摘要 / 百度估值 / 东财研报）", ""]

    md.append("## 一、PEG 排名表（全样本，按最优 PEG 升序）")
    md.append("")
    md += _md_table(ranking, RANK_COLS)
    md.append("")

    md.append(f"## 二、PEG < 1 极具吸引力标的（{len(attractive)} 只）")
    md.append("")
    if attractive.empty:
        md.append("_本次样本中无 PEG < 1 的标的。_")
    else:
        md += _md_table(attractive, RANK_COLS)
    md.append("")

    md.append("## 三、Top 10 组合配置方案")
    md.append("")
    md.append(f"按林奇五仓框架分配，总权重 100%：核心仓35% / 进攻仓25% / "
              f"价值仓20% / 质量仓15% / 防守仓5%。")
    md.append("")
    bucket_cols = [
        ("组合仓位", "仓位"), ("建议权重%", "权重%"), ("code", "代码"),
        ("name", "名称"), ("industry", "行业"), ("lynch_category", "林奇分类"),
        ("pe_ttm", "PE(TTM)"), ("roe", "ROE%"), ("g_forward", "前瞻增速%"),
        ("peg_rank_value", "PEG"), ("quality_score", "质量分"),
        ("notes", "备注"),
    ]
    if top.empty:
        md.append("_无足够合格标的构建组合。_")
    else:
        md += _md_table(top, bucket_cols)
    md.append("")

    md.append("## 四、方法论与免责声明")
    md.append("")
    md.append("- **七步流程**：股票池→原始财务→估值指标→历史百分位→前瞻增速→PEG计算→林奇分类与组合。")
    md.append("- **PEG 口径**：基础PEG=PE/年增速；调整PEG=PE/(年增速+股息率)；前瞻PEG=PE/券商一致预期增速。")
    md.append("- **数据局限**：周期股/隐蔽资产类难以从财务摘要自动识别；部分个股券商覆盖不足导致前瞻增速缺失。")
    md.append("- **行业列口径**：优先取券商研报行业，缺失时用深交所批量接口兜底回填深市（0/3 开头）；"
              "沪市（6 开头）在研报缺失时仍显示「-」（本环境全市场行业接口不稳定，仅深交所接口可用）。")
    md.append("- 本报告为量化辅助工具输出，不构成任何投资建议。")
    md.append("")
    return "\n".join(md)


def save_markdown(text: str, name: str = "林奇PEG分析报告.md") -> str:
    path = os.path.join(config.OUTPUT_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path
