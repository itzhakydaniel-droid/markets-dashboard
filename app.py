"""
Institutional-Grade Macroeconomics & Stock Analysis Dashboard
Run with: streamlit run app.py
"""
from __future__ import annotations

import os, sys
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
sys.path.insert(0, os.path.dirname(__file__))

# ── Streamlit Cloud secrets → os.environ bridge ───────────────────────────────
# When deployed on Streamlit Community Cloud, secrets are in st.secrets (not .env).
# We push them into os.environ so every downstream module reads them transparently.
try:
    import streamlit as _st
    for _k in ["FRED_API_KEY","ANTHROPIC_API_KEY","MAKE_WEBHOOK_URL",
                "DISCORD_WEBHOOK_URL","UNUSUAL_WHALES_API_KEY","REFRESH_INTERVAL_SECONDS"]:
        if _k in _st.secrets and not os.getenv(_k):
            os.environ[_k] = str(_st.secrets[_k])
except Exception:
    pass

from src.data.macro_data import fetch_macro_indicators
from src.data.market_data import (
    fetch_quotes, fetch_relative_strength, fetch_vix_history,
    fetch_sector_performance, fetch_breadth_data, fetch_ohlcv, fetch_fundamentals,
    DEFAULT_WATCHLIST,
)
from src.data.smart_money import fetch_insider_trades, fetch_dark_pool_prints, fetch_13f_changes
from src.data.cta_proxy import fetch_cta_exposure_proxy, fetch_vix_term_structure
from src.utils.scoring import score_all_indicators, interpret_score
from src.utils.alerts import PriceAlert, check_alerts, send_webhook
from src.components.charts import (
    macro_gauge, score_breakdown_bar,
    vix_chart, vix_term_bar,
    sector_heatmap, sector_bars,
    stocks_heatmap, watchlist_performance_chart,
    advance_decline_chart, candlestick_chart,
    cta_exposure_chart, macro_indicator_sparkline,
    kill_zone_radar, macro_liquidity_chart,
)
from src.data.ai_engine import (
    ask_ai, generate_market_brief, analyze_ticker,
    _build_market_context, is_ai_available,
)
from src.data.black_raven import (
    TIER_UNIVERSE, score_catalyst, save_catalyst, load_catalysts,
    fetch_tier_radar, fetch_macro_matrix, compute_hedge_params,
    compute_rsi,
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Markets Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
.main { background: #080c14; }
.block-container { padding: 0.8rem 2rem 2rem; max-width: 1800px; }

/* Hide sidebar */
section[data-testid="stSidebar"]          { display: none !important; }
button[data-testid="collapsedControl"]    { display: none !important; }
[data-testid="stSidebarCollapsedControl"] { display: none !important; }

/* Cards */
.card {
    background: linear-gradient(135deg,#111827 0%,#0f172a 100%);
    border: 1px solid #1e2533; border-radius: 14px; padding: 18px 20px; margin-bottom: 10px;
}
.card-sm {
    background: #111827; border: 1px solid #1e2533; border-radius: 10px;
    padding: 12px 16px; margin-bottom: 8px;
}
.card-accent-green  { border-left: 3px solid #10b981 !important; }
.card-accent-red    { border-left: 3px solid #ef4444 !important; }
.card-accent-yellow { border-left: 3px solid #f59e0b !important; }
.card-accent-blue   { border-left: 3px solid #3b82f6 !important; }

/* KPI tiles */
.kpi-tile {
    background: #111827; border: 1px solid #1e2533; border-radius: 12px;
    padding: 13px 12px; text-align: center; overflow: hidden;
}
.kpi-label { font-size: .66rem; color: #6b7280; text-transform: uppercase;
             letter-spacing: .08em; font-weight: 600; margin-bottom: 3px; }
.kpi-value { font-size: 1.35rem; font-weight: 800; color: #f1f5f9; line-height: 1.1; }
.kpi-delta-pos { font-size: .75rem; color: #10b981; font-weight: 600; margin-top: 2px; }
.kpi-delta-neg { font-size: .75rem; color: #ef4444; font-weight: 600; margin-top: 2px; }

/* Indicator cards */
.ind-card {
    background: #111827; border: 1px solid #1e2533; border-radius: 12px;
    padding: 14px 16px; margin-bottom: 8px;
}
.ind-name  { font-size: .78rem; color: #9ca3af; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; }
.ind-value { font-size: 1.3rem; font-weight: 800; color: #f1f5f9; margin: 2px 0; }
.ind-score-bar-bg   { background: #1e2533; border-radius: 99px; height: 6px; margin-top: 8px; }
.ind-score-bar-fill { border-radius: 99px; height: 6px; }
.score-badge {
    display: inline-block; font-size: .7rem; font-weight: 700; padding: 2px 9px;
    border-radius: 99px; float: right; margin-top: -2px;
}

/* Regime banner */
.regime-banner {
    border-radius: 14px; padding: 20px 28px; margin-bottom: 4px;
    display: flex; align-items: center; gap: 20px;
}

/* Pills */
.pill {
    display: inline-block; font-size: .65rem; font-weight: 700; padding: 3px 10px;
    border-radius: 99px; text-transform: uppercase; letter-spacing: .06em;
}
.pill-green  { background: #10b98122; color: #10b981; }
.pill-red    { background: #ef444422; color: #ef4444; }
.pill-yellow { background: #f59e0b22; color: #f59e0b; }
.pill-blue   { background: #3b82f622; color: #3b82f6; }
.pill-gray   { background: #6b728022; color: #6b7280; }
.pill-purple { background: #8b5cf622; color: #8b5cf6; }

/* Section headers */
.section-title {
    font-size: .7rem; font-weight: 700; color: #6b7280; text-transform: uppercase;
    letter-spacing: .12em; margin: 18px 0 10px; padding-bottom: 6px;
    border-bottom: 1px solid #1e2533;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] { gap: 4px; background: #0d1117; border-bottom: 1px solid #1e2533; padding: 0 4px; }
.stTabs [data-baseweb="tab"] { background: transparent; border-radius: 8px 8px 0 0;
    padding: 10px 18px; font-weight: 600; font-size: .82rem; color: #6b7280; }
.stTabs [aria-selected="true"] { background: #111827 !important; color: #f1f5f9 !important;
    border-top: 2px solid #3b82f6 !important; }

/* Input overrides */
.stTextArea textarea, .stTextInput input {
    background: #0d1117 !important; border: 1px solid #1e2533 !important;
    border-radius: 8px !important; color: #f1f5f9 !important; font-size: .85rem !important;
}
.stSelectbox div[data-baseweb="select"] > div {
    background: #0d1117 !important; border: 1px solid #1e2533 !important; color: #f1f5f9 !important;
}
.stButton > button {
    background: #1e2533 !important; color: #f1f5f9 !important; border: 1px solid #2d3748 !important;
    border-radius: 8px !important; font-weight: 600 !important; font-size: .82rem !important;
}
.stButton > button:hover { background: #2d3748 !important; border-color: #3b82f6 !important; }

/* DataFrame */
.stDataFrame { border-radius: 12px !important; overflow: hidden; }
.stDataFrame thead th {
    background: #0d1117 !important; color: #9ca3af !important;
    font-size: .72rem !important; text-transform: uppercase; font-weight: 700;
    letter-spacing: .06em; border-bottom: 1px solid #1e2533 !important;
}
.stDataFrame tbody tr { border-bottom: 1px solid #1e2533 !important; }
.stDataFrame tbody tr:hover { background: #1a2236 !important; }
.stDataFrame tbody td { color: #f1f5f9 !important; font-size: .85rem !important; }

/* AI chat */
.ai-message {
    background: linear-gradient(135deg,#0f172a,#111827); border: 1px solid #1e3a5f;
    border-radius: 12px; padding: 16px 20px; margin-bottom: 10px;
    border-left: 3px solid #3b82f6;
}
.ai-question {
    background: #111827; border: 1px solid #1e2533; border-radius: 12px;
    padding: 14px 18px; margin-bottom: 8px; border-left: 3px solid #8b5cf6;
    font-size: .88rem; color: #d1d5db;
}

/* Metric overrides */
div[data-testid="stMetricValue"]  { font-size: 1.3rem !important; font-weight: 800 !important; color: #f1f5f9 !important; }
div[data-testid="stMetricLabel"]  { font-size: .72rem !important; color: #6b7280 !important; text-transform: uppercase; }
div[data-testid="stMetricDelta"]  { font-size: .8rem !important; font-weight: 600 !important; }

/* Radio buttons */
.stRadio > div { gap: 8px; }
.stRadio label { background: #111827; border: 1px solid #1e2533; border-radius: 8px;
    padding: 6px 16px !important; color: #9ca3af !important; font-weight: 600 !important;
    font-size: .8rem !important; }
.stRadio label:has(input:checked) { background: #1e3a5f !important;
    border-color: #3b82f6 !important; color: #f1f5f9 !important; }

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #1e2533; border-radius: 3px; }
</style>
""", unsafe_allow_html=True)

REFRESH_SEC = int(os.getenv("REFRESH_INTERVAL_SECONDS", 300))

# ── Session state ─────────────────────────────────────────────────────────────
for k, v in [
    ("watchlist", DEFAULT_WATCHLIST.copy()),
    ("alerts", []),
    ("last_refresh", None),
    ("selected_ticker", "NVDA"),
    ("ai_history", []),
]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── Cached loaders ────────────────────────────────────────────────────────────
@st.cache_data(ttl=REFRESH_SEC, show_spinner=False)
def load_macro():
    return fetch_macro_indicators()

@st.cache_data(ttl=90, show_spinner=False)          # real-time quotes — 90s is fine intraday
def load_quotes(tickers):
    return fetch_quotes(list(tickers))

@st.cache_data(ttl=300, show_spinner=False)          # RS changes slowly
def load_rs(tickers):
    return fetch_relative_strength(list(tickers))

@st.cache_data(ttl=120, show_spinner=False)
def load_vix():
    return fetch_vix_history(252)

@st.cache_data(ttl=300, show_spinner=False)
def load_sector_perf():
    return fetch_sector_performance(["1d", "5d", "1mo"])

@st.cache_data(ttl=600, show_spinner=False)          # breadth is slow to compute — cache longer
def load_breadth():
    return fetch_breadth_data()

@st.cache_data(ttl=600, show_spinner=False)
def load_cta():
    return fetch_cta_exposure_proxy()

@st.cache_data(ttl=3600, show_spinner=False)
def load_smart_money(ticker):
    return fetch_insider_trades(ticker), fetch_dark_pool_prints(ticker), fetch_13f_changes(ticker)

@st.cache_data(ttl=3600, show_spinner=False)
def load_fundamentals(ticker):
    return fetch_fundamentals(ticker)

@st.cache_data(ttl=300, show_spinner=False)
def load_ohlcv(ticker, period="1y"):
    return fetch_ohlcv(ticker, period)

@st.cache_data(ttl=180, show_spinner=False)          # Black Raven — shared by Kill Zone + Execution modules
def load_tier_radar():
    return fetch_tier_radar()

@st.cache_data(ttl=120, show_spinner=False)
def load_macro_matrix():
    return fetch_macro_matrix()

@st.cache_data(ttl=300, show_spinner=False)
def load_oil_price():
    from src.data.price_fetcher import fetch_history_robust
    from datetime import timedelta
    s = fetch_history_robust("CL=F", (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"))
    return float(s.iloc[-1]) if s is not None and not s.empty else None

# ── Helpers ───────────────────────────────────────────────────────────────────
def kpi(label, value, delta=None, delta_positive=None, accent=None):
    if delta is not None:
        pos = delta_positive if delta_positive is not None else (delta >= 0 if isinstance(delta, (int, float)) else True)
        dc = "kpi-delta-pos" if pos else "kpi-delta-neg"
        dh = f"<div class='{dc}'>{'+' if isinstance(delta,(int,float)) and delta>0 else ''}{delta}</div>"
    else:
        dh = ""
    border = f"border-top:2px solid {accent};" if accent else ""
    st.markdown(f"""<div class='kpi-tile' style='{border}'>
        <div class='kpi-label'>{label}</div>
        <div class='kpi-value'>{value}</div>{dh}
    </div>""", unsafe_allow_html=True)

def section(title):
    st.markdown(f"<div class='section-title'>{title}</div>", unsafe_allow_html=True)

def pill(text, color="gray"):
    return f"<span class='pill pill-{color}'>{text}</span>"

def fmt_big(n):
    if n is None: return "—"
    if n >= 1e12: return f"${n/1e12:.2f}T"
    if n >= 1e9:  return f"${n/1e9:.2f}B"
    if n >= 1e6:  return f"${n/1e6:.2f}M"
    return f"${n:,.0f}"

def color_pct(v):
    if isinstance(v, (int, float)):
        return "#10b981" if v >= 0 else "#ef4444"
    return "#6b7280"

# ══════════════════════════════════════════════════════════════════════════════
# PREFETCH all header data — run slow loaders in parallel threads
# ══════════════════════════════════════════════════════════════════════════════
now = datetime.now()
fred_key  = os.getenv("FRED_API_KEY", "")
fred_live = bool(fred_key) and "your_fred" not in fred_key
make_ok   = bool(os.getenv("MAKE_WEBHOOK_URL","")) and "your_webhook" not in os.getenv("MAKE_WEBHOOK_URL","")
ai_ok     = is_ai_available()

# These are all cached — first call hits the network, subsequent calls are instant.
# Fire them concurrently so cold-start only pays the max single latency, not the sum.
from concurrent.futures import ThreadPoolExecutor as _TPE
with _TPE(max_workers=5) as _ex:
    _f_quotes  = _ex.submit(load_quotes, ("SPY","QQQ","IWM","^VIX"))
    _f_vix     = _ex.submit(load_vix)
    _f_breadth = _ex.submit(load_breadth)
    _f_cta     = _ex.submit(load_cta)
    _f_sector  = _ex.submit(load_sector_perf)
    _hdr_quotes = _f_quotes.result()
    _hdr_vix    = _f_vix.result()
    _breadth    = _f_breadth.result()
    _cta_data   = _f_cta.result()
    _sector_df  = _f_sector.result()

_hdr_map = dict(zip(_hdr_quotes["Ticker"], _hdr_quotes.to_dict("records"))) if not _hdr_quotes.empty else {}

# ══════════════════════════════════════════════════════════════════════════════
# HEADER — Title + pills + controls
# ══════════════════════════════════════════════════════════════════════════════
title_col, pills_col = st.columns([3, 5])

with title_col:
    st.markdown(f"""
    <div style='padding:6px 0 2px'>
        <div style='font-size:1.45rem;font-weight:800;color:#f1f5f9;letter-spacing:-.03em'>
            📊 Markets Intelligence
        </div>
        <div style='font-size:.72rem;color:#6b7280;margin-top:3px'>
            {now.strftime('%A %d %b %Y')} &nbsp;•&nbsp; {now.strftime('%H:%M')} ET &nbsp;•&nbsp; Auto-refresh {REFRESH_SEC//60}m
        </div>
    </div>""", unsafe_allow_html=True)

with pills_col:
    st.markdown(f"""
    <div style='padding-top:10px;display:flex;gap:6px;flex-wrap:wrap;align-items:center'>
        {"<span class='pill pill-green'>● FRED LIVE</span>" if fred_live else "<span class='pill pill-red'>● FRED OFFLINE</span>"}
        <span class='pill pill-green'>● YAHOO FINANCE</span>
        {"<span class='pill pill-green'>● WEBHOOK</span>" if make_ok else "<span class='pill pill-gray'>● WEBHOOK OFF</span>"}
        <span class='pill pill-blue'>● SEC EDGAR</span>
        {"<span class='pill pill-purple'>● AI ACTIVE</span>" if ai_ok else "<span class='pill pill-gray'>● AI OFFLINE</span>"}
    </div>""", unsafe_allow_html=True)

# Watchlist controls (flat)
wl_c1, wl_c2, wl_c3 = st.columns([6, 2, 1])
with wl_c1:
    wl_input = st.text_input(
        "Watchlist", value=", ".join(st.session_state.watchlist),
        label_visibility="collapsed", placeholder="Tickers: NVDA, AAPL, SPY, QQQ…"
    )
with wl_c2:
    if st.button("Update Watchlist", use_container_width=True):
        st.session_state.watchlist = [t.strip().upper() for t in wl_input.split(",") if t.strip()]
        st.cache_data.clear(); st.rerun()
with wl_c3:
    if st.button("⟳", use_container_width=True, help="Force refresh all data"):
        st.cache_data.clear(); st.rerun()

st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TOP BAR — ROW 1: SPY / QQQ / IWM / VIX / Macro
# ══════════════════════════════════════════════════════════════════════════════
r1 = st.columns(5)
for col, ticker, label in zip(r1[:3], ["SPY","QQQ","IWM"], ["S&P 500","Nasdaq 100","Russell 2000"]):
    with col:
        r = _hdr_map.get(ticker, {})
        p   = r.get("Price"); chg = r.get("Change %")
        p_s = f"${p:,.2f}" if isinstance(p,(int,float)) else "—"
        c_s = f"{chg:+.2f}%" if isinstance(chg,(int,float)) else "—"
        col_s = color_pct(chg)
        st.markdown(f"""<div class='kpi-tile'>
            <div class='kpi-label'>{label}</div>
            <div class='kpi-value'>{p_s}</div>
            <div style='font-size:.75rem;color:{col_s};font-weight:600'>{c_s}</div>
        </div>""", unsafe_allow_html=True)

with r1[3]:
    vix_val  = float(_hdr_vix["VIX"].iloc[-1]) if not _hdr_vix.empty else 0
    vix_prev = float(_hdr_vix["VIX"].iloc[-2]) if len(_hdr_vix)>1 else vix_val
    vix_chg  = vix_val - vix_prev
    vix_rgm  = "EXTREME FEAR" if vix_val>30 else "FEAR" if vix_val>20 else "NORMAL" if vix_val>15 else "COMPLACENT"
    vc = "#ef4444" if vix_val>25 else "#f59e0b" if vix_val>18 else "#10b981"
    st.markdown(f"""<div class='kpi-tile' style='border-top:2px solid {vc}'>
        <div class='kpi-label'>VIX Fear Index</div>
        <div class='kpi-value' style='color:{vc}'>{vix_val:.2f}</div>
        <div style='font-size:.68rem;color:{vc};font-weight:700'>
            {vix_rgm} &nbsp;<span style='color:{"#10b981" if vix_chg<0 else "#ef4444"}'>{vix_chg:+.2f}</span>
        </div>
    </div>""", unsafe_allow_html=True)

with r1[4]:
    if fred_live:
        try:
            _pm = load_macro(); _ps, _pt = score_all_indicators(_pm); _pi = interpret_score(_pt)
            mc = _pi["color"]
            st.markdown(f"""<div class='kpi-tile' style='border-top:2px solid {mc}'>
                <div class='kpi-label'>Macro Score</div>
                <div class='kpi-value' style='color:{mc}'>{_pt}/70</div>
                <div style='font-size:.68rem;color:{mc};font-weight:700'>{_pi["emoji"]} {_pi["label"].split("—")[0].strip()}</div>
            </div>""", unsafe_allow_html=True)
        except Exception:
            kpi("Macro Score","—")
    else:
        st.markdown("""<div class='kpi-tile'><div class='kpi-label'>Macro Score</div>
            <div class='kpi-value' style='color:#6b7280'>—</div>
            <div style='font-size:.68rem;color:#4b5563'>FRED key needed</div></div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TOP BAR — ROW 2: Breadth / CTA / Sectors
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
r2 = st.columns(6)

_bc_data = [
    ("Above 50-Day MA",  _breadth.get("pct_above_50d")  if _breadth else None),
    ("Above 200-Day MA", _breadth.get("pct_above_200d") if _breadth else None),
]
for col, (lbl, val) in zip(r2[:2], _bc_data):
    with col:
        if val is not None:
            bc = "#10b981" if val>70 else "#f59e0b" if val>50 else "#ef4444"
            bl = "HEALTHY" if val>70 else "NEUTRAL" if val>50 else "WEAK"
            st.markdown(f"""<div class='kpi-tile' style='border-top:2px solid {bc}'>
                <div class='kpi-label'>{lbl}</div>
                <div class='kpi-value' style='color:{bc}'>{val:.0f}%</div>
                <div style='font-size:.68rem;color:{bc};font-weight:700'>{bl}</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""<div class='kpi-tile'><div class='kpi-label'>{lbl}</div>
                <div class='kpi-value' style='color:#4b5563'>—</div></div>""", unsafe_allow_html=True)

for col, asset_key, lbl in zip(r2[2:4], ["Equities (SPY)","Bonds (TLT)"], ["CTA Equities","CTA Bonds"]):
    with col:
        d = _cta_data.get(asset_key) if _cta_data else None
        if d:
            exp = d["exposure"]; reg = d["regime"]
            cc = "#10b981" if exp>20 else "#ef4444" if exp<-20 else "#f59e0b"
            st.markdown(f"""<div class='kpi-tile' style='border-top:2px solid {cc}'>
                <div class='kpi-label'>{lbl}</div>
                <div class='kpi-value' style='color:{cc}'>{exp:+.0f}</div>
                <div style='font-size:.68rem;color:{cc};font-weight:700'>{reg}</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""<div class='kpi-tile'><div class='kpi-label'>{lbl}</div>
                <div class='kpi-value' style='color:#4b5563'>—</div></div>""", unsafe_allow_html=True)

with r2[4]:
    if not _sector_df.empty:
        _td = _sector_df[_sector_df["Period"]=="1d"]
        if not _td.empty:
            _bst = _td.loc[_td["Return %"].idxmax()]
            bc = color_pct(float(_bst["Return %"]))
            _bn = str(_bst["Sector"]).replace("Consumer ","Con. ")
            st.markdown(f"""<div class='kpi-tile' style='border-top:2px solid {bc}'>
                <div class='kpi-label'>Best Sector</div>
                <div class='kpi-value' style='color:{bc};font-size:1.05rem'>{_bn}</div>
                <div style='font-size:.72rem;color:{bc};font-weight:700'>{float(_bst["Return %"]):+.2f}%</div>
            </div>""", unsafe_allow_html=True)
        else:
            kpi("Best Sector","—")
    else:
        kpi("Best Sector","—")

with r2[5]:
    if not _sector_df.empty:
        _td = _sector_df[_sector_df["Period"]=="1d"]
        if not _td.empty:
            _wst = _td.loc[_td["Return %"].idxmin()]
            wc = color_pct(float(_wst["Return %"]))
            _wn = str(_wst["Sector"]).replace("Consumer ","Con. ")
            alert_count = len([a for a in st.session_state.alerts if not a.triggered])
            st.markdown(f"""<div class='kpi-tile' style='border-top:2px solid {wc}'>
                <div class='kpi-label'>Worst Sector &nbsp;
                    <span style='color:#4b5563'>| 🔔 {alert_count}</span></div>
                <div class='kpi-value' style='color:{wc};font-size:1.05rem'>{_wn}</div>
                <div style='font-size:.72rem;color:{wc};font-weight:700'>{float(_wst["Return %"]):+.2f}%</div>
            </div>""", unsafe_allow_html=True)
        else:
            kpi("Worst Sector","—")
    else:
        kpi("Worst Sector","—")

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tabs = st.tabs([
    "🌡️  Macro Score",
    "🦅  Black Raven",
    "📈  Watchlist & RS",
    "🗺️  Heatmaps",
    "🫁  Market Breadth",
    "🌪️  Volatility & CTA",
    "🔔  Price Alerts",
    "🔍  Stock Review",
    "🐋  Big Hands",
])
(tab_macro, tab_raven, tab_watch, tab_heat_stocks,
 tab_breadth, tab_vol, tab_alert, tab_review, tab_smart) = tabs


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — MACRO SCORE
# ══════════════════════════════════════════════════════════════════════════════
with tab_macro:
    if not fred_live:
        st.markdown("""<div class='card card-accent-yellow' style='margin-top:10px'>
            <div style='font-size:1rem;font-weight:700;color:#f59e0b;margin-bottom:6px'>⚠️ FRED API Key Required</div>
            <div style='color:#9ca3af;font-size:.85rem'>
                Add <code>FRED_API_KEY=your_key</code> to your <code>.env</code> file.<br>
                Free key at: fred.stlouisfed.org/docs/api/api_key.html
            </div>
        </div>""", unsafe_allow_html=True)
    else:
        with st.spinner("Loading FRED macro data…"):
            try:
                macro_data = load_macro()
                scores, total = score_all_indicators(macro_data)
                interp = interpret_score(total)
                st.session_state.last_refresh = now.strftime("%H:%M:%S")

                col_g, col_r = st.columns([1, 1])
                with col_g:
                    st.plotly_chart(macro_gauge(total), use_container_width=True)

                with col_r:
                    pct = total / 70
                    regime_bg  = interp["color"] + "18"
                    regime_bdr = interp["color"]
                    st.markdown(f"""
                    <div class='regime-banner' style='background:{regime_bg};border:1px solid {regime_bdr}33;margin-top:12px'>
                        <div style='font-size:2.6rem'>{interp["emoji"]}</div>
                        <div>
                            <div style='font-size:1.35rem;font-weight:800;color:{regime_bdr}'>{interp["label"]}</div>
                            <div style='font-size:.85rem;color:#9ca3af;margin-top:4px'>
                                Score: <b style='color:#f1f5f9'>{total}/70</b> &nbsp;({pct*100:.0f}%)
                            </div>
                            <div style='background:#1e2533;border-radius:99px;height:8px;width:100%;margin-top:10px'>
                                <div style='background:{regime_bdr};width:{int(pct*100)}%;height:8px;border-radius:99px'></div>
                            </div>
                        </div>
                    </div>""", unsafe_allow_html=True)

                    st.markdown("<div class='card-sm' style='margin-top:10px'><div style='font-size:.68rem;color:#6b7280;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px'>Regime Scale</div>", unsafe_allow_html=True)
                    for rng, lbl, col in [
                        ("56–70","Too Hot — Fed Tightens","#ef4444"),
                        ("42–55","Warm — Growth Solid","#f59e0b"),
                        ("28–41","Neutral — Mixed Signals","#3b82f6"),
                        ("14–27","Cool — Slowing","#6366f1"),
                        ("0–13", "Too Cold — Fed Eases","#10b981"),
                    ]:
                        hi = " ← YOU ARE HERE" if interp["color"]==col else ""
                        st.markdown(f"""<div style='display:flex;align-items:center;gap:8px;margin-bottom:5px;font-size:.78rem'>
                            <span style='width:8px;height:8px;border-radius:50%;background:{col};display:inline-block;flex-shrink:0'></span>
                            <span style='color:{col};min-width:44px'>{rng}</span>
                            <span style='color:#9ca3af'>{lbl}<b style='color:{col}'>{hi}</b></span>
                        </div>""", unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)

                section("Individual Indicator Scores  •  Max 10 pts each")
                ind_cols = st.columns(4)
                for i, s in enumerate(scores):
                    sc_pct = s.total / 10
                    bc = "#10b981" if sc_pct>=.7 else "#f59e0b" if sc_pct>=.4 else "#ef4444"
                    checks = [
                        ("3M", s.score_3m), ("6M", s.score_6m),
                        ("YoY", s.score_yoy), ("Abs", s.score_abs),
                    ]
                    checks_html = " ".join([
                        f"<span style='color:{'#10b981' if v else '#ef4444'}'>"
                        f"{'✓' if v else '✗'} {l}</span>"
                        for l, v in checks
                    ])
                    with ind_cols[i % 4]:
                        st.markdown(f"""<div class='ind-card'>
                            <div class='ind-name'>{s.name}</div>
                            <div style='display:flex;align-items:flex-end;justify-content:space-between'>
                                <div class='ind-value'>{s.latest_value:,.2f}</div>
                                <span class='score-badge' style='background:{bc}22;color:{bc}'>{s.total}/10</span>
                            </div>
                            <div class='ind-score-bar-bg'>
                                <div class='ind-score-bar-fill' style='background:{bc};width:{sc_pct*100:.0f}%'></div>
                            </div>
                            <div style='display:flex;gap:10px;margin-top:9px;font-size:.68rem;font-weight:600'>
                                {checks_html}
                            </div>
                        </div>""", unsafe_allow_html=True)

                section("Score Breakdown by Indicator")
                st.plotly_chart(score_breakdown_bar([s.breakdown() for s in scores]), use_container_width=True)

                section("Historical Trend (24 Months)")
                spark_cols = st.columns(4)
                ind_keys = ["ISM_PMI","ISM_NMI","UMICH","BUILDING_PERMITS","NFIB_SBO","NFP","SPY"]
                for i,(key,sc) in enumerate(zip(ind_keys, scores)):
                    with spark_cols[i % 4]:
                        st.plotly_chart(macro_indicator_sparkline(
                            macro_data.get(key, pd.Series(dtype=float)), sc.name
                        ), use_container_width=True)

            except Exception as e:
                st.error(f"Macro data error: {e}")
                with st.expander("Debug"):
                    st.exception(e)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — WATCHLIST & RS
# ══════════════════════════════════════════════════════════════════════════════
with tab_watch:
    with st.spinner("Loading quotes & relative strength…"):
        quotes_df = load_quotes(tuple(st.session_state.watchlist))
        rs_df     = load_rs(tuple(st.session_state.watchlist))

    if not quotes_df.empty:
        merged = quotes_df.merge(rs_df, on="Ticker", how="left") if not rs_df.empty else quotes_df
        rs_col = [c for c in merged.columns if "RS vs" in c]

        # ── Stat tiles ───────────────────────────────────────────────────────
        valid_pct = merged["Change %"].dropna()
        pos_count = int((valid_pct >= 0).sum())
        neg_count = int((valid_pct < 0).sum())
        best  = merged.loc[valid_pct.idxmax()] if not valid_pct.empty else None
        worst = merged.loc[valid_pct.idxmin()] if not valid_pct.empty else None

        tc = st.columns(4)
        with tc[0]:
            st.markdown(f"""<div class='kpi-tile' style='border-top:2px solid #10b981'>
                <div class='kpi-label'>Advancing</div>
                <div class='kpi-value' style='color:#10b981'>{pos_count}</div>
                <div style='font-size:.7rem;color:#10b981'>stocks up today</div>
            </div>""", unsafe_allow_html=True)
        with tc[1]:
            st.markdown(f"""<div class='kpi-tile' style='border-top:2px solid #ef4444'>
                <div class='kpi-label'>Declining</div>
                <div class='kpi-value' style='color:#ef4444'>{neg_count}</div>
                <div style='font-size:.7rem;color:#ef4444'>stocks down today</div>
            </div>""", unsafe_allow_html=True)
        with tc[2]:
            if best is not None:
                bc = "#10b981"
                st.markdown(f"""<div class='kpi-tile' style='border-top:2px solid {bc}'>
                    <div class='kpi-label'>Best: {best["Ticker"]}</div>
                    <div class='kpi-value' style='color:{bc}'>{best["Change %"]:+.2f}%</div>
                    <div style='font-size:.7rem;color:#6b7280'>${best.get("Price",0):,.2f}</div>
                </div>""", unsafe_allow_html=True)
        with tc[3]:
            if worst is not None:
                rc = "#ef4444"
                st.markdown(f"""<div class='kpi-tile' style='border-top:2px solid {rc}'>
                    <div class='kpi-label'>Worst: {worst["Ticker"]}</div>
                    <div class='kpi-value' style='color:{rc}'>{worst["Change %"]:+.2f}%</div>
                    <div style='font-size:.7rem;color:#6b7280'>${worst.get("Price",0):,.2f}</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

        # ── Performance bar chart ─────────────────────────────────────────────
        chart_c, table_c = st.columns([1, 1])
        with chart_c:
            st.plotly_chart(watchlist_performance_chart(merged), use_container_width=True)

        with table_c:
            section("Live Quotes & Relative Strength vs SPY (63-Day)")

            # Build a styled display table
            display_cols = ["Ticker", "Price", "Change", "Change %"]
            if rs_col:
                display_cols += rs_col
            if "Volume" in merged.columns:
                display_cols.append("Volume")

            display = merged[display_cols].copy()

            def _color_row(row):
                chg = row.get("Change %", 0)
                is_pos = isinstance(chg, (int, float)) and chg >= 0
                base = "background-color: rgba(16,185,129,0.05)" if is_pos else "background-color: rgba(239,68,68,0.05)"
                return [base] * len(row)

            def _fmt_price(v):
                return f"${v:,.2f}" if isinstance(v, (int, float)) and v else "—"

            def _fmt_chg(v):
                if not isinstance(v, (int, float)):
                    return "—"
                col = "color:#10b981" if v >= 0 else "color:#ef4444"
                return f'<span style="{col};font-weight:700">{v:+.2f}%</span>'

            # Render as HTML table for full color control
            rows_html = []
            for _, row in display.iterrows():
                ticker = row["Ticker"]
                price  = _fmt_price(row.get("Price"))
                chg    = row.get("Change", 0)
                chgp   = row.get("Change %", 0)
                chgp_s = f"{chgp:+.2f}%" if isinstance(chgp,(int,float)) else "—"
                chg_s  = f"{chg:+.2f}" if isinstance(chg,(int,float)) else "—"
                chg_c  = "#10b981" if isinstance(chgp,(int,float)) and chgp>=0 else "#ef4444"
                rs_s   = ""
                if rs_col and rs_col[0] in row:
                    rv = row[rs_col[0]]
                    rs_c = "#10b981" if isinstance(rv,(int,float)) and rv>=0 else "#ef4444"
                    rs_s = f'<td style="color:{rs_c};font-weight:600;padding:8px 10px">{rv:+.2f}</td>' if isinstance(rv,(int,float)) else '<td style="color:#6b7280;padding:8px 10px">—</td>'
                vol_s = ""
                if "Volume" in row:
                    v = row.get("Volume", 0)
                    vol_s = f'<td style="color:#9ca3af;padding:8px 10px">{int(v):,}</td>' if isinstance(v,(int,float)) and v else '<td style="color:#4b5563;padding:8px 10px">—</td>'

                row_bg = "rgba(16,185,129,0.04)" if isinstance(chgp,(int,float)) and chgp>=0 else "rgba(239,68,68,0.04)"
                rows_html.append(f"""<tr style='background:{row_bg};border-bottom:1px solid #1e2533'>
                    <td style='padding:8px 10px;font-weight:700;color:#f1f5f9'>{ticker}</td>
                    <td style='padding:8px 10px;color:#f1f5f9;font-weight:600'>{price}</td>
                    <td style='padding:8px 10px;color:{chg_c};font-weight:600'>{chg_s}</td>
                    <td style='padding:8px 10px;color:{chg_c};font-weight:700'>{chgp_s}</td>
                    {rs_s}{vol_s}
                </tr>""")

            rs_header = f'<th style="padding:8px 10px;color:#9ca3af;font-size:.72rem;font-weight:700;text-transform:uppercase">RS vs SPY</th>' if rs_col else ""
            vol_header = '<th style="padding:8px 10px;color:#9ca3af;font-size:.72rem;font-weight:700;text-transform:uppercase">Volume</th>' if "Volume" in merged.columns else ""

            st.markdown(f"""
            <div style='border-radius:12px;overflow:hidden;border:1px solid #1e2533'>
            <table style='width:100%;border-collapse:collapse;background:#111827'>
                <thead>
                <tr style='background:#0d1117;border-bottom:1px solid #1e2533'>
                    <th style='padding:8px 10px;color:#9ca3af;font-size:.72rem;font-weight:700;text-transform:uppercase;text-align:left'>Ticker</th>
                    <th style='padding:8px 10px;color:#9ca3af;font-size:.72rem;font-weight:700;text-transform:uppercase;text-align:left'>Price</th>
                    <th style='padding:8px 10px;color:#9ca3af;font-size:.72rem;font-weight:700;text-transform:uppercase;text-align:left'>Change</th>
                    <th style='padding:8px 10px;color:#9ca3af;font-size:.72rem;font-weight:700;text-transform:uppercase;text-align:left'>Change %</th>
                    {rs_header}{vol_header}
                </tr>
                </thead>
                <tbody>{''.join(rows_html)}</tbody>
            </table>
            </div>""", unsafe_allow_html=True)

        # ── Quick jump buttons ────────────────────────────────────────────────
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        section("Quick Review Jump")
        pill_cols = st.columns(min(len(st.session_state.watchlist), 12))
        for i, t in enumerate(st.session_state.watchlist):
            with pill_cols[i % len(pill_cols)]:
                if st.button(t, key=f"wl_{t}", use_container_width=True):
                    st.session_state.selected_ticker = t
                    st.toast(f"Selected {t} — open Stock Review tab", icon="📈")

        if st.session_state.alerts:
            triggered = check_alerts(st.session_state.alerts, merged)
            for alert in triggered:
                pr = merged[merged["Ticker"]==alert.ticker]
                cp = float(pr["Price"].iloc[0]) if not pr.empty else alert.threshold
                st.toast(f"🔔 {alert.ticker} {alert.condition} ${alert.threshold}", icon="🔔")
                send_webhook(alert, cp)
    else:
        st.warning("Could not load quote data. Check connection.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — STOCKS HEATMAP
# ══════════════════════════════════════════════════════════════════════════════
with tab_heat_stocks:
    section("Watchlist Stock Performance Heatmap")

    with st.spinner("Loading stock data…"):
        hmap_quotes = load_quotes(tuple(st.session_state.watchlist))

    if not hmap_quotes.empty:
        valid = hmap_quotes.dropna(subset=["Change %"])
        if not valid.empty:
            st.plotly_chart(
                stocks_heatmap(valid, title=f"Watchlist Heatmap — {now.strftime('%d %b %Y')}"),
                use_container_width=True
            )
        else:
            st.info("No price change data available.")

    # ── Extended market heatmap using sector ETFs ─────────────────────────────
    section("S&P 500 Sector ETF Heatmap")
    if not _sector_df.empty:
        _today_etfs = _sector_df[_sector_df["Period"]=="1d"].copy()
        if not _today_etfs.empty:
            etf_quotes = load_quotes(tuple(_today_etfs["ETF"].tolist()))
            if not etf_quotes.empty:
                # Merge sector name in
                etf_map = dict(zip(_today_etfs["ETF"], _today_etfs["Sector"]))
                etf_quotes["Sector"] = etf_quotes["Ticker"].map(etf_map)
                st.plotly_chart(
                    stocks_heatmap(etf_quotes.rename(columns={"Sector": "Ticker"}).assign(
                        Ticker=etf_quotes.apply(
                            lambda r: f"{etf_map.get(r['Ticker'], r['Ticker'])}", axis=1
                        )
                    ), title="Sector ETF Heatmap — Today"),
                    use_container_width=True
                )

    # ── Performance table ─────────────────────────────────────────────────────
    if not hmap_quotes.empty:
        section("Ranked Performance Table")
        ranked = hmap_quotes.dropna(subset=["Change %"]).sort_values("Change %", ascending=False).copy()

        rows_html = []
        for rank, (_, row) in enumerate(ranked.iterrows(), 1):
            chgp   = row.get("Change %", 0)
            chg_c  = "#10b981" if isinstance(chgp,(int,float)) and chgp>=0 else "#ef4444"
            arrow  = "▲" if isinstance(chgp,(int,float)) and chgp>=0 else "▼"
            price  = f"${row.get('Price',0):,.2f}" if isinstance(row.get('Price'),(int,float)) else "—"
            bar_w  = min(abs(chgp)*10, 100) if isinstance(chgp,(int,float)) else 0
            rows_html.append(f"""<tr style='border-bottom:1px solid #1e2533'>
                <td style='padding:8px 10px;color:#6b7280;font-size:.8rem'>#{rank}</td>
                <td style='padding:8px 10px;font-weight:700;color:#f1f5f9'>{row["Ticker"]}</td>
                <td style='padding:8px 10px;color:#9ca3af'>{price}</td>
                <td style='padding:8px 14px;min-width:180px'>
                    <div style='display:flex;align-items:center;gap:8px'>
                        <div style='background:#1e2533;border-radius:4px;height:6px;width:100px;flex-shrink:0'>
                            <div style='background:{chg_c};height:6px;border-radius:4px;width:{bar_w:.0f}px'></div>
                        </div>
                        <span style='color:{chg_c};font-weight:700;font-size:.85rem'>{arrow} {abs(chgp):.2f}%</span>
                    </div>
                </td>
            </tr>""")

        st.markdown(f"""
        <div style='border-radius:12px;overflow:hidden;border:1px solid #1e2533'>
        <table style='width:100%;border-collapse:collapse;background:#111827'>
            <thead><tr style='background:#0d1117;border-bottom:1px solid #1e2533'>
                <th style='padding:8px 10px;color:#6b7280;font-size:.72rem;font-weight:700;text-align:left'>#</th>
                <th style='padding:8px 10px;color:#9ca3af;font-size:.72rem;font-weight:700;text-transform:uppercase;text-align:left'>Ticker</th>
                <th style='padding:8px 10px;color:#9ca3af;font-size:.72rem;font-weight:700;text-transform:uppercase;text-align:left'>Price</th>
                <th style='padding:8px 10px;color:#9ca3af;font-size:.72rem;font-weight:700;text-transform:uppercase;text-align:left'>Performance</th>
            </tr></thead>
            <tbody>{''.join(rows_html)}</tbody>
        </table></div>""", unsafe_allow_html=True)

    # ── SECTOR HEATMAP (merged) ───────────────────────────────────────────────
    st.markdown("<div style='margin-top:24px'></div>", unsafe_allow_html=True)
    section("S&P 500 Sector Heatmap")

    sector_df = _sector_df
    if sector_df.empty:
        with st.spinner("Loading sector data…"):
            sector_df = load_sector_perf()

    if not sector_df.empty:
        p_col, _ = st.columns([3, 5])
        with p_col:
            period_choice = st.radio(
                "Timeframe", ["1d","5d","1mo"], horizontal=True, index=0,
                key="heatmap_period",
                format_func=lambda x: {"1d":"Today","5d":"1 Week","1mo":"1 Month"}[x],
            )

        hm_col, bar_col = st.columns([3, 2])
        with hm_col:
            st.plotly_chart(sector_heatmap(sector_df, period_choice), use_container_width=True)
        with bar_col:
            st.plotly_chart(sector_bars(sector_df, period_choice), use_container_width=True)

        section("Sector Performance Table — All Timeframes")
        pivot = sector_df.pivot_table(values="Return %", index="Sector", columns="Period")
        pivot = pivot.reindex(columns=["1d","5d","1mo"]).rename(
            columns={"1d":"Today %","5d":"1 Week %","1mo":"1 Month %"})
        pivot = pivot.sort_values("Today %", ascending=False)

        sec_rows_html = []
        for sector, row in pivot.iterrows():
            td_html = f"<td style='padding:10px 14px;color:#d1d5db;font-weight:600'>{sector}</td>"
            for col_name in ["Today %","1 Week %","1 Month %"]:
                v = row.get(col_name)
                if pd.isna(v):
                    td_html += "<td style='padding:10px 14px;color:#4b5563'>—</td>"
                else:
                    c = "#10b981" if v >= 0 else "#ef4444"
                    bar_w = min(abs(v) * 12, 80)
                    td_html += f"""<td style='padding:10px 14px'>
                        <div style='display:flex;align-items:center;gap:8px'>
                            <div style='background:#1e2533;border-radius:3px;height:6px;width:80px;flex-shrink:0'>
                                <div style='background:{c};height:6px;border-radius:3px;width:{bar_w:.0f}px'></div>
                            </div>
                            <span style='color:{c};font-weight:700;font-size:.85rem'>{v:+.2f}%</span>
                        </div>
                    </td>"""
            sec_rows_html.append(f"<tr style='border-bottom:1px solid #1e2533'>{td_html}</tr>")

        st.markdown(f"""
        <div style='border-radius:12px;overflow:hidden;border:1px solid #1e2533'>
        <table style='width:100%;border-collapse:collapse;background:#111827'>
            <thead><tr style='background:#0d1117;border-bottom:1px solid #1e2533'>
                <th style='padding:10px 14px;color:#9ca3af;font-size:.72rem;font-weight:700;text-transform:uppercase;text-align:left'>Sector</th>
                <th style='padding:10px 14px;color:#9ca3af;font-size:.72rem;font-weight:700;text-transform:uppercase;text-align:left'>Today</th>
                <th style='padding:10px 14px;color:#9ca3af;font-size:.72rem;font-weight:700;text-transform:uppercase;text-align:left'>1 Week</th>
                <th style='padding:10px 14px;color:#9ca3af;font-size:.72rem;font-weight:700;text-transform:uppercase;text-align:left'>1 Month</th>
            </tr></thead>
            <tbody>{''.join(sec_rows_html)}</tbody>
        </table></div>""", unsafe_allow_html=True)
    else:
        st.warning("Sector data unavailable.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — MARKET BREADTH
# ══════════════════════════════════════════════════════════════════════════════
with tab_breadth:
    section("Market Breadth & Internal Health  •  25-Stock S&P 500 Sample")
    breadth = _breadth

    if breadth:
        p50  = breadth.get("pct_above_50d", 0)
        p200 = breadth.get("pct_above_200d", 0)
        n    = breadth.get("sample_size", 0)
        combined = (p50 + p200) / 2

        def bc(p):  return "#10b981" if p>70 else "#f59e0b" if p>50 else "#ef4444"
        def bl(p):  return "Healthy" if p>70 else "Neutral" if p>50 else "Caution" if p>30 else "Breakdown"

        bc4 = st.columns(4)
        for col, lbl, val in zip(bc4, ["Above 50-Day MA","Above 200-Day MA","Sample Universe","Composite Health"],
                                       [p50, p200, n, combined]):
            with col:
                c = bc(val) if lbl != "Sample Universe" else "#3b82f6"
                lb = bl(val) if lbl not in ("Sample Universe","Composite Health") else ("stocks" if lbl == "Sample Universe" else bl(combined))
                vfmt = f"{val:.0f}%" if lbl != "Sample Universe" else str(int(val))
                st.markdown(f"""<div class='kpi-tile' style='border-top:2px solid {c}'>
                    <div class='kpi-label'>{lbl}</div>
                    <div class='kpi-value' style='color:{c}'>{vfmt}</div>
                    <div style='font-size:.7rem;color:{c};font-weight:700'>{lb}</div>
                </div>""", unsafe_allow_html=True)

        # Progress bars
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        for lbl, val in [("Stocks Above 50-Day MA", p50), ("Stocks Above 200-Day MA", p200)]:
            c = bc(val)
            st.markdown(f"""<div class='card-sm' style='margin-bottom:8px'>
                <div style='display:flex;justify-content:space-between;margin-bottom:6px'>
                    <span style='font-size:.85rem;color:#d1d5db;font-weight:600'>{lbl}</span>
                    <span style='font-size:.85rem;color:{c};font-weight:700'>{val}%</span>
                </div>
                <div style='background:#1e2533;border-radius:99px;height:10px'>
                    <div style='background:{c};width:{val}%;height:10px;border-radius:99px'></div>
                </div>
            </div>""", unsafe_allow_html=True)

        section("Advance / Decline Line (30-Day Rolling)")
        ad_df = breadth.get("advance_decline", pd.DataFrame())
        if not ad_df.empty:
            st.plotly_chart(advance_decline_chart(ad_df), use_container_width=True)
    else:
        st.error("Breadth data unavailable.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — VOLATILITY & CTA
# ══════════════════════════════════════════════════════════════════════════════
with tab_vol:
    with st.spinner("Loading VIX & CTA data…"):
        vix_df   = load_vix()
        cta_data = _cta_data or load_cta()
        term_df  = fetch_vix_term_structure()

    # ── VIX headline ─────────────────────────────────────────────────────────
    if not vix_df.empty:
        cv = float(vix_df["VIX"].iloc[-1])
        pv = float(vix_df["VIX"].iloc[-2])
        mv = float(vix_df["VIX"].tail(252).mean())
        hv = float(vix_df["VIX"].tail(252).max())
        lv = float(vix_df["VIX"].tail(252).min())
        vr = "EXTREME FEAR" if cv>30 else "FEAR" if cv>20 else "NORMAL" if cv>15 else "COMPLACENT"
        vc = "#ef4444" if cv>30 else "#f59e0b" if cv>20 else "#10b981"

        section("VIX Fear Index — Current Reading")
        v5 = st.columns(5)
        for col, lbl, val, fmts in zip(v5,
            ["VIX Now","Change","52W Mean","52W High","52W Low"],
            [cv, cv-pv, mv, hv, lv],
            ["{:.2f}","{:+.2f}","{:.2f}","{:.2f}","{:.2f}"]):
            if lbl == "VIX Now":
                col.markdown(f"""<div class='kpi-tile' style='border-top:2px solid {vc}'>
                    <div class='kpi-label'>{lbl}</div>
                    <div class='kpi-value' style='color:{vc}'>{fmts.format(val)}</div>
                    <div style='font-size:.7rem;color:{vc};font-weight:700'>{vr}</div>
                </div>""", unsafe_allow_html=True)
            elif lbl == "Change":
                cc = "#10b981" if val<0 else "#ef4444"
                col.markdown(f"""<div class='kpi-tile'>
                    <div class='kpi-label'>{lbl}</div>
                    <div class='kpi-value' style='color:{cc}'>{fmts.format(val)}</div>
                    <div style='font-size:.7rem;color:{cc};font-weight:700'>{'↓ Less Fear' if val<0 else '↑ More Fear'}</div>
                </div>""", unsafe_allow_html=True)
            else:
                col.markdown(f"""<div class='kpi-tile'>
                    <div class='kpi-label'>{lbl}</div>
                    <div class='kpi-value' style='color:#f1f5f9'>{fmts.format(val)}</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

        # VIX chart (left) + term structure bar (right)
        cv_col, ts_col = st.columns([2, 1])
        with cv_col:
            st.plotly_chart(vix_chart(vix_df), use_container_width=True)
        with ts_col:
            if not term_df.empty:
                st.plotly_chart(vix_term_bar(term_df), use_container_width=True)
                # Interpretation guide
                st.markdown("""<div class='card-sm'>
                    <div style='font-size:.68rem;color:#6b7280;font-weight:700;margin-bottom:8px;text-transform:uppercase;letter-spacing:.08em'>
                        Regime Guide
                    </div>
                    <div style='font-size:.8rem;color:#9ca3af;line-height:1.9'>
                        <span style='color:#10b981'>●</span> &lt;15 &nbsp; Complacency / Low vol<br>
                        <span style='color:#3b82f6'>●</span> 15–20 Normal range<br>
                        <span style='color:#f59e0b'>●</span> 20–30 Elevated / Caution<br>
                        <span style='color:#ef4444'>●</span> &gt;30 &nbsp; Fear / Hedge demand<br>
                        <span style='color:#dc2626'>●</span> &gt;40 &nbsp; Panic / Reversal zone
                    </div>
                </div>""", unsafe_allow_html=True)
            else:
                st.info("Term structure data unavailable.")
    else:
        st.warning("VIX data unavailable.")

    # ── CTA ───────────────────────────────────────────────────────────────────
    if cta_data:
        section("CTA Trend-Following Exposure Proxy  •  Multi-Horizon Momentum Z-Score")

        cta_cols = st.columns(len(cta_data))
        for col, (label, d) in zip(cta_cols, cta_data.items()):
            exp = d["exposure"]; reg = d["regime"]
            cc  = "#10b981" if exp>20 else "#ef4444" if exp<-20 else "#f59e0b"
            s20 = d.get("signal_20d", 0); s63 = d.get("signal_63d", 0)
            col.markdown(f"""<div class='kpi-tile' style='border-top:2px solid {cc}'>
                <div class='kpi-label' style='font-size:.62rem'>{label}</div>
                <div class='kpi-value' style='color:{cc}'>{exp:+.0f}</div>
                <div style='font-size:.68rem;color:{cc};font-weight:700'>{reg}</div>
                <div style='font-size:.62rem;color:#4b5563;margin-top:4px'>20d: {s20:+.1f} &nbsp; 63d: {s63:+.1f}</div>
            </div>""", unsafe_allow_html=True)

        st.plotly_chart(cta_exposure_chart(cta_data), use_container_width=True)
        st.caption("⚠️ Proxy only — constructed from price momentum Z-scores, not actual CTA fund positioning data.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — PRICE ALERTS
# ══════════════════════════════════════════════════════════════════════════════
with tab_alert:
    add_col, list_col, wh_col = st.columns([1, 1, 1])

    with add_col:
        section("Add New Alert")
        a_t  = st.text_input("Ticker", "SPY", key="al_tick_inline")
        a_c  = st.selectbox("Condition", ["above","below"], key="al_cond_inline")
        a_p  = st.number_input("Target Price $", min_value=0.0, value=500.0, step=0.5, key="al_price_inline")
        a_n  = st.text_input("Note (optional)", "", key="al_note_inline", placeholder="e.g. ATH breakout")
        if st.button("＋ Add Alert", use_container_width=True, key="al_add_btn"):
            st.session_state.alerts.append(PriceAlert(a_t.upper(), a_c, a_p, a_n))
            st.success(f"Alert set: {a_t.upper()} {a_c} ${a_p:.2f}")
        if st.session_state.alerts:
            if st.button("Clear All Alerts", use_container_width=True, key="al_clear"):
                st.session_state.alerts = []; st.rerun()

    with list_col:
        section("Active Price Alerts")
        if not st.session_state.alerts:
            st.markdown("""<div class='card-sm' style='text-align:center;color:#4b5563;padding:28px'>
                No alerts set. Add one on the left.
            </div>""", unsafe_allow_html=True)
        else:
            for a in st.session_state.alerts:
                sc  = "green" if a.triggered else "yellow"
                lbl = "✓ TRIGGERED" if a.triggered else "● WATCHING"
                arr = "▲" if a.condition=="above" else "▼"
                st.markdown(f"""<div class='card-sm card-accent-{"green" if a.triggered else "yellow"}'>
                    <div style='display:flex;align-items:center;justify-content:space-between'>
                        <div>
                            <span style='font-size:.95rem;font-weight:700;color:#f1f5f9'>{a.ticker}</span>
                            <span style='color:#6b7280;margin:0 6px'>{arr}</span>
                            <span style='font-size:.9rem;color:#f1f5f9'>${a.threshold:.2f}</span>
                            {"<div style='font-size:.72rem;color:#6b7280'>" + a.note + "</div>" if a.note else ""}
                        </div>
                        {pill(lbl, sc)}
                    </div>
                </div>""", unsafe_allow_html=True)

    with wh_col:
        section("Webhook Configuration")
        make_url = os.getenv("MAKE_WEBHOOK_URL",""); disc_url = os.getenv("DISCORD_WEBHOOK_URL","")
        mo2 = bool(make_url) and "your_webhook" not in make_url
        do  = bool(disc_url) and "your_webhook" not in disc_url
        st.markdown(f"""<div class='card-sm'>
            <div style='display:flex;align-items:center;gap:10px;margin-bottom:8px'>
                {pill("● Live","green") if mo2 else pill("● Offline","gray")}
                <span style='font-size:.82rem;color:#9ca3af'>Make.com Webhook</span>
            </div>
            <div style='display:flex;align-items:center;gap:10px'>
                {pill("● Live","green") if do else pill("● Offline","gray")}
                <span style='font-size:.82rem;color:#9ca3af'>Discord Direct</span>
            </div>
        </div>""", unsafe_allow_html=True)
        if st.button("🔔 Test Webhook", use_container_width=True, key="test_wh"):
            ta = PriceAlert("TEST","above",999.99,"connectivity test",True,datetime.now().isoformat())
            ok = send_webhook(ta, 999.99)
            st.success("Webhook delivered!") if ok else st.error("Webhook failed — check URL in .env")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 8 — STOCK REVIEW
# ══════════════════════════════════════════════════════════════════════════════
with tab_review:
    inp_col, per_col, ai_col = st.columns([2, 1, 1])
    review_ticker = inp_col.text_input(
        "Ticker", value=st.session_state.selected_ticker,
        placeholder="NVDA, AAPL, MSFT…", key="review_tick"
    ).upper().strip()
    chart_period  = per_col.selectbox("Period", ["3mo","6mo","1y","2y","5y"], index=2)

    if review_ticker:
        with st.spinner(f"Loading {review_ticker}…"):
            fund     = load_fundamentals(review_ticker)
            price_df = load_ohlcv(review_ticker, chart_period)

        if "error" in fund:
            st.error(f"Could not load {review_ticker}: {fund['error']}")
        else:
            rec = str(fund.get("recommendation","N/A")).upper()
            rec_color = "#10b981" if "buy" in rec.lower() else "#ef4444" if "sell" in rec.lower() else "#f59e0b"
            st.markdown(f"""<div style='margin:8px 0 14px'>
                <span style='font-size:1.25rem;font-weight:800;color:#f1f5f9'>{fund.get("name",review_ticker)}</span>
                <span style='background:#1e2533;color:#9ca3af;font-size:.72rem;font-weight:700;
                             padding:3px 10px;border-radius:99px;margin-left:10px'>{review_ticker}</span>
                &nbsp;
                <span style='background:{rec_color}22;color:{rec_color};font-size:.72rem;font-weight:700;
                             padding:3px 10px;border-radius:99px'>{rec}</span>
                <br><span style='font-size:.78rem;color:#6b7280'>{fund.get("sector","—")} → {fund.get("industry","—")}</span>
                &nbsp;•&nbsp;
                <span style='font-size:.78rem;color:#6b7280'>Target: <b style='color:#f1f5f9'>${fund.get("target_price","N/A")}</b></span>
            </div>""", unsafe_allow_html=True)

            top = st.columns(6)
            for col, (lbl, val) in zip(top, [
                ("Market Cap",  fmt_big(fund.get("market_cap"))),
                ("P/E (TTM)",   f"{fund.get('pe_ratio','—')}"),
                ("Fwd P/E",     f"{fund.get('fwd_pe','—')}"),
                ("P/S",         f"{fund.get('ps_ratio','—')}"),
                ("Rev Growth",  f"{(fund.get('revenue_growth') or 0)*100:.1f}%" if fund.get('revenue_growth') else "—"),
                ("Beta",        f"{fund.get('beta','—')}"),
            ]):
                with col: kpi(lbl, val)

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            chart_col, fund_col = st.columns([3, 1])
            with chart_col:
                if not price_df.empty:
                    st.plotly_chart(candlestick_chart(price_df, review_ticker), use_container_width=True)
                else:
                    st.warning("Price data unavailable.")
            with fund_col:
                section("Key Metrics")
                for lbl, val in [
                    ("ROE",           f"{(fund.get('roe') or 0)*100:.1f}%" if fund.get('roe') else "—"),
                    ("Profit Margin", f"{(fund.get('profit_margin') or 0)*100:.1f}%" if fund.get('profit_margin') else "—"),
                    ("P/B Ratio",     f"{fund.get('pb_ratio','—')}"),
                    ("Debt/Equity",   f"{fund.get('debt_to_equity','—')}"),
                    ("Current Ratio", f"{fund.get('current_ratio','—')}"),
                    ("52W High",      f"${fund.get('52w_high','—')}"),
                    ("52W Low",       f"${fund.get('52w_low','—')}"),
                    ("Avg Volume",    f"{int(fund.get('avg_volume') or 0):,}" if fund.get('avg_volume') else "—"),
                ]:
                    st.markdown(f"""<div style='display:flex;justify-content:space-between;align-items:center;
                                            padding:7px 0;border-bottom:1px solid #1e2533;font-size:.82rem'>
                        <span style='color:#6b7280'>{lbl}</span>
                        <span style='color:#f1f5f9;font-weight:600'>{val}</span>
                    </div>""", unsafe_allow_html=True)

            if fund.get("summary"):
                section("Business Summary")
                st.markdown(f"""<div class='card-sm' style='color:#9ca3af;font-size:.84rem;line-height:1.7'>{fund["summary"]}…</div>""", unsafe_allow_html=True)

            # AI quick analysis
            if ai_ok:
                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
                if st.button(f"🤖 Generate AI Analysis for {review_ticker}", use_container_width=False, key="ai_stock_btn"):
                    with st.spinner(f"AI analyzing {review_ticker}…"):
                        try:
                            ai_text = analyze_ticker(review_ticker, fund, price_df)
                            st.markdown(f"""<div class='ai-message'>
                                <div style='font-size:.68rem;color:#3b82f6;font-weight:700;text-transform:uppercase;margin-bottom:8px'>
                                    🤖 AI Analysis — {review_ticker}
                                </div>
                                {ai_text}
                            </div>""", unsafe_allow_html=True)
                        except Exception as e:
                            st.error(f"AI error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 9 — BIG HANDS
# ══════════════════════════════════════════════════════════════════════════════
with tab_smart:
    si_col, _ = st.columns([1,3])
    smart_ticker = si_col.text_input(
        "Ticker", value=st.session_state.selected_ticker,
        key="smart_ticker", placeholder="NVDA, AAPL…"
    ).upper().strip()

    if smart_ticker:
        with st.spinner(f"Loading institutional data for {smart_ticker}…"):
            insiders, dark_pool, filings = load_smart_money(smart_ticker)

        st.markdown(f"<div style='font-size:1rem;font-weight:700;color:#f1f5f9;margin:8px 0 14px'>{smart_ticker} — Smart Money Activity</div>", unsafe_allow_html=True)
        in_tab, dp_tab, f13_tab = st.tabs(["👤 Insider Trades","🌑 Dark Pool","🏦 13F Filings"])

        with in_tab:
            st.caption("Source: OpenInsider.com • Public SEC filings • 180-day lookback")
            if insiders is not None and not insiders.empty:
                trade_col = next((c for c in insiders.columns if "Trade" in c), None)
                buys  = insiders[insiders[trade_col].str.contains("P -",na=False)] if trade_col else pd.DataFrame()
                sells = insiders[insiders[trade_col].str.contains("S -",na=False)] if trade_col else pd.DataFrame()
                net = len(buys) - len(sells)
                nc = "#10b981" if net>0 else "#ef4444" if net<0 else "#6b7280"
                nl = "NET BUYERS" if net>0 else "NET SELLERS" if net<0 else "NEUTRAL"
                bc3 = st.columns(3)
                with bc3[0]: kpi("Insider Buys", str(len(buys)), accent="#10b981")
                with bc3[1]: kpi("Insider Sells", str(len(sells)), accent="#ef4444")
                with bc3[2]:
                    st.markdown(f"""<div class='kpi-tile' style='border-top:2px solid {nc}'>
                        <div class='kpi-label'>Signal</div>
                        <div class='kpi-value' style='color:{nc};font-size:1rem'>{nl}</div>
                    </div>""", unsafe_allow_html=True)
                st.dataframe(insiders, use_container_width=True, hide_index=True)
            else:
                st.info("No insider data found for this ticker in the last 180 days.")

        with dp_tab:
            st.caption("Source: Unusual Whales API • Requires UNUSUAL_WHALES_API_KEY in .env")
            if dark_pool is not None and not dark_pool.empty:
                st.dataframe(dark_pool, use_container_width=True, hide_index=True)
            else:
                st.info("No dark pool data. Add UNUSUAL_WHALES_API_KEY to your .env file.")

        with f13_tab:
            st.caption("Source: SEC EDGAR • 13F-HR filings • 120-day lookback")
            if filings is not None and not filings.empty:
                st.markdown(f"Found **{len(filings)}** filings mentioning **{smart_ticker}**")
                st.dataframe(filings, use_container_width=True, hide_index=True)
            else:
                st.info("No 13F filings found in the past 120 days.")

    st.divider()
    st.caption("⚠️ For informational purposes only. Not financial advice.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 9 (2) — BLACK RAVEN EXECUTIVE DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
with tab_raven:

    # ── Protocol header ───────────────────────────────────────────────────────
    st.markdown("""
    <div style='background:linear-gradient(135deg,#0a0f1a,#0d1117);border:1px solid #1e2533;
                border-left:3px solid #ef4444;border-radius:14px;padding:18px 24px;margin-bottom:4px'>
        <div style='display:flex;align-items:center;gap:14px'>
            <span style='font-size:2rem'>🦅</span>
            <div>
                <div style='font-size:1.2rem;font-weight:900;color:#f1f5f9;letter-spacing:-.02em'>
                    BLACK RAVEN PROTOCOL v1.0
                </div>
                <div style='font-size:.78rem;color:#6b7280;margin-top:3px'>
                    K-Economy Framework &nbsp;•&nbsp; Physical AI Infrastructure &nbsp;•&nbsp;
                    Kill Zone Execution &nbsp;•&nbsp; Institutional Grade Only
                </div>
            </div>
            <div style='margin-left:auto;text-align:right'>
                <div style='font-size:.68rem;color:#4b5563;font-weight:700;text-transform:uppercase;letter-spacing:.08em'>
                    Investment Tiers
                </div>
                <div style='display:flex;gap:6px;margin-top:4px'>
                    <span style='background:#10b98122;color:#10b981;font-size:.62rem;font-weight:700;padding:2px 8px;border-radius:99px'>T1 MONOPOLY</span>
                    <span style='background:#3b82f622;color:#3b82f6;font-size:.62rem;font-weight:700;padding:2px 8px;border-radius:99px'>T2 CAPEX</span>
                    <span style='background:#f59e0b22;color:#f59e0b;font-size:.62rem;font-weight:700;padding:2px 8px;border-radius:99px'>T3 MOMENTUM</span>
                    <span style='background:#ef444422;color:#ef4444;font-size:.62rem;font-weight:700;padding:2px 8px;border-radius:99px'>T4 AVOID</span>
                </div>
            </div>
        </div>
    </div>""", unsafe_allow_html=True)

    # ── MODULE SELECTOR ───────────────────────────────────────────────────────
    br_mod = st.radio(
        "Module",
        ["📡 Macro Matrix", "🎯 Kill Zone Radar", "📰 Catalyst Feed", "⚡ Execution Commands"],
        horizontal=True, label_visibility="collapsed",
    )
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════════
    # MODULE 1 — MACRO & LIQUIDITY MATRIX
    # ════════════════════════════════════════════════════════════════════════
    if br_mod == "📡 Macro Matrix":
        section("MODULE 1 — MACRO & LIQUIDITY MATRIX  •  K-Economy Regime Overlay")

        with st.spinner("Fetching macro instruments…"):
            br_macro = load_macro_matrix()

        signals = br_macro.pop("_signals", [])

        # Regime signal banner
        if signals:
            for sig_label, sig_desc, sig_color in signals:
                st.markdown(f"""<div style='background:{sig_color}11;border:1px solid {sig_color}44;
                    border-left:3px solid {sig_color};border-radius:10px;padding:10px 16px;
                    margin-bottom:6px;display:flex;align-items:center;gap:12px'>
                    <span style='font-size:1rem;font-weight:800;color:{sig_color}'>{sig_label}</span>
                    <span style='font-size:.82rem;color:#9ca3af'>{sig_desc}</span>
                </div>""", unsafe_allow_html=True)

        # Macro tiles
        macro_keys = list(br_macro.keys())
        mc_cols = st.columns(len(macro_keys)) if macro_keys else []

        # Bearish on rise (yields, dollar, oil)
        bearish_rise = {"US 10Y", "US 2Y", "WTI Oil", "DXY"}

        for col, key in zip(mc_cols, macro_keys):
            d   = br_macro[key]
            val = d["value"]; chgp = d["change_pct"]; chg = d["change"]
            arrow = "▲" if chgp > 0 else "▼" if chgp < 0 else "—"
            # For yields/dollar/oil: rise = bearish (red), fall = bullish (green)
            if key in bearish_rise:
                tile_c = "#ef4444" if chgp > 0.05 else "#10b981" if chgp < -0.05 else "#6b7280"
                eq_label = "BEARISH ↑" if chgp > 0.1 else "BULLISH ↓" if chgp < -0.1 else "NEUTRAL"
            else:
                tile_c = "#10b981" if chgp > 0.05 else "#ef4444" if chgp < -0.05 else "#6b7280"
                eq_label = "BULLISH ↑" if chgp > 0.1 else "BEARISH ↓" if chgp < -0.1 else "NEUTRAL"

            # Special: VIX read
            if key == "VIX" or d["ticker"] == "^VIX":
                eq_label = "FEAR" if val > 20 else "CALM" if val > 15 else "COMPLACENT"
                tile_c = "#ef4444" if val > 25 else "#f59e0b" if val > 18 else "#10b981"

            col.markdown(f"""<div class='kpi-tile' style='border-top:2px solid {tile_c}'>
                <div class='kpi-label'>{key}</div>
                <div class='kpi-value' style='color:{tile_c}'>{val:.2f}</div>
                <div style='font-size:.68rem;color:{tile_c};font-weight:700'>
                    {arrow} {chgp:+.2f}%
                </div>
                <div style='font-size:.6rem;color:#4b5563;margin-top:2px'>{eq_label}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

        # Macro liquidity bar chart
        if br_macro:
            st.plotly_chart(macro_liquidity_chart(br_macro), use_container_width=True)

        # K-Economy quick reference
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        section("K-ECONOMY REGIME MATRIX  •  Signal Interpretation")
        kg_c1, kg_c2 = st.columns(2)
        with kg_c1:
            st.markdown("""<div class='card-sm'>
                <div style='font-size:.72rem;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px'>
                    BULLISH SIGNALS FOR TIER 1/2
                </div>
                <div style='font-size:.82rem;color:#9ca3af;line-height:2'>
                    <span style='color:#10b981'>✓</span> 10Y Yield falling (rate cut regime)<br>
                    <span style='color:#10b981'>✓</span> VIX &gt; 30 (retail panic = institutional buy)<br>
                    <span style='color:#10b981'>✓</span> HYG stable or rising (credit OK)<br>
                    <span style='color:#10b981'>✓</span> DXY weakening (EM capex flows)<br>
                    <span style='color:#10b981'>✓</span> Hyperscaler CapEx guidance raised<br>
                    <span style='color:#10b981'>✓</span> Book-to-Bill &gt; 1.0 for T1/T2 names
                </div>
            </div>""", unsafe_allow_html=True)
        with kg_c2:
            st.markdown("""<div class='card-sm'>
                <div style='font-size:.72rem;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px'>
                    HEDGE / AVOID SIGNALS
                </div>
                <div style='font-size:.82rem;color:#9ca3af;line-height:2'>
                    <span style='color:#ef4444'>✗</span> 10Y Yield &gt; 4.5% (tightening risk)<br>
                    <span style='color:#ef4444'>✗</span> VIX &lt; 13 + RSI &gt; 70 (complacency = top)<br>
                    <span style='color:#ef4444'>✗</span> HYG falling (credit spreads widening)<br>
                    <span style='color:#ef4444'>✗</span> Oil &gt; $90 (energy shock → hedge XLE)<br>
                    <span style='color:#ef4444'>✗</span> DXY &gt; 106 (liquidity squeeze)<br>
                    <span style='color:#ef4444'>✗</span> Core PCE &gt; 4% sticky (no pivot)
                </div>
            </div>""", unsafe_allow_html=True)

        # Protocol reminder
        st.markdown("""<div style='background:#0d1117;border:1px solid #1e2533;border-radius:10px;
            padding:12px 16px;margin-top:4px;font-size:.78rem;color:#4b5563;line-height:1.8'>
            <b style='color:#6b7280'>PROTOCOL RULE:</b>
            The bottom leg of the K-Economy (consumers, retail, cyclicals) is structurally impaired.
            We exclusively invest in the top leg: sovereign wealth CapEx flows and hyper-scaler infrastructure spending.
            If a data center cannot run without it → we own it.
        </div>""", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════════
    # MODULE 2 — 4-TIER KILL ZONE RADAR
    # ════════════════════════════════════════════════════════════════════════
    elif br_mod == "🎯 Kill Zone Radar":
        section("MODULE 2 — 4-TIER KILL ZONE RADAR  •  Proximity to 50SMA Buy Zones")

        with st.spinner("Scanning all 22 protocol tickers vs 50SMA…"):
            tier_df = load_tier_radar()

        if tier_df.empty:
            st.warning("Could not load tier radar data. Check connection.")
        else:
            # Summary tiles
            in_kz     = tier_df[tier_df["Dist_50SMA%"] <= 0]
            near_kz   = tier_df[(tier_df["Dist_50SMA%"] > 0) & (tier_df["Dist_50SMA%"] <= 3)]
            extended  = tier_df[tier_df["Dist_50SMA%"] > 8]
            t1_near   = tier_df[(tier_df["Tier"] == 1) & (tier_df["Dist_50SMA%"] <= 5)]

            rk1, rk2, rk3, rk4 = st.columns(4)
            with rk1:
                c = "#10b981" if len(in_kz) > 0 else "#6b7280"
                st.markdown(f"""<div class='kpi-tile' style='border-top:2px solid {c}'>
                    <div class='kpi-label'>In Kill Zone</div>
                    <div class='kpi-value' style='color:{c}'>{len(in_kz)}</div>
                    <div style='font-size:.7rem;color:{c};font-weight:700'>
                        {", ".join(in_kz["Ticker"].tolist()[:4]) or "None"}
                    </div>
                </div>""", unsafe_allow_html=True)
            with rk2:
                c = "#84cc16" if len(near_kz) > 0 else "#6b7280"
                st.markdown(f"""<div class='kpi-tile' style='border-top:2px solid {c}'>
                    <div class='kpi-label'>Approaching (&lt;3%)</div>
                    <div class='kpi-value' style='color:{c}'>{len(near_kz)}</div>
                    <div style='font-size:.7rem;color:{c};font-weight:700'>Place GTC limits</div>
                </div>""", unsafe_allow_html=True)
            with rk3:
                c = "#f59e0b" if len(t1_near) > 0 else "#6b7280"
                st.markdown(f"""<div class='kpi-tile' style='border-top:2px solid {c}'>
                    <div class='kpi-label'>T1 Near Zone</div>
                    <div class='kpi-value' style='color:{c}'>{len(t1_near)}</div>
                    <div style='font-size:.7rem;color:{c};font-weight:700'>Max priority watch</div>
                </div>""", unsafe_allow_html=True)
            with rk4:
                c = "#ef4444" if len(extended) > 5 else "#6b7280"
                st.markdown(f"""<div class='kpi-tile' style='border-top:2px solid {c}'>
                    <div class='kpi-label'>Extended / Chase</div>
                    <div class='kpi-value' style='color:{c}'>{len(extended)}</div>
                    <div style='font-size:.7rem;color:{c};font-weight:700'>No buy — wait for flush</div>
                </div>""", unsafe_allow_html=True)

            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

            # Kill zone radar chart
            # Only show T1-T3 in chart (T4 is always avoid)
            radar_df = tier_df[tier_df["Tier"] <= 3].copy()
            st.plotly_chart(kill_zone_radar(radar_df), use_container_width=True)

            # ── Tier tables (T1 priority) ─────────────────────────────────────
            for tier_num, tier_label, tier_color, tier_desc in [
                (1, "TIER 1 — ABSOLUTE MONOPOLIES (MAX CONVICTION)",         "#10b981",
                 "TSM · ASML · NVDA · VRT · POWL — 5–8% position size"),
                (2, "TIER 2 — CAPEX RECEIVERS (HIGH CONVICTION)",            "#3b82f6",
                 "GLW · AMAT · LRCX · CEG · VST · ETN · NVT — 3–5% position size"),
                (3, "TIER 3 — MOMENTUM / OPTICAL (MEDIUM CONVICTION)",        "#f59e0b",
                 "ONTO · AMD · MRVL · CAMT · LITE — 1–3% position size"),
            ]:
                section(f"{tier_label}  •  {tier_desc}")
                sub = tier_df[tier_df["Tier"] == tier_num].copy()
                if sub.empty:
                    st.info("No data loaded.")
                    continue

                rows_html = []
                for _, r in sub.iterrows():
                    zc   = r["ZoneColor"]
                    d50  = r["Dist_50SMA%"]
                    rsi  = r.get("RSI14")
                    rsi_c = "#ef4444" if (rsi or 50) > 70 else "#f59e0b" if (rsi or 50) > 60 else "#10b981"
                    trend_c = "#10b981" if r["Trend"] == "UPTREND" else "#ef4444"
                    ret1d_c = "#10b981" if r["Ret_1d%"] >= 0 else "#ef4444"
                    dist_bar = min(abs(d50) * 6, 80)
                    bar_c = zc
                    rows_html.append(f"""<tr style='border-bottom:1px solid #1e2533'>
                        <td style='padding:8px 10px;font-weight:800;color:{tier_color}'>{r["Ticker"]}</td>
                        <td style='padding:8px 10px;color:#9ca3af;font-size:.78rem'>{r["Description"]}</td>
                        <td style='padding:8px 10px;color:#f1f5f9;font-weight:600'>${r["Price"]:,.2f}</td>
                        <td style='padding:8px 10px;color:#9ca3af'>${r["50SMA"]:,.2f}</td>
                        <td style='padding:8px 12px;min-width:160px'>
                            <div style='display:flex;align-items:center;gap:8px'>
                                <div style='background:#1e2533;border-radius:4px;height:6px;width:80px;flex-shrink:0'>
                                    <div style='background:{bar_c};height:6px;border-radius:4px;width:{dist_bar:.0f}px'></div>
                                </div>
                                <span style='color:{zc};font-weight:700;font-size:.82rem'>{d50:+.2f}%</span>
                            </div>
                        </td>
                        <td style='padding:8px 10px'>
                            <span style='background:{zc}22;color:{zc};font-size:.68rem;font-weight:700;
                                         padding:2px 8px;border-radius:99px;white-space:nowrap'>{r["Zone"]}</span>
                        </td>
                        <td style='padding:8px 10px;color:{rsi_c};font-weight:600'>{rsi if rsi else "—"}</td>
                        <td style='padding:8px 10px;color:{trend_c};font-size:.72rem;font-weight:700'>{r["Trend"]}</td>
                        <td style='padding:8px 10px;color:{ret1d_c};font-weight:600'>{r["Ret_1d%"]:+.2f}%</td>
                        <td style='padding:8px 10px;color:#10b981;font-weight:700'>${r["Limit_Price"]:,.2f}</td>
                        <td style='padding:8px 10px;color:#ef4444;font-size:.78rem'>${r["Stop_Loss"]:,.2f}</td>
                    </tr>""")

                st.markdown(f"""
                <div style='border-radius:12px;overflow:hidden;border:1px solid {tier_color}44;margin-bottom:4px'>
                <table style='width:100%;border-collapse:collapse;background:#111827'>
                    <thead><tr style='background:#0d1117;border-bottom:1px solid #1e2533'>
                        <th style='padding:8px 10px;color:{tier_color};font-size:.7rem;font-weight:800;text-align:left'>TICKER</th>
                        <th style='padding:8px 10px;color:#6b7280;font-size:.7rem;font-weight:700;text-align:left'>NAME</th>
                        <th style='padding:8px 10px;color:#6b7280;font-size:.7rem;font-weight:700;text-align:left'>PRICE</th>
                        <th style='padding:8px 10px;color:#6b7280;font-size:.7rem;font-weight:700;text-align:left'>50SMA</th>
                        <th style='padding:8px 10px;color:#6b7280;font-size:.7rem;font-weight:700;text-align:left'>DIST</th>
                        <th style='padding:8px 10px;color:#6b7280;font-size:.7rem;font-weight:700;text-align:left'>ZONE</th>
                        <th style='padding:8px 10px;color:#6b7280;font-size:.7rem;font-weight:700;text-align:left'>RSI</th>
                        <th style='padding:8px 10px;color:#6b7280;font-size:.7rem;font-weight:700;text-align:left'>TREND</th>
                        <th style='padding:8px 10px;color:#6b7280;font-size:.7rem;font-weight:700;text-align:left'>1D</th>
                        <th style='padding:8px 10px;color:#10b981;font-size:.7rem;font-weight:800;text-align:left'>LIMIT $</th>
                        <th style='padding:8px 10px;color:#ef4444;font-size:.7rem;font-weight:700;text-align:left'>STOP $</th>
                    </tr></thead>
                    <tbody>{''.join(rows_html)}</tbody>
                </table></div>""", unsafe_allow_html=True)

            # T4 AVOID
            section("TIER 4 — STRICT AVOID ZONE  •  No buy under any conditions")
            t4_sub = tier_df[tier_df["Tier"] == 4]
            if not t4_sub.empty:
                t4_rows = []
                for _, r in t4_sub.iterrows():
                    rsi = r.get("RSI14")
                    t4_rows.append(f"""<tr style='border-bottom:1px solid #1e2533;opacity:0.6'>
                        <td style='padding:7px 10px;font-weight:700;color:#ef4444'>{r["Ticker"]}</td>
                        <td style='padding:7px 10px;color:#6b7280;font-size:.78rem'>{r["Thesis"][:60]}…</td>
                        <td style='padding:7px 10px;color:#9ca3af'>${r["Price"]:,.2f}</td>
                        <td style='padding:7px 10px;color:#ef444488;font-weight:600'>{r["Dist_50SMA%"]:+.2f}%</td>
                        <td style='padding:7px 10px;color:#ef444488;font-size:.72rem;font-weight:700'>{rsi if rsi else "—"}</td>
                        <td style='padding:7px 10px'>
                            <span style='background:#ef444422;color:#ef4444;font-size:.65rem;font-weight:700;padding:2px 8px;border-radius:99px'>
                                AVOID ✗
                            </span>
                        </td>
                    </tr>""")
                st.markdown(f"""
                <div style='border-radius:12px;overflow:hidden;border:1px solid #ef444444;margin-bottom:4px'>
                <table style='width:100%;border-collapse:collapse;background:#0d1117'>
                    <thead><tr style='border-bottom:1px solid #1e2533'>
                        <th style='padding:7px 10px;color:#ef4444;font-size:.7rem;font-weight:800;text-align:left'>TICKER</th>
                        <th style='padding:7px 10px;color:#4b5563;font-size:.7rem;font-weight:700;text-align:left'>REASON TO AVOID</th>
                        <th style='padding:7px 10px;color:#4b5563;font-size:.7rem;font-weight:700;text-align:left'>PRICE</th>
                        <th style='padding:7px 10px;color:#4b5563;font-size:.7rem;font-weight:700;text-align:left'>DIST 50SMA</th>
                        <th style='padding:7px 10px;color:#4b5563;font-size:.7rem;font-weight:700;text-align:left'>RSI</th>
                        <th style='padding:7px 10px;color:#4b5563;font-size:.7rem;font-weight:700;text-align:left'>STATUS</th>
                    </tr></thead>
                    <tbody>{''.join(t4_rows)}</tbody>
                </table></div>""", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════════
    # MODULE 3 — CATALYST ALERT SYSTEM
    # ════════════════════════════════════════════════════════════════════════
    elif br_mod == "📰 Catalyst Feed":
        section("MODULE 3 — CATALYST ALERT SYSTEM  •  Narrative Execution Filter")

        cat_left, cat_right = st.columns([1, 1])

        with cat_left:
            st.markdown("""<div class='card-sm' style='margin-bottom:10px'>
                <div style='font-size:.72rem;font-weight:700;color:#6b7280;text-transform:uppercase;
                            letter-spacing:.08em;margin-bottom:10px'>
                    INJECT CATALYST
                </div>
                <div style='font-size:.78rem;color:#4b5563;margin-bottom:8px'>
                    Paste a news headline below. The Narrative Execution Filter scores it
                    against Grade A/B/C criteria and checks for real CapEx vs AI dream narratives.
                </div>
            </div>""", unsafe_allow_html=True)

            cat_source = st.selectbox(
                "Source", ["Bloomberg", "Reuters", "WSJ", "Make.com Webhook",
                           "Discord Feed", "Manual", "SEC Filing", "Earnings Call"],
                label_visibility="collapsed",
            )
            cat_headline = st.text_input(
                "Headline", placeholder="e.g. TSMC reports record Q2 order backlog, book-to-bill 1.34…",
                label_visibility="collapsed",
            )
            cat_body = st.text_area(
                "Body (optional)", height=80, label_visibility="collapsed",
                placeholder="Paste full text for deeper scoring…",
            )

            if st.button("⚡ Score & Inject Catalyst", use_container_width=True) and cat_headline.strip():
                result = score_catalyst(cat_headline.strip(), cat_body.strip(), cat_source)
                save_catalyst(result)
                st.session_state["br_last_catalyst"] = result
                st.rerun()

            # Grade legend
            st.markdown("""<div class='card-sm' style='margin-top:8px'>
                <div style='font-size:.72rem;font-weight:700;color:#6b7280;text-transform:uppercase;
                            letter-spacing:.08em;margin-bottom:8px'>GRADING SYSTEM</div>
                <div style='font-size:.78rem;color:#9ca3af;line-height:2'>
                    <span style='color:#ef4444;font-weight:700'>Grade A</span>
                        — Macro regime shifts · T1/T2 CapEx events · Fed decisions<br>
                    <span style='color:#f59e0b;font-weight:700'>Grade B</span>
                        — Chips Act · Tariffs · Sector CapEx data · Supply chain<br>
                    <span style='color:#8b5cf6;font-weight:700'>Grade C</span>
                        — Black Swan · Oil shock · Geopolitical escalation<br>
                    <span style='color:#6b7280;font-weight:700'>Grade D</span>
                        — Noise · AI software PR · No immediate action
                </div>
                <div style='margin-top:10px;padding-top:10px;border-top:1px solid #1e2533;
                            font-size:.78rem;color:#9ca3af;line-height:2'>
                    <span style='color:#10b981;font-weight:700'>CAPEX REAL ✓</span>
                        — Signed contract / order backlog / Book-to-Bill data<br>
                    <span style='color:#ef4444;font-weight:700'>AI DREAM ✗</span>
                        — Partnership announcements / roadmaps / "exploring" language
                </div>
            </div>""", unsafe_allow_html=True)

        with cat_right:
            # Show last scored catalyst
            if "br_last_catalyst" in st.session_state:
                r = st.session_state["br_last_catalyst"]
                gc = r["color"]
                investable_html = (
                    "<span style='color:#10b981;font-weight:700'>INVESTABLE ✓</span>" if r["investable"] else
                    "<span style='color:#ef4444;font-weight:700'>NOT INVESTABLE ✗</span>" if r["investable"] is False else
                    "<span style='color:#6b7280;font-weight:700'>NEUTRAL</span>"
                )
                tier_html = " ".join([
                    f"<span style='background:{gc}22;color:{gc};font-size:.65rem;font-weight:700;padding:2px 7px;border-radius:99px'>{t}</span>"
                    for t in r.get("tier_affinity", [])
                ]) or "<span style='color:#4b5563;font-size:.75rem'>No specific tier mentioned</span>"

                st.markdown(f"""<div style='background:#0d1117;border:1px solid {gc}55;
                    border-left:3px solid {gc};border-radius:12px;padding:16px 20px'>
                    <div style='display:flex;align-items:center;gap:10px;margin-bottom:12px'>
                        <span style='background:{gc};color:#000;font-weight:900;font-size:.85rem;
                                     padding:4px 12px;border-radius:6px'>GRADE {r["grade"]}</span>
                        <span style='font-size:.82rem;color:{gc};font-weight:700'>{r["urgency"]}</span>
                    </div>
                    <div style='font-size:.95rem;font-weight:700;color:#f1f5f9;margin-bottom:8px'>
                        {r["headline"][:120]}
                    </div>
                    <div style='display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:10px'>
                        <span style='font-size:.78rem;font-weight:700;color:#9ca3af'>Narrative: </span>
                        <span style='font-size:.78rem;font-weight:700;
                            color:{"#10b981" if "REAL" in r["narrative"] else "#ef4444" if "DREAM" in r["narrative"] else "#6b7280"}'>{r["narrative"]}</span>
                        &nbsp;•&nbsp;
                        {investable_html}
                    </div>
                    <div style='font-size:.75rem;color:#6b7280;margin-bottom:6px'>Tier Affinity:</div>
                    <div>{tier_html}</div>
                </div>""", unsafe_allow_html=True)

            # Feed of stored catalysts
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            section("CATALYST FEED  •  Last 10 Signals")
            catalysts = load_catalysts()[:10]
            if not catalysts:
                st.markdown("""<div class='card-sm' style='text-align:center;color:#4b5563;padding:28px'>
                    No catalysts yet. Inject one above or connect Make.com webhook.
                </div>""", unsafe_allow_html=True)
            else:
                for c in catalysts:
                    gc = c["color"]
                    ts = c.get("timestamp","")[:16].replace("T"," ")
                    inv = "✓" if c.get("investable") else "✗" if c.get("investable") is False else "—"
                    inv_c = "#10b981" if c.get("investable") else "#ef4444" if c.get("investable") is False else "#6b7280"
                    st.markdown(f"""<div style='background:#111827;border:1px solid #1e2533;
                        border-left:3px solid {gc};border-radius:8px;padding:10px 14px;
                        margin-bottom:5px;display:flex;align-items:center;gap:12px'>
                        <span style='background:{gc};color:#000;font-size:.65rem;font-weight:900;
                                     padding:2px 8px;border-radius:5px;flex-shrink:0'>G{c["grade"]}</span>
                        <div style='flex:1;min-width:0'>
                            <div style='font-size:.82rem;color:#f1f5f9;font-weight:600;
                                        white-space:nowrap;overflow:hidden;text-overflow:ellipsis'>
                                {c["headline"][:90]}
                            </div>
                            <div style='font-size:.68rem;color:#6b7280;margin-top:2px'>
                                {c.get("source","manual")} &nbsp;•&nbsp; {ts}
                                &nbsp;•&nbsp; Narrative: <span style='color:{"#10b981" if "REAL" in c.get("narrative","") else "#ef4444" if "DREAM" in c.get("narrative","") else "#6b7280"}'>{c.get("narrative","—")}</span>
                                &nbsp;•&nbsp; <span style='color:{inv_c}'>Investable: {inv}</span>
                            </div>
                        </div>
                    </div>""", unsafe_allow_html=True)

                if st.button("🗑️ Clear Catalyst Feed", key="br_clear_cats"):
                    save_catalyst.__wrapped__ if hasattr(save_catalyst,'__wrapped__') else None
                    import json
                    from pathlib import Path
                    Path("/Users/danielitzhaky/markets map clude/data/catalysts.json").write_text("[]")
                    st.rerun()

    # ════════════════════════════════════════════════════════════════════════
    # MODULE 4 — EXECUTION COMMAND CENTER
    # ════════════════════════════════════════════════════════════════════════
    elif br_mod == "⚡ Execution Commands":
        section("MODULE 4 — EXECUTION COMMAND CENTER  •  Limit Orders · Position Sizing · Hedge Ratios")

        with st.spinner("Computing kill zone parameters…"):
            exec_df = load_tier_radar()   # shared cache with Kill Zone module

        # Gather hedge inputs from live data
        vix_now = float(_hdr_vix["VIX"].iloc[-1]) if not _hdr_vix.empty else None
        spy_series = None
        spy_rsi = None
        if not _hdr_vix.empty:
            try:
                from src.data.price_fetcher import fetch_history_robust
                from datetime import timedelta
                s_start = (datetime.now() - timedelta(days=80)).strftime("%Y-%m-%d")
                spy_s = fetch_history_robust("SPY", s_start)
                if spy_s is not None and len(spy_s) >= 14:
                    spy_rsi = compute_rsi(spy_s)
            except Exception:
                pass

        oil_val = None
        try:
            oil_val = load_oil_price()
        except Exception:
            pass

        breadth_50 = _breadth.get("pct_above_50d") if _breadth else None
        hedge = compute_hedge_params(vix_now, spy_rsi, breadth_50, oil_val)

        # ── Market Regime Banner ─────────────────────────────────────────────
        regime_sig  = hedge["regime_signal"]
        regime_data = {
            "BUY FLUSH":  ("#10b981", "🟢 BUY FLUSH PROTOCOL",  "VIX > 30 detected — Retail panic = institutional buy opportunity. Activate all GTC kill zone orders on T1/T2."),
            "HEDGE":      ("#ef4444", "🔴 HEDGE PROTOCOL",       "Overbought / complacency signals active. Open asymmetric put spreads on QQQ before close."),
            "NEUTRAL":    ("#3b82f6", "🔵 NEUTRAL — MONITOR",    "No extreme signals. Maintain GTC limits on kill zone stocks. Monitor yields and breadth daily."),
        }
        reg_color, reg_label, reg_desc = regime_data.get(regime_sig, ("#6b7280","—",""))
        # Pre-format to avoid invalid format specifier in f-string
        _vix_fmt  = f"{vix_now:.1f}"   if vix_now   else "—"
        _rsi_fmt  = f"{spy_rsi:.1f}"   if spy_rsi   else "—"
        _oil_fmt  = f"${oil_val:.1f}"  if oil_val   else "—"
        _rsi_col  = "#ef4444" if (spy_rsi or 0) > 70 else "#10b981"
        _oil_col  = "#f59e0b" if (oil_val or 0) > 90 else "#f1f5f9"
        st.markdown(f"""<div style='background:{reg_color}11;border:1px solid {reg_color}44;
            border-left:4px solid {reg_color};border-radius:12px;padding:14px 20px;
            margin-bottom:12px;display:flex;align-items:center;gap:14px'>
            <div>
                <div style='font-size:1.05rem;font-weight:800;color:{reg_color}'>{reg_label}</div>
                <div style='font-size:.82rem;color:#9ca3af;margin-top:4px'>{reg_desc}</div>
            </div>
            <div style='margin-left:auto;text-align:right;flex-shrink:0'>
                <div style='font-size:.68rem;color:#4b5563;font-weight:700;text-transform:uppercase'>LIVE INPUTS</div>
                <div style='font-size:.78rem;color:#9ca3af;margin-top:2px'>
                    VIX: <b style='color:#f1f5f9'>{_vix_fmt}</b> &nbsp;•&nbsp;
                    SPY RSI: <b style='color:{_rsi_col}'>{_rsi_fmt}</b> &nbsp;•&nbsp;
                    Oil: <b style='color:{_oil_col}'>{_oil_fmt}</b>
                </div>
            </div>
        </div>""", unsafe_allow_html=True)

        exec_c1, exec_c2 = st.columns([3, 2])

        with exec_c1:
            section("LIMIT ORDER PARAMETERS  •  Active Kill Zone & Approaching Stocks")

            if exec_df.empty:
                st.warning("No execution data.")
            else:
                # Show buy opportunities: Tier 1-3 only, within 8% of 50SMA
                buy_candidates = exec_df[
                    (exec_df["Tier"] <= 3) & (exec_df["Dist_50SMA%"] <= 8)
                ].sort_values(["Tier", "Dist_50SMA%"])

                if buy_candidates.empty:
                    st.info("No stocks within 8% of 50SMA. Market appears extended. Maintain GTC orders and wait for flush.")
                else:
                    for _, r in buy_candidates.iterrows():
                        tier_c = {1:"#10b981", 2:"#3b82f6", 3:"#f59e0b"}.get(r["Tier"], "#6b7280")
                        zc = r["ZoneColor"]
                        is_kz = r["Dist_50SMA%"] <= 0
                        priority = "🔴 EXECUTE NOW" if is_kz and r["Tier"]==1 else \
                                   "🟠 PLACE LIMIT"  if is_kz else \
                                   "🟡 PRE-POSITION"
                        st.markdown(f"""<div style='background:{"rgba(16,185,129,0.06)" if is_kz else "#111827"};
                            border:1px solid {"#10b98144" if is_kz else "#1e2533"};
                            border-left:3px solid {zc};border-radius:10px;
                            padding:12px 16px;margin-bottom:6px'>
                            <div style='display:flex;align-items:center;justify-content:space-between;margin-bottom:8px'>
                                <div style='display:flex;align-items:center;gap:8px'>
                                    <span style='font-size:1rem;font-weight:900;color:{tier_c}'>{r["Ticker"]}</span>
                                    <span style='background:{tier_c}22;color:{tier_c};font-size:.62rem;font-weight:700;padding:2px 7px;border-radius:99px'>T{r["Tier"]}</span>
                                    <span style='font-size:.72rem;color:{zc};font-weight:700'>{priority}</span>
                                </div>
                                <span style='font-size:.75rem;color:{zc};font-weight:700'>{r["Zone"]}</span>
                            </div>
                            <div style='display:grid;grid-template-columns:repeat(4,1fr);gap:6px'>
                                <div style='background:#0d1117;border-radius:6px;padding:7px 10px;text-align:center'>
                                    <div style='font-size:.6rem;color:#6b7280;font-weight:700;text-transform:uppercase'>Current</div>
                                    <div style='font-size:.9rem;font-weight:700;color:#f1f5f9'>${r["Price"]:,.2f}</div>
                                </div>
                                <div style='background:#0d1117;border-radius:6px;padding:7px 10px;text-align:center;border:1px solid #10b98133'>
                                    <div style='font-size:.6rem;color:#10b981;font-weight:700;text-transform:uppercase'>BUY LIMIT</div>
                                    <div style='font-size:.9rem;font-weight:800;color:#10b981'>${r["Limit_Price"]:,.2f}</div>
                                </div>
                                <div style='background:#0d1117;border-radius:6px;padding:7px 10px;text-align:center;border:1px solid #ef444433'>
                                    <div style='font-size:.6rem;color:#ef4444;font-weight:700;text-transform:uppercase'>STOP LOSS</div>
                                    <div style='font-size:.9rem;font-weight:700;color:#ef4444'>${r["Stop_Loss"]:,.2f}</div>
                                </div>
                                <div style='background:#0d1117;border-radius:6px;padding:7px 10px;text-align:center'>
                                    <div style='font-size:.6rem;color:#6b7280;font-weight:700;text-transform:uppercase'>TARGET 1</div>
                                    <div style='font-size:.9rem;font-weight:700;color:#3b82f6'>${r["Target_1"]:,.2f}</div>
                                </div>
                            </div>
                            <div style='display:flex;gap:12px;margin-top:8px;font-size:.72rem;color:#6b7280'>
                                <span>Size: <b style='color:{tier_c}'>{r["Min_Size%"]}–{r["Max_Size%"]}%</b> portfolio</span>
                                &nbsp;•&nbsp;
                                <span>R/R: <b style='color:#f1f5f9'>{r["RR_Ratio"]}:1</b></span>
                                &nbsp;•&nbsp;
                                <span>Dist: <b style='color:{zc}'>{r["Dist_50SMA%"]:+.2f}%</b> from 50SMA</span>
                                &nbsp;•&nbsp;
                                <span>RSI: <b style='color:{"#ef4444" if (r.get("RSI14") or 50)>70 else "#f1f5f9"}'>{r.get("RSI14","—")}</b></span>
                            </div>
                        </div>""", unsafe_allow_html=True)

        with exec_c2:
            section("HEDGE PARAMETERS  •  Asymmetric Protection")

            for h in hedge["hedges"]:
                hc = h["color"]
                st.markdown(f"""<div style='background:#111827;border:1px solid {hc}44;
                    border-left:3px solid {hc};border-radius:10px;padding:14px 16px;
                    margin-bottom:8px'>
                    <div style='display:flex;align-items:center;gap:8px;margin-bottom:10px'>
                        <span style='background:{hc}22;color:{hc};font-size:.65rem;font-weight:800;
                                     padding:2px 8px;border-radius:5px'>{h["priority"]}</span>
                        <span style='font-size:.82rem;font-weight:700;color:#f1f5f9'>{h["instrument"]}</span>
                    </div>
                    <div style='font-size:.8rem;color:#9ca3af;margin-bottom:4px'>
                        <b style='color:#6b7280'>Structure:</b> {h["structure"]}
                    </div>
                    <div style='font-size:.8rem;color:#9ca3af;margin-bottom:4px'>
                        <b style='color:#6b7280'>Size:</b> {h["size"]}
                    </div>
                    <div style='font-size:.8rem;color:#9ca3af;margin-bottom:8px'>
                        <b style='color:#6b7280'>Rationale:</b> {h["rationale"]}
                    </div>
                    <div style='font-size:.72rem;font-weight:700;color:{hc}'>{h["urgency"]}</div>
                </div>""", unsafe_allow_html=True)

            section("PROTOCOL RULES  •  Execution Discipline")
            st.markdown("""<div class='card-sm'>
                <div style='font-size:.78rem;color:#9ca3af;line-height:2.1'>
                    <span style='color:#ef4444;font-weight:700'>✗ NO CHASING</span>
                    — Never market-buy when RSI &gt; 70 or at ATH<br>
                    <span style='color:#10b981;font-weight:700'>✓ BUY LIMIT GTC</span>
                    — All orders sit deep at 50SMA kill zones<br>
                    <span style='color:#3b82f6;font-weight:700'>◎ LIQUIDITY AMBUSH</span>
                    — Wait for retail panic flush to fill limits<br>
                    <span style='color:#8b5cf6;font-weight:700'>⚡ ASYMMETRIC HEDGE</span>
                    — Put spreads on complacency, calls on oil shock<br>
                    <span style='color:#f59e0b;font-weight:700'>◈ 5% CASH</span>
                    — Permanent reserve for black swan opportunities<br>
                    <span style='color:#06b6d4;font-weight:700'>☑ SIGNED BACKLOG</span>
                    — Never buy narrative. Only buy proven CapEx flow.
                </div>
            </div>""", unsafe_allow_html=True)


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='text-align:center;color:#1e2533;font-size:.72rem;padding:16px 0 4px;
            border-top:1px solid #111827;margin-top:8px'>
    Markets Intelligence Dashboard &nbsp;•&nbsp; FRED · Yahoo Finance · SEC EDGAR · OpenInsider · Claude AI
    &nbsp;•&nbsp; Not financial advice &nbsp;•&nbsp; Prices may be delayed
</div>""", unsafe_allow_html=True)
