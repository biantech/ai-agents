from __future__ import annotations
import os
from datetime import datetime
from . import config

def fmt(value, suffix=""):
    if value is None: return "数据缺失"
    if isinstance(value, float): return f"{value:.2f}{suffix}"
    return f"{value}{suffix}"

def _section(title, body): return [f"## {title}", "", *body, ""]

def build_markdown(item: dict) -> str:
    name, code = item.get("name", "待补充"), item.get("code", "")
    price = fmt(item.get("price"), " 元")
    ma = item.get("ma20")
    trend = "上升" if ma and item.get("price", 0) > ma else "下降/震荡" if ma else "数据缺失"
    lines = [f"# {name}（{code}）股票投资价值分析报告", "", f"> 生成日期：{datetime.now():%Y-%m-%d}。本报告基于公开数据自动整理，仅供学习研究，不构成投资建议。", ""]
    lines += _section("1. 公司基本面概述", ["### 1.1 基本信息", "", "| 项目 | 内容 |", "| --- | --- |", f"| 公司全称 | {name} |", f"| 股票代码 | {code} |", "| 所属行业 | 数据缺失（需结合公司公告核实） |", f"| 最新股价 | {price} |", "| 总市值 | 数据缺失 |", "| 主营业务 | 数据缺失（需阅读最新年报） |", "", "### 1.2 商业模式与核心竞争力", "", "公开接口未提供结构化商业模式信息，请结合年报、公告和实地调研核实。", "", "### 1.3 股权结构与管理层", "", "前十大股东、实际控制人和管理层履历：数据缺失。", "", "### 1.4 发展历程与重大事件", "", "重大事件：数据缺失。"])
    lines += _section("2. 行业与竞争格局分析", ["行业规模、政策、集中度、市占率及竞争对手：数据缺失，不能据此作出行业判断。", "", "建议补充来源：国家统计局、行业协会、交易所公告和公司年报。"])
    lines += _section("3. 财务分析", ["### 3.1 盈利能力", "", "| 指标 | 最新值 |", "| --- | --- |", f"| 营业收入 | {fmt(item.get('revenue'), ' 亿元')} |", f"| 归母净利润 | {fmt(item.get('profit'), ' 亿元')} |", f"| 净利润增速 | {fmt(item.get('growth'), '%')} |", f"| 毛利率 | {fmt(item.get('gross_margin'), '%')} |", f"| 净利率 | {fmt(item.get('net_margin'), '%')} |", f"| ROE | {fmt(item.get('roe'), '%')} |", f"| ROIC | {fmt(item.get('roic'), '%')} |", "", "### 3.2 成长能力", "", f"前瞻盈利增速：{fmt(item.get('forecast_growth'), '%')}。", "", "### 3.3 运营效率", "", "周转天数、总资产周转率：数据缺失。", "", "### 3.4 偿债能力与现金流", "", f"资产负债率：{fmt(item.get('debt_ratio'), '%')}；经营现金流/净利润：{fmt(item.get('cash_quality'))}。", "", "### 3.5 分红与股东回报", "", "分红数据：数据缺失。", "", "### 3.6 财务排雷清单", "", "应收、商誉、存货、关联交易及会计政策变更：需人工查阅年报，当前接口数据不足。"])
    peg = item.get("peg_forward") if item.get("peg_forward") is not None else item.get("peg_trailing")
    lines += _section("4. 估值分析", ["### 4.1 相对估值", "", "| 方法 | 当前值 |", "| --- | --- |", f"| PE（TTM） | {fmt(item.get('pe'))} |", f"| PB | {fmt(item.get('pb'))} |", f"| PS | {fmt(item.get('ps'))} |", f"| PEG | {fmt(peg)} |", "| EV/EBITDA | 数据缺失 |", "", "### 4.2 绝对估值（DCF）", "", "自由现金流、预测期、WACC 和永续增长率数据不足，未进行伪精确 DCF 估值。", "", "### 4.3 估值结论", "", f"当前股价：{price}；合理估值区间：数据缺失；安全边际：数据缺失。"])
    lines += _section("5. 技术面辅助分析", [f"均线趋势：{trend}；MA5={fmt(item.get('ma5'))}，MA20={fmt(item.get('ma20'))}，MA60={fmt(item.get('ma60'))}。", "关键支撑位、压力位、筹码及资金动向：数据缺失。"])
    lines += _section("6. 风险提示", ["| 风险类别 | 具体内容 | 影响程度 |", "| --- | --- | --- |", "| 经营风险 | 产品、客户和技术迭代信息未核实 | 中 |", "| 行业风险 | 政策、需求和竞争格局未核实 | 中 |", "| 财务风险 | 现金流、杠杆和商誉需结合年报核实 | 中 |", "| 市场风险 | 估值和流动性可能波动 | 高 |", "| 治理风险 | 股权质押、关联交易和诉讼未核实 | 中 |"])
    lines += _section("7. 投资结论与建议", ["### 7.1 综合评级", "", "评级：中性（数据不足，不能形成确定性投资判断）。", "", "### 7.2 核心逻辑", "", "1. 当前报告仅对可获得的结构化数据做客观展示。", "2. 商业模式、行业地位和治理质量仍需人工核验。", "3. 估值和技术指标不完整时不建议据此交易。", "", "### 7.3 关键催化剂", "", "未来 6~12 个月催化剂：数据缺失。", "", "### 7.4 操作建议", "", "合理估值区间、建仓区间、目标价、止损位和仓位：数据缺失。"])
    lines += _section("8. 数据来源汇总", ["AKShare 公开接口（行情、财务摘要、估值、研报预测）；公司年报、公告和交易所披露信息需人工复核。"])
    lines += _section("9. 分析原则", ["先定性后定量；纵向与横向对比；关注现金流；独立验证关键假设；随季报和行业变化动态更新。", "", "免责声明：本报告仅供学习与研究参考，不构成任何投资建议。"])
    return "\n".join(lines)

def save(item: dict) -> str:
    config.ensure_dirs(); code = item["code"]
    path = os.path.join(config.OUTPUT_DIR, f"{code}_{item.get('name', '股票')}_分析报告.md")
    with open(path, "w", encoding="utf-8") as handle: handle.write(build_markdown(item))
    return path
