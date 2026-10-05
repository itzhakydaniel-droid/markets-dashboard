"""Desk Prep tab — daily briefing, club watchlist tracking, market data, potential hedges.

Reads the analyst outputs in insiders_club/ (briefings, ranking, quality screen,
estimate-revision table) and joins them with live Yahoo data.
"""
from __future__ import annotations

import glob
import os
import re

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "insiders_club")
BRIEF_DIR = os.path.join(ROOT, "briefing")
KNOW_DIR = os.path.join(ROOT, "knowledge")

RTL_CSS = """
<style>
.rtl {direction: rtl; text-align: right; font-size: .92rem; line-height: 1.7;}
.rtl table {direction: rtl; border-collapse: collapse; width: 100%; margin: 8px 0 14px; font-size: .84rem;}
.rtl th {background: #111827; color: #9ca3af; font-weight: 600; padding: 6px 8px; border: 1px solid #1f2937; text-align: right;}
.rtl td {padding: 5px 8px; border: 1px solid #1f2937; vertical-align: top;}
.rtl h1 {font-size: 1.35rem;} .rtl h2 {font-size: 1.12rem; margin-top: 18px; border-bottom: 1px solid #1f2937; padding-bottom: 4px;}
.rtl h3 {font-size: 1rem;}
.rtl code {direction: ltr; unicode-bidi: embed;}
.desk-note {direction: rtl; text-align: right; color: #9ca3af; font-size: .8rem; margin: 2px 0 10px;}
</style>
"""

MACRO = {"ES=F": "חוזה S&P", "NQ=F": "חוזה נאסד\"ק", "^VIX": "VIX", "^TNX": "תשואת 10 שנים",
         "DX-Y.NYB": "דולר (DXY)", "BZ=F": "ברנט", "GC=F": "זהב", "HYG": "אג\"ח זבל (HYG)"}
INDICES = ["SPY", "QQQ", "SMH", "IWM", "RSP"]
HEDGE_VEHICLES = ["SPY", "QQQ", "SMH", "IWM"]


def _rtl(html: str):
    st.markdown(f"<div class='rtl'>{html}</div>", unsafe_allow_html=True)


def _note(text: str):
    st.markdown(f"<div class='desk-note'>{text}</div>", unsafe_allow_html=True)


# ── Data ──────────────────────────────────────────────────────────────────────
def list_briefings() -> list[str]:
    files = glob.glob(os.path.join(BRIEF_DIR, "20*.md"))
    return sorted((os.path.basename(f)[:-3] for f in files), reverse=True)


def read_briefing(day: str) -> str:
    with open(os.path.join(BRIEF_DIR, f"{day}.md"), encoding="utf-8") as f:
        return f.read()


_BLOCK_START = re.compile(r"^(\||- |\* |\d+\. )")


def _md_to_html(md: str) -> str:
    """Python-Markdown needs a blank line before tables/lists; the briefings often omit it."""
    import markdown
    out, prev = [], ""
    for line in md.splitlines():
        if _BLOCK_START.match(line) and prev.strip() and not _BLOCK_START.match(prev):
            out.append("")
        out.append(line)
        prev = line
    return markdown.markdown("\n".join(out), extensions=["tables", "sane_lists"])


@st.cache_data(ttl=120, show_spinner=False)
def _closes(tickers: tuple[str, ...], period: str = "1y") -> pd.DataFrame:
    c = yf.download(list(tickers), period=period, progress=False, auto_adjust=True)["Close"]
    return c.to_frame(tickers[0]) if isinstance(c, pd.Series) else c


def _trend_row(x: pd.Series) -> dict:
    x = x.dropna()
    p = float(x.iloc[-1])
    sma = {n: float(x.tail(n).mean()) for n in (50, 100, 200)}
    below = {n: v for n, v in sma.items() if v < p}
    amb_n, amb_v = (max(below.items(), key=lambda kv: kv[1]) if below else (None, None))
    return dict(price=p, day=p / float(x.iloc[-2]) - 1, d50=p / sma[50] - 1, d200=p / sma[200] - 1,
                from_hi=p / float(x.max()) - 1, m1=p / float(x.iloc[-22]) - 1,
                sma50=sma[50], sma100=sma[100], sma200=sma[200],
                ambush=f"ממוצע {amb_n}" if amb_n else "מתחת לכל הממוצעים",
                ambush_px=amb_v, to_ambush=(amb_v / p - 1) if amb_v else np.nan)


