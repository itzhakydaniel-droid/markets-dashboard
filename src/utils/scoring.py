"""
Macro scoring engine — 70-point system.
Each of 7 indicators scored out of 10:
  +2  positive trend last 3 months
  +2  positive trend last 6 months
  +3  positive trend YoY (12 months)
  +3  absolute threshold met
"""
from __future__ import annotations

import pandas as pd
import numpy as np
from dataclasses import dataclass
from src.data.macro_data import DISPLAY_NAMES, ABS_THRESHOLD


@dataclass
class IndicatorScore:
    key: str
    name: str
    latest_value: float
    score_3m:  int = 0
    score_6m:  int = 0
    score_yoy: int = 0
    score_abs: int = 0

    @property
    def total(self) -> int:
        return self.score_3m + self.score_6m + self.score_yoy + self.score_abs

    def breakdown(self) -> dict:
        return {
            "name":               self.name,
            "latest":             round(self.latest_value, 2),
            "3M Trend (+2)":      self.score_3m,
            "6M Trend (+2)":      self.score_6m,
            "YoY Trend (+3)":     self.score_yoy,
            "Abs Threshold (+3)": self.score_abs,
            "Total":              self.total,
        }


def _monthly(series: pd.Series) -> pd.Series:
    return series.resample("ME").last().dropna()


def score_indicator(key: str, series: pd.Series) -> IndicatorScore:
    name = DISPLAY_NAMES.get(key, key)
    if series is None or series.empty:
        return IndicatorScore(key=key, name=name, latest_value=0.0)

    m = _monthly(series)
    if m.empty:
        return IndicatorScore(key=key, name=name, latest_value=0.0)

    latest = float(m.iloc[-1])
    s = IndicatorScore(key=key, name=name, latest_value=latest)

    # ── Trend scores ──────────────────────────────────────────────────────────
    # NFCI is inverted: lower = better, so trend is positive when value FELL
    invert = (ABS_THRESHOLD.get(key) == "invert")

    def trend(periods: int) -> bool:
        if len(m) <= periods:
            return False
        delta = m.iloc[-1] - m.iloc[-(periods + 1)]
        return (delta < 0) if invert else (delta > 0)

    s.score_3m  = 2 if len(m) >= 4  and trend(3)  else 0
    s.score_6m  = 2 if len(m) >= 7  and trend(6)  else 0
    s.score_yoy = 3 if len(m) >= 13 and trend(12) else 0

    # ── Absolute threshold ────────────────────────────────────────────────────
    thresh_cfg = ABS_THRESHOLD.get(key)

    if thresh_cfg == "36m_ma":
        if len(m) >= 36:
            s.score_abs = 3 if latest > m.tail(36).mean() else 0

    elif thresh_cfg == "invert":
        # NFCI: below 0 = loose financial conditions = bullish
        s.score_abs = 3 if latest < 0 else 0

    elif isinstance(thresh_cfg, (int, float)):
        s.score_abs = 3 if latest > thresh_cfg else 0

    else:
        # None → use long-term mean
        lt_mean = m.mean()
        s.score_abs = 3 if latest > lt_mean else 0

    return s


def score_all_indicators(
    macro_data: dict[str, pd.Series]
) -> tuple[list[IndicatorScore], int]:
    keys = ["ISM_PMI", "ISM_NMI", "UMICH", "BUILDING_PERMITS", "NFIB_SBO", "NFP", "SPY"]
    scores = [score_indicator(k, macro_data.get(k, pd.Series(dtype=float))) for k in keys]
    total  = sum(s.total for s in scores)
    return scores, total


def interpret_score(total: int) -> dict:
    pct = total / 70.0
    if pct >= 0.80:
        return {"label": "Too Hot — Fed Will Cool Down",     "color": "#ef4444", "emoji": "🔥"}
    elif pct >= 0.60:
        return {"label": "Warm — Growth Momentum Strong",    "color": "#f59e0b", "emoji": "☀️"}
    elif pct >= 0.40:
        return {"label": "Neutral — Mixed Signals",          "color": "#3b82f6", "emoji": "⚖️"}
    elif pct >= 0.20:
        return {"label": "Cool — Growth Slowing",            "color": "#6366f1", "emoji": "🌧️"}
    else:
        return {"label": "Too Cold — Fed Will Heat Up",      "color": "#10b981", "emoji": "❄️"}
