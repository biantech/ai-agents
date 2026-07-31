# -*- coding: utf-8 -*-
"""Lynch qualitative classification + Step-7 overlay flags.

Categories (analysis-step.md Step 7):
  快速增长 / 稳定增长 / 缓慢增长 / 周期 / 困境反转 / 隐蔽资产
Cyclical / asset-play cannot be reliably auto-detected from abstract data, so
we rely on growth profile + turnaround signal and note the limitation.
"""
from __future__ import annotations

from typing import Optional

from . import config


def classify(g_annual: Optional[float], g_forward: Optional[float],
             roe: Optional[float]) -> str:
    """Return a Lynch category label based on growth profile."""
    g = g_annual if g_annual is not None else g_forward
    # Turnaround: trailing negative but forward turns positive & meaningful.
    if g_annual is not None and g_annual < 0:
        if g_forward is not None and g_forward > config.STALWART_LOW:
            return "困境反转"
        return "负增长(排除)"
    if g is None:
        return "数据不足"
    if g >= config.FAST_GROWTH:
        return "快速增长"
    if g >= config.STALWART_LOW:
        return "稳定增长"
    if g >= 0:
        return "缓慢增长"
    return "负增长(排除)"


def overlay_flags(f: dict) -> dict:
    """Step-7 overlay: acceleration, margin trend, cash quality, debt warning."""
    flags: dict = {
        "accelerating": None, "margin_up": None,
        "cash_healthy": None, "debt_warn": None, "notes": [],
    }
    # Growth acceleration: Q1 growth vs annual growth.
    q1, ann = f.get("g_profit_q1"), f.get("g_profit_annual")
    if q1 is not None and ann is not None:
        flags["accelerating"] = q1 > ann
        flags["notes"].append("增速加速" if q1 > ann else "增速放缓")

    # Gross-margin trend (pricing power).
    gm, gm_prev = f.get("gross_margin"), f.get("gross_margin_prev")
    if gm is not None and gm_prev is not None:
        flags["margin_up"] = gm > gm_prev
        if gm > gm_prev:
            flags["notes"].append("毛利率上升")

    # Cash flow quality.
    cq = f.get("cash_quality")
    if cq is not None:
        flags["cash_healthy"] = cq >= config.CASH_QUALITY_GOOD
        if cq < config.CASH_QUALITY_GOOD:
            flags["notes"].append("现金流质量偏弱")

    # Debt warning.
    dr = f.get("debt_ratio")
    if dr is not None:
        flags["debt_warn"] = dr > config.DEBT_WARN
        if dr > config.DEBT_WARN:
            flags["notes"].append("高负债(>60%)")
    return flags


def quality_score(f: dict, flags: dict) -> float:
    """Composite fundamental-strength score (0-100) used for core-bucket rank."""
    score = 0.0
    roe = f.get("roe")
    if roe is not None:
        score += min(roe, 30) / 30 * 30           # up to 30 pts from ROE
    gm = f.get("gross_margin")
    if gm is not None:
        score += min(gm, 60) / 60 * 20            # up to 20 pts from margin
    cq = f.get("cash_quality")
    if cq is not None:
        score += min(max(cq, 0), 1.5) / 1.5 * 20  # up to 20 pts from cash
    if flags.get("accelerating"):
        score += 10
    if flags.get("margin_up"):
        score += 10
    if flags.get("debt_warn"):
        score -= 10
    g = f.get("g_profit_annual")
    if g is not None and g > 0:
        score += min(g, 40) / 40 * 10             # up to 10 pts from growth
    return round(max(score, 0.0), 1)
