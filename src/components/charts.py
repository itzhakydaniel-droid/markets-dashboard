"""
Plotly chart builders — dark institutional theme.
"""
from __future__ import annotations

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# ── Theme constants ───────────────────────────────────────────────────────────
BG       = "#0d141c"
CARD     = "#101828"
BORDER   = "#1E2832"
GRID     = "#22304a"
TEXT     = "#fffffe"
MUTED    = "#a2b6df"
DIM      = "#475467"
GREEN    = "#10b981"
RED      = "#ef4444"
YELLOW   = "#f59e0b"
BLUE     = "#3b82f6"
PURPLE   = "#8b5cf6"
INDIGO   = "#6366f1"
CYAN     = "#0CABC2"
MAGENTA  = "#f00069"
TEAL     = "#5DC7D6"

BASE_LAYOUT = dict(
    paper_bgcolor=BG,
    plot_bgcolor=CARD,
    font=dict(family="Inter, sans-serif", color=TEXT, size=12),
    xaxis=dict(gridcolor=GRID, zeroline=False, showgrid=True,
               tickfont=dict(color=MUTED, size=11), linecolor=BORDER),
    yaxis=dict(gridcolor=GRID, zeroline=False, showgrid=True,
               tickfont=dict(color=MUTED, size=11), linecolor=BORDER),
    margin=dict(l=14, r=14, t=48, b=14),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor=BORDER,
                font=dict(color=MUTED, size=11)),
)


def _apply(fig: go.Figure, h: int = 340, title: str = "") -> go.Figure:
    layout = dict(**BASE_LAYOUT, height=h)
    if title:
        layout["title"] = dict(
            text=title,
            font=dict(color=TEXT, size=13, family="Inter"),
            x=0.01, xanchor="left"
        )
    fig.update_layout(**layout)
    fig.update_xaxes(showspikes=True, spikecolor=BORDER, spikethickness=1)
    fig.update_yaxes(showspikes=True, spikecolor=BORDER, spikethickness=1)
    return fig


# ── 1. Macro gauge ────────────────────────────────────────────────────────────
def macro_gauge(total: int, max_score: int = 70) -> go.Figure:
    pct = total / max_score
    if pct >= .80:   bar_c, lbl = "#ef4444", "TOO HOT"
    elif pct >= .60: bar_c, lbl = "#f59e0b", "WARM"
    elif pct >= .40: bar_c, lbl = BLUE,      "NEUTRAL"
    elif pct >= .20: bar_c, lbl = INDIGO,    "COOL"
    else:            bar_c, lbl = GREEN,      "TOO COLD"

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=total,
        number=dict(suffix=f"/{max_score}", font=dict(size=40, color=bar_c, family="Inter")),
        title=dict(
            text=(f"<span style='font-size:14px;color:{DIM}'>MACRO SCORE</span><br>"
                  f"<span style='font-size:16px;font-weight:700;color:{bar_c}'>{lbl}</span>"),
            font=dict(family="Inter")
        ),
        gauge=dict(
            axis=dict(range=[0, max_score], tickcolor=DIM,
                      tickfont=dict(color=DIM, size=10), tickwidth=1, nticks=8),
            bar=dict(color=bar_c, thickness=0.22),
            bgcolor=CARD,
            borderwidth=0,
            steps=[
                dict(range=[0,14],  color="rgba(16,185,129,0.08)"),
                dict(range=[14,28], color="rgba(99,102,241,0.08)"),
                dict(range=[28,42], color="rgba(59,130,246,0.08)"),
                dict(range=[42,56], color="rgba(245,158,11,0.08)"),
                dict(range=[56,70], color="rgba(239,68,68,0.08)"),
            ],
            threshold=dict(line=dict(color=bar_c, width=3), thickness=0.8, value=total),
        ),
    ))
    fig.update_layout(paper_bgcolor=BG, plot_bgcolor=BG,
                      font=dict(family="Inter", color=TEXT),
                      height=300, margin=dict(l=20, r=20, t=50, b=10))
    return fig


# ── 2. Score breakdown bar ────────────────────────────────────────────────────
def score_breakdown_bar(scores_data: list[dict]) -> go.Figure:
    if not scores_data:
        return go.Figure()
    df = pd.DataFrame(scores_data)
    fig = go.Figure()
    comp_cfg = [
        ("3M Trend (+2)",       BLUE,   "3-Month Trend"),
        ("6M Trend (+2)",       INDIGO, "6-Month Trend"),
        ("YoY Trend (+3)",      PURPLE, "Year-over-Year"),
        ("Abs Threshold (+3)",  YELLOW, "Absolute Threshold"),
    ]
    for col, color, name in comp_cfg:
        if col not in df.columns:
            continue
        fig.add_trace(go.Bar(
            name=name, x=df["name"], y=df[col],
            marker=dict(color=color, opacity=0.9, line=dict(width=0)),
            hovertemplate=f"<b>%{{x}}</b><br>{name}: %{{y}} pts<extra></extra>",
        ))
    fig.update_layout(barmode="stack", yaxis_range=[0, 10.5], **BASE_LAYOUT, height=320)
    fig.update_layout(
        legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center",
                    bgcolor="rgba(0,0,0,0)", font=dict(color=MUTED, size=11)),
        title=dict(text="Score Breakdown by Component",
                   font=dict(color=TEXT, size=13, family="Inter"), x=0.01),
    )
    return fig


