"""
Sector rating engine — applies the project's 10-point scoring method
to the 11 S&P sector ETFs, using 2 years of daily price history.

Per-sector score out of 10 (same weights as the macro engine):
  +2  positive trend last 3 months
  +2  positive trend last 6 months
  +3  positive trend YoY (12 months)
  +3  absolute threshold met (price above 200-day moving average)
"""
from __future__ import annotations

import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

from src.data.price_fetcher import fetch_history_robust, SECTOR_ETFS


def _trend_ok(monthly: pd.Series, months: int) -> bool:
    if len(monthly) <= months:
        return False
    return float(monthly.iloc[-1] - monthly.iloc[-(months + 1)]) > 0


def _score_series(s: pd.Series) -> dict:
    """Score one sector's daily close series with the 10-point method."""
    m = s.resample("ME").last().dropna()
    latest = float(s.iloc[-1])

    sc_3m  = 2 if _trend_ok(m, 3)  else 0
    sc_6m  = 2 if _trend_ok(m, 6)  else 0
    sc_yoy = 3 if _trend_ok(m, 12) else 0
    sma200 = float(s.tail(200).mean()) if len(s) >= 200 else None
    sc_abs = 3 if (sma200 is not None and latest > sma200) else 0

    return {
        "score_3m": sc_3m, "score_6m": sc_6m,
        "score_yoy": sc_yoy, "score_abs": sc_abs,
        "total": sc_3m + sc_6m + sc_yoy + sc_abs,
        "sma200": round(sma200, 2) if sma200 else None,
        "sma50": round(float(s.tail(50).mean()), 2) if len(s) >= 50 else None,
        "price": round(latest, 2),
    }


def _window_ret(s: pd.Series, days: int) -> float | None:
    """Calendar-accurate return: last close vs last close on/before (today - days)."""
    if s is None or len(s) < 2:
        return None
    cutoff = s.index[-1] - pd.Timedelta(days=days)
    past = s[s.index <= cutoff]
    if past.empty:
        return None
    base = float(past.iloc[-1])
    if base == 0:
        return None
    return round((float(s.iloc[-1]) / base - 1) * 100, 2)


def interpret_sector_score(total: int) -> dict:
    if total >= 8:
        return {"label": "STRONG — Leadership",   "color": "#10b981", "emoji": "🚀"}
    if total >= 6:
        return {"label": "POSITIVE — Uptrend",    "color": "#5DC7D6", "emoji": "📈"}
    if total >= 4:
        return {"label": "NEUTRAL — Mixed",       "color": "#f59e0b", "emoji": "⚖️"}
    if total >= 2:
        return {"label": "WEAK — Losing Momentum","color": "#f97316", "emoji": "🌧️"}
    return {"label": "AVOID — Downtrend",         "color": "#ef4444", "emoji": "🚨"}


def _situation_text(name: str, d: dict) -> str:
    """Rule-based one-paragraph situation summary for the sector."""
    parts = []
    up = [h for h, k in [("3-month", "score_3m"), ("6-month", "score_6m"), ("12-month", "score_yoy")] if d[k] > 0]
    dn = [h for h, k in [("3-month", "score_3m"), ("6-month", "score_6m"), ("12-month", "score_yoy")] if d[k] == 0]
    if len(up) == 3:
        parts.append("Uptrend confirmed across all horizons (3M, 6M, 12M).")
    elif len(up) == 0:
        parts.append("Downtrend across every horizon — no positive momentum window.")
    else:
        parts.append(f"Mixed trend: positive on the {' and '.join(up)} window{'s' if len(up)>1 else ''}, "
                     f"negative on {' and '.join(dn)}.")
    if d["score_abs"]:
        parts.append("Price holds above its 200-day average — the long-term structure is intact.")
    else:
        parts.append("Price is below its 200-day average — long-term structure is broken.")
    rs = d.get("rs_1y")
    if isinstance(rs, (int, float)):
        if rs > 5:
            parts.append(f"Leading the S&P 500 by {rs:+.1f}pp over 12 months.")
        elif rs < -5:
            parts.append(f"Lagging the S&P 500 by {rs:+.1f}pp over 12 months.")
        else:
            parts.append(f"Tracking the S&P 500 (RS {rs:+.1f}pp over 12 months).")
    dd = d.get("max_drawdown")
    if isinstance(dd, (int, float)) and dd < -20:
        parts.append(f"Deep {dd:.0f}% drawdown from the 2-year high — recovery still incomplete.")
    return " ".join(parts)


def fetch_sector_ratings(years: int = 2) -> dict:
    """
    Fetch ~2y of daily closes for all 11 sector ETFs + SPY (parallel),
    score each with the 10-point method, and attach analytics + series
    for the breakdown view.  Returns {sector_name: {...}}.
    """
    start = (datetime.now() - timedelta(days=int(365.25 * years) + 30)).strftime("%Y-%m-%d")
    tickers = {**SECTOR_ETFS, "S&P 500": "SPY"}

    series: dict[str, pd.Series] = {}

    def _one(item):
        name, etf = item
        try:
            s = fetch_history_robust(etf, start)
            if not s.empty and len(s) >= 60:
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
    out: dict = {}

    for name, etf in SECTOR_ETFS.items():
        s = series.get(name)
        if s is None:
            continue
        d = _score_series(s)
        d["etf"] = etf

        # returns across horizons (calendar-accurate)
        for lbl, days in [("ret_1m", 30), ("ret_3m", 91), ("ret_6m", 182),
                          ("ret_1y", 365), ("ret_2y", 730)]:
            d[lbl] = _window_ret(s, days)

        # relative strength vs SPY (12 months)
        if spy is not None:
            r_s, r_spy = _window_ret(s, 365), _window_ret(spy, 365)
            d["rs_1y"] = round(r_s - r_spy, 2) if (r_s is not None and r_spy is not None) else None

        # risk stats over the full window
        daily = s.pct_change().dropna()
        d["volatility"]   = round(float(daily.std() * (252 ** 0.5)) * 100, 1) if len(daily) > 20 else None
        d["max_drawdown"] = round(float((s / s.cummax() - 1).min()) * 100, 1)

        d["verdict"]   = interpret_sector_score(d["total"])
        d["situation"] = _situation_text(name, d)
        d["series"]    = s
        d["spy"]       = spy
        out[name] = d

    return out
