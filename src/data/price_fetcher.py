"""
Multi-source price fetcher with automatic fallback.

Priority chain for every request:
  1. curl_cffi  — browser TLS fingerprint impersonation (bypasses Yahoo rate limits)
  2. yfinance   — standard library (works when not rate-limited)
  3. Google Finance scraper — lightweight HTML scrape as last resort

Historical OHLCV always uses curl_cffi → yfinance fallback.
"""
from __future__ import annotations

import os
import re
import time
import warnings
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

# ── curl_cffi Yahoo Finance (primary, no rate limits) ─────────────────────────
try:
    from curl_cffi import requests as _curl_requests
    _CURL_OK = True
except ImportError:
    _CURL_OK = False

_YF_CHART   = "https://query2.finance.yahoo.com/v8/finance/chart/{ticker}"
_YF_QUOTE   = "https://query2.finance.yahoo.com/v7/finance/quote?symbols={ticker}"
_GF_SCRAPE  = "https://www.google.com/finance/quote/{symbol}:{exchange}"

_IMPERSONATE = "chrome110"

# Exchange map for Google Finance fallback
_GF_EXCHANGE = {
    "SPY": "NYSEARCA", "QQQ": "NASDAQ", "IWM": "NYSEARCA",
    "GLD": "NYSEARCA", "TLT": "NASDAQ", "USO": "NYSEARCA",
    "UUP": "NYSEARCA", "VXX": "NYSEARCA", "^VIX": None,
    "XLK": "NYSEARCA", "XLY": "NYSEARCA", "XLV": "NYSEARCA",
    "XLF": "NYSEARCA", "XLE": "NYSEARCA", "XLI": "NYSEARCA",
    "XLB": "NYSEARCA", "XLU": "NYSEARCA", "XLRE": "NYSEARCA",
    "XLC": "NYSEARCA", "XLP": "NYSEARCA",
}


def _curl_get(url: str, **kwargs) -> dict | None:
    if not _CURL_OK:
        return None
    try:
        r = _curl_requests.get(url, impersonate=_IMPERSONATE, timeout=8, **kwargs)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[curl] {url[:60]}: {e}")
    return None


def _std_get(url: str) -> dict | None:
    import requests as _req
    try:
        r = _req.get(url, timeout=7, headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
        })
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[req] {url[:60]}: {e}")
    return None


# ── Real-time quote ───────────────────────────────────────────────────────────

def get_quote(ticker: str) -> dict | None:
    """
    Return dict with keys: price, change, change_pct, volume, prev_close
    Uses curl_cffi → standard requests fallback.
    """
    # curl_cffi path
    if _CURL_OK:
        data = _curl_get(_YF_CHART.format(ticker=ticker) + "?interval=1d&range=5d")
        if data:
            try:
                meta = data["chart"]["result"][0]["meta"]
                return {
                    "ticker":     ticker,
                    "price":      meta.get("regularMarketPrice"),
                    "prev_close": meta.get("previousClose") or meta.get("chartPreviousClose"),
                    "change":     (meta.get("regularMarketPrice", 0) or 0)
                                  - (meta.get("previousClose") or meta.get("chartPreviousClose") or 0),
                    "change_pct": None,  # computed below
                    "volume":     meta.get("regularMarketVolume"),
                    "source":     "yahoo/curl",
                }
            except Exception:
                pass

    # standard requests fallback
    data = _std_get(_YF_CHART.format(ticker=ticker) + "?interval=1d&range=5d")
    if data:
        try:
            meta = data["chart"]["result"][0]["meta"]
            return {
                "ticker":     ticker,
                "price":      meta.get("regularMarketPrice"),
                "prev_close": meta.get("previousClose") or meta.get("chartPreviousClose"),
                "change":     (meta.get("regularMarketPrice", 0) or 0)
                              - (meta.get("previousClose") or meta.get("chartPreviousClose") or 0),
                "change_pct": None,
                "volume":     meta.get("regularMarketVolume"),
                "source":     "yahoo/requests",
            }
        except Exception:
            pass

    return None


def _finalize(q: dict | None) -> dict | None:
    if q is None:
        return None
    p  = q.get("price")
    pc = q.get("prev_close")
    if p and pc and pc != 0:
        q["change"]     = round(p - pc, 2)
        q["change_pct"] = round((p - pc) / pc * 100, 2)
    elif p and q.get("change"):
        q["change_pct"] = round(q["change"] / (p - q["change"]) * 100, 2) if (p - q["change"]) else 0
    return q