# ── 3. VIX chart (enhanced visibility) ───────────────────────────────────────
def vix_chart(vix_df: pd.DataFrame) -> go.Figure:
    if vix_df.empty:
        return go.Figure()
    vix = vix_df["VIX"]

    fig = go.Figure()

    # Regime background bands
    ymax = max(float(vix.max()) + 5, 45)
    fig.add_hrect(y0=30, y1=ymax, fillcolor="rgba(239,68,68,0.08)", line_width=0,
                  annotation_text="EXTREME FEAR", annotation_position="top right",
                  annotation_font=dict(color="#ef4444", size=10))
    fig.add_hrect(y0=20, y1=30, fillcolor="rgba(245,158,11,0.08)", line_width=0,
                  annotation_text="FEAR", annotation_position="top right",
                  annotation_font=dict(color="#f59e0b", size=10))
    fig.add_hrect(y0=15, y1=20, fillcolor="rgba(59,130,246,0.06)", line_width=0,
                  annotation_text="NORMAL", annotation_position="top right",
                  annotation_font=dict(color="#3b82f6", size=10))
    fig.add_hrect(y0=0, y1=15, fillcolor="rgba(16,185,129,0.06)", line_width=0,
                  annotation_text="COMPLACENT", annotation_position="top right",
                  annotation_font=dict(color="#10b981", size=10))

    # Threshold lines (bright and visible)
    for level, color, label in [
        (15, GREEN,  "15 — Calm"),
        (20, YELLOW, "20 — Caution"),
        (30, RED,    "30 — Fear"),
    ]:
        fig.add_hline(y=level, line_dash="dash", line_color=color, line_width=1.5, opacity=0.7,
                      annotation_text=f"<b>{label}</b>",
                      annotation_font=dict(color=color, size=11, family="Inter"),
                      annotation_position="top left")

    # 20-day rolling avg
    ma20 = vix.rolling(20).mean()
    fig.add_trace(go.Scatter(
        x=vix_df.index, y=ma20,
        mode="lines", name="20-Day MA",
        line=dict(color=YELLOW, width=1.5, dash="dot"),
        hovertemplate="20-Day MA: %{y:.2f}<extra></extra>",
    ))

    # VIX area fill
    fig.add_trace(go.Scatter(
        x=vix_df.index, y=vix,
        mode="lines", name="VIX",
        line=dict(color="#f87171", width=2.2),
        fill="tozeroy", fillcolor="rgba(239,68,68,0.12)",
        hovertemplate="<b>%{x|%b %d %Y}</b><br>VIX: <b>%{y:.2f}</b><extra></extra>",
    ))

    # Current level dot
    fig.add_trace(go.Scatter(
        x=[vix_df.index[-1]], y=[float(vix.iloc[-1])],
        mode="markers+text",
        marker=dict(color=RED, size=10, line=dict(color=TEXT, width=2)),
        text=[f"  {float(vix.iloc[-1]):.2f}"],
        textfont=dict(color=TEXT, size=13, family="Inter"),
        textposition="middle right",
        showlegend=False,
        hovertemplate=f"Current VIX: {float(vix.iloc[-1]):.2f}<extra></extra>",
    ))

    _apply(fig, h=380, title="VIX — 1 Year with Regime Bands")
    fig.update_layout(
        yaxis=dict(gridcolor=GRID, tickfont=dict(color=MUTED, size=11),
                   title=dict(text="VIX Level", font=dict(color=MUTED, size=11)),
                   range=[0, ymax]),
        xaxis=dict(gridcolor=GRID, tickfont=dict(color=MUTED, size=11)),
        showlegend=True,
        legend=dict(orientation="h", y=1.06, x=0.5, xanchor="center",
                    bgcolor="rgba(0,0,0,0)", font=dict(color=MUTED, size=11)),
    )
    return fig


# ── 4. Sector heatmap (treemap) ───────────────────────────────────────────────
def sector_heatmap(sector_df: pd.DataFrame, period: str = "1d") -> go.Figure:
    df = sector_df[sector_df["Period"] == period].copy()
    if df.empty:
        return go.Figure()
    df = df.sort_values("Return %", ascending=False)

    fig = go.Figure(go.Treemap(
        labels=df["Sector"],
        parents=[""] * len(df),
        values=[abs(x) + 1.2 for x in df["Return %"]],
        customdata=np.stack([df["Return %"], df["ETF"]], axis=1),
        texttemplate="<b>%{label}</b><br><span style='font-size:14px'>%{customdata[0]:+.2f}%</span><br><span style='font-size:10px;color:#9ca3af'>%{customdata[1]}</span>",
        textfont=dict(family="Inter", size=13),
        marker=dict(
            colors=df["Return %"],
            colorscale=[
                [0.0,  "#7f1d1d"],
                [0.2,  "#ef4444"],
                [0.42, "#1f2937"],
                [0.5,  "#1e2533"],
                [0.58, "#1f2937"],
                [0.8,  "#10b981"],
                [1.0,  "#064e3b"],
            ],
            cmid=0, showscale=True,
            colorbar=dict(
                title=dict(text="Return %", font=dict(color=MUTED, size=11)),
                tickfont=dict(color=MUTED, size=10),
                tickformat="+.1f",
                thickness=14, len=0.8,
            ),
            line=dict(width=2, color=BG),
            pad=dict(t=8, l=8, r=8, b=8),
        ),
        hovertemplate="<b>%{label}</b><br>Return: <b>%{customdata[0]:+.2f}%</b><br>ETF: %{customdata[1]}<extra></extra>",
    ))
    period_labels = {"1d": "Today", "5d": "1 Week", "1mo": "1 Month"}
    fig.update_layout(
        paper_bgcolor=BG, plot_bgcolor=BG,
        font=dict(family="Inter", color=TEXT),
        height=480, margin=dict(l=0, r=0, t=48, b=0),
        title=dict(
            text=f"Sector Rotation Heatmap — {period_labels.get(period, period)}",
            font=dict(color=TEXT, size=13, family="Inter"), x=0.01
        ),
    )
    return fig


