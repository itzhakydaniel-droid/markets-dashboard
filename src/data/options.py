"""Black-Scholes Greeks + live option-chain helpers (Yahoo, with CBOE delayed-quote fallback)."""
from __future__ import annotations

import math
import re
from datetime import date, datetime

import numpy as np
import pandas as pd
import requests
import yfinance as yf

R = 0.04  # risk-free (13W bill ~4.0%)


def _n(x):
    return math.exp(-x * x / 2) / math.sqrt(2 * math.pi)


def _N(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def greeks(S, K, T, iv, kind):
    if T <= 0 or iv <= 0:
        return dict(delta=np.nan, gamma=np.nan, theta=np.nan, vega=np.nan)
    d1 = (math.log(S / K) + (R + iv * iv / 2) * T) / (iv * math.sqrt(T))
    d2 = d1 - iv * math.sqrt(T)
    gamma = _n(d1) / (S * iv * math.sqrt(T))
    vega = S * _n(d1) * math.sqrt(T) / 100  # per 1 vol point
    if kind == "C":
        delta = _N(d1)
        theta = (-S * _n(d1) * iv / (2 * math.sqrt(T)) - R * K * math.exp(-R * T) * _N(d2)) / 365
    else:
        delta = _N(d1) - 1
        theta = (-S * _n(d1) * iv / (2 * math.sqrt(T)) + R * K * math.exp(-R * T) * _N(-d2)) / 365
    return dict(delta=delta, gamma=gamma, theta=theta, vega=vega)


def realized_vol(close: pd.Series, days: int = 30) -> float:
    return float(np.log(close).diff().tail(days).std() * math.sqrt(252))


def chain(tk: str, exp: str, S: float) -> pd.DataFrame:
    """One expiry, calls+puts, with mid price and Greeks."""
    ch = yf.Ticker(tk).option_chain(exp)
    dte = (datetime.strptime(exp, "%Y-%m-%d").date() - date.today()).days
    T = max(dte, 0.5) / 365
    rows = []
    for kind, df in (("C", ch.calls), ("P", ch.puts)):
        for _, r in df.iterrows():
            mid = (r.bid + r.ask) / 2 if r.bid > 0 and r.ask > 0 else r.lastPrice
            rows.append(dict(kind=kind, strike=float(r.strike), mid=float(mid), iv=float(r.impliedVolatility),
                             oi=r.openInterest, dte=dte, **greeks(S, r.strike, T, r.impliedVolatility, kind)))
    return pd.DataFrame(rows)


def expiries_between(tk: str, dmin: int, dmax: int) -> list[str]:
    today = date.today()
    out = []
    for e in yf.Ticker(tk).options:
        d = (datetime.strptime(e, "%Y-%m-%d").date() - today).days
        if dmin <= d <= dmax:
            out.append(e)
    return out


# ── CBOE fallback (Yahoo's options endpoint is often blocked from cloud hosts) ──
_CBOE_URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/{}.json"
_OCC = re.compile(r"^(?P<root>[A-Z.]+?)(?P<ymd>\d{6})(?P<kind>[CP])(?P<k>\d{8})$")


def cboe_chain_all(tk: str) -> pd.DataFrame:
    """All expiries from CBOE delayed quotes, in the same columns as chain()."""
    r = requests.get(_CBOE_URL.format(tk.upper()), headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    r.raise_for_status()
    today = date.today()
    rows = []
    for o in r.json()["data"]["options"]:
        m = _OCC.match(o["option"])
        if not m:
            continue
        exp = datetime.strptime(m["ymd"], "%y%m%d").date()
        bid, ask = o.get("bid") or 0, o.get("ask") or 0
        mid = (bid + ask) / 2 if bid > 0 and ask > 0 else (o.get("last_trade_price") or 0)
        rows.append(dict(expiry=exp.isoformat(), kind=m["kind"], strike=int(m["k"]) / 1000, mid=float(mid),
                         iv=float(o.get("iv") or 0), oi=o.get("open_interest"), dte=(exp - today).days,
                         delta=o.get("delta"), gamma=o.get("gamma"), theta=o.get("theta"), vega=o.get("vega")))
    return pd.DataFrame(rows)


def _nearest(df: pd.DataFrame, k: float) -> pd.Series:
    return df.iloc[(df.strike - k).abs().argsort()].iloc[0]


def put_spread(tk: str, dmin: int = 25, dmax: int = 50, long_otm: float = 0.05, short_otm: float = 0.12) -> dict | None:
    """Bear put spread candidate: buy ~long_otm below spot, sell ~short_otm below spot.
    Tries Yahoo first, then CBOE delayed quotes."""
    h = yf.download(tk, period="1y", progress=False, auto_adjust=True)["Close"]
    h = h.iloc[:, 0] if isinstance(h, pd.DataFrame) else h
    h = h.dropna()
    if h.empty:
        return None
    S = float(h.iloc[-1])
    d, exp, source = None, None, "Yahoo"
    try:
        exps = expiries_between(tk, dmin, dmax)
        if exps:
            exp = exps[0]
            d = chain(tk, exp, S)
    except Exception:
        d = None
    if d is None or d.empty or (d.mid > 0).sum() < 5:
        source = "CBOE"
        allc = cboe_chain_all(tk)
        allc = allc[(allc.dte >= dmin) & (allc.dte <= dmax)]
        if allc.empty:
            return None
        exp = allc.expiry.min()
        d = allc[allc.expiry == exp]
    puts = d[(d.kind == "P") & (d.mid > 0)]
    if puts.empty or not (puts.strike < S * (1 - long_otm)).any():
        return None
    lp = _nearest(puts, S * (1 - long_otm))
    lower = puts[puts.strike < lp.strike]
    if lower.empty:
        return None
    sp = _nearest(lower, S * (1 - short_otm))
    atm = _nearest(puts, S)
    cost = lp.mid - sp.mid
    width = lp.strike - sp.strike
    return dict(
        ticker=tk, spot=S, expiry=exp, dte=int(lp.dte), source=source,
        long_k=lp.strike, short_k=sp.strike, cost=cost, cost_pct=cost / S,
        max_pay=width - cost, pay_ratio=(width - cost) / cost if cost > 0 else np.nan,
        breakeven=lp.strike - cost, iv_long=lp.iv, iv_short=sp.iv, iv_atm=atm.iv,
        skew=sp.iv - atm.iv, rv=realized_vol(h),
        delta=lp.delta - sp.delta, theta=lp.theta - sp.theta, vega=lp.vega - sp.vega,
        sma50=float(h.tail(50).mean()), sma200=float(h.tail(200).mean()),
    )