def fetch_quotes_multi(tickers: list[str]) -> pd.DataFrame:
    """Fetch quotes for all tickers in parallel. Returns DataFrame with Price, Change, Change %, Volume."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _fetch_one(ticker: str) -> dict:
        q = _finalize(get_quote(ticker))
        if q and q.get("price"):
            return {
                "Ticker":   ticker,
                "Price":    round(float(q["price"]), 2),
                "Change":   round(float(q.get("change") or 0), 2),
                "Change %": round(float(q.get("change_pct") or 0), 2),
                "Volume":   int(q.get("volume") or 0),
                "Source":   q.get("source", "?"),
            }
        return {"Ticker": ticker, "Price": None, "Change": None, "Change %": None,
                "Volume": None, "Source": "failed"}

    ticker_list = list(tickers)
    rows: list[dict] = [None] * len(ticker_list)  # preserve order
    with ThreadPoolExecutor(max_workers=min(16, len(ticker_list))) as ex:
        futures = {ex.submit(_fetch_one, t): i for i, t in enumerate(ticker_list)}
        for fut in as_completed(futures):
            rows[futures[fut]] = fut.result()
    return pd.DataFrame(rows)


# ── Intraday series ───────────────────────────────────────────────────────────

def fetch_intraday(ticker: str, interval: str = "5m", range_: str = "1d") -> pd.Series:
    """
    Fetch intraday close prices for one ticker (default: 5-minute bars, today).
    Returns a pd.Series indexed by timestamp; empty Series on failure.
    """
    url = _YF_CHART.format(ticker=ticker) + f"?interval={interval}&range={range_}&includePrePost=false"
    data = _curl_get(url) or _std_get(url)
    if not data:
        return pd.Series(dtype=float)
    try:
        result = data["chart"]["result"][0]
        ts     = result.get("timestamp") or []
        closes = result["indicators"]["quote"][0].get("close") or []
        if not ts or not closes:
            return pd.Series(dtype=float)
        s = pd.Series(closes, index=pd.to_datetime(ts, unit="s"), dtype=float).dropna()
        return s
    except Exception:
        return pd.Series(dtype=float)


def fetch_intraday_multi(tickers: list[str], interval: str = "5m", range_: str = "1d") -> dict[str, pd.Series]:
    """Fetch intraday series for many tickers in parallel. Returns {ticker: Series}."""
    from concurrent.futures import ThreadPoolExecutor

    def _one(t: str):
        return t, fetch_intraday(t, interval, range_)

    out: dict[str, pd.Series] = {}
    tickers = list(tickers)
    if not tickers:
        return out
    with ThreadPoolExecutor(max_workers=min(16, len(tickers))) as ex:
        for t, s in ex.map(_one, tickers):
            if not s.empty:
                out[t] = s
    return out


# ── Historical OHLCV ──────────────────────────────────────────────────────────

def fetch_ohlcv_robust(ticker: str, period: str = "1y") -> pd.DataFrame:
    """
    Fetch OHLCV using curl_cffi first, yfinance fallback.
    period: '3mo','6mo','1y','2y','5y'
    """
    period_map = {"3mo": "3mo", "6mo": "6mo", "1y": "1y", "2y": "2y", "5y": "5y"}
    yf_period = period_map.get(period, "1y")

    # curl_cffi path
    if _CURL_OK:
        url = _YF_CHART.format(ticker=ticker) + f"?interval=1d&range={yf_period}"
        data = _curl_get(url)
        if data:
            df = _parse_chart_response(data)
            if not df.empty:
                return df

    # yfinance fallback
    try:
        import yfinance as yf
        df = yf.download(ticker, period=yf_period, progress=False, auto_adjust=True)
        if not df.empty:
            df.index = pd.to_datetime(df.index)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            return df
    except Exception as e:
        print(f"[yf] {ticker}: {e}")

    return pd.DataFrame()


def fetch_history_robust(ticker: str, start: str, monthly: bool = False) -> pd.Series:
    """
    Fetch close price history from start date.
    Returns pd.Series of Close prices, optionally resampled to monthly.
    """
    if _CURL_OK:
        url = _YF_CHART.format(ticker=ticker) + f"?interval={'1mo' if monthly else '1d'}&period1={_to_epoch(start)}&period2={int(time.time())}"
        data = _curl_get(url)
        if data:
            df = _parse_chart_response(data)
            if not df.empty:
                s = df["Close"].dropna()
                if monthly:
                    s = s.resample("ME").last().dropna()
                s.name = ticker
                return s

    # yfinance fallback
    try:
        import yfinance as yf
        df = yf.download(ticker, start=start, progress=False, auto_adjust=True)
        if not df.empty:
            df.index = pd.to_datetime(df.index)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            s = df["Close"].dropna()
            if monthly:
                s = s.resample("ME").last().dropna()
            s.name = ticker
            return s
    except Exception as e:
        print(f"[yf history] {ticker}: {e}")

    return pd.Series(dtype=float)


def _parse_chart_response(data: dict) -> pd.DataFrame:
    try:
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        ohlcv = result["indicators"]["quote"][0]
        adj_close = None
        if "adjclose" in result.get("indicators", {}):
            adj_close = result["indicators"]["adjclose"][0].get("adjclose")
        dates = pd.to_datetime(timestamps, unit="s").normalize()
        df = pd.DataFrame({
            "Open":   ohlcv.get("open"),
            "High":   ohlcv.get("high"),
            "Low":    ohlcv.get("low"),
            "Close":  adj_close if adj_close else ohlcv.get("close"),
            "Volume": ohlcv.get("volume"),
        }, index=dates)
        return df.dropna(subset=["Close"])
    except Exception:
        return pd.DataFrame()


def _to_epoch(date_str: str) -> int:
    return int(datetime.strptime(date_str, "%Y-%m-%d").timestamp())


# ── Relative strength ─────────────────────────────────────────────────────────

def fetch_relative_strength_robust(tickers: list[str], period_days: int = 63) -> pd.DataFrame:
    from concurrent.futures import ThreadPoolExecutor, as_completed
    start = (datetime.now() - timedelta(days=period_days + 15)).strftime("%Y-%m-%d")
    all_t = list(set(tickers + ["SPY"]))
    series: dict[str, pd.Series] = {}

    def _fetch(t):
        return t, fetch_history_robust(t, start)

    with ThreadPoolExecutor(max_workers=min(16, len(all_t))) as ex:
        for t, s in ex.map(_fetch, all_t):
            if not s.empty:
                series[t] = s

    if "SPY" not in series:
        return pd.DataFrame()

    spy_ret = (series["SPY"].iloc[-1] / series["SPY"].iloc[0]) - 1
    rows = []
    for t in tickers:
        if t not in series or len(series[t]) < 5:
            continue
        t_ret = (series[t].iloc[-1] / series[t].iloc[0]) - 1
        rows.append({"Ticker": t, f"RS vs SPY ({period_days}d)": round((t_ret - spy_ret) * 100, 2)})
    return pd.DataFrame(rows)


# ── VIX history ───────────────────────────────────────────────────────────────

def fetch_vix_history_robust(days: int = 252) -> pd.DataFrame:
    start = (datetime.now() - timedelta(days=days + 10)).strftime("%Y-%m-%d")
    s = fetch_history_robust("^VIX", start)
    if s.empty:
        return pd.DataFrame()
    df = s.to_frame(name="VIX")
    df.index = pd.to_datetime(df.index)
    return df.dropna()


# ── Sector performance ────────────────────────────────────────────────────────

SECTOR_ETFS = {
    "Technology":       "XLK",
    "Consumer Disc.":   "XLY",
    "Healthcare":       "XLV",
    "Financials":       "XLF",
    "Energy":           "XLE",
    "Industrials":      "XLI",
    "Materials":        "XLB",
    "Utilities":        "XLU",
    "Real Estate":      "XLRE",
    "Comm. Services":   "XLC",
    "Consumer Staples": "XLP",
}


def fetch_sector_performance_robust(periods: list[str] = ["1d", "5d", "1mo"]) -> pd.DataFrame:
    from concurrent.futures import ThreadPoolExecutor
    period_days = {"1d": 3, "5d": 10, "1mo": 35}
    tickers = list(SECTOR_ETFS.values())
    max_days = max(period_days.values())
    start = (datetime.now() - timedelta(days=max_days + 5)).strftime("%Y-%m-%d")
    rows: list[dict] = []

    def _fetch_etf(etf: str) -> list[dict]:
        local_rows = []
        s = fetch_history_robust(etf, start)
        if s.empty or len(s) < 2:
            return local_rows
        s = s.sort_index()
        sector = next((k for k, v in SECTOR_ETFS.items() if v == etf), etf)
        for period, days in period_days.items():
            if period not in periods:
                continue
            window = s.tail(days)
            if len(window) < 2:
                continue
            ret = (window.iloc[-1] / window.iloc[0] - 1) * 100
            local_rows.append({"Sector": sector, "ETF": etf, "Period": period, "Return %": round(float(ret), 2)})
        return local_rows

    with ThreadPoolExecutor(max_workers=min(11, len(tickers))) as ex:
        for etf_rows in ex.map(_fetch_etf, tickers):
            rows.extend(etf_rows)

    return pd.DataFrame(rows)
