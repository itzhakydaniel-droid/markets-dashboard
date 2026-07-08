"""
US Treasury yield curve — official US Treasury Department daily feed.
Same primary source as ustreasuryyieldcurve.com (free, no API key).

Endpoint (CSV, one file per year):
https://home.treasury.gov/resource-center/data-chart-center/interest-rates/
    daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve&_format=csv
"""
from __future__ import annotations

import io
import pandas as pd
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

_CSV_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve"
    "&field_tdr_date_value={year}&_format=csv"
)

_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

# Standard maturities we display, in curve order
MATURITIES = ["1 Mo", "3 Mo", "6 Mo", "1 Yr", "2 Yr", "3 Yr", "5 Yr", "7 Yr", "10 Yr", "20 Yr", "30 Yr"]


def _fetch_year(year: int) -> pd.DataFrame:
    try:
        r = requests.get(_CSV_URL.format(year=year), headers=_HEADERS, timeout=12)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        df["Date"] = pd.to_datetime(df["Date"])
        return df.set_index("Date").sort_index()
    except Exception:
        return pd.DataFrame()


def fetch_yield_curve(years_back: int = 3) -> dict:
    """
    Fetch daily Treasury yield-curve history for the last `years_back`
    calendar years (parallel, one CSV per year) from the official
    US Treasury feed. Returns:
      history   — DataFrame (date × maturity, %)
      latest    — most recent curve (Series)
      month_ago / year_ago — comparison curves
      spread_2s10s / spread_3m10y — full daily spread history (Series, pp)
      inverted  — bool, 2s10s below zero now
      asof      — date string of the latest observation
    """
    this_year = datetime.now().year
    years = list(range(this_year - years_back + 1, this_year + 1))

    frames: list[pd.DataFrame] = []
    with ThreadPoolExecutor(max_workers=len(years)) as ex:
        for df in ex.map(_fetch_year, years):
            if not df.empty:
                frames.append(df)

    if not frames:
        return {}

    hist = pd.concat(frames).sort_index()
    cols = [c for c in MATURITIES if c in hist.columns]
    hist = hist[cols].dropna(how="all")
    if hist.empty:
        return {}

    latest = hist.iloc[-1]
    asof   = hist.index[-1]

    def _closest(days: int) -> pd.Series | None:
        target = asof - pd.Timedelta(days=days)
        past = hist[hist.index <= target]
        return past.iloc[-1] if not past.empty else None

    out = {
        "history":   hist,
        "latest":    latest,
        "month_ago": _closest(30),
        "year_ago":  _closest(365),
        "asof":      asof.strftime("%d %b %Y"),
    }

    if "2 Yr" in hist.columns and "10 Yr" in hist.columns:
        out["spread_2s10s"] = (hist["10 Yr"] - hist["2 Yr"]).dropna()
        out["inverted"] = bool(out["spread_2s10s"].iloc[-1] < 0)
    if "3 Mo" in hist.columns and "10 Yr" in hist.columns:
        out["spread_3m10y"] = (hist["10 Yr"] - hist["3 Mo"]).dropna()

    return out
