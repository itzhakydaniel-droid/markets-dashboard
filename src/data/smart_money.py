"""
"Big Hands" module: institutional 13F changes, insider trading, dark pool proxy.
Data sources:
  - OpenInsider (public scraper, no key)
  - SEC EDGAR 13F (no key, public API)
  - Unusual Whales API (optional, requires key)
"""
from __future__ import annotations

import os
import requests
import pandas as pd
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

OPENINSIDER_URL = "http://openinsider.com/screener?s={ticker}&o=&pl=&ph=&ll=&lh=&fd=180&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago=&xp=1&xs=1&vl=&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=20&page=1"
SEC_EDGAR_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_COMPANY_SEARCH = "https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&dateRange=custom&startdt={start}&enddt={end}&forms=13F-HR"

UNUSUAL_WHALES_DARKPOOL = "https://phx.unusualwhales.com/api/darkpool/ticker/{ticker}"

HEADERS = {
    "User-Agent": "MarketsDashboard/1.0 (research tool; contact: user@example.com)",
    "Accept": "application/json",
}


def fetch_insider_trades(ticker: str) -> pd.DataFrame:
    """Scrape recent insider transactions from OpenInsider."""
    url = OPENINSIDER_URL.format(ticker=ticker.upper())
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        table = soup.find("table", {"class": "tinytable"})
        if not table:
            return pd.DataFrame()
        rows = []
        headers_row = [th.text.strip() for th in table.find("tr").find_all("th")]
        for tr in table.find_all("tr")[1:]:
            cols = [td.text.strip() for td in tr.find_all("td")]
            if cols:
                rows.append(dict(zip(headers_row, cols)))
        df = pd.DataFrame(rows)
        # Keep key columns
        keep = ["Filing Date", "Trade Date", "Ticker", "Insider Name", "Title",
                "Trade Type", "Price", "Qty", "Owned", "ΔOwn", "Value"]
        keep = [c for c in keep if c in df.columns]
        return df[keep].head(20)
    except Exception as e:
        print(f"[WARN] Insider scrape failed for {ticker}: {e}")
        return pd.DataFrame()


def fetch_dark_pool_prints(ticker: str) -> pd.DataFrame:
    """
    Fetch dark pool / block trade data from Unusual Whales (requires API key).
    Falls back to empty DataFrame if key not set.
    """
    api_key = os.getenv("UNUSUAL_WHALES_API_KEY", "")
    if not api_key or api_key == "your_key_here":
        return pd.DataFrame(
            [{"Info": "Set UNUSUAL_WHALES_API_KEY to enable dark pool data."}]
        )
    url = UNUSUAL_WHALES_DARKPOOL.format(ticker=ticker.upper())
    try:
        resp = requests.get(
            url,
            headers={**HEADERS, "Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        cols = ["date", "ticker", "price", "size", "premium", "sentiment"]
        cols = [c for c in cols if c in df.columns]
        return df[cols].head(30)
    except Exception as e:
        print(f"[WARN] Dark pool fetch failed for {ticker}: {e}")
        return pd.DataFrame()


def fetch_13f_changes(ticker: str) -> pd.DataFrame:
    """
    Pull recent 13F filings mentioning a ticker from SEC EDGAR full-text search.
    Returns a summary DataFrame of filer names and change signals.
    """
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d")
    url = f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker.upper()}%22&dateRange=custom&startdt={start}&enddt={end}&forms=13F-HR"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        hits = resp.json().get("hits", {}).get("hits", [])
        rows = []
        for h in hits[:15]:
            src = h.get("_source", {})
            rows.append({
                "Filed": src.get("file_date", ""),
                "Filer": src.get("display_names", ["Unknown"])[0] if src.get("display_names") else "Unknown",
                "Form": src.get("form_type", "13F-HR"),
                "Period": src.get("period_of_report", ""),
                "Link": f"https://www.sec.gov/Archives/edgar/data/{src.get('entity_id','')}/{src.get('file_num','')}",
            })
        return pd.DataFrame(rows)
    except Exception as e:
        print(f"[WARN] SEC EDGAR 13F fetch failed for {ticker}: {e}")
        return pd.DataFrame()