# ── 5. Sector performance bars ────────────────────────────────────────────────
def sector_bars(sector_df: pd.DataFrame, period: str = "1d") -> go.Figure:
    """Horizontal bar chart with clear color coding."""
    df = sector_df[sector_df["Period"] == period].copy().sort_values("Return %")
    if df.empty:
        return go.Figure()

    colors = [GREEN if v >= 0 else RED for v in df["Return %"]]
    text_vals = [f"{v:+.2f}%" for v in df["Return %"]]

    fig = go.Figure(go.Bar(
        x=df["Return %"],
        y=df["Sector"],
        orientation="h",
        marker=dict(
            color=colors,
            opacity=0.9,
            line=dict(width=0),
        ),
        text=text_vals,
        textposition="outside",
        textfont=dict(color=TEXT, size=12, family="Inter"),
        hovertemplate="<b>%{y}</b><br>Return: <b>%{x:+.2f}%</b><extra></extra>",
    ))

    fig.add_vline(x=0, line_color=BORDER, line_width=2)
    period_labels = {"1d": "Today", "5d": "1 Week", "1mo": "1 Month"}
    _apply(fig, h=380, title=f"Sector Returns — {period_labels.get(period, period)}")
    fig.update_layout(
        showlegend=False,
        xaxis=dict(ticksuffix="%", gridcolor=GRID, tickfont=dict(color=MUTED, size=11),
                   zeroline=True, zerolinecolor=BORDER, zerolinewidth=2),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", tickfont=dict(color=TEXT, size=12),
                   linecolor=BORDER),
        margin=dict(l=14, r=80, t=48, b=14),
    )
    return fig


# ── 6. Stocks heatmap ─────────────────────────────────────────────────────────
def stocks_heatmap(quotes_df: pd.DataFrame, title: str = "Watchlist Heatmap") -> go.Figure:
    """
    Treemap heatmap of individual stocks colored by % change.
    quotes_df must have columns: Ticker, Price, Change %
    """
    df = quotes_df.dropna(subset=["Change %"]).copy()
    if df.empty:
        return go.Figure()

    df["abs_change"] = df["Change %"].abs()
    df["size"] = df["abs_change"].clip(lower=0.2) + 1.0  # min tile size

    fig = go.Figure(go.Treemap(
        labels=df["Ticker"],
        parents=[""] * len(df),
        values=df["size"],
        customdata=np.stack([
            df["Change %"],
            df["Price"].fillna(0),
            df.get("Volume", pd.Series([0]*len(df))).fillna(0),
        ], axis=1),
        texttemplate=(
            "<b>%{label}</b><br>"
            "<span style='font-size:16px'>%{customdata[0]:+.2f}%</span><br>"
            "<span style='font-size:11px;color:#9ca3af'>$%{customdata[1]:,.2f}</span>"
        ),
        textfont=dict(family="Inter", size=14),
        marker=dict(
            colors=df["Change %"],
            colorscale=[
                [0.0,  "#7f1d1d"],
                [0.2,  "#dc2626"],
                [0.4,  "#1f2937"],
                [0.5,  "#1e2533"],
                [0.6,  "#1f2937"],
                [0.8,  "#059669"],
                [1.0,  "#064e3b"],
            ],
            cmid=0,
            showscale=True,
            colorbar=dict(
                title=dict(text="Change %", font=dict(color=MUTED, size=11)),
                tickfont=dict(color=MUTED, size=10),
                tickformat="+.1f",
                ticksuffix="%",
                thickness=14, len=0.85,
                x=1.01,
            ),
            line=dict(width=2, color=BG),
            pad=dict(t=8, l=8, r=8, b=8),
        ),
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Change: <b>%{customdata[0]:+.2f}%</b><br>"
            "Price: $%{customdata[1]:,.2f}<extra></extra>"
        ),
    ))
    fig.update_layout(
        paper_bgcolor=BG, plot_bgcolor=BG,
        font=dict(family="Inter", color=TEXT),
        height=420,
        margin=dict(l=0, r=0, t=48, b=0),
        title=dict(text=title, font=dict(color=TEXT, size=13, family="Inter"), x=0.01),
    )
    return fig


