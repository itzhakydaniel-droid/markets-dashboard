"""
REAL CTA / fund positioning — CFTC Commitments of Traders (official, free API).

Sources (publicreporting.cftc.gov, Socrata — no key required):
  gpe5-46if  Traders in Financial Futures (TFF), Futures-Only:
             "Leveraged Funds" = hedge funds / CTAs / managed futures.
  72hh-3qpy  Disaggregated (commodities), Futures-Only:
             "Managed Money" = CTAs / commodity funds.

Published weekly (Friday, positions as of Tuesday) — this is the real,
regulator-collected positioning data behind every "CTA positioning" note.
"""
from __future__ import annotations

import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

_TFF_URL    = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"
_DISAGG_URL = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json"
_HEADERS    = {"User-Agent": "MarketsDashboard/1.0"}

# market label → (dataset, filter clause, long col, short col)
MARKETS: dict[str, dict] = {
    "S&P 500 (E-mini)": {
        "url": _TFF_URL, "where": "contract_market_name='E-MINI S&P 500'",
        "long": "lev_money_positions_long", "short": "lev_money_positions_short",
        "group": "Leveraged Funds",
    },
    "Nasdaq 100 (mini)": {
        "url": _TFF_URL, "where": "contract_market_name='NASDAQ MINI'",
        "long": "lev_money_positions_long", "short": "lev_money_positions_short",
        "group": "Leveraged Funds",
    },
    "Russell 2000 (E-mini)": {
        "url": _TFF_URL, "where": "contract_market_name='RUSSELL E-MINI'",
        "long": "lev_money_positions_long", "short": "lev_money_positions_short",
        "group": "Leveraged Funds",
    },
    "10Y Treasury Note": {
        "url": _TFF_URL, "where": "contract_market_name='UST 10Y NOTE'",
        "long": "lev_money_positions_long", "short": "lev_money_positions_short",
        "group": "Leveraged Funds",
    },
    "US Treasury Bond": {
        "url": _TFF_URL, "where": "contract_market_name='UST BOND'",
        "long": "lev_money_positions_long", "short": "lev_money_positions_short",
        "group": "Leveraged Funds",
    },
    "Gold": {
        "url": _DISAGG_URL, "where": "commodity_name='GOLD'",
        "long": "m_money_positions_long_all", "short": "m_money_positions_short_all",
        "group": "Managed Money",
    },
    "WTI Crude Oil": {
        "url": _DISAGG_URL, "where": "contract_market_name='WTI-PHYSICAL'",
        "long": "m_money_positions_long_all", "short": "m_money_positions_short_all",
        "group": "Managed Money",
    },
}


def _classify(pctile: float) -> tuple[str, str]:
    if pctile >= 85: return ("MAX LONG — crowded, unwind risk", "#ef4444")
    if pctile >= 60: return ("NET LONG — trend following in", "#10b981")
    if pctile >= 40: return ("NEUTRAL — no conviction", "#f59e0b")
    if pctile >= 15: return ("NET SHORT — de-grossed", "#f97316")
    return ("MAX SHORT — squeeze fuel", "#0CABC2")


def _fetch_market(item) -> dict | None:
    label, cfg = item
    params = {
        "$select": f"report_date_as_yyyy_mm_dd,contract_market_name,"
                   f"{cfg['long']},{cfg['short']},open_interest_all",
        "$where":  cfg["where"],
        "$order":  "report_date_as_yyyy_mm_dd DESC",
        "$limit":  "900",
    }
    try:
        r = requests.get(cfg["url"], params=params, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        rows = r.json()
        if not rows:
            return None
        df = pd.DataFrame(rows)
        df["date"]  = pd.to_datetime(df["report_date_as_yyyy_mm_dd"])
        for c in (cfg["long"], cfg["short"], "open_interest_all"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        # commodities can return several contract variants — keep the deepest book per week
        df = (df.sort_values("open_interest_all", ascending=False)
                .drop_duplicates("date").sort_values("date"))
        df["net"] = df[cfg["long"]] - df[cfg["short"]]
        df = df.dropna(subset=["net"]).tail(160)          # ~3 years of weekly reports
        if len(df) < 10:
            return None

        net_now  = float(df["net"].iloc[-1])
        net_prev = float(df["net"].iloc[-2])
        oi       = float(df["open_interest_all"].iloc[-1]) or 1.0
        pctile   = float((df["net"] <= net_now).mean() * 100)
        regime, color = _classify(pctile)

        return {
            "Market":      label,
            "Group":       cfg["group"],
            "Contract":    str(df["contract_market_name"].iloc[-1]),
            "Long":        int(df[cfg["long"]].iloc[-1]),
            "Short":       int(df[cfg["short"]].iloc[-1]),
            "Net":         int(net_now),
            "Change_1w":   int(net_now - net_prev),
            "Net_pct_OI":  round(net_now / oi * 100, 1),
            "Pctile_3y":   round(pctile, 0),
            "Regime":      regime,
            "Color":       color,
            "AsOf":        df["date"].iloc[-1].strftime("%d %b %Y"),
            "History":     df.set_index("date")["net"],
        }
    except Exception:
        return None


def fetch_cta_positioning() -> dict:
    """Fetch real weekly CTA/fund positioning for all configured markets in parallel."""
    out: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=len(MARKETS)) as ex:
        for res in ex.map(_fetch_market, MARKETS.items()):
            if res is not None:
                out[res["Market"]] = res
    return out
