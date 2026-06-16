"""
CTA (Commodity Trading Advisor) systematic exposure proxy.
Since direct CTA positioning data is proprietary, we construct a proxy from:
  1. COT (CFTC Commitments of Traders) report - non-commercial net positioning
  2. Price-momentum Z-score (trend-following signal strength)
  3. VIX regime (risk-on / risk-off context)

COT data via: https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm
"""
from __future__ import annotations

import pandas as pd
import numpy as np
import requests
import io
from datetime import datetime, timedelta
from src.data.price_fetcher import fetch_history_robust, fetch_quotes_multi

COT_URL = "https://www.cftc.gov/files/dea/history/fut_fin_txt_{year}.zip"
# Simplified: use the disaggregated futures report CSV that CFTC publishes
COT_CURRENT_URL = "https://www.cftc.gov/dea/newcot/f_disagg.txt"


def _compute_momentum_zscore(prices: pd.Series, window: int = 63) -> float:
    """Compute rolling momentum Z-score as a CTA positioning proxy."""
    if len(prices) < window + 30:
        return 0.0
    ret = prices.pct_change(window).dropna()
    mu = ret.mean()
    sigma = ret.std()
    if sigma == 0:
        return 0.0
    return float((ret.iloc[-1] - mu) / sigma)


def fetch_cta_exposure_proxy(tickers: dict[str, str] | None = None) -> dict:
    """
    Compute a CTA trend-following exposure proxy for key asset classes.
    Returns a dict with estimated positioning (-100 to +100 scale).
    """
    if tickers is None:
        tickers = {
            "Equities (SPY)": "SPY",
            "Bonds (TLT)": "TLT",
            "Gold (GLD)": "GLD",
            "Oil (USO)": "USO",
            "Dollar (UUP)": "UUP",
        }

    end = datetime.now()
    start = (end - timedelta(days=400)).strftime("%Y-%m-%d")

    result = {}
    for label, ticker in tickers.items():
        prices = fetch_history_robust(ticker, start)
        if prices.empty:
            continue
        # Multi-horizon momentum (20d, 63d, 126d) — classic CTA signal
        z20 = _compute_momentum_zscore(prices, 20)
        z63 = _compute_momentum_zscore(prices, 63)
        z126 = _compute_momentum_zscore(prices, 126)
        # Equal weight blend, clip to ±2 sigma, scale to 0-100
        combined = np.clip((z20 + z63 + z126) / 3, -2, 2)
        exposure = round(combined * 50, 1)  # -100 to +100
        result[label] = {
            "exposure": exposure,
            "signal_20d": round(z20, 2),
            "signal_63d": round(z63, 2),
            "signal_126d": round(z126, 2),
            "regime": "LONG" if exposure > 20 else "SHORT" if exposure < -20 else "NEUTRAL",
        }
    return result


def fetch_vix_term_structure() -> pd.DataFrame:
    """
    Fetch VIX and VIX futures proxies (VX1, VX2 approximated via VXX, UVXY).
    Returns spot VIX and 3/6 month implied vol context.
    """
    tickers = {"VIX": "^VIX", "VIX3M": "^VIX3M", "VXX": "VXX"}
    quotes = fetch_quotes_multi(list(tickers.values()))
    rows = []
    for label, t in tickers.items():
        row = quotes[quotes["Ticker"] == t] if not quotes.empty else pd.DataFrame()
        if not row.empty and row["Price"].iloc[0] is not None:
            rows.append({"Instrument": label, "Level": round(float(row["Price"].iloc[0]), 2)})
    return pd.DataFrame(rows)
