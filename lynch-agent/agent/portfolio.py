# -*- coding: utf-8 -*-
"""Ranking + Top-10 portfolio construction (Step 6 ranking, Step 7 buckets)."""
from __future__ import annotations

import pandas as pd

from . import config


def _best_peg(row: dict):
    """Preferred PEG for ranking: base -> forward -> adjusted (first valid)."""
    for k in ("peg_base", "peg_forward", "peg_adjusted"):
        v = row.get(k)
        if v is not None and v > 0:
            return v
    return None


def build_ranking(records: list[dict]) -> pd.DataFrame:
    """PEG ranking table over all stocks (Step 6)."""
    df = pd.DataFrame(records)
    df["peg_rank_value"] = df.apply(lambda r: _best_peg(r.to_dict()), axis=1)
    # Non-null PEG first (ascending); nulls sink to bottom.
    df = df.sort_values("peg_rank_value", ascending=True, na_position="last").reset_index(drop=True)
    df.insert(0, "排名", range(1, len(df) + 1))
    return df


def peg_band(peg) -> str:
    """Interpret a PEG value per Step 6 bands."""
    if peg is None or peg <= 0:
        return "-"
    if peg < config.PEG_ATTRACTIVE:
        return "极具吸引力"
    if peg <= config.PEG_FAIR:
        return "合理"
    if peg > config.PEG_EXPENSIVE:
        return "偏贵"
    return "略贵"


def attractive_targets(df: pd.DataFrame) -> pd.DataFrame:
    """PEG < 1 filter (Step 6)."""
    return df[(df["peg_rank_value"].notna()) &
              (df["peg_rank_value"] < config.PEG_ATTRACTIVE)].copy()


def _eligible(df: pd.DataFrame) -> pd.DataFrame:
    """Exclude negative-growth / no-PEG names from portfolio consideration."""
    m = df["peg_rank_value"].notna() & (df["peg_rank_value"] > 0)
    m &= ~df["lynch_category"].isin(["负增长(排除)"])
    return df[m].copy()


def build_portfolio(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Assign Top-10 into 5 Lynch buckets without duplication.

    Selection order per bucket (greedy, non-overlapping):
      核心仓: lowest PEG & highest quality_score
      进攻仓: highest forward growth / turnaround
      价值仓: lowest PE_TTM with reasonable percentile
      质量仓: highest ROE
      防守仓: low debt + high dividend + low PE
    """
    pool = _eligible(df)
    used: set[str] = set()
    buckets: dict[str, list[str]] = {}

    def take(name: str, ordered: pd.DataFrame, n: int):
        picks = []
        for _, r in ordered.iterrows():
            if r["code"] in used:
                continue
            picks.append(r["code"])
            used.add(r["code"])
            if len(picks) >= n:
                break
        buckets[name] = picks

    # Target counts scaled from weights to Top-N.
    counts = {"核心仓": 3, "进攻仓": 2, "价值仓": 2, "质量仓": 2, "防守仓": 1}

    core = pool.sort_values(["peg_rank_value", "quality_score"],
                            ascending=[True, False])
    take("核心仓", core, counts["核心仓"])

    offense = pool.sort_values("g_forward", ascending=False, na_position="last")
    take("进攻仓", offense, counts["进攻仓"])

    value = pool.sort_values(["pe_ttm", "pe_percentile"],
                             ascending=[True, True], na_position="last")
    take("价值仓", value, counts["价值仓"])

    quality = pool.sort_values("roe", ascending=False, na_position="last")
    take("质量仓", quality, counts["质量仓"])

    defense = pool.copy()
    defense = defense.sort_values(["dividend_yield", "debt_ratio", "pe_ttm"],
                                  ascending=[False, True, True], na_position="last")
    take("防守仓", defense, counts["防守仓"])

    # Re-normalise weights so empty buckets don't leak allocation: the total
    # weight of filled buckets is scaled back up to 100%.
    filled = {b: c for b, c in buckets.items() if c}
    base_sum = sum(config.PORTFOLIO_WEIGHTS[b] for b in filled) or 1.0
    scale = 1.0 / base_sum

    # Assemble Top-N frame with bucket + per-name position weight.
    rows = []
    for bucket, codes in buckets.items():
        if not codes:
            continue
        w = config.PORTFOLIO_WEIGHTS[bucket] * scale
        per = round(w / len(codes) * 100, 2)
        for code in codes:
            src = df[df["code"] == code].iloc[0].to_dict()
            src["组合仓位"] = bucket
            src["建议权重%"] = per
            rows.append(src)
    top = pd.DataFrame(rows)
    return top, buckets