# ── 7. Watchlist bar chart ────────────────────────────────────────────────────
def watchlist_performance_chart(quotes_df: pd.DataFrame) -> go.Figure:
    """Horizontal bars showing daily % change for each ticker."""
    df = quotes_df.dropna(subset=["Change %"]).copy().sort_values("Change %")
    if df.empty:
        return go.Figure()

    colors = [GREEN if v >= 0 else RED for v in df["Change %"]]

    fig = go.Figure(go.Bar(
        x=df["Change %"],
        y=df["Ticker"],
        orientation="h",
        marker=dict(color=colors, opacity=0.9, line=dict(width=0)),
        text=[f"{v:+.2f}%" for v in df["Change %"]],
        textposition="outside",
        textfont=dict(color=TEXT, size=12, family="Inter"),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Change: <b>%{x:+.2f}%</b><br>"
            "Price: $%{customdata:.2f}<extra></extra>"
        ),
        customdata=df["Price"].fillna(0),
    ))
    fig.add_vline(x=0, line_color=BORDER, line_width=2)
    _apply(fig, h=max(250, len(df) * 36), title="Daily Performance by Ticker")
    fig.update_layout(
        showlegend=False,
        xaxis=dict(ticksuffix="%", gridcolor=GRID, tickfont=dict(color=MUTED, size=11),
                   zeroline=True, zerolinecolor=BORDER, zerolinewidth=2),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", tickfont=dict(color=TEXT, size=13),
                   linecolor=BORDER),
        margin=dict(l=14, r=70, t=48, b=14),
    )
    return fig


# ── 8. Advance / Decline line ─────────────────────────────────────────────────
def advance_decline_chart(ad_df: pd.DataFrame) -> go.Figure:
    if ad_df.empty or "Cumulative_AD" not in ad_df.columns:
        return go.Figure()

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.65, 0.35], vertical_spacing=0.04,
        subplot_titles=("Cumulative A/D Line", "Daily Net Advances"),
    )

    # A/D line with fill
    fig.add_trace(go.Scatter(
        x=ad_df["Date"], y=ad_df["Cumulative_AD"],
        mode="lines", name="A/D Line",
        line=dict(color=BLUE, width=2.2),
        fill="tozeroy", fillcolor="rgba(59,130,246,0.10)",
        hovertemplate="<b>%{x|%b %d}</b><br>Cumulative: <b>%{y}</b><extra></extra>",
    ), row=1, col=1)

    # Net advances bars
    bar_colors = [GREEN if n >= 0 else RED for n in ad_df["Net"]]
    fig.add_trace(go.Bar(
        x=ad_df["Date"], y=ad_df["Net"],
        name="Net Advances", marker_color=bar_colors,
        marker_line_width=0, opacity=0.8,
        hovertemplate=(
            "<b>%{x|%b %d}</b><br>"
            "Advances: %{customdata[0]}  Declines: %{customdata[1]}<extra></extra>"
        ),
        customdata=np.stack([ad_df["Advances"], ad_df["Declines"]], axis=1),
    ), row=2, col=1)

    _apply(fig, h=400)
    fig.update_layout(showlegend=False)
    for ann in fig.layout.annotations:
        ann.font = dict(color=MUTED, size=11, family="Inter")
    return fig


# ── 9. Candlestick chart ──────────────────────────────────────────────────────
def candlestick_chart(df: pd.DataFrame, ticker: str, show_ma: bool = True) -> go.Figure:
    if df.empty:
        return go.Figure()
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.75, 0.25], vertical_spacing=0.02,
    )

    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"], name=ticker,
        increasing=dict(line=dict(color=GREEN, width=1), fillcolor="rgba(16,185,129,0.7)"),
        decreasing=dict(line=dict(color=RED,   width=1), fillcolor="rgba(239,68,68,0.7)"),
    ), row=1, col=1)

    if show_ma:
        close = df["Close"]
        for ma, color, dash in [(20, YELLOW, "dash"), (50, BLUE, "solid"), (200, PURPLE, "dot")]:
            if len(close) >= ma:
                fig.add_trace(go.Scatter(
                    x=df.index, y=close.rolling(ma).mean(),
                    name=f"MA{ma}", line=dict(color=color, width=1.5, dash=dash),
                    hovertemplate=f"MA{ma}: %{{y:.2f}}<extra></extra>",
                ), row=1, col=1)

    vol_colors = [GREEN if c >= o else RED
                  for c, o in zip(df["Close"], df["Open"])]
    fig.add_trace(go.Bar(
        x=df.index, y=df["Volume"],
        name="Volume", marker_color=vol_colors,
        marker_line_width=0, opacity=0.5,
    ), row=2, col=1)

    _apply(fig, h=520, title=f"{ticker} — Price & Volume")
    fig.update_layout(xaxis_rangeslider_visible=False)
    return fig


# ── 10. CTA exposure bar ──────────────────────────────────────────────────────
def cta_exposure_chart(cta_data: dict) -> go.Figure:
    if not cta_data:
        return go.Figure()
    labels = list(cta_data.keys())
    values = [v["exposure"] for v in cta_data.values()]
    regimes = [v["regime"] for v in cta_data.values()]
    colors = [GREEN if v >= 20 else RED if v <= -20 else YELLOW for v in values]

    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        marker=dict(color=colors, opacity=0.9, line=dict(width=0)),
        text=[f"<b>{v:+.0f}</b>  {r}" for v, r in zip(values, regimes)],
        textposition="outside",
        textfont=dict(color=TEXT, size=12, family="Inter"),
        hovertemplate="<b>%{y}</b><br>Exposure: <b>%{x:+.0f}</b><extra></extra>",
    ))
    fig.add_vline(x=0, line_color=MUTED, line_width=1.5)
    fig.add_vrect(x0=-20, x1=20, fillcolor="rgba(245,158,11,0.05)", line_width=0,
                  annotation_text="NEUTRAL ZONE", annotation_position="top",
                  annotation_font=dict(color=YELLOW, size=10))

    _apply(fig, h=300, title="CTA Trend-Following Exposure  (−100 = Max Short  ·  +100 = Max Long)")
    fig.update_layout(
        xaxis=dict(range=[-120, 140], ticksuffix="", gridcolor=GRID,
                   tickfont=dict(color=MUTED, size=11)),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", tickfont=dict(color=TEXT, size=12)),
        showlegend=False,
        margin=dict(l=14, r=120, t=48, b=14),
    )
    return fig


