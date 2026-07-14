"""
Institutional-Grade Macroeconomics & Stock Analysis Dashboard
Run with: streamlit run app.py
"""
from __future__ import annotations

import os, sys
from datetime import datetime

# ── Page config — MUST be the absolute first Streamlit command ────────────────
import streamlit as st
st.set_page_config(
    page_title="Markets Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

import pandas as pd
import numpy as np
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
sys.path.insert(0, os.path.dirname(__file__))

# ── Streamlit Cloud secrets → os.environ bridge ───────────────────────────────
try:
    for _k in ["FRED_API_KEY","ANTHROPIC_API_KEY","MAKE_WEBHOOK_URL",
                "DISCORD_WEBHOOK_URL","UNUSUAL_WHALES_API_KEY","REFRESH_INTERVAL_SECONDS",
                "PLOTLY_USERNAME","PLOTLY_API_KEY"]:
        if _k in st.secrets and not os.getenv(_k):
            os.environ[_k] = str(st.secrets[_k])
except Exception:
    pass


# ── Security: redact secrets from anything shown to viewers ───────────────────
import re as _re

def redact_secrets(text) -> str:
    """Strip API keys, tokens, webhook URLs and configured secret values from
    any string before it is rendered in the UI (error messages, tracebacks)."""
    s = str(text)
    # exact values of every configured secret
    for _name in ["FRED_API_KEY", "ANTHROPIC_API_KEY", "MAKE_WEBHOOK_URL",
                  "DISCORD_WEBHOOK_URL", "UNUSUAL_WHALES_API_KEY",
                  "PLOTLY_API_KEY", "GITHUB_TOKEN"]:
        _v = os.getenv(_name, "")
        if _v and len(_v) >= 8:
            s = s.replace(_v, f"[{_name} REDACTED]")
    # common credential patterns
    s = _re.sub(r"api_key=[^&\s\"']+", "api_key=[REDACTED]", s)
    s = _re.sub(r"sk-ant-[A-Za-z0-9\-_]{8,}", "sk-ant-[REDACTED]", s)
    s = _re.sub(r"ghp_[A-Za-z0-9]{20,}", "ghp_[REDACTED]", s)
    s = _re.sub(r"(hook\.(?:eu\d+\.)?make\.com/)[A-Za-z0-9]+", r"\1[REDACTED]", s)
    s = _re.sub(r"(discord\.com/api/webhooks/)\S+", r"\1[REDACTED]", s)
    s = _re.sub(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", r"\1[REDACTED]", s)
    return s

try:
    from src.data.macro_data import fetch_macro_indicators
    from src.data.market_data import (
        fetch_quotes, fetch_relative_strength, fetch_vix_history,
        fetch_sector_performance, fetch_breadth_data, fetch_ohlcv, fetch_fundamentals,
        DEFAULT_WATCHLIST,
    )
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
        intraday_live_chart,
    )
    from src.data.price_fetcher import fetch_intraday_multi
    from src.data.sector_rating import fetch_sector_ratings, interpret_sector_score
    from src.data.sector_rotation import fetch_sector_rotation
    from src.components.charts import rotation_scores_chart, rs_flow_heatmap, ratings_scores_chart
    from src.data.cta_positioning import fetch_cta_positioning
    from src.components.charts import cot_net_chart, stock_deep_chart
    from src.components.charts import sector_detail_chart, yield_curve_chart, yield_spread_chart
    from src.data.yield_curve import fetch_yield_curve
    from src.data.ai_engine import (
        ask_ai, generate_market_brief, analyze_ticker,
        _build_market_context, is_ai_available,
    )
    from src.data.black_raven import (
        TIER_UNIVERSE, MASTER_WATCHLIST, score_catalyst, save_catalyst, load_catalysts,
        fetch_tier_radar, fetch_macro_matrix, fetch_raven_dashboard, compute_hedge_params,
        compute_rsi,
    )
    from src.data.tactical_agent import (
        build_live_context, ask_tactical_agent, is_agent_available, AGENT_SYSTEM_PROMPT,
    )
except Exception as _import_err:
    import traceback as _tb
    st.error(f"**Startup import error** — please report this:\n\n```\n{redact_secrets(_tb.format_exc())}\n```")
    st.stop()

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
.main { background: #0d141c; }
.stApp { background: #0d141c; }
.block-container { padding: 0.9rem 2.2rem 2.4rem; max-width: 1800px; }

/* Hide sidebar */
section[data-testid="stSidebar"]          { display: none !important; }
button[data-testid="collapsedControl"]    { display: none !important; }
[data-testid="stSidebarCollapsedControl"] { display: none !important; }

/* Cards */
.card {
    background: linear-gradient(135deg,#101828 0%,#0d141c 100%);
    border: 1px solid #1E2832; border-radius: 16px; padding: 20px 24px; margin-bottom: 12px;
}
.card-sm {
    background: #101828; border: 1px solid #1E2832; border-radius: 12px;
    padding: 12px 16px; margin-bottom: 8px;
}
.card-accent-green  { border-left: 3px solid #10b981 !important; }
.card-accent-red    { border-left: 3px solid #ef4444 !important; }
.card-accent-yellow { border-left: 3px solid #f59e0b !important; }
.card-accent-blue   { border-left: 3px solid #3b82f6 !important; }

/* KPI tiles */
.kpi-tile {
    background: linear-gradient(160deg,#16202e 0%,#101828 100%);
    border: 1px solid #243040; border-radius: 16px;
    padding: 15px 12px 11px; text-align: center; overflow: hidden;
    transition: border-color .18s ease, transform .18s ease, box-shadow .18s ease;
}
.kpi-tile:hover {
    border-color: #f00069; transform: translateY(-2px);
    box-shadow: 0 10px 28px rgba(240,0,105,.16);
}
.kpi-label { font-size: .68rem; color: #a2b6df; text-transform: uppercase;
             letter-spacing: .09em; font-weight: 700; margin-bottom: 4px; }
.kpi-value { font-size: 1.55rem; font-weight: 800; color: #fffffe; line-height: 1.12;
             letter-spacing: -.02em; }
.kpi-delta-pos { font-size: .8rem; color: #10b981; font-weight: 700; margin-top: 2px; }
.kpi-delta-neg { font-size: .8rem; color: #ef4444; font-weight: 700; margin-top: 2px; }
.kpi-spark { margin-top: 4px; opacity: .95; }

/* ── Ticker tape ── */
.tape-wrap {
    overflow: hidden; background: linear-gradient(90deg,#101828,#16202e 50%,#101828);
    border: 1px solid #243040; border-radius: 12px; margin: 2px 0 10px;
    position: relative; height: 38px; display:flex; align-items:center;
}
.tape-track {
    display: inline-flex; gap: 34px; white-space: nowrap; padding-left: 100%;
    animation: tape-scroll 45s linear infinite; align-items: center;
}
.tape-wrap:hover .tape-track { animation-play-state: paused; }
@keyframes tape-scroll {
    0%   { transform: translateX(0); }
    100% { transform: translateX(-100%); }
}
.tape-item { font-size: .82rem; font-weight: 700; color: #d5d4d0; }
.tape-item .sym { color: #5DC7D6; margin-right: 7px; font-weight: 800; }
.tape-item .up  { color: #10b981; }
.tape-item .dn  { color: #ef4444; }

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
    font-size: .72rem; font-weight: 800; color: #a2b6df; text-transform: uppercase;
    letter-spacing: .14em; margin: 20px 0 12px; padding: 0 0 7px 12px;
    border-bottom: 1px solid #1E2832; position: relative;
}
.section-title::before {
    content: ''; position: absolute; left: 0; top: 1px; bottom: 9px;
    width: 4px; border-radius: 4px;
    background: linear-gradient(180deg,#f00069,#0CABC2);
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] { gap: 6px; background: #101828; border-bottom: 1px solid #1E2832;
    padding: 4px 6px 0; border-radius: 14px 14px 0 0; position: sticky; top: 0; z-index: 50; }
.stTabs [data-baseweb="tab"] { background: transparent; border-radius: 10px 10px 0 0;
    padding: 12px 20px; font-weight: 700; font-size: .9rem; color: #a2b6df;
    transition: color .15s ease, background .15s ease; }
.stTabs [data-baseweb="tab"]:hover { color: #fffffe; background: #16202e; }
.stTabs [aria-selected="true"] { background: #1a2332 !important; color: #fffffe !important;
    border-top: 3px solid #f00069 !important; box-shadow: 0 -4px 18px rgba(240,0,105,.18); }

/* Input overrides */
.stTextArea textarea, .stTextInput input {
    background: #101828 !important; border: 1px solid #243040 !important;
    border-radius: 10px !important; color: #fffffe !important; font-size: .85rem !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: #f00069 !important; box-shadow: 0 0 0 2px rgba(240,0,105,.18) !important;
}
.stSelectbox div[data-baseweb="select"] > div {
    background: #101828 !important; border: 1px solid #243040 !important; color: #fffffe !important;
}
.stButton > button {
    background: #1E2832 !important; color: #fffffe !important; border: 1px solid #2d3a4a !important;
    border-radius: 10px !important; font-weight: 700 !important; font-size: .82rem !important;
    transition: all .15s ease !important;
}
.stButton > button:hover {
    background: #f00069 !important; border-color: #f00069 !important; color: #fff !important;
    box-shadow: 0 4px 16px rgba(240,0,105,.3) !important;
}

/* DataFrame */
.stDataFrame { border-radius: 14px !important; overflow: hidden; }
.stDataFrame thead th {
    background: #101828 !important; color: #a2b6df !important;
    font-size: .72rem !important; text-transform: uppercase; font-weight: 700;
    letter-spacing: .06em; border-bottom: 1px solid #1E2832 !important;
}
.stDataFrame tbody tr { border-bottom: 1px solid #1E2832 !important; }
.stDataFrame tbody tr:hover { background: #1a2332 !important; }
.stDataFrame tbody td { color: #fffffe !important; font-size: .85rem !important; }

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
.stRadio label { background: #101828; border: 1px solid #243040; border-radius: 10px;
    padding: 6px 16px !important; color: #a2b6df !important; font-weight: 600 !important;
    font-size: .8rem !important; transition: all .15s ease; }
.stRadio label:has(input:checked) { background: #2a1020 !important;
    border-color: #f00069 !important; color: #fffffe !important; }

/* Expander */
.streamlit-expanderHeader, [data-testid="stExpander"] summary {
    background: #101828 !important; border-radius: 12px !important;
    font-weight: 700 !important; color: #a2b6df !important;
}
[data-testid="stExpander"] {
    border: 1px solid #1E2832 !important; border-radius: 14px !important;
    background: #0f1622 !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0d141c; }
::-webkit-scrollbar-thumb { background: #243040; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #f00069; }
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
def load_vix(days: int = 252):
    return fetch_vix_history(days)

@st.cache_data(ttl=300, show_spinner=False)
def load_sector_perf():
    return fetch_sector_performance(["1d", "5d", "1mo", "3mo", "6mo", "1y"])

@st.cache_data(ttl=600, show_spinner=False)          # breadth is slow to compute — cache longer
def load_breadth():
    return fetch_breadth_data()

@st.cache_data(ttl=600, show_spinner=False)
def load_cta():
    return fetch_cta_exposure_proxy()

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

@st.cache_data(ttl=120, show_spinner=False)          # live tape — crypto/commodities/FX/yields
def load_tape_quotes():
    return fetch_quotes([
        "BTC-USD", "ETH-USD", "GC=F", "SI=F", "CL=F", "NG=F",
        "^TNX", "DX-Y.NYB", "EURUSD=X", "GBPUSD=X", "USDJPY=X",
        "SPY", "QQQ", "IWM", "DIA", "TLT", "HYG", "GLD",
    ])

@st.cache_data(ttl=120, show_spinner=False)          # intraday bars for live charts + sparklines
def load_intraday(tickers, interval: str = "5m", range_: str = "1d"):
    return fetch_intraday_multi(list(tickers), interval=interval, range_=range_)

@st.cache_data(ttl=900, show_spinner=False)          # sector ratings — 2y of bars × 12 ETFs
def load_sector_ratings():
    return fetch_sector_ratings(years=2)

@st.cache_data(ttl=300, show_spinner=False)          # BLACK RAVEN 50-stock sweep
def load_raven_dashboard():
    return fetch_raven_dashboard()

@st.cache_data(ttl=3600, show_spinner=False)         # Treasury yield curve — updates once per day EOD
def load_yield_curve():
    return fetch_yield_curve(years_back=3)

@st.cache_data(ttl=600, show_spinner=False)          # Sector Rotation Engine — RS math on 11 ETFs
def load_sector_rotation():
    return fetch_sector_rotation()

@st.cache_data(ttl=3600, show_spinner=False)         # real CFTC COT positioning — weekly data
def load_cta_positioning():
    return fetch_cta_positioning()

@st.cache_data(ttl=600, show_spinner=False)          # deep-dive series for drill-down panels
def load_deep_series(ticker: str):
    from src.data.price_fetcher import fetch_history_robust
    from datetime import timedelta
    start = (datetime.now() - timedelta(days=560)).strftime("%Y-%m-%d")
    s   = fetch_history_robust(ticker, start)
    spy = fetch_history_robust("SPY", start)
    return (s.sort_index() if s is not None and not s.empty else None,
            spy.sort_index() if spy is not None and not spy.empty else None)

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

def svg_spark(series, color: str = "#3b82f6", w: int = 110, h: int = 26) -> str:
    """Tiny inline SVG sparkline from a numeric series — zero dependencies."""
    try:
        vals = [float(v) for v in series if v is not None and v == v]  # drop NaN
    except Exception:
        return ""
    if len(vals) < 2:
        return ""
    # downsample to ≤60 points
    step = max(1, len(vals) // 60)
    vals = vals[::step]
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    pts = []
    for i, v in enumerate(vals):
        x = i / (len(vals) - 1) * w
        y = h - 2 - (v - lo) / rng * (h - 4)
        pts.append(f"{x:.1f},{y:.1f}")
    path = " ".join(pts)
    fill_pts = f"0,{h} {path.split(' ')[0]} {path} {w},{h}"
    return (
        f"<svg class='kpi-spark' width='{w}' height='{h}' viewBox='0 0 {w} {h}' "
        f"xmlns='http://www.w3.org/2000/svg'>"
        f"<polyline points='{fill_pts}' fill='{color}18' stroke='none'/>"
        f"<polyline points='{path}' fill='none' stroke='{color}' stroke-width='1.8' "
        f"stroke-linejoin='round' stroke-linecap='round'/></svg>"
    )

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
_hdr_quotes = pd.DataFrame()
_hdr_vix    = pd.DataFrame()
_breadth    = {}
_cta_data   = {}
_sector_df  = pd.DataFrame()
_tape_df    = pd.DataFrame()
_intraday   = {}
_wl_quotes  = pd.DataFrame()
_wl_intraday = {}
_wl_tuple = tuple(st.session_state.watchlist)
try:
    with _TPE(max_workers=9) as _ex:
        _f_quotes  = _ex.submit(load_quotes, ("SPY","QQQ","IWM","^VIX"))
        _f_vix     = _ex.submit(load_vix)
        _f_breadth = _ex.submit(load_breadth)
        _f_cta     = _ex.submit(load_cta)
        _f_sector  = _ex.submit(load_sector_perf)
        _f_tape    = _ex.submit(load_tape_quotes)
        _f_intra   = _ex.submit(load_intraday, ("SPY","QQQ","IWM","^VIX"))
        _f_wl_q    = _ex.submit(load_quotes, _wl_tuple)
        _f_wl_i    = _ex.submit(load_intraday, _wl_tuple)
        _hdr_quotes = _f_quotes.result()
        _hdr_vix    = _f_vix.result()
        _breadth    = _f_breadth.result()
        _cta_data   = _f_cta.result()
        _sector_df  = _f_sector.result()
        _tape_df    = _f_tape.result()
        _intraday   = _f_intra.result()
        _wl_quotes  = _f_wl_q.result()
        _wl_intraday = _f_wl_i.result()
except Exception as _prefetch_err:
    st.warning(f"⚠️ Prefetch error (non-fatal): {redact_secrets(_prefetch_err)}")

_hdr_map = dict(zip(_hdr_quotes["Ticker"], _hdr_quotes.to_dict("records"))) if not _hdr_quotes.empty else {}

# ══════════════════════════════════════════════════════════════════════════════
# HEADER — Title + pills + controls
# ══════════════════════════════════════════════════════════════════════════════
title_col, pills_col = st.columns([3, 5])

with title_col:
    st.markdown(f"""
    <div style='padding:6px 0 2px'>
        <div style='font-size:1.55rem;font-weight:800;letter-spacing:-.03em'>
            <span>📊</span>
            <span style='background:linear-gradient(90deg,#fffffe 30%,#5DC7D6 70%,#f00069 100%);
                    -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                    background-clip:text'>Markets Intelligence</span>
        </div>
        <div style='font-size:.72rem;color:#a2b6df;margin-top:3px'>
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
# LIVE TICKER TAPE — crypto / commodities / FX / yields
# ══════════════════════════════════════════════════════════════════════════════
_TAPE_LABELS = {
    "BTC-USD": "BTC", "ETH-USD": "ETH", "GC=F": "GOLD", "SI=F": "SILVER",
    "CL=F": "OIL", "NG=F": "NATGAS", "^TNX": "US10Y", "DX-Y.NYB": "DXY",
    "EURUSD=X": "EUR/USD", "GBPUSD=X": "GBP/USD", "USDJPY=X": "USD/JPY",
    "SPY": "S&P500", "QQQ": "NASDAQ", "IWM": "RUSSELL", "DIA": "DOW",
    "TLT": "20Y BOND", "HYG": "HY CREDIT", "GLD": "GLD",
}
if not _tape_df.empty:
    _items = []
    for _, _r in _tape_df.iterrows():
        _p, _c = _r.get("Price"), _r.get("Change %")
        if not isinstance(_p, (int, float)) or _p != _p:   # skip None and NaN
            continue
        if isinstance(_c, float) and _c != _c:
            _c = None
        _sym = _TAPE_LABELS.get(_r["Ticker"], _r["Ticker"])
        if _r["Ticker"] == "^TNX":
            _ps = f"{_p/10:.2f}%"
        elif _p >= 1000:
            _ps = f"{_p:,.0f}"
        elif _p >= 10:
            _ps = f"{_p:,.2f}"
        else:
            _ps = f"{_p:.4f}"
        _cls = "up" if (_c or 0) >= 0 else "dn"
        _arr = "▲" if (_c or 0) >= 0 else "▼"
        _items.append(
            f"<span class='tape-item'><span class='sym'>{_sym}</span>{_ps} "
            f"<span class='{_cls}'>{_arr} {abs(_c or 0):.2f}%</span></span>"
        )
    if _items:
        _tape_html = "".join(_items)
        st.markdown(
            f"<div class='tape-wrap'><div class='tape-track'>{_tape_html}"
            f"<span style='width:60px'></span>{_tape_html}</div></div>",
            unsafe_allow_html=True,
        )

# ══════════════════════════════════════════════════════════════════════════════
# TOP BAR — ROW 1: SPY / QQQ / IWM / VIX / Macro  (with live sparklines)
# ══════════════════════════════════════════════════════════════════════════════
r1 = st.columns(5)
for col, ticker, label in zip(r1[:3], ["SPY","QQQ","IWM"], ["S&P 500","Nasdaq 100","Russell 2000"]):
    with col:
        r = _hdr_map.get(ticker, {})
        p   = r.get("Price"); chg = r.get("Change %")
        p_s = f"${p:,.2f}" if isinstance(p,(int,float)) else "—"
        c_s = f"{chg:+.2f}%" if isinstance(chg,(int,float)) else "—"
        col_s = color_pct(chg)
        _spk = svg_spark(_intraday.get(ticker, []), col_s)
        st.markdown(f"""<div class='kpi-tile' style='border-top:2px solid {col_s}'>
            <div class='kpi-label'>{label}</div>
            <div class='kpi-value'>{p_s}</div>
            <div style='font-size:.8rem;color:{col_s};font-weight:700'>{c_s}</div>
            {_spk}
        </div>""", unsafe_allow_html=True)

with r1[3]:
    vix_val  = float(_hdr_vix["VIX"].iloc[-1]) if not _hdr_vix.empty else 0
    vix_prev = float(_hdr_vix["VIX"].iloc[-2]) if len(_hdr_vix)>1 else vix_val
    vix_chg  = vix_val - vix_prev
    vix_rgm  = "EXTREME FEAR" if vix_val>30 else "FEAR" if vix_val>20 else "NORMAL" if vix_val>15 else "COMPLACENT"
    vc = "#ef4444" if vix_val>25 else "#f59e0b" if vix_val>18 else "#10b981"
    _vspk = svg_spark(_intraday.get("^VIX", []), vc)
    st.markdown(f"""<div class='kpi-tile' style='border-top:2px solid {vc}'>
        <div class='kpi-label'>VIX Fear Index</div>
        <div class='kpi-value' style='color:{vc}'>{vix_val:.2f}</div>
        <div style='font-size:.72rem;color:{vc};font-weight:700'>
            {vix_rgm} &nbsp;<span style='color:{"#10b981" if vix_chg<0 else "#ef4444"}'>{vix_chg:+.2f}</span>
        </div>
        {_vspk}
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
# LIVE INTRADAY CHART — indices vs open, today's session
# ══════════════════════════════════════════════════════════════════════════════
with st.expander("📡 Live Market Chart — Indices vs Open", expanded=True):
    _live_range = st.radio(
        "Range", ["1D", "5D", "1M", "3M"], index=0, horizontal=True,
        key="live_chart_range", label_visibility="collapsed",
    )
    _range_cfg = {
        "1D": ("5m",  "1d"),
        "5D": ("15m", "5d"),
        "1M": ("1h",  "1mo"),
        "3M": ("1d",  "3mo"),
    }[_live_range]
    if _live_range == "1D":
        _live_series = {t: s for t, s in _intraday.items() if t in ("SPY", "QQQ", "IWM")}
    else:
        _live_series = load_intraday(("SPY", "QQQ", "IWM"), _range_cfg[0], _range_cfg[1])
    if _live_series:
        st.plotly_chart(
            intraday_live_chart(_live_series,
                {"SPY": "S&P 500", "QQQ": "Nasdaq 100", "IWM": "Russell 2000"},
                title=f"Live — {_live_range} • % Change"),
            use_container_width=True, config={"displayModeBar": False},
            key="pc_live_market",
        )
    else:
        st.info("Live chart data unavailable right now.")

def render_deep_dive(ticker: str, entry_px: float | None = None, entry_note: str = ""):
    """Drill-down analysis panel: MA-stack chart + RS panel + metrics matrix."""
    from src.data.black_raven import compute_rsi
    from src.data.price_fetcher import window_return

    with st.spinner(f"Deep analysis — {ticker}…"):
        s, spy = load_deep_series(ticker)
    if s is None or len(s) < 30:
        st.warning(f"No price history available for {ticker}.")
        return

    px = float(s.iloc[-1])
    chart_col, mx_col = st.columns([3, 1])
    with chart_col:
        st.plotly_chart(
            stock_deep_chart(s, spy, ticker, entry_px=entry_px, entry_note=entry_note),
            use_container_width=True, config={"displayModeBar": False},
            key=f"pc_deep_{ticker}",
        )
    with mx_col:
        section("Analysis Matrix")
        rsi = compute_rsi(s.tail(60))
        daily = s.pct_change().dropna()
        vol   = float(daily.std() * (252 ** 0.5)) * 100 if len(daily) > 20 else None
        dd    = float((s / s.cummax() - 1).min()) * 100

        rows_m: list[tuple[str, str, str]] = []
        for lbl, days in [("1W", 7), ("1M", 30), ("3M", 91), ("6M", 182), ("1Y", 365)]:
            r  = window_return(s, days)
            rs = window_return(spy, days) if spy is not None else None
            rel = (r - rs) if (r is not None and rs is not None) else None
            r_s   = f"{r:+.1f}%" if r is not None else "—"
            rel_s = f"{rel:+.1f}pp" if rel is not None else "—"
            rows_m.append((f"{lbl} Return", r_s, "#10b981" if (r or 0) >= 0 else "#ef4444"))
            rows_m.append((f"{lbl} vs SPY", rel_s, "#10b981" if (rel or 0) >= 0 else "#ef4444"))
        for n in (20, 50, 100, 200):
            if len(s) >= n:
                ma = float(s.tail(n).mean())
                dist = (px / ma - 1) * 100
                rows_m.append((f"vs SMA {n}", f"{dist:+.1f}%", "#10b981" if dist >= 0 else "#ef4444"))
        if rsi == rsi:
            rows_m.append(("RSI 14", f"{rsi:.0f}", "#ef4444" if rsi > 70 else "#0CABC2" if rsi < 30 else "#a2b6df"))
        if vol is not None:
            rows_m.append(("Ann. Vol", f"{vol:.0f}%", "#a2b6df"))
        rows_m.append(("Max DD", f"{dd:.0f}%", "#ef4444"))

        _mx_html = "".join(
            f"<div style='display:flex;justify-content:space-between;padding:5px 0;"
            f"border-bottom:1px solid #1E2832;font-size:.78rem'>"
            f"<span style='color:#a2b6df'>{l}</span>"
            f"<span style='color:{c};font-weight:700'>{v}</span></div>"
            for l, v, c in rows_m
        )
        st.markdown(f"<div class='card-sm'>{_mx_html}</div>", unsafe_allow_html=True)


def render_live_watchlist():
    """Live watchlist grid — real-time quotes + sparklines (shown in Watchlist & RS tab)."""
    if _wl_quotes.empty:
        return
    section("⚡ Live Watchlist")
    _wl_rows = [r for _, r in _wl_quotes.iterrows()
                if isinstance(r.get("Price"), (int, float)) and r.get("Price") == r.get("Price")]
    _per_row = 6
    for _start in range(0, len(_wl_rows), _per_row):
        _chunk = _wl_rows[_start:_start + _per_row]
        _cols = st.columns(_per_row)
        for _col, _r in zip(_cols, _chunk):
            with _col:
                _t   = _r["Ticker"]
                _p   = _r["Price"]
                _chg = _r.get("Change %")
                _cs  = color_pct(_chg)
                _c_s = f"{_chg:+.2f}%" if isinstance(_chg, (int, float)) else "—"
                _p_s = f"${_p:,.2f}" if _p >= 1 else f"${_p:.4f}"
                _spk = svg_spark(_wl_intraday.get(_t, []), _cs, w=100, h=22)
                st.markdown(f"""<div class='kpi-tile' style='border-top:2px solid {_cs};padding:10px 8px 8px'>
                    <div class='kpi-label'>{_t}</div>
                    <div class='kpi-value' style='font-size:1.15rem'>{_p_s}</div>
                    <div style='font-size:.75rem;color:{_cs};font-weight:700'>{_c_s}</div>
                    {_spk}
                </div>""", unsafe_allow_html=True)
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SECTOR RATINGS — rendered inside its own tab
# ══════════════════════════════════════════════════════════════════════════════
def render_sector_ratings():
    section("🏆 Sector Ratings — 10-Point System • 2-Year Data")
    try:
        _ratings = load_sector_ratings()
    except Exception:
        _ratings = {}

    if _ratings:
        if "selected_sector" not in st.session_state:
            st.session_state.selected_sector = None

        # Visual score breakdown across all sectors
        st.plotly_chart(ratings_scores_chart(_ratings), use_container_width=True,
                        config={"displayModeBar": False}, key="pc_ratings_scores")
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

        _ranked = sorted(_ratings.items(), key=lambda kv: kv[1]["total"], reverse=True)
        _per_row = 6
        for _start in range(0, len(_ranked), _per_row):
            _cols = st.columns(_per_row)
            for _col, (_name, _d) in zip(_cols, _ranked[_start:_start + _per_row]):
                with _col:
                    _v = _d["verdict"]
                    _fill = int(_d["total"] / 10 * 100)
                    st.markdown(f"""<div class='kpi-tile' style='border-top:2px solid {_v["color"]};padding:11px 8px 8px'>
                        <div class='kpi-label'>{_name}</div>
                        <div class='kpi-value' style='color:{_v["color"]};font-size:1.45rem'>{_d["total"]}<span style='font-size:.8rem;color:#475467'>/10</span></div>
                        <div style='background:#1E2832;border-radius:99px;height:5px;margin:6px 8px 4px'>
                            <div style='background:{_v["color"]};height:5px;border-radius:99px;width:{_fill}%'></div>
                        </div>
                        <div style='font-size:.6rem;color:{_v["color"]};font-weight:700'>{_v["emoji"]} {_v["label"].split("—")[0].strip()}</div>
                    </div>""", unsafe_allow_html=True)
                    if st.button("Breakdown", key=f"sec_btn_{_d['etf']}", use_container_width=True):
                        st.session_state.selected_sector = None if st.session_state.selected_sector == _name else _name

        # ── Breakdown panel for the clicked sector ────────────────────────────────
        _sel = st.session_state.selected_sector
        if _sel and _sel in _ratings:
            _d = _ratings[_sel]
            _v = _d["verdict"]
            st.markdown(f"""<div class='card' style='border-left:4px solid {_v["color"]};margin-top:10px'>
                <div style='display:flex;align-items:center;gap:14px;flex-wrap:wrap'>
                    <span style='font-size:1.9rem'>{_v["emoji"]}</span>
                    <div>
                        <div style='font-size:1.25rem;font-weight:800;color:#fffffe'>{_sel}
                            <span style='background:#1E2832;color:#a2b6df;font-size:.72rem;font-weight:700;padding:3px 10px;border-radius:99px;margin-left:8px'>{_d["etf"]}</span>
                        </div>
                        <div style='font-size:.85rem;color:{_v["color"]};font-weight:700;margin-top:2px'>{_v["label"]} • Score {_d["total"]}/10</div>
                    </div>
                    <div style='margin-left:auto;text-align:right'>
                        <div style='font-size:.68rem;color:#475467;text-transform:uppercase;font-weight:700'>Price</div>
                        <div style='font-size:1.2rem;font-weight:800;color:#fffffe'>${_d["price"]:,.2f}</div>
                    </div>
                </div>
                <div style='font-size:.86rem;color:#a2b6df;line-height:1.75;margin-top:12px'>{_d["situation"]}</div>
            </div>""", unsafe_allow_html=True)

            # Score components as chips
            _comp_cols = st.columns(4)
            for _cc, (_lbl, _pts, _max) in zip(_comp_cols, [
                ("3-Month Trend",  _d["score_3m"],  2),
                ("6-Month Trend",  _d["score_6m"],  2),
                ("YoY Trend",      _d["score_yoy"], 3),
                ("Above 200-D MA", _d["score_abs"], 3),
            ]):
                _cc2 = "#10b981" if _pts == _max else "#ef4444" if _pts == 0 else "#f59e0b"
                _cc.markdown(f"""<div class='kpi-tile' style='border-top:2px solid {_cc2}'>
                    <div class='kpi-label'>{_lbl}</div>
                    <div class='kpi-value' style='color:{_cc2};font-size:1.3rem'>{_pts}<span style='font-size:.75rem;color:#475467'>/{_max}</span></div>
                    <div style='font-size:.66rem;color:{_cc2};font-weight:700'>{"✅ EARNED" if _pts == _max else "❌ MISSED"}</div>
                </div>""", unsafe_allow_html=True)

            # Returns / risk row
            _stat_cols = st.columns(7)
            for _sc, (_lbl, _val, _sfx) in zip(_stat_cols, [
                ("1M Return", _d.get("ret_1m"), "%"), ("3M Return", _d.get("ret_3m"), "%"),
                ("6M Return", _d.get("ret_6m"), "%"), ("1Y Return", _d.get("ret_1y"), "%"),
                ("2Y Return", _d.get("ret_2y"), "%"), ("RS vs SPY 1Y", _d.get("rs_1y"), "pp"),
                ("Max Drawdown", _d.get("max_drawdown"), "%"),
            ]):
                if isinstance(_val, (int, float)):
                    _c = "#10b981" if _val >= 0 else "#ef4444"
                    _sc.markdown(f"""<div class='kpi-tile' style='padding:10px 6px 8px'>
                        <div class='kpi-label' style='font-size:.58rem'>{_lbl}</div>
                        <div style='font-size:1.02rem;font-weight:800;color:{_c}'>{_val:+.1f}{_sfx}</div>
                    </div>""", unsafe_allow_html=True)
                else:
                    _sc.markdown(f"""<div class='kpi-tile' style='padding:10px 6px 8px'>
                        <div class='kpi-label' style='font-size:.58rem'>{_lbl}</div>
                        <div style='font-size:1.02rem;font-weight:800;color:#475467'>—</div>
                    </div>""", unsafe_allow_html=True)

            st.plotly_chart(
                sector_detail_chart(_d["series"], _d.get("spy"), _sel),
                use_container_width=True, config={"displayModeBar": False},
                key="pc_sector_detail",
            )
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    else:
        st.info("Sector ratings unavailable — data fetch failed.")

# ══════════════════════════════════════════════════════════════════════════════
# PLOTLY CHART STUDIO — publish charts to the user's Plotly account
# ══════════════════════════════════════════════════════════════════════════════
with st.expander("📤 Share Charts — Interactive HTML Export", expanded=False):
    st.markdown("""<div class='card-sm' style='font-size:.8rem;color:#a2b6df;line-height:1.8'>
        Export any dashboard chart as a <b style='color:#5DC7D6'>standalone interactive HTML file</b> —
        full hover/zoom/pan, opens in any browser, no account needed. Send it to anyone or embed it in
        a site. <span style='color:#475467'>(Plotly discontinued Chart Studio uploads; your Plotly Cloud
        account hosts Dash apps instead — this export gives the same one-chart shareability.)</span>
    </div>""", unsafe_allow_html=True)

    def _build_export_fig(kind: str):
        if kind == "live":
            _series = {t: s for t, s in _intraday.items() if t in ("SPY", "QQQ", "IWM")}
            return intraday_live_chart(_series,
                {"SPY": "S&P 500", "QQQ": "Nasdaq 100", "IWM": "Russell 2000"})
        if kind == "yc":
            return yield_curve_chart(load_yield_curve())
        return yield_spread_chart(load_yield_curve().get("spread_2s10s"), "10Y − 2Y")

    _exp_choices = {
        "Live Market Chart — Indices vs Open": ("live",   "markets-live-indices.html"),
        "US Treasury Yield Curve":             ("yc",     "us-treasury-yield-curve.html"),
        "Yield Spread 10Y−2Y (3Y history)":    ("spread", "yield-spread-2s10s.html"),
    }
    _exp_pick = st.selectbox("Chart to export", list(_exp_choices.keys()),
                             label_visibility="collapsed", key="plotly_exp_pick")
    _kind, _fname = _exp_choices[_exp_pick]
    try:
        _html = _build_export_fig(_kind).to_html(include_plotlyjs="cdn", full_html=True)
        st.download_button(
            "⬇ Download Interactive Chart (HTML)", data=_html,
            file_name=_fname, mime="text/html", key="plotly_exp_dl",
        )
    except Exception as _exp_err:
        st.error(f"Export failed: {redact_secrets(_exp_err)}")

# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tabs = st.tabs([
    "🌡️  Macro Score",
    "🦅  Black Raven",
    "🤖  Tactical Agent",
    "🏆  Sector Ratings",
    "📈  Watchlist & RS",
    "🗺️  Heatmaps",
    "🫁  Market Breadth",
    "🌪️  Volatility & CTA",
    "🔔  Price Alerts",
    "🔍  Stock Review",
])
(tab_macro, tab_raven, tab_agent, tab_ratings, tab_watch, tab_heat_stocks,
 tab_breadth, tab_vol, tab_alert, tab_review) = tabs


# ══════════════════════════════════════════════════════════════════════════════
# TAB — SECTOR RATINGS (10-point method + visual breakdown)
# ══════════════════════════════════════════════════════════════════════════════
with tab_ratings:
    render_sector_ratings()


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
                    st.plotly_chart(macro_gauge(total), use_container_width=True, key="pc_992")

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
                st.plotly_chart(score_breakdown_bar([s.breakdown() for s in scores]), use_container_width=True, key="pc_1058")

                section("Historical Trend (24 Months)")
                spark_cols = st.columns(4)
                ind_keys = ["ISM_PMI","ISM_NMI","UMICH","BUILDING_PERMITS","NFIB_SBO","NFP","SPY"]
                for i,(key,sc) in enumerate(zip(ind_keys, scores)):
                    with spark_cols[i % 4]:
                        st.plotly_chart(macro_indicator_sparkline(
                            macro_data.get(key, pd.Series(dtype=float)), sc.name
                        ), use_container_width=True, key=f"macro_spark_{key}")

            except Exception as e:
                st.error(f"Macro data error: {redact_secrets(e)}")
                with st.expander("Debug"):
                    import traceback as _mtb
                    st.code(redact_secrets(_mtb.format_exc()), language="python")

    # ── US TREASURY YIELD CURVE — official Treasury Dept feed (no key) ────────
    section("🏛️ US Treasury Yield Curve — Official Treasury Department Data")
    try:
        _yc = load_yield_curve()
    except Exception:
        _yc = {}

    if _yc and "latest" in _yc:
        _l = _yc["latest"]
        _s2510 = _yc.get("spread_2s10s")
        _s3m10 = _yc.get("spread_3m10y")
        _inv   = _yc.get("inverted", False)

        _yc_cols = st.columns(6)
        _kpis = [
            ("3-Month",  _l.get("3 Mo"),  "%"), ("2-Year", _l.get("2 Yr"), "%"),
            ("10-Year",  _l.get("10 Yr"), "%"), ("30-Year", _l.get("30 Yr"), "%"),
        ]
        for _c, (_lbl, _v, _sfx) in zip(_yc_cols[:4], _kpis):
            _c.markdown(f"""<div class='kpi-tile'>
                <div class='kpi-label'>{_lbl} Yield</div>
                <div class='kpi-value' style='font-size:1.3rem'>{_v:.2f}{_sfx}</div>
            </div>""", unsafe_allow_html=True)
        with _yc_cols[4]:
            _sv = float(_s2510.iloc[-1]) if _s2510 is not None else None
            _sc = "#ef4444" if _inv else "#10b981"
            st.markdown(f"""<div class='kpi-tile' style='border-top:2px solid {_sc}'>
                <div class='kpi-label'>2s10s Spread</div>
                <div class='kpi-value' style='font-size:1.3rem;color:{_sc}'>{_sv:+.2f}pp</div>
                <div style='font-size:.64rem;color:{_sc};font-weight:700'>{"🚨 INVERTED" if _inv else "NORMAL SLOPE"}</div>
            </div>""", unsafe_allow_html=True)
        with _yc_cols[5]:
            _sv3 = float(_s3m10.iloc[-1]) if _s3m10 is not None else None
            _sc3 = "#ef4444" if (_sv3 is not None and _sv3 < 0) else "#10b981"
            st.markdown(f"""<div class='kpi-tile' style='border-top:2px solid {_sc3}'>
                <div class='kpi-label'>3m10y Spread</div>
                <div class='kpi-value' style='font-size:1.3rem;color:{_sc3}'>{_sv3:+.2f}pp</div>
                <div style='font-size:.64rem;color:{_sc3};font-weight:700'>{"🚨 INVERTED" if _sv3 is not None and _sv3 < 0 else "NORMAL SLOPE"}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        _yc1, _yc2 = st.columns(2)
        with _yc1:
            st.plotly_chart(yield_curve_chart(_yc), use_container_width=True,
                            config={"displayModeBar": False}, key="pc_yield_curve")
        with _yc2:
            if _s2510 is not None:
                st.plotly_chart(yield_spread_chart(_s2510, "10Y − 2Y"), use_container_width=True,
                                config={"displayModeBar": False}, key="pc_yield_spread")
        st.caption(f"Source: US Treasury Department daily yield curve rates (same primary source as "
                   f"ustreasuryyieldcurve.com) • As of {_yc.get('asof','—')} • Refreshes hourly")
    else:
        st.info("Treasury yield curve data unavailable right now.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — WATCHLIST & RS
# ══════════════════════════════════════════════════════════════════════════════
with tab_watch:
    render_live_watchlist()
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
            st.plotly_chart(watchlist_performance_chart(merged), use_container_width=True, key="pc_1184")

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
                return f"${v:,.2f}" if isinstance(v, (int, float)) and v == v and v else "—"

            def _fmt_chg(v):
                if not isinstance(v, (int, float)) or v != v:
                    return "—"
                col = "color:#10b981" if v >= 0 else "color:#ef4444"
                return f'<span style="{col};font-weight:700">{v:+.2f}%</span>'

            def _num(x):
                """Return float(x) or None for None/NaN/non-numeric — NaN-safe guard."""
                return float(x) if isinstance(x, (int, float)) and x == x else None

            # Render as HTML table for full color control
            rows_html = []
            for _, row in display.iterrows():
                ticker = row["Ticker"]
                price  = _fmt_price(row.get("Price"))
                chg    = _num(row.get("Change"))
                chgp   = _num(row.get("Change %"))
                chgp_s = f"{chgp:+.2f}%" if chgp is not None else "—"
                chg_s  = f"{chg:+.2f}" if chg is not None else "—"
                chg_c  = "#10b981" if (chgp or 0) >= 0 else "#ef4444"
                rs_s   = ""
                if rs_col and rs_col[0] in row:
                    rv = _num(row[rs_col[0]])
                    rs_c = "#10b981" if (rv or 0) >= 0 else "#ef4444"
                    rs_s = f'<td style="color:{rs_c};font-weight:600;padding:8px 10px">{rv:+.2f}</td>' if rv is not None else '<td style="color:#6b7280;padding:8px 10px">—</td>'
                vol_s = ""
                if "Volume" in row:
                    v = _num(row.get("Volume"))
                    vol_s = f'<td style="color:#9ca3af;padding:8px 10px">{int(v):,}</td>' if v else '<td style="color:#4b5563;padding:8px 10px">—</td>'

                row_bg = "rgba(16,185,129,0.04)" if (chgp or 0) >= 0 else "rgba(239,68,68,0.04)"
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

        # ── Relative strength across horizons ────────────────────────────────
        _rs_multi = [c for c in merged.columns if c.startswith("RS ") and "vs" not in c]
        if _rs_multi:
            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            section("Relative Strength vs SPY — 1M / 3M / 6M / 1Y")
            _rs_view = merged[["Ticker"] + _rs_multi].set_index("Ticker")
            st.dataframe(
                _rs_view.style
                    .format("{:+.2f}", na_rep="—")
                    .map(lambda v: "color:#10b981;font-weight:700" if isinstance(v,(int,float)) and v >= 0
                         else ("color:#ef4444;font-weight:700" if isinstance(v,(int,float)) else "color:#475467")),
                use_container_width=True, height=min(420, 38 * (len(_rs_view) + 1)),
            )

        # ── Quick deep-dive buttons — click any ticker for full analysis ─────
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        section("🔬 Click Any Ticker — Deep Analysis Chart & Matrix")
        pill_cols = st.columns(min(len(st.session_state.watchlist), 12))
        for i, t in enumerate(st.session_state.watchlist):
            with pill_cols[i % len(pill_cols)]:
                if st.button(t, key=f"wl_{t}", use_container_width=True):
                    st.session_state.selected_ticker = t
                    st.session_state.wl_deep_ticker = None if st.session_state.get("wl_deep_ticker") == t else t

        _deep_t = st.session_state.get("wl_deep_ticker")
        if _deep_t:
            _dd_meta = MASTER_WATCHLIST.get(_deep_t, {})
            st.markdown(f"""<div class='card' style='border-left:4px solid #f00069;margin-top:10px;padding:14px 20px'>
                <span style='font-size:1.15rem;font-weight:800;color:#fffffe'>🔬 {_deep_t}</span>
                <span style='color:#a2b6df;font-size:.82rem;margin-left:10px'>{_dd_meta.get("name","")}
                {("· " + _dd_meta["sector"]) if _dd_meta.get("sector") else ""}
                {("· Tier " + str(_dd_meta["tier"])) if _dd_meta.get("tier") else ""}</span>
            </div>""", unsafe_allow_html=True)
            render_deep_dive(_deep_t)

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
                use_container_width=True, key="pc_wl_heatmap"
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
                # Show sector names as tile labels (no duplicate columns)
                etf_map = dict(zip(_today_etfs["ETF"], _today_etfs["Sector"]))
                _etf_view = etf_quotes.copy()
                _etf_view["Ticker"] = _etf_view["Ticker"].map(lambda t: etf_map.get(t, t))
                st.plotly_chart(
                    stocks_heatmap(_etf_view, title="Sector ETF Heatmap — Today"),
                    use_container_width=True, key="pc_etf_heatmap"
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
        _PERIOD_LBL = {"1d":"Today","5d":"1 Week","1mo":"1 Month","3mo":"3 Months","6mo":"6 Months","1y":"1 Year"}
        p_col, _ = st.columns([5, 3])
        with p_col:
            period_choice = st.radio(
                "Timeframe", ["1d","5d","1mo","3mo","6mo","1y"], horizontal=True, index=0,
                key="heatmap_period",
                format_func=lambda x: _PERIOD_LBL[x],
            )

        hm_col, bar_col = st.columns([3, 2])
        with hm_col:
            st.plotly_chart(sector_heatmap(sector_df, period_choice), use_container_width=True, key="pc_1405")
        with bar_col:
            st.plotly_chart(sector_bars(sector_df, period_choice), use_container_width=True, key="pc_1407")

        section("Sector Performance Table — All Timeframes")
        pivot = sector_df.pivot_table(values="Return %", index="Sector", columns="Period")
        _pcols  = ["1d","5d","1mo","3mo","6mo","1y"]
        _pnames = ["Today %","1 Week %","1 Month %","3 Months %","6 Months %","1 Year %"]
        pivot = pivot.reindex(columns=_pcols).rename(columns=dict(zip(_pcols,_pnames)))
        pivot = pivot.dropna(axis=1, how="all")
        pivot = pivot.sort_values("Today %", ascending=False)

        sec_rows_html = []
        for sector, row in pivot.iterrows():
            td_html = f"<td style='padding:10px 14px;color:#d1d5db;font-weight:600'>{sector}</td>"
            for col_name in pivot.columns:
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
                {''.join(f"<th style='padding:10px 14px;color:#9ca3af;font-size:.72rem;font-weight:700;text-transform:uppercase;text-align:left'>{c.replace(' %','')}</th>" for c in pivot.columns)}
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
            st.plotly_chart(advance_decline_chart(ad_df), use_container_width=True, key="pc_1496")
    else:
        st.error("Breadth data unavailable.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — VOLATILITY & CTA
# ══════════════════════════════════════════════════════════════════════════════
with tab_vol:
    _vix_range = st.radio(
        "VIX history range", ["6M", "1Y", "2Y", "5Y"], index=1,
        horizontal=True, key="vix_range", label_visibility="collapsed",
    )
    _vix_days = {"6M": 126, "1Y": 252, "2Y": 504, "5Y": 1260}[_vix_range]
    with st.spinner("Loading VIX & CTA data…"):
        vix_df   = load_vix(_vix_days)
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
            st.plotly_chart(vix_chart(vix_df), use_container_width=True, key="pc_1555")
        with ts_col:
            if not term_df.empty:
                st.plotly_chart(vix_term_bar(term_df), use_container_width=True, key="pc_1558")
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

    # ── REAL CTA / FUND POSITIONING — CFTC COT ────────────────────────────────
    section("🏦 REAL CTA / Fund Positioning — CFTC Commitments of Traders (Official)")
    try:
        _cot = load_cta_positioning()
    except Exception:
        _cot = {}

    if _cot:
        _asof = next(iter(_cot.values()))["AsOf"]
        st.markdown(f"""<div style='font-size:.76rem;color:#a2b6df;margin-bottom:8px'>
            <b style='color:#5DC7D6'>Leveraged Funds</b> (hedge funds / CTAs / managed futures) on financials •
            <b style='color:#5DC7D6'>Managed Money</b> on commodities • Regulator-collected, published weekly •
            Positions as of <b style='color:#fffffe'>{_asof}</b></div>""", unsafe_allow_html=True)

        _mkts = list(_cot.values())
        _per_row = 4
        for _s0 in range(0, len(_mkts), _per_row):
            _ccols = st.columns(_per_row)
            for _cc, _m in zip(_ccols, _mkts[_s0:_s0 + _per_row]):
                _net_c = "#10b981" if _m["Net"] >= 0 else "#ef4444"
                _chg_c = "#10b981" if _m["Change_1w"] >= 0 else "#ef4444"
                _cc.markdown(f"""<div class='kpi-tile' style='border-top:2px solid {_m["Color"]};padding:12px 10px 9px'>
                    <div class='kpi-label' style='font-size:.6rem'>{_m["Market"]}</div>
                    <div class='kpi-value' style='font-size:1.15rem;color:{_net_c}'>{_m["Net"]:+,}</div>
                    <div style='font-size:.66rem;color:#a2b6df'>net contracts ({_m["Net_pct_OI"]:+.1f}% OI)</div>
                    <div style='font-size:.66rem;color:{_chg_c};font-weight:700'>Δ1w {_m["Change_1w"]:+,}</div>
                    <div style='background:#1E2832;border-radius:99px;height:4px;margin:6px 8px 4px'>
                        <div style='background:{_m["Color"]};height:4px;border-radius:99px;width:{_m["Pctile_3y"]:.0f}%'></div>
                    </div>
                    <div style='font-size:.58rem;color:{_m["Color"]};font-weight:800'>{_m["Regime"]} · {_m["Pctile_3y"]:.0f}th pct 3Y</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        _hist_pick = st.selectbox("Positioning history", list(_cot.keys()), index=0,
                                  label_visibility="collapsed", key="cot_hist_market")
        _hm = _cot.get(_hist_pick)
        if _hm is not None:
            st.plotly_chart(cot_net_chart(_hm["History"], _hist_pick),
                            use_container_width=True, config={"displayModeBar": False},
                            key="pc_cot_history")
        st.caption("Source: CFTC Traders-in-Financial-Futures + Disaggregated COT reports "
                   "(publicreporting.cftc.gov) — actual reported positions, updated every Friday "
                   "(as-of Tuesday). Percentile is the net position's rank over ~3 years of weekly data.")
    else:
        st.warning("CFTC COT API unavailable right now — retry shortly.")

    # ── CTA momentum model (secondary) ────────────────────────────────────────
    if cta_data:
        section("CTA Trend-Following Model Estimate  •  Momentum Z-Score (Daily Proxy)")

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

        st.plotly_chart(cta_exposure_chart(cta_data), use_container_width=True, key="pc_1638")
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
            st.error(f"Could not load {review_ticker}: {redact_secrets(fund['error'])}")
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
                    st.plotly_chart(candlestick_chart(price_df, review_ticker), use_container_width=True, key="pc_1753")
                else:
                    st.warning("Price data unavailable.")
            with fund_col:
                section("Key Metrics")
                def _fmt_px(v):  return f"${v:,.2f}" if isinstance(v,(int,float)) and v == v else "—"
                def _fmt_pct(v): return f"{v:+.1f}%" if isinstance(v,(int,float)) and v == v else "—"
                _sma50, _sma200 = fund.get("sma50"), fund.get("sma200")
                _px = fund.get("price")
                _trend = "—"
                if isinstance(_px,(int,float)) and isinstance(_sma50,(int,float)):
                    _trend = "Above 50D ✅" if _px > _sma50 else "Below 50D ⚠️"
                for lbl, val in [
                    ("1Y Return",     _fmt_pct(fund.get('ret_1y'))),
                    ("Volatility (1Y)", f"{fund.get('volatility')}%" if fund.get('volatility') is not None else "—"),
                    ("Max Drawdown",  _fmt_pct(fund.get('max_drawdown'))),
                    ("Trend",         _trend),
                    ("SMA 50",        _fmt_px(_sma50)),
                    ("SMA 200",       _fmt_px(_sma200)),
                    ("52W High",      _fmt_px(fund.get('52w_high'))),
                    ("52W Low",       _fmt_px(fund.get('52w_low'))),
                    ("Avg Volume",    f"{int(fund.get('avg_volume') or 0):,}" if fund.get('avg_volume') else "—"),
                    ("ROE",           f"{(fund.get('roe') or 0)*100:.1f}%" if fund.get('roe') else "—"),
                    ("Profit Margin", f"{(fund.get('profit_margin') or 0)*100:.1f}%" if fund.get('profit_margin') else "—"),
                    ("P/B Ratio",     f"{fund.get('pb_ratio') or '—'}"),
                    ("Debt/Equity",   f"{fund.get('debt_to_equity') or '—'}"),
                    ("Current Ratio", f"{fund.get('current_ratio') or '—'}"),
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
                            st.error(f"AI error: {redact_secrets(e)}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB — BLACK RAVEN EXECUTIVE DASHBOARD
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
        ["🦅 Master Dashboard", "🔄 Sector Rotation", "📡 Macro Matrix", "🎯 Kill Zone Radar", "📰 Catalyst Feed", "⚡ Execution Commands"],
        horizontal=True, label_visibility="collapsed",
    )
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════════
    # MODULE — SECTOR ROTATION ENGINE (Institutional Sector Scorecard)
    # ════════════════════════════════════════════════════════════════════════
    if br_mod == "🔄 Sector Rotation":
        section("SECTOR ROTATION ENGINE  •  RS Mathematics × Macro Paradigms  •  Institutional Scorecard")

        with st.spinner("Computing RS ratios, slopes & flow matrix…"):
            rot_df = load_sector_rotation()

        if rot_df.empty:
            st.error("Rotation engine returned no data.")
        else:
            # ── 1. Sector Ranking Table ──────────────────────────────────────
            _rows = []
            for _, _r in rot_df.iterrows():
                _flow_cells = ""
                for _h in ["RS_1W", "RS_1M", "RS_3M", "RS_6M", "RS_1Y"]:
                    _v = _r[_h]
                    if isinstance(_v, (int, float)) and not pd.isna(_v):
                        _fc = "#10b981" if _v > 0 else "#ef4444"
                        _flow_cells += f"<td style='padding:7px 8px;color:{_fc};font-weight:700;font-size:.78rem'>{_v:+.1f}</td>"
                    else:
                        _flow_cells += "<td style='padding:7px 8px;color:#475467'>—</td>"
                _st_c = "#10b981" if "ACCUMULATION" in _r["Slope_State"] else "#ef4444" if "DISTRIBUTION" in _r["Slope_State"] or "NEGATIVE" in _r["Slope_State"] else "#f59e0b"
                _q_struct = ("✓ RS&gt;QMA" if _r["Above_QMA"] else "✗ RS&lt;QMA") + " · " + ("✓ QMA&gt;YMA" if _r["QMA_gt_YMA"] else "✗ QMA&lt;YMA")
                _ov = _r["Overlay"]
                _ov_c = "#10b981" if _ov > 0 else "#ef4444" if _ov < 0 else "#475467"
                _rows.append(f"""<tr style='border-bottom:1px solid #1E2832'>
                    <td style='padding:7px 8px;font-weight:800;color:{_r["TierColor"]};font-size:1.02rem'>{_r["Final_Score"]:.1f}</td>
                    <td style='padding:7px 8px;font-weight:700;color:#fffffe'>{_r["Sector"]}
                        <span style='color:#475467;font-size:.72rem'>({_r["ETF"]})</span><br>
                        <span style='font-size:.66rem;color:#a2b6df'>{_q_struct}</span></td>
                    <td style='padding:7px 8px'><span style='background:{_r["TierColor"]}18;color:{_r["TierColor"]};
                        font-size:.7rem;font-weight:800;padding:3px 9px;border-radius:99px'>{_r["Tier"]}</span></td>
                    {_flow_cells}
                    <td style='padding:7px 8px;color:{_st_c};font-size:.72rem;font-weight:700'>{_r["Slope_State"].split(" — ")[0]}</td>
                    <td style='padding:7px 8px;color:{_ov_c};font-weight:800'>{_ov:+.0f}</td>
                    <td style='padding:7px 8px;color:#fffffe;font-weight:700;font-size:.78rem'>${_r["Ambush_50SMA"]:,.2f}<br>
                        <span style='font-size:.68rem;color:{"#10b981" if _r["Dist_Ambush%"]<=0 else "#f59e0b"}'>{_r["Dist_Ambush%"]:+.1f}% away</span></td>
                </tr>""")

            st.markdown(f"""<div style='border-radius:12px;overflow-x:auto;border:1px solid #1E2832'>
            <table style='width:100%;border-collapse:collapse;background:#101828;min-width:1000px'>
                <thead><tr style='background:#0d141c;border-bottom:1px solid #1E2832'>
                    {''.join(f"<th style='padding:8px;color:#a2b6df;font-size:.66rem;font-weight:800;text-transform:uppercase;text-align:left;letter-spacing:.05em'>{h}</th>"
                             for h in ["Score","Sector · RS Structure","Conviction Tier","RS 1W","RS 1M","RS 3M","RS 6M","RS 1Y","Slope","Macro","Ambush 50SMA"])}
                </tr></thead>
                <tbody>{''.join(_rows)}</tbody>
            </table></div>""", unsafe_allow_html=True)

            # ── Visual layer: conviction ranking + RS flow heatmap ───────────
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            _vc1, _vc2 = st.columns(2)
            with _vc1:
                st.plotly_chart(rotation_scores_chart(rot_df), use_container_width=True,
                                config={"displayModeBar": False}, key="pc_rot_scores")
            with _vc2:
                st.plotly_chart(rs_flow_heatmap(rot_df), use_container_width=True,
                                config={"displayModeBar": False}, key="pc_rot_heatmap")

            # ── 2 & 3. Flow analysis + macro alignment ───────────────────────
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            _fa, _ma = st.columns(2)
            with _fa:
                section("Slopes & Flow Analysis")
                _accum = rot_df[rot_df["Slope_State"].str.contains("ACCUMULATION")]["Sector"].tolist()
                _dist  = rot_df[rot_df["Slope_State"].str.contains("DISTRIBUTION|NEGATIVE")]["Sector"].tolist()
                st.markdown(f"""<div class='card-sm' style='font-size:.84rem;color:#a2b6df;line-height:1.9'>
                    <span style='color:#10b981;font-weight:700'>▲ Capital inflows (RS accelerating):</span><br>
                    {", ".join(_accum) if _accum else "None"}<br><br>
                    <span style='color:#ef4444;font-weight:700'>▼ Capital outflows (RS deteriorating):</span><br>
                    {", ".join(_dist) if _dist else "None"}
                </div>""", unsafe_allow_html=True)
            with _ma:
                section("Macro Alignment Check")
                _notes = []
                for _, _r in rot_df.iterrows():
                    if _r["Overlay"] != 0:
                        _al = "ALIGNED" if (_r["Overlay"] > 0) == (_r["Quant_Score"] >= 5) else "DIVERGENT"
                        _al_c = "#10b981" if _al == "ALIGNED" else "#f59e0b"
                        _notes.append(f"<span style='color:{_al_c};font-weight:700'>{_r['ETF']} {_al}</span> — {_r['Overlay_Note']} (quant {_r['Quant_Score']}/10)")
                st.markdown(f"""<div class='card-sm' style='font-size:.78rem;color:#a2b6df;line-height:2'>
                    {"<br>".join(_notes)}
                </div>""", unsafe_allow_html=True)

            # ── 4. Execution directives ──────────────────────────────────────
            section("Execution Directives — Liquidity Ambush Levels")
            _top = rot_df[rot_df["Final_Score"] >= 7]
            if _top.empty:
                st.info("No sectors currently qualify for capital deployment (score ≥ 7).")
            else:
                _ex_cols = st.columns(min(4, len(_top)))
                for _c, (_, _r) in zip(_ex_cols, _top.iterrows()):
                    _c.markdown(f"""<div class='kpi-tile' style='border-top:2px solid {_r["TierColor"]}'>
                        <div class='kpi-label'>{_r["Sector"]} ({_r["ETF"]})</div>
                        <div class='kpi-value' style='font-size:1.2rem;color:{_r["TierColor"]}'>${_r["Ambush_50SMA"]:,.2f}</div>
                        <div style='font-size:.64rem;color:#a2b6df;font-weight:600'>BUY LIMIT @ 50SMA · now {_r["Dist_Ambush%"]:+.1f}%</div>
                    </div>""", unsafe_allow_html=True)
            st.caption("Engine: RS ratio vs SPY → QMA(63)/YMA(252) structure → 21-bar slope regime → RS Flow matrix "
                       "(1W/1M/3M/6M/1Y calendar windows) → K-Economy penalty / Economy-of-Shortage premium. "
                       "Analytical tool — not financial advice.")

    # ════════════════════════════════════════════════════════════════════════
    # MODULE 0 — MASTER DASHBOARD (50-stock institutional table + BLACK RAVEN)
    # ════════════════════════════════════════════════════════════════════════
    if br_mod == "🦅 Master Dashboard":
        section("MASTER WATCHLIST — 50 CORE STOCKS  •  Spenders vs. Receivers  •  Live Algorithmic Alerts")

        with st.spinner("Running BLACK RAVEN sweep across 50 tickers…"):
            raven_df = load_raven_dashboard()

        if raven_df.empty:
            st.error("BLACK RAVEN sweep failed — no data returned.")
        else:
            # Alert distribution summary
            _n_risk  = int(raven_df["RAVEN"].str.contains("VaR|DE-GROSSING|ILLIQUIDITY").sum())
            _n_entry = int(raven_df["RAVEN"].str.contains("LIMIT ORDER|KILL ZONE").sum())
            _n_warn  = int(raven_df["RAVEN"].str.contains("SPOT UP|EXTENDED|200-SMA").sum())
            _n_safe  = int(raven_df["RAVEN"].str.contains("SAFE").sum())
            _sm = st.columns(4)
            for _c, (_lbl, _n, _clr) in zip(_sm, [
                ("🚨 Risk Events", _n_risk, "#ef4444"), ("🎯 Entry Signals", _n_entry, "#10b981"),
                ("⚠️ Tactical Warnings", _n_warn, "#f59e0b"), ("🟢 Safe / Stable", _n_safe, "#5DC7D6"),
            ]):
                _c.markdown(f"""<div class='kpi-tile' style='border-top:2px solid {_clr}'>
                    <div class='kpi-label'>{_lbl}</div>
                    <div class='kpi-value' style='color:{_clr}'>{_n}</div>
                </div>""", unsafe_allow_html=True)
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

            _tier_meta = {
                1: ("TIER 1 — ULTIMATE CONVICTION", "Monopolies, Absolute Scarcity & Pricing Power", "#10b981"),
                2: ("TIER 2 — HIGH CONVICTION", "Test, Measurement, Optics & Infrastructure Layer", "#5DC7D6"),
                3: ("TIER 3 — MEDIUM CONVICTION", "Policy Beta, Integration & Defensive Hedges", "#f59e0b"),
                4: ("TIER 4 — DANGER ZONE", "Spenders, Leveraged Cloud & OEMs Without Pricing Power — Avoid / Short Legs Only", "#ef4444"),
            }
            for _tier in [1, 2, 3, 4]:
                _sub = raven_df[raven_df["Tier"] == _tier]
                if _sub.empty:
                    continue
                _tl, _td, _tc = _tier_meta[_tier]
                st.markdown(f"""<div style='margin:14px 0 8px'>
                    <span style='background:{_tc}22;color:{_tc};font-size:.78rem;font-weight:800;
                                 padding:4px 14px;border-radius:99px;letter-spacing:.06em'>{_tl}</span>
                    <span style='font-size:.72rem;color:#475467;margin-left:10px'>{_td}</span>
                </div>""", unsafe_allow_html=True)

                _rows = []
                for _, _r in _sub.iterrows():
                    _dist = _r["Dist_Entry%"]
                    _dist_s = f"{_dist:+.1f}%" if isinstance(_dist, (int, float)) and not pd.isna(_dist) else "—"
                    _dist_c = "#10b981" if isinstance(_dist, (int, float)) and not pd.isna(_dist) and _dist <= 0 else "#f59e0b"
                    _entry_s = f"${_r['Entry_Price']:,.2f}" if isinstance(_r["Entry_Price"], (int, float)) and not pd.isna(_r["Entry_Price"]) else "—"
                    _r1d = _r["Ret_1d%"]
                    _r1d_c = "#10b981" if isinstance(_r1d, (int, float)) and _r1d >= 0 else "#ef4444"
                    _rows.append(f"""<tr style='border-bottom:1px solid #1E2832'>
                        <td style='padding:8px 10px;font-weight:800;color:#fffffe'>{_r["Ticker"]}</td>
                        <td style='padding:8px 10px;color:#d5d4d0'>{_r["Company"]}</td>
                        <td style='padding:8px 10px;color:#a2b6df;font-size:.78rem'>{_r["Sector"]}</td>
                        <td style='padding:8px 10px;color:#a2b6df;font-size:.78rem'>{_r["Entry_Rule"]}<br>
                            <span style='color:#fffffe;font-weight:700'>{_entry_s}</span></td>
                        <td style='padding:8px 10px;color:#fffffe;font-weight:700'>${_r["Price"]:,.2f}<br>
                            <span style='font-size:.72rem;color:{_r1d_c}'>{_r1d:+.2f}% 1d</span></td>
                        <td style='padding:8px 10px;color:{_dist_c};font-weight:700'>{_dist_s}</td>
                        <td style='padding:8px 10px'><span style='background:{_r["RavenColor"]}18;color:{_r["RavenColor"]};
                            font-size:.72rem;font-weight:800;padding:3px 10px;border-radius:99px'>{_r["RAVEN"]}</span></td>
                    </tr>""")

                st.markdown(f"""<div style='border-radius:12px;overflow-x:auto;border:1px solid #1E2832'>
                <table style='width:100%;border-collapse:collapse;background:#101828;min-width:900px'>
                    <thead><tr style='background:#0d141c;border-bottom:1px solid #1E2832'>
                        {''.join(f"<th style='padding:8px 10px;color:#a2b6df;font-size:.68rem;font-weight:800;text-transform:uppercase;text-align:left;letter-spacing:.05em'>{h}</th>"
                                 for h in ["Ticker","Company","Hardware Sector","Optimal Entry","Price","Dist to Entry","BLACK RAVEN"])}
                    </tr></thead>
                    <tbody>{''.join(_rows)}</tbody>
                </table></div>""", unsafe_allow_html=True)

            st.caption("BLACK RAVEN alert engine: VaR breach → CTA de-grossing → illiquidity trap → Spot Up/Vol Up → "
                       "structure breaks → limit-order triggers → kill zones. Limit orders only at algorithmic support zones — never chase thin books.")

            # ── Deep analysis drill-down ─────────────────────────────────────
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            section("🔬 Deep Analysis — Pick Any Watchlist Stock")
            _rv_pick = st.selectbox(
                "Deep analysis ticker",
                raven_df["Ticker"].tolist(),
                format_func=lambda t: f"{t} — {MASTER_WATCHLIST.get(t,{}).get('name',t)} (T{MASTER_WATCHLIST.get(t,{}).get('tier','?')})",
                label_visibility="collapsed", key="raven_deep_pick",
            )
            if _rv_pick:
                _rv_row = raven_df[raven_df["Ticker"] == _rv_pick].iloc[0]
                _rv_alert_c = _rv_row["RavenColor"]
                st.markdown(f"""<div class='card' style='border-left:4px solid {_rv_alert_c};padding:12px 20px'>
                    <span style='font-size:1.05rem;font-weight:800;color:#fffffe'>{_rv_pick}</span>
                    <span style='color:#a2b6df;font-size:.8rem;margin-left:8px'>{_rv_row["Company"]} · {_rv_row["Sector"]}</span>
                    <span style='background:{_rv_alert_c}18;color:{_rv_alert_c};font-size:.7rem;font-weight:800;
                          padding:3px 10px;border-radius:99px;margin-left:10px'>{_rv_row["RAVEN"]}</span>
                </div>""", unsafe_allow_html=True)
                _rv_entry = _rv_row["Entry_Price"]
                render_deep_dive(
                    _rv_pick,
                    entry_px=float(_rv_entry) if isinstance(_rv_entry, (int, float)) and _rv_entry == _rv_entry else None,
                    entry_note=str(_rv_row["Entry_Rule"]),
                )

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
            st.plotly_chart(macro_liquidity_chart(br_macro), use_container_width=True, key="pc_2103")

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
            st.plotly_chart(kill_zone_radar(radar_df), use_container_width=True, key="pc_2202")

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
                    from src.data.black_raven import CATALYSTS_FILE
                    CATALYSTS_FILE.parent.mkdir(parents=True, exist_ok=True)
                    CATALYSTS_FILE.write_text("[]")
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


# ══════════════════════════════════════════════════════════════════════════════
# TAB — TACTICAL AI AGENT (interactive command center)
# ══════════════════════════════════════════════════════════════════════════════
with tab_agent:
    st.markdown("""
    <div style='background:linear-gradient(135deg,#101828,#0d141c);border:1px solid #1E2832;
                border-left:3px solid #f00069;border-radius:14px;padding:16px 22px;margin-bottom:8px'>
        <span style='font-size:1.15rem;font-weight:900;color:#fffffe'>🤖 TACTICAL AI AGENT</span>
        <span style='color:#a2b6df;font-size:.78rem;margin-left:10px'>
            Black Raven command center — live data querying · scenario building · strict protocol adherence
        </span>
    </div>""", unsafe_allow_html=True)

    if not is_agent_available():
        st.markdown("""<div class='card-sm' style='font-size:.84rem;color:#a2b6df;line-height:1.9'>
            <b style='color:#f00069'>Agent offline — API key required.</b><br>
            Add <code>ANTHROPIC_API_KEY = "sk-ant-..."</code> to <code>.env</code> (local) or
            Streamlit Cloud → Settings → Secrets, then refresh. Get a key at
            <a href='https://platform.claude.com' target='_blank' style='color:#5DC7D6'>platform.claude.com</a>.
        </div>""", unsafe_allow_html=True)
    else:
        if "agent_chat" not in st.session_state:
            st.session_state.agent_chat = []

        # Quick-strike prompts
        _qs = st.columns(3)
        _quick = None
        with _qs[0]:
            if st.button("🎯 Kill-zone status — Tier 1/2 vs entries", use_container_width=True, key="qa1"):
                _quick = "Which Tier 1 and Tier 2 stocks are at or within 3% of their entry zones right now? Table with exact GTC limit levels."
        with _qs[1]:
            if st.button("⚡ Liquidity Ambush plan: QQQ −2% day", use_container_width=True, key="qa2"):
                _quick = "Generate a Liquidity Ambush plan if QQQ drops 2% today. Cold if-then execution framework with GTC buy limits from live data."
        with _qs[2]:
            if st.button("📡 Full tactical brief", use_container_width=True, key="qa3"):
                _quick = "Full tactical brief: yields, VIX, COT positioning extremes, sector rotation leaders/laggards, top 3 protocol opportunities. Cite live numbers."

        # Replay history
        for _m in st.session_state.agent_chat:
            with st.chat_message(_m["role"], avatar="🦅" if _m["role"] == "assistant" else "👤"):
                st.markdown(_m["content"])

        _user_q = st.chat_input("Ask the agent — live data, scenarios, execution frameworks…")
        if _quick and not _user_q:
            _user_q = _quick

        if _user_q:
            with st.chat_message("user", avatar="👤"):
                st.markdown(_user_q)
            with st.chat_message("assistant", avatar="🦅"):
                with st.spinner("Agent computing — injecting live dashboard state…"):
                    try:
                        # Step 2: dynamic context injection — the agent sees the live
                        # sector matrix, 51-stock raven sweep, macro & COT feeds
                        _ctx = build_live_context(
                            raven_df=load_raven_dashboard(),
                            rotation_df=load_sector_rotation(),
                            macro_matrix={k: v for k, v in (load_macro_matrix() or {}).items()
                                          if not k.startswith("_")},
                            yield_curve=load_yield_curve(),
                            vix_value=float(_hdr_vix["VIX"].iloc[-1]) if not _hdr_vix.empty else None,
                            cot=load_cta_positioning(),
                        )
                        _answer = ask_tactical_agent(_user_q, st.session_state.agent_chat, _ctx)
                    except Exception as _agent_err:
                        _answer = f"⚠️ Agent error: {redact_secrets(_agent_err)}"
                st.markdown(_answer)
            st.session_state.agent_chat.append({"role": "user", "content": _user_q})
            st.session_state.agent_chat.append({"role": "assistant", "content": _answer})

        if st.session_state.agent_chat:
            if st.button("🗑 Clear session", key="agent_clear"):
                st.session_state.agent_chat = []
                st.rerun()

        st.caption("Context injected per turn: 51-stock BLACK RAVEN sweep · Sector Rotation scorecard · "
                   "macro matrix · Treasury curve · VIX · CFTC COT positioning. "
                   "Protocol analytics — not financial advice.")


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='text-align:center;color:#1e2533;font-size:.72rem;padding:16px 0 4px;
            border-top:1px solid #111827;margin-top:8px'>
    Markets Intelligence Dashboard &nbsp;•&nbsp; FRED · Yahoo Finance · SEC EDGAR · OpenInsider · Claude AI
    &nbsp;•&nbsp; Not financial advice &nbsp;•&nbsp; Prices may be delayed
</div>""", unsafe_allow_html=True)
