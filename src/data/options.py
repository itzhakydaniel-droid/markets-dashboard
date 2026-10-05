"""Black-Scholes Greeks + live option-chain helpers (Yahoo)."""
from __future__ import annotations

import math
from datetime import date, datetime

import numpy as np
import pandas as pd
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


def _nearest(df: pd.DataFrame, k: float) -> pd.Series:
    return df.iloc[(df.strike - k).abs().argsort()].iloc[0]


def put_spread(tk: str, dmin: int = 25, dmax: int = 50, long_otm: float = 0.05, short_otm: float = 0.12) -> dict | None:
    """Bear put spread candidate: buy ~long_otm below spot, sell ~short_otm below spot."""
    h = yf.Ticker(tk).history(period="1y")
    if h.empty:
        return None
    S = float(h.Close.iloc[-1])
    exps = expiries_between(tk, dmin, dmax)
    if not exps:
        return None
    exp = exps[0]
    d = chain(tk, exp, S)
    puts = d[(d.kind == "P") & (d.mid > 0)]
    if puts.empty:
        return None
    lp = _nearest(puts, S * (1 - long_otm))
    sp = _nearest(puts[puts.strike < lp.strike], S * (1 - short_otm)) if (puts.strike < lp.strike).any() else None
    if sp is None:
        return None
    atm = _nearest(puts, S)
    cost = lp.mid - sp.mid
    width = lp.strike - sp.strike
    return dict(
        ticker=tk, spot=S, expiry=exp, dte=int(lp.dte),
        long_k=lp.strike, short_k=sp.strike, cost=cost, cost_pct=cost / S,
        max_pay=width - cost, pay_ratio=(width - cost) / cost if cost > 0 else np.nan,
        breakeven=lp.strike - cost, iv_long=lp.iv, iv_short=sp.iv, iv_atm=atm.iv,
        skew=sp.iv - atm.iv, rv=realized_vol(h.Close),
        delta=lp.delta - sp.delta, theta=lp.theta - sp.theta, vega=lp.vega - sp.vega,
        sma50=float(h.Close.tail(50).mean()), sma200=float(h.Close.tail(200).mean()),
    )