# ── 11. Macro indicator sparkline ─────────────────────────────────────────────
def macro_indicator_sparkline(series: pd.Series, name: str) -> go.Figure:
    if series is None or series.empty:
        return go.Figure()
    monthly = series.resample("ME").last().tail(24).dropna()
    if len(monthly) < 2:
        return go.Figure()

    is_up = monthly.iloc[-1] > monthly.iloc[-2]
    color = GREEN if is_up else RED
    arrow = "▲" if is_up else "▼"

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=monthly.index, y=monthly.values,
        mode="lines+markers",
        line=dict(color=color, width=2),
        marker=dict(size=3, color=color),
        fill="tozeroy",
        fillcolor=f"rgba(16,185,129,0.09)" if color == GREEN else "rgba(239,68,68,0.09)",
        hovertemplate=f"<b>{name}</b><br>%{{x|%b %Y}}: %{{y:,.2f}}<extra></extra>",
    ))
    last_val = monthly.iloc[-1]
    fig.add_annotation(
        x=monthly.index[-1], y=last_val,
        text=f"<b>{last_val:,.1f}</b>",
        showarrow=False, yanchor="bottom", xanchor="right",
        font=dict(color=color, size=11, family="Inter"),
    )
    _apply(fig, h=185, title=f"{name}  <span style='color:{color}'>{arrow}</span>")
    fig.update_layout(showlegend=False, margin=dict(l=10, r=10, t=44, b=10))
    fig.update_xaxes(showgrid=False, tickformat="%b %y")
    return fig


# ── 12. VIX term structure bar ────────────────────────────────────────────────
def vix_term_bar(term_df: pd.DataFrame) -> go.Figure:
    """Bar chart of VIX term structure (spot vs VIX3M vs VXX)."""
    if term_df.empty:
        return go.Figure()

    colors = []
    for lvl in term_df["Level"]:
        if lvl > 25:   colors.append(RED)
        elif lvl > 18: colors.append(YELLOW)
        else:          colors.append(GREEN)

    fig = go.Figure(go.Bar(
        x=term_df["Instrument"],
        y=term_df["Level"],
        marker=dict(color=colors, opacity=0.9, line=dict(width=0)),
        text=[f"<b>{v:.2f}</b>" for v in term_df["Level"]],
        textposition="outside",
        textfont=dict(color=TEXT, size=13, family="Inter"),
        hovertemplate="<b>%{x}</b><br>Level: <b>%{y:.2f}</b><extra></extra>",
        width=0.4,
    ))

    # Reference lines
    for level, color, label in [(15, GREEN, "Calm"), (20, YELLOW, "Caution"), (30, RED, "Fear")]:
        fig.add_hline(y=level, line_dash="dot", line_color=color, line_width=1.5, opacity=0.6,
                      annotation_text=label, annotation_font=dict(color=color, size=10),
                      annotation_position="top right")

    _apply(fig, h=280, title="VIX Term Structure")
    fig.update_layout(
        showlegend=False,
        yaxis=dict(title=dict(text="Level", font=dict(color=MUTED, size=11)),
                   gridcolor=GRID, range=[0, max(float(term_df["Level"].max()) * 1.4, 35)]),
        xaxis=dict(tickfont=dict(color=TEXT, size=13), linecolor=BORDER),
    )
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# BLACK RAVEN PROTOCOL — Chart Suite
# ══════════════════════════════════════════════════════════════════════════════

