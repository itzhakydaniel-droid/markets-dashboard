"""
Black Raven Protocol v1.0 — Sector Rotation Engine
Dual-layer institutional sector scoring:

LAYER 1 — Quantitative Engine (Relative Strength mathematics)
  RS ratio (ETF/SPY), QMA (63d) & YMA (252d) of RS, RS slope +
  steepening/flattening, multi-timeframe RS Flow (1W/1M/3M/6M/1Y).

LAYER 2 — Macro Overlays (Protocol paradigms)
  K-Economy penalty on consumer-dependent sectors;
  Economy-of-Shortage structural premium on Physical-AI infrastructure.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

from src.data.price_fetcher import fetch_history_robust, SECTOR_ETFS

# ── Layer 2 configuration ─────────────────────────────────────────────────────
SHORTAGE_PREMIUM = {"XLK", "XLU", "XLE", "XLI"}   # Physical-AI / CapEx bottlenecks: +2
K_ECONOMY_PENALTY = {"XLY"}                        # consumer breaking: −3

OVERLAY_NOTES = {
    "XLK": "Economy of Shortage — silicon & data-center constraint premium",
    "XLU": "Economy of Shortage — AI baseload power premium",
    "XLE": "Economy of Shortage — geopolitical hedge & grid demand premium",
    "XLI": "Economy of Shortage — electrical equipment / build-out premium",
    "XLY": "K-Economy — consumer breaking under sticky inflation: automatic penalty",
}


def _rs_flow_ret(rs: pd.Series, days: int) -> float | None:
    """Calendar-accurate % change of the RS ratio over a lookback window."""
    if rs is None or len(rs) < 2:
        return None
    past = rs[rs.index <= rs.index[-1] - pd.Timedelta(days=days)]
    if past.empty or float(past.iloc[-1]) == 0:
        return None
    return round((float(rs.iloc[-1]) / float(past.iloc[-1]) - 1) * 100, 2)


def _slope_pct_month(rs: pd.Series, bars: int = 21, offset: int = 0) -> float | None:
    """Linear-regression slope of the RS line over `bars` bars, as %/month of its mean."""
    w = rs.iloc[-(bars + offset): len(rs) - offset if offset else None]
    if len(w) < bars:
        return None
    y = w.values.astype(float)
    x = np.arange(len(y))
    slope = float(np.polyfit(x, y, 1)[0])           # RS units per bar
    return round(slope / (abs(y.mean()) or 1) * 21 * 100, 2)  # % of RS level per month


def classify_rotation(final: float) -> dict:
    if final >= 9:
        return {"tier": "TIER 1 — ACCUMULATION", "color": "#10b981", "action": "DEPLOY — liquidity ambush at 50SMA on flushes"}
    if final >= 7:
        return {"tier": "TIER 2 — OVERWEIGHT",   "color": "#5DC7D6", "action": "SCALE IN — buy limits at support"}
    if final >= 4:
        return {"tier": "NEUTRAL — MONITOR",     "color": "#f59e0b", "action": "HOLD — no fresh capital"}
    if final >= 2:
        return {"tier": "DISTRIBUTE",            "color": "#f97316", "action": "REDUCE — sell strength"}
    return {"tier": "AVOID",                     "color": "#ef4444", "action": "NO POSITION — structural underperformance"}


def fetch_sector_rotation() -> pd.DataFrame:
    """
    Run the full dual-layer Sector Rotation Engine.
    Returns one row per sector with RS structure, flow matrix, slopes,
    quant score, macro overlay, final score, tier and execution level.
    """
    start = (datetime.now() - timedelta(days=560)).strftime("%Y-%m-%d")
    tickers = {**SECTOR_ETFS, "S&P 500": "SPY"}

    series: dict[str, pd.Series] = {}

    def _one(item):
        name, etf = item
        try:
            s = fetch_history_robust(etf, start)
            if not s.empty and len(s) >= 260:
                s.index = pd.to_datetime(s.index)
                return name, s.sort_index()
        except Exception:
            pass
        return name, None

    with ThreadPoolExecutor(max_workers=12) as ex:
        for name, s in ex.map(_one, tickers.items()):
            if s is not None:
                series[name] = s

    spy = series.get("S&P 500")
    if spy is None:
        return pd.DataFrame()

    rows = []
    for sector, etf in SECTOR_ETFS.items():
        s = series.get(sector)
        if s is None:
            continue
        joined = pd.concat([s, spy], axis=1, keys=["etf", "spy"]).dropna()
        if len(joined) < 260:
            continue
        rs = joined["etf"] / joined["spy"]

        # ── Structure: QMA / YMA of the RS ratio ─────────────────────────────
        qma = float(rs.tail(63).mean())
        yma = float(rs.tail(252).mean())
        rs_now = float(rs.iloc[-1])
        above_qma = rs_now > qma
        qma_above_yma = qma > yma

        # ── Slopes: current vs prior month (steepening / flattening) ─────────
        slope_now  = _slope_pct_month(rs, 21, 0)
        slope_prev = _slope_pct_month(rs, 21, 21)
        if slope_now is not None and slope_prev is not None:
            if slope_now > 0 and slope_now > slope_prev:
                slope_state = "ACCUMULATION — positive & steepening"
            elif slope_now < 0 and slope_now < slope_prev:
                slope_state = "DISTRIBUTION — negative & steepening down"
            elif slope_now > 0:
                slope_state = "POSITIVE — but flattening"
            else:
                slope_state = "NEGATIVE — flattening"
        else:
            slope_state = "—"

        # ── RS Flow matrix (calendar windows) ────────────────────────────────
        flow = {
            "1W": _rs_flow_ret(rs, 7),   "1M": _rs_flow_ret(rs, 30),
            "3M": _rs_flow_ret(rs, 91),  "6M": _rs_flow_ret(rs, 182),
            "1Y": _rs_flow_ret(rs, 365),
        }

        # ── Layer 1 quant score (0–10) ───────────────────────────────────────
        q = 0.0
        q += 1.0 if (flow["1W"] or 0) > 0 else 0
        q += 1.5 if (flow["1M"] or 0) > 0 else 0
        q += 1.5 if (flow["3M"] or 0) > 0 else 0
        q += 2.0 if (flow["6M"] or 0) > 0 else 0
        q += 1.0 if (flow["1Y"] or 0) > 0 else 0
        q += 1.5 if above_qma else 0
        q += 1.5 if qma_above_yma else 0

        # ── Layer 2 macro overlay ────────────────────────────────────────────
        overlay = 2.0 if etf in SHORTAGE_PREMIUM else (-3.0 if etf in K_ECONOMY_PENALTY else 0.0)
        final = max(0.0, min(12.0, q + overlay))
        cls = classify_rotation(final)

        # ── Execution level: liquidity ambush at ETF 50SMA ───────────────────
        px    = float(s.iloc[-1])
        sma50 = float(s.tail(50).mean())

        rows.append({
            "Sector":     sector,
            "ETF":        etf,
            "RS_now":     round(rs_now, 4),
            "Above_QMA":  above_qma,
            "QMA_gt_YMA": qma_above_yma,
            "Slope_Now":  slope_now,
            "Slope_Prev": slope_prev,
            "Slope_State": slope_state,
            "RS_1W": flow["1W"], "RS_1M": flow["1M"], "RS_3M": flow["3M"],
            "RS_6M": flow["6M"], "RS_1Y": flow["1Y"],
            "Quant_Score":  round(q, 1),
            "Overlay":      overlay,
            "Overlay_Note": OVERLAY_NOTES.get(etf, "No structural bias"),
            "Final_Score":  round(final, 1),
            "Tier":         cls["tier"],
            "TierColor":    cls["color"],
            "Action":       cls["action"],
            "Price":        round(px, 2),
            "Ambush_50SMA": round(sma50, 2),
            "Dist_Ambush%": round((px / sma50 - 1) * 100, 1),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Final_Score", ascending=False).reset_index(drop=True)
    return df