def _status(r) -> str:
    near = min(abs(r.price / r.sma50 - 1), abs(r.price / r.sma100 - 1), abs(r.price / r.sma200 - 1))
    if r.d200 < 0:
        return "🔴 מגמה שבורה"
    if near <= 0.015:
        return "🎯 ברשת"
    if r.d50 > 0.15:
        return "🟠 מתוחה — לא לרדוף"
    return "🟢 מגמה תקינה"


@st.cache_data(ttl=120, show_spinner=False)
def watchlist_table() -> pd.DataFrame:
    rank_path = os.path.join(KNOW_DIR, "club_ranking.csv")
    rk = pd.read_csv(rank_path)
    c = _closes(tuple(rk.ticker))
    rows = []
    for t in rk.ticker:
        if t in c and c[t].dropna().size > 200:
            rows.append(dict(ticker=t, **_trend_row(c[t])))
    d = rk.merge(pd.DataFrame(rows), on="ticker", how="left")
    scr = os.path.join(ROOT, "screen_latest.csv")
    if os.path.exists(scr):
        s = pd.read_csv(scr)[["ticker", "grade", "fcf_pos", "fwdPE"]]
        d = d.merge(s, on="ticker", how="left")
    est = os.path.join(KNOW_DIR, "estimates_ratio.csv")
    if os.path.exists(est):
        d = d.merge(pd.read_csv(est), on="ticker", how="left")
    d["status"] = d.apply(_status, axis=1)
    return d


@st.cache_data(ttl=120, show_spinner=False)
def macro_table() -> tuple[pd.DataFrame, pd.DataFrame]:
    c = _closes(tuple(MACRO), period="3mo").ffill()
    m = []
    for t, name in MACRO.items():
        x = c[t].dropna()
        if len(x) < 6:
            continue
        m.append(dict(name=name, last=float(x.iloc[-1]), day=float(x.iloc[-1] / x.iloc[-2] - 1),
                      week=float(x.iloc[-1] / x.iloc[-6] - 1)))
    ci = _closes(tuple(INDICES))
    idx = [dict(ticker=t, **_trend_row(ci[t])) for t in INDICES if t in ci]
    return pd.DataFrame(m), pd.DataFrame(idx)


@st.cache_data(ttl=900, show_spinner=False)
def hedge_table(dmin: int, dmax: int, long_otm: float, short_otm: float) -> pd.DataFrame:
    from src.data.options import put_spread
    rows = []
    for t in HEDGE_VEHICLES:
        try:
            r = put_spread(t, dmin, dmax, long_otm, short_otm)
            if r:
                rows.append(r)
        except Exception:
            continue
    return pd.DataFrame(rows)


# ── Render ────────────────────────────────────────────────────────────────────
def _pct(v, signed=True):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v:+.1%}" if signed else f"{v:.1%}"


def _render_briefing():
    days = list_briefings()
    if not days:
        _rtl("<p>התדריך המלא לא מפורסם בגרסה הציבורית, כי הוא כולל תוכן של המועדון.</p>"
             "<p>הוא מוצג בהרצה מקומית של הדאשבורד. רשימת המעקב, הנתונים והגידורים זמינים כאן.</p>")
        return
    c1, c2 = st.columns([1, 3])
    with c1:
        day = st.selectbox("תאריך", days, index=0, key="desk_brief_day")
    with c2:
        _note(f"{len(days)} תדריכים בארכיון. התדריך העדכני ביותר מוצג כברירת מחדל.")
    md = read_briefing(day)
    md = re.sub(r"^## מקורות[\s\S]*$", "", md, flags=re.M)  # sources list is long; keep the file for it
    _rtl(_md_to_html(md))