def kill_zone_radar(df: pd.DataFrame) -> go.Figure:
    """
    Black Raven Kill Zone Radar v2 — clean, readable institutional design.
    Each row = one stock. Bar length = % distance from 50SMA.
    Tiers separated by header rows. Zone color coded. All labels in hover.
    """
    if df.empty:
        return go.Figure()

    tier_meta = {
        1: ("T1", "#10b981", "ABSOLUTE MONOPOLY"),
        2: ("T2", "#3b82f6", "CAPEX RECEIVERS"),
        3: ("T3", "#f59e0b", "MOMENTUM"),
    }

    # ── Build ordered row list (T1 top → T3 bottom in Plotly = reverse order) ──
    # Plotly horizontal bars: first item in list = bottom of chart
    # We want T1 at top, so we add T3 first, T1 last
    y_labels   = []
    x_vals     = []
    bar_colors = []
    bar_texts  = []   # short inside-bar label
    hover_data = []
    is_header  = []   # True for tier divider rows

    for tier in [3, 2, 1]:
        sub = df[df["Tier"] == tier].sort_values("Dist_50SMA%", ascending=True)
        prefix, tc, tdesc = tier_meta[tier]

        for _, r in sub.iterrows():
            dist  = float(r["Dist_50SMA%"])
            zone  = str(r["Zone"])
            price = float(r["Price"])
            sma   = float(r["50SMA"])
            lim   = float(r["Limit_Price"])
            stop  = float(r["Stop_Loss"])
            rsi   = r.get("RSI14", "—")
            zc    = str(r["ZoneColor"])

            # Short inside-bar indicator (only shown if bar wide enough)
            if "KILL" in zone:   short = "● KZ"
            elif "DEEP" in zone: short = "◆ DV"
            elif "APPR" in zone: short = "▼"
            elif "ELEV" in zone: short = "~"
            elif "EXT"  in zone: short = "↑"
            else:                short = "✗"

            hover = (
                f"<b>{r['Ticker']}</b>  ·  {prefix} {tdesc}<br>"
                f"──────────────────────<br>"
                f"Current Price : <b>${price:,.2f}</b><br>"
                f"50-Day SMA    : <b>${sma:,.2f}</b><br>"
                f"Distance      : <b>{dist:+.2f}%</b><br>"
                f"Zone          : <b>{zone}</b><br>"
                f"Action        : <b>{r['Action']}</b><br>"
                f"──────────────────────<br>"
                f"Buy Limit GTC : <b>${lim:,.2f}</b><br>"
                f"Stop Loss     : <b>${stop:,.2f}</b><br>"
                f"RSI (14)      : {rsi}"
            )

            # Y-label: "T1  NVDA" with fixed-width tier badge
            y_labels.append(f"{prefix}  {r['Ticker']}")
            x_vals.append(dist)
            bar_colors.append(zc)
            bar_texts.append(short)
            hover_data.append(hover)
            is_header.append(False)

        # Tier header spacer row (zero-length invisible bar)
        badge, tc, desc = tier_meta[tier]
        y_labels.append(f"── {badge}  {desc} ──────────────────")
        x_vals.append(0)
        bar_colors.append("rgba(0,0,0,0)")
        bar_texts.append("")
        hover_data.append("")
        is_header.append(True)

    fig = go.Figure()

    # ── Background zone bands (no annotation text — keeps labels clean) ───────
    fig.add_shape(type="rect", x0=-999, x1=-5,
                  y0=-0.5, y1=len(y_labels)-0.5, yref="y",
                  fillcolor="rgba(6,182,212,0.05)", line_width=0, layer="below")
    fig.add_shape(type="rect", x0=-5, x1=0,
                  y0=-0.5, y1=len(y_labels)-0.5, yref="y",
                  fillcolor="rgba(16,185,129,0.10)", line_width=0, layer="below")

    # ── Bars ──────────────────────────────────────────────────────────────────
    fig.add_trace(go.Bar(
        x=x_vals,
        y=y_labels,
        orientation="h",
        marker=dict(
            color=bar_colors,
            opacity=0.88,
            line=dict(color="rgba(8,12,20,0.6)", width=1),
        ),
        text=bar_texts,
        textposition="inside",
        insidetextanchor="middle",
        textfont=dict(color="rgba(255,255,255,0.75)", size=10, family="Inter"),
        hovertemplate="%{customdata}<extra></extra>",
        customdata=hover_data,
        showlegend=False,
        width=0.65,
    ))

    # ── Reference lines ───────────────────────────────────────────────────────
    # 0% = 50SMA = Buy zone boundary
    fig.add_vline(x=0,  line_dash="solid", line_color=GREEN,  line_width=2.5, opacity=0.8)
    fig.add_vline(x=8,  line_dash="dot",   line_color=YELLOW, line_width=1.5, opacity=0.55)
    fig.add_vline(x=15, line_dash="dot",   line_color=RED,    line_width=1.5, opacity=0.55)

    # ── Zone labels above the chart (using paper coords — never overlaps bars) ─
    x_max_val = max(float(df["Dist_50SMA%"].max()) * 1.1, 28)
    x_max_val = min(x_max_val, 40)

    for xpos, label, color in [
        (-7,  "◆ DEEP VALUE",  CYAN),
        (-2,  "● KILL ZONE",   GREEN),
        (4,   "▼ APPROACHING", "#84cc16"),
        (11,  "~ ELEVATED",    YELLOW),
        (20,  "✗ CHASE ZONE",  RED),
    ]:
        if xpos < x_max_val:
            fig.add_annotation(
                x=xpos, y=1.0, yref="paper",
                text=f"<b>{label}</b>",
                showarrow=False,
                font=dict(color=color, size=9, family="Inter"),
                xanchor="center", yanchor="bottom",
                bgcolor="rgba(8,12,20,0.7)",
                borderpad=3,
            )

    # ── Tier header row styling: add right-aligned annotations ────────────────
    for i, (y_lbl, is_hdr) in enumerate(zip(y_labels, is_header)):
        if is_hdr:
            fig.add_shape(
                type="line",
                x0=-12, x1=x_max_val,
                y0=i, y1=i,
                yref="y", xref="x",
                line=dict(color=BORDER, width=1, dash="dot"),
                layer="below",
            )

    # ── Layout ────────────────────────────────────────────────────────────────
    h = max(520, len(y_labels) * 28 + 80)
    _apply(fig, h=h, title="")

    fig.update_layout(
        title=dict(
            text=(
                "<b>4-Tier Kill Zone Radar</b>"
                "<span style='color:#6b7280;font-size:11px'>"
                "  ·  % distance from 50-day SMA  ·  Hover any bar for full order parameters"
                "</span>"
            ),
            font=dict(color=TEXT, size=14, family="Inter"),
            x=0, xanchor="left",
        ),
        showlegend=False,
        bargap=0.25,
        xaxis=dict(
            zeroline=False,
            range=[-12, x_max_val],
            gridcolor=GRID,
            ticksuffix="%",
            tickfont=dict(color=MUTED, size=11),
            title=dict(
                text="← Negative = Below 50SMA = Buy Zone  |  0% = At 50SMA (Limit Price)  |  Positive = Above 50SMA →",
                font=dict(color=DIM, size=10),
            ),
        ),
        yaxis=dict(
            gridcolor="rgba(0,0,0,0)",
            tickfont=dict(color=TEXT, size=12, family="Inter"),
            categoryorder="array",
            categoryarray=y_labels,
            ticklabelposition="outside left",
        ),
        margin=dict(l=140, r=24, t=68, b=44),
        hoverlabel=dict(
            bgcolor="#0d1117",
            bordercolor=BORDER,
            font=dict(color=TEXT, size=12, family="Inter"),
        ),
    )
    return fig


