"""
Macro data fetching via FRED and Yahoo Finance.

FRED series used (ISM/NFIB are proprietary & not on FRED — best available proxies):
  ISM_PMI  → IPMAN   Industrial Production: Manufacturing (2017=100, threshold 100)
  ISM_NMI  → MCUMFN  Capacity Utilization: Manufacturing (%, LT avg threshold)
  UMICH    → UMCSENT University of Michigan Consumer Sentiment
  PERMITS  → PERMIT  Building Permits (thousands, SA)
  NFIB_SBO → NFCI    Chicago Fed National Financial Conditions Index
               (INVERTED: lower/negative = looser = bullish; threshold = 0)
  NFP      → PAYEMS  Nonfarm Payrolls (thousands, SA)
  SPY      → Yahoo Finance monthly close
"""
from __future__ import annotations

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from fredapi import Fred
from src.data.price_fetcher import fetch_history_robust

_fred: Fred | None = None


def _get_fred() -> Fred:
    global _fred
    if _fred is None:
        key = os.getenv("FRED_API_KEY", "")
        if not key:
            raise EnvironmentError(
                "FRED_API_KEY not set. "
                "Free key at: https://fred.stlouisfed.org/docs/api/api_key.html"
            )
        _fred = Fred(api_key=key)
    return _fred


# ── Verified FRED series (all confirmed to exist as of 2025) ──────────────────
FRED_SERIES = {
    "ISM_PMI":          "IPMAN",    # Industrial Production: Manufacturing
    "ISM_NMI":          "MCUMFN",   # Capacity Utilization: Manufacturing
    "UMICH":            "UMCSENT",  # U of Mich Consumer Sentiment
    "BUILDING_PERMITS": "PERMIT",   # Building Permits
    "NFIB_SBO":         "NFCI",     # National Financial Conditions (inverted)
    "NFP":              "PAYEMS",   # Nonfarm Payrolls
}

# Display labels shown in the dashboard
DISPLAY_NAMES = {
    "ISM_PMI":          "Mfg Production (IPMAN)",
    "ISM_NMI":          "Capacity Utilization",
    "UMICH":            "Consumer Sentiment",
    "BUILDING_PERMITS": "Building Permits",
    "NFIB_SBO":         "Fin. Conditions (NFCI)",
    "NFP":              "Non-Farm Payrolls",
    "SPY":              "S&P 500 (SPY)",
}

# Absolute threshold config:
#   fixed=float  → compare latest vs this number
#   None         → use long-term series mean
#   "invert"     → LOWER is better (NFCI); score abs when value < 0
ABS_THRESHOLD = {
    "ISM_PMI":          100.0,    # above 100 = expansion
    "ISM_NMI":          None,     # long-term mean
    "UMICH":            None,
    "BUILDING_PERMITS": None,
    "NFIB_SBO":         "invert", # NFCI: below 0 = loose / bullish
    "NFP":              None,
    "SPY":              "36m_ma", # above 36-month MA
}

SPY_TICKER    = "SPY"
LOOKBACK_YEARS = 6


def _fetch_fred_series(series_id: str, start: str) -> pd.Series:
    fred = _get_fred()
    try:
        data = fred.get_series(series_id, observation_start=start)
        return data.dropna()
    except Exception as e:
        print(f"[WARN] FRED {series_id}: {e}")
        return pd.Series(dtype=float)


def fetch_macro_indicators() -> dict[str, pd.Series]:
    """Fetch all 7 macro indicators. Returns {key: monthly pd.Series}."""
    start = (datetime.now() - timedelta(days=365 * LOOKBACK_YEARS)).strftime("%Y-%m-%d")
    result: dict[str, pd.Series] = {}
    for key, sid in FRED_SERIES.items():
        result[key] = _fetch_fred_series(sid, start)
    result["SPY"] = _fetch_spy(start)
    return result


def _fetch_spy(start: str) -> pd.Series:
    return fetch_history_robust(SPY_TICKER, start, monthly=True)
