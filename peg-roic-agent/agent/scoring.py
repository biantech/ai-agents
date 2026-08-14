"""Composite scoring and ranking for PEG plus ROIC."""
from __future__ import annotations

import pandas as pd

from . import config


def best_peg(record: dict):
    for key in ("peg_forward", "peg_trailing"):
        value = record.get(key)
        if value is not None and value > 0:
            return value
    return None


def evaluate(record: dict) -> dict:
    peg = best_peg(record)
    roic = record.get("roic")
    cash_quality = record.get("cash_quality")
    debt_ratio = record.get("debt_ratio")
    spread = None if roic is None else round(roic - config.DEFAULT_WACC, 2)

    peg_score = 0.0 if peg is None else min(40.0, 40.0 / max(peg, 1.0))
    roic_score = 0.0 if roic is None else min(max(roic, 0.0), 20.0) / 20.0 * 25.0
    spread_score = 0.0 if spread is None else min(max(spread, 0.0), 12.0) / 12.0 * 15.0
    cash_score = 0.0 if cash_quality is None else min(max(cash_quality, 0.0), 1.2) / 1.2 * 10.0
    debt_score = 0.0 if debt_ratio is None else max(0.0, 1.0 - debt_ratio / 100.0) * 10.0

    if peg is None or roic is None:
        grade = "数据不足"
    elif peg < config.PEG_ATTRACTIVE and spread >= config.SPREAD_GOOD:
        grade = "优选"
    elif peg <= 1.5 and spread > 0:
        grade = "观察"
    elif spread <= 0:
        grade = "未创造超额回报"
    else:
        grade = "估值偏高"

    notes = []
    if roic is not None and spread is not None:
        notes.append(f"ROIC-WACC={spread:.2f}%")
    if record.get("roic_stability") is not None and record["roic_stability"] > 8:
        notes.append("ROIC波动较大")
    if cash_quality is not None and cash_quality < config.CASH_QUALITY_GOOD:
        notes.append("现金流转化偏弱")
    if debt_ratio is not None and debt_ratio > config.DEBT_WARN:
        notes.append("负债率较高")

    return {
        "peg_rank_value": peg,
        "wacc_assumption": config.DEFAULT_WACC,
        "roic_wacc_spread": spread,
        "composite_score": round(peg_score + roic_score + spread_score + cash_score + debt_score, 1),
        "grade": grade,
        "notes": "; ".join(notes),
    }


def build_ranking(records: list[dict]) -> pd.DataFrame:
    enriched = []
    for record in records:
        row = dict(record)
        row.update(evaluate(row))
        enriched.append(row)
    frame = pd.DataFrame(enriched)
    if frame.empty:
        return frame
    frame = frame.sort_values(
        ["composite_score", "roic_wacc_spread", "peg_rank_value"],
        ascending=[False, False, True], na_position="last").reset_index(drop=True)
    frame.insert(0, "排名", range(1, len(frame) + 1))
    return frame


def preferred_targets(ranking: pd.DataFrame) -> pd.DataFrame:
    if ranking.empty:
        return ranking.copy()
    return ranking[ranking["grade"] == "优选"].copy()


def top_targets(ranking: pd.DataFrame, top_n: int = config.TOP_N) -> pd.DataFrame:
    if ranking.empty:
        return ranking.copy()
    eligible = ranking[ranking["grade"].isin(["优选", "观察"])].copy()
    return eligible.head(top_n)