def macro_liquidity_chart(macro_dict: dict) -> go.Figure:
    """
    Black Raven Macro Matrix — gauge/bullet chart for key macro instruments.
    Shows current value + 1-day direction for each instrument.
    """
    instruments = [k for k in macro_dict if not k.startswith("_")]
    if not instruments:
        return go.Figure()

    values    = [macro_dict[k]["value"]      for k in instruments]
    changes   = [macro_dict[k]["change_pct"] for k in instruments]
    colors    = [GREEN if c < 0 else RED if c > 0 else MUTED for c in changes]

    # For yields and DXY, a rise is bearish for equities → flip color
    bearish_on_rise = ["US 10Y", "US 2Y", "DXY", "WTI Oil"]
    colors = [
        RED if (k in bearish_on_rise and chg > 0.1) else
        GREEN if (k in bearish_on_rise and chg < -0.1) else
        GREEN if chg < -0.1 else
        RED if chg > 0.1 else MUTED
        for k, chg in zip(instruments, changes)
    ]

    fig = go.Figure()
    for i, (inst, val, chg, col) in enumerate(zip(instruments, values, changes, colors)):
        arrow = "▲" if chg > 0 else "▼" if chg < 0 else "—"
        fig.add_trace(go.Bar(
            x=[inst],
            y=[val],
            name=inst,
            marker=dict(color=col, opacity=0.8, line=dict(width=0)),
            text=f"<b>{val:.2f}</b><br><span style='font-size:10px'>{arrow} {chg:+.2f}%</span>",
            textposition="outside",
            textfont=dict(color=TEXT, size=10),
            hovertemplate=f"<b>{inst}</b><br>Value: {val:.2f}<br>Change: {chg:+.2f}%<extra></extra>",
            showlegend=False,
        ))

    _apply(fig, h=260, title="Macro & Liquidity Matrix  •  1-Day Signal")
    fig.update_layout(
        barmode="group",
        xaxis=dict(tickfont=dict(color=TEXT, size=11)),
        yaxis=dict(showgrid=True, gridcolor=GRID, showticklabels=False),
        margin=dict(l=14, r=14, t=44, b=14),
    )
    return fig


def intraday_live_chart(
    series_map: dict[str, pd.Series],
    label_map: dict[str, str] | None = None,
    title: str = "Live Intraday  •  Today's Session  •  % vs Open",
) -> go.Figure:
    """
    Live performance chart — each ticker normalized to % change
    from its first bar in the window. Expects {ticker: pd.Series of closes}.
    """
    label_map = label_map or {}
    palette = [TEAL, MAGENTA, YELLOW, BLUE, GREEN, PURPLE]
    fig = go.Figure()

    # multi-day windows need date ticks, single-day needs clock ticks
    _spans = [(s.index[-1] - s.index[0]).days for s in series_map.values() if s is not None and len(s) > 1]
    _multi_day = bool(_spans) and max(_spans) >= 2
    _tickfmt = "%d %b" if _multi_day else "%H:%M"

    for i, (ticker, s) in enumerate(series_map.items()):
        if s is None or len(s) < 2:
            continue
        base = float(s.iloc[0])
        if base == 0:
            continue
        pct = (s / base - 1.0) * 100.0
        col = palette[i % len(palette)]
        last = float(pct.iloc[-1])
        fig.add_trace(go.Scatter(
            x=pct.index, y=pct.values,
            mode="lines",
            name=f"{label_map.get(ticker, ticker)}  {last:+.2f}%",
            line=dict(color=col, width=2.2, shape="spline", smoothing=0.6),
            hovertemplate=f"<b>{label_map.get(ticker, ticker)}</b> %{{y:+.2f}}%%<extra></extra>",
        ))

    fig.add_hline(y=0, line=dict(color=DIM, width=1, dash="dot"))
    _apply(fig, h=310, title=title)
    fig.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1.0,
                    font=dict(size=11, color=TEXT), bgcolor="rgba(0,0,0,0)"),
        yaxis=dict(ticksuffix="%", showgrid=True, gridcolor=GRID, zeroline=False),
        xaxis=dict(showgrid=False, tickformat=_tickfmt),
        margin=dict(l=14, r=14, t=48, b=14),
        hovermode="x unified",
    )
    return fig