def _render_watchlist():
    try:
        d = watchlist_table()
    except FileNotFoundError:
        _rtl("<p>קובץ הדירוג לא נמצא (insiders_club/knowledge/club_ranking.csv). הוא זמין בהרצה מקומית.</p>")
        return
    counts = d.status.value_counts()
    k = st.columns(4)
    for col, key in zip(k, ["🎯 ברשת", "🟢 מגמה תקינה", "🟠 מתוחה — לא לרדוף", "🔴 מגמה שבורה"]):
        col.metric(key, int(counts.get(key, 0)))
    groups = ["כל הקבוצות"] + sorted(d.group.dropna().unique().tolist())
    c1, c2 = st.columns([1, 1])
    with c1:
        g = st.selectbox("קבוצת ביטחון", groups, key="desk_wl_group")
    with c2:
        only_net = st.checkbox("רק מניות ברשת או במרחק של עד 3% מרמת המארב", key="desk_wl_net")
    v = d if g == "כל הקבוצות" else d[d.group == g]
    if only_net:
        v = v[(v.status == "🎯 ברשת") | (v.to_ambush.abs() <= 0.03)]
    out = pd.DataFrame({
        "דירוג": v["rank"], "מניה": v.ticker, "קבוצה": v.group, "מצב": v.status,
        "מחיר": v.price.round(2), "היום": v.day.map(_pct), "חודש": v.m1.map(_pct),
        "מממוצע 50": v.d50.map(_pct), "מממוצע 200": v.d200.map(_pct),
        "רמת מארב": v.ambush, "מחיר המארב": v.ambush_px.round(2), "מרחק": v.to_ambush.map(_pct),
        "איכות": v.get("grade"), "תחזיות מול מחיר": v.get("ratio"),
        "הנימוק": v.reason,
    })
    st.dataframe(out, hide_index=True, use_container_width=True, height=min(38 * (len(out) + 1), 980))
    _note("דירוג = ביטחון בביצועי יתר ל-3–6 חודשים, מעודכן ע\"י האנליסט. "
          "'תחזיות מול מחיר' מעל 1 = התחזיות עלו יותר מהמחיר. "
          "'ברשת' = עד 1.5% מממוצע 50/100/200. מחירים חיים (Yahoo, השהיה אפשרית).")


def _render_data():
    m, idx = macro_table()
    if not m.empty:
        cols = st.columns(len(m))
        for col, r in zip(cols, m.itertuples()):
            fmt = f"{r.last:,.2f}" if r.last < 1000 else f"{r.last:,.0f}"
            col.metric(r.name, fmt, f"{r.day:+.2%}")
        _note("שינוי יומי מתחת לכל נתון. תשואת 10 שנים: אזור המפתח בשיטה 5.2%–5.4%. "
              "אג\"ח זבל יורד = מרווחי האשראי מתרחבים — בודקים אותו יחד עם התשואה.")
    if not idx.empty:
        _rtl("<h3>רמות CTA — המדדים מול הממוצעים</h3>")
        out = pd.DataFrame({
            "מדד": idx.ticker, "מחיר": idx.price.round(2), "היום": idx.day.map(_pct),
            "מממוצע 50": idx.d50.map(_pct), "מממוצע 200": idx.d200.map(_pct),
            "ממוצע 50": idx.sma50.round(2), "ממוצע 200": idx.sma200.round(2), "מהשיא": idx.from_hi.map(_pct),
        })
        st.dataframe(out, hide_index=True, use_container_width=True)
        if {"SPY", "RSP"} <= set(idx.ticker):
            spy = idx.set_index("ticker").loc["SPY", "m1"]
            rsp = idx.set_index("ticker").loc["RSP", "m1"]
            _note(f"רוחב שוק: בחודש האחרון SPY {_pct(spy)} מול RSP (משקל שווה) {_pct(rsp)}. "
                  "פער גדול לטובת SPY = הראלי נשען על הענקיות.")
    cat = os.path.join(KNOW_DIR, "catalysts.md")
    if os.path.exists(cat):
        with st.expander("יומן הקטליסטים", expanded=False):
            with open(cat, encoding="utf-8") as f:
                _rtl(_md_to_html(f.read()))


