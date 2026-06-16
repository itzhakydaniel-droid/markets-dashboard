"""
Market data module — delegates to price_fetcher for all real-time and historical data.
price_fetcher uses curl_cffi (browser impersonation) as primary source,
yfinance as fallback. No rate-limit issues.
"""
from __future__ import annotations

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta

from src.data.price_fetcher import (
    fetch_quotes_multi,
    fetch_ohlcv_robust,
    fetch_relative_strength_robust,
    fetch_vix_history_robust,
    fetch_sector_performance_robust,
    SECTOR_ETFS,
)

DEFAULT_WATCHLIST = [
    "SMCI", "GOOGL", "NVDA", "AAPL", "MSFT",
    "ARKX", "UFO", "ROKT",
    "SPY", "QQQ", "IWM",
]


def fetch_quotes(tickers: list[str]) -> pd.DataFrame:
    return fetch_quotes_multi(tickers)


def fetch_relative_strength(tickers: list[str], period_days: int = 63) -> pd.DataFrame:
    return fetch_relative_strength_robust(tickers, period_days)


def fetch_vix_history(days: int = 252) -> pd.DataFrame:
    return fetch_vix_history_robust(days)


def fetch_sector_performance(periods: list[str] = ["1d", "5d", "1mo"]) -> pd.DataFrame:
    return fetch_sector_performance_robust(periods)


def fetch_breadth_data(sample_tickers: list[str] | None = None) -> dict:
    """Compute breadth metrics from a sample universe using curl_cffi."""
    from src.data.price_fetcher import fetch_history_robust

    if sample_tickers is None:
        # Use a focused 25-stock universe — fast with curl_cffi
        sample_tickers = [
            "AAPL","MSFT","NVDA","AMZN","GOOGL","META","LLY","AVGO","JPM","UNH",
            "XOM","V","TSLA","PG","MA","COST","HD","CVX","ABBV","WMT",
            "BAC","NFLX","KO","TXN","AMD",
        ]

    end   = datetime.now()
    start = (end - timedelta(days=220)).strftime("%Y-%m-%d")

    # Fetch all tickers in parallel via curl_cffi
    from concurrent.futures import ThreadPoolExecutor
    series_map: dict[str, pd.Series] = {}

    def _fetch(ticker: str):
        try:
            s = fetch_history_robust(ticker, start)
            if not s.empty and len(s) >= 50:
                return ticker, s
        except Exception:
            pass
        return ticker, None

    with ThreadPoolExecutor(max_workers=min(16, len(sample_tickers))) as ex:
        for ticker, s in ex.map(_fetch, sample_tickers):
            if s is not None:
                series_map[ticker] = s

    if not series_map:
        return {}

    above_50 = above_200 = total = 0
    ad_line: list[dict] = []

    for ticker, series in series_map.items():
        series = series.dropna()
        if len(series) < 50:
            continue
        total += 1
        price = float(series.iloc[-1])
        if price > float(series.tail(50).mean()):
            above_50 += 1
        if len(series) >= 200 and price > float(series.tail(200).mean()):
            above_200 += 1

    # Build A/D line from the common date range
    all_series = pd.DataFrame(series_map)
    daily_rets = all_series.pct_change()
    for date, row in daily_rets.tail(30).iterrows():
        valid = row.dropna()
        adv = int((valid > 0).sum())
        dec = int((valid < 0).sum())
        ad_line.append({"Date": date, "Advances": adv, "Declines": dec, "Net": adv - dec})

    ad_df = pd.DataFrame(ad_line)
    if not ad_df.empty:
        ad_df["Cumulative_AD"] = ad_df["Net"].cumsum()

    return {
        "pct_above_50d":  round((above_50  / total) * 100, 1) if total else 0,
        "pct_above_200d": round((above_200 / total) * 100, 1) if total else 0,
        "advance_decline": ad_df,
        "sample_size": total,
    }


def fetch_ohlcv(ticker: str, period: str = "1y") -> pd.DataFrame:
    return fetch_ohlcv_robust(ticker, period)


def fetch_fundamentals(ticker: str) -> dict:
    try:
        t = yf.Ticker(ticker)
        info = t.info
        return {
            "name":           info.get("longName", ticker),
            "sector":         info.get("sector", "N/A"),
            "industry":       info.get("industry", "N/A"),
            "market_cap":     info.get("marketCap"),
            "pe_ratio":       info.get("trailingPE"),
            "fwd_pe":         info.get("forwardPE"),
            "ps_ratio":       info.get("priceToSalesTrailing12Months"),
            "pb_ratio":       info.get("priceToBook"),
            "roe":            info.get("returnOnEquity"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth":info.get("earningsGrowth"),
            "profit_margin":  info.get("profitMargins"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio":  info.get("currentRatio"),
            "52w_high":       info.get("fiftyTwoWeekHigh"),
            "52w_low":        info.get("fiftyTwoWeekLow"),
            "avg_volume":     info.get("averageVolume"),
            "beta":           info.get("beta"),
            "summary":        (info.get("longBusinessSummary") or "")[:500],
            "recommendation": info.get("recommendationKey", "N/A"),
            "target_price":   info.get("targetMeanPrice"),
        }
    except Exception as e:
        return {"error": str(e)}