def sector_detail_chart(s: pd.Series, spy: pd.Series | None, name: str) -> go.Figure:
    """
    Sector breakdown chart: 2-year price with 50/200-day MAs (top panel)
    and cumulative relative performance vs SPY (bottom panel).
    """
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, row_heights=[0.68, 0.32],
        vertical_spacing=0.06,
        subplot_titles=(f"{name} — 2-Year Price & Moving Averages", "Relative Performance vs S&P 500 (%)"),
    )

    fig.add_trace(go.Scatter(
        x=s.index, y=s.values, name="Price",
        line=dict(color=TEAL, width=2.2),
        hovertemplate="%{y:.2f}<extra>Price</extra>",
    ), row=1, col=1)

    if len(s) >= 50:
        ma50 = s.rolling(50).mean()
        fig.add_trace(go.Scatter(
            x=ma50.index, y=ma50.values, name="SMA 50",
            line=dict(color=YELLOW, width=1.3, dash="dot"),
            hovertemplate="%{y:.2f}<extra>SMA 50</extra>",
        ), row=1, col=1)
    if len(s) >= 200:
        ma200 = s.rolling(200).mean()
        fig.add_trace(go.Scatter(
            x=ma200.index, y=ma200.values, name="SMA 200",
            line=dict(color=MAGENTA, width=1.6),
            hovertemplate="%{y:.2f}<extra>SMA 200</extra>",
        ), row=1, col=1)

    if spy is not None and not spy.empty:
        joined = pd.concat([s, spy], axis=1, keys=["sec", "spy"]).dropna()
        if len(joined) > 5:
            rel = (joined["sec"] / joined["sec"].iloc[0]) / (joined["spy"] / joined["spy"].iloc[0]) - 1
            rel_pct = rel * 100
            fig.add_trace(go.Scatter(
                x=rel_pct.index, y=rel_pct.values, name="RS vs SPY",
                line=dict(color=BLUE, width=1.8),
                fill="tozeroy", fillcolor="rgba(59,130,246,.10)",
                hovertemplate="%{y:+.1f}%<extra>vs SPY</extra>",
            ), row=2, col=1)
            fig.add_hline(y=0, line=dict(color=DIM, width=1, dash="dot"), row=2, col=1)

    _layout = dict(BASE_LAYOUT)
    _layout.update(
        height=520,
        legend=dict(orientation="h", yanchor="bottom", y=1.03, xanchor="right", x=1.0,
                    font=dict(size=11, color=TEXT), bgcolor="rgba(0,0,0,0)"),
        hovermode="x unified",
    )
    fig.update_layout(**_layout)
    fig.update_annotations(font=dict(color=MUTED, size=12))
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    fig.update_xaxes(gridcolor=GRID, showgrid=False)
    return fig


def yield_curve_chart(curve_data: dict) -> go.Figure:
    """
    US Treasury yield curve — latest vs 1 month ago vs 1 year ago.
    Category x-axis in maturity order (1 Mo → 30 Yr).
    """
    latest = curve_data.get("latest")
    if latest is None or latest.empty:
        return go.Figure()

    fig = go.Figure()
    series_cfg = [
        (curve_data.get("year_ago"),  "1 Year Ago",  DIM,     1.4, "dot"),
        (curve_data.get("month_ago"), "1 Month Ago", YELLOW,  1.6, "dash"),
        (latest,                      f"Latest ({curve_data.get('asof','')})", TEAL, 2.8, None),
    ]
    for s, name, color, width, dash in series_cfg:
        if s is None:
            continue
        s = s.dropna()
        line = dict(color=color, width=width)
        if dash:
            line["dash"] = dash
        fig.add_trace(go.Scatter(
            x=list(s.index), y=list(s.values),
            mode="lines+markers", name=name,
            line=line, marker=dict(size=6 if dash is None else 4),
            hovertemplate="<b>%{x}</b>: %{y:.2f}%<extra>" + name + "</extra>",
        ))

    _apply(fig, h=380, title="US Treasury Yield Curve  •  Official Treasury Dept Data")
    fig.update_layout(
        yaxis=dict(ticksuffix="%", showgrid=True, gridcolor=GRID),
        xaxis=dict(showgrid=False, type="category"),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1.0,
                    font=dict(size=11, color=TEXT), bgcolor="rgba(0,0,0,0)"),
        hovermode="x unified",
    )
    return fig


def yield_spread_chart(spread: pd.Series, label: str = "10Y − 2Y") -> go.Figure:
    """Yield-spread history with inversion shading below zero."""
    if spread is None or spread.empty:
        return go.Figure()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=spread.index, y=spread.values,
        mode="lines", name=label,
        line=dict(color=MAGENTA, width=1.8),
        fill="tozeroy", fillcolor="rgba(240,0,105,.08)",
        hovertemplate="%{x|%d %b %Y}: %{y:+.2f}pp<extra></extra>",
    ))
    fig.add_hline(y=0, line=dict(color=RED, width=1.4, dash="dash"),
                  annotation_text="INVERSION LINE", annotation_position="bottom right",
                  annotation_font=dict(color=RED, size=10))

    cur = float(spread.iloc[-1])
    fig.add_trace(go.Scatter(
        x=[spread.index[-1]], y=[cur],
        mode="markers+text",
        marker=dict(color=TEAL, size=9, line=dict(color=TEXT, width=1.5)),
        text=[f"  {cur:+.2f}"], textposition="middle right",
        textfont=dict(color=TEXT, size=12), showlegend=False,
    ))

    _apply(fig, h=380, title=f"Curve Spread  •  {label}  •  Recession Signal When Below Zero")
    fig.update_layout(
        yaxis=dict(ticksuffix="pp", showgrid=True, gridcolor=GRID, zeroline=False),
        xaxis=dict(showgrid=False),
        showlegend=False,
    )
    return fig