def _render_hedges():
    _rtl("<p>מרווח פוטים (Bear Put Spread): קנייה של פוט קרוב ומכירה של פוט רחוק. "
         "לפי השיטה שומרים 30–50% מההגנות גם בימי עליות. "
         "ההגנה זולה כשהתנודתיות הגלומה נמוכה ביחס לתנודתיות בפועל.</p>")
    c1, c2, c3 = st.columns(3)
    with c1:
        windows = {"14–30": (14, 30), "25–50": (25, 50), "45–75": (45, 75), "75–120": (75, 120)}
        dte = windows[st.select_slider("ימים לפקיעה", options=list(windows), value="25–50", key="desk_h_dte")]
    with c2:
        lo = st.slider("הפוט הנקנה — מרחק מהמחיר", 0, 10, 5, 1, format="%d%%", key="desk_h_lo") / 100
    with c3:
        so = st.slider("הפוט הנמכר — מרחק מהמחיר", 6, 25, 12, 1, format="%d%%", key="desk_h_so") / 100
    if so <= lo:
        st.warning("הפוט הנמכר חייב להיות רחוק יותר מהפוט הנקנה.")
        return
    with st.spinner("מושך שרשראות אופציות..."):
        h = hedge_table(dte[0], dte[1], lo, so)
    if h.empty:
        _rtl("<p>לא התקבלו נתוני אופציות כרגע.</p>")
        return
    out = pd.DataFrame({
        "נכס": h.ticker, "מחיר": h.spot.round(2), "פקיעה": h.expiry, "ימים": h.dte,
        "קנייה": h.long_k, "מכירה": h.short_k, "עלות": h.cost.round(2), "עלות מהנכס": h.cost_pct.map(lambda v: f"{v:.2%}"),
        "תשלום מקסימלי": h.max_pay.round(2), "יחס תשלום לעלות": h.pay_ratio.round(1),
        "נקודת איזון": h.breakeven.round(2),
        "תנודתיות על הכסף": h.iv_atm.map(lambda v: f"{v:.0%}"), "תנודתיות בפועל": h.rv.map(lambda v: f"{v:.0%}"),
        "יחס": (h.iv_atm / h.rv).round(2), "סקיו": h["skew"].map(lambda v: f"{v:+.0%}"),
        "דלתא": h.delta.round(2), "תטא ליום": h.theta.round(3), "וגה": h.vega.round(3),
        "ממוצע 50": h.sma50.round(2), "ממוצע 200": h.sma200.round(2), "מקור": h.source,
    })
    st.dataframe(out, hide_index=True, use_container_width=True)
    best = h.loc[h.pay_ratio.idxmax()]
    _note(f"היחס הטוב ביותר כרגע: {best.ticker} — עלות {best.cost:.2f}$ לתשלום מקסימלי של {best.max_pay:.2f}$ "
          f"(פי {best.pay_ratio:.1f}). יחס תשלום גבוה מאוד = הגנה רחוקה וזולה שהסיכוי שתשלם קטן — בודקים יחד עם הדלתא. 'יחס' =תנודתיות גלומה חלקי בפועל: מתחת ל-0.9 ההגנה זולה, מעל 1.3 יקרה. "
          "'סקיו' = כמה הפוט הנמכר יקר יותר מהפוט שעל הכסף — סקיו גבוה מוזיל את המרווח. "
          "מחירי אמצע (Yahoo, בהשהיה). ניתוח לפי השיטה — לא המלצה; ההחלטות וגודל הפוזיציה שלך.")


def render_desk_prep():
    st.markdown(RTL_CSS, unsafe_allow_html=True)
    sub = st.tabs(["📋 הכנה ליום המסחר", "👁️ מעקב רשימת המעקב", "📊 נתונים", "🛡️ גידורים"])
    with sub[0]:
        _render_briefing()
    with sub[1]:
        _render_watchlist()
    with sub[2]:
        _render_data()
    with sub[3]:
        _render_hedges()
