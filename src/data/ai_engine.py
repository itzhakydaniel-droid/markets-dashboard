"""
AI Market Analysis Engine — routed through OmniRoute (OpenRouter).

Every call goes through src.data.llm_router, which walks a priority-ordered
model chain and steps down to the next model when the current one runs out of
tokens/credits, gets rate-limited, or goes down. See llm_router.py.
"""
from __future__ import annotations

import pandas as pd
from datetime import datetime

from . import llm_router
from .llm_router import RouterError  # noqa: F401 — re-exported for callers


# ── System prompt ─────────────────────────────────────────────────────────────
_SYSTEM = """You are an expert institutional macro analyst and portfolio strategist with 20+ years experience.
You analyze markets with precision, referencing specific data points provided.
Be concise but insightful. Use bullet points for clarity.
Format responses in markdown. Never give specific investment advice or recommendations to buy/sell.
Focus on analytical observations, regime context, and risk factors.
Keep responses under 400 words unless the user asks for more depth."""


def _build_market_context(
    macro_total: int | None = None,
    macro_label: str | None = None,
    scores: list | None = None,
    vix: float | None = None,
    spy_chg: float | None = None,
    qqq_chg: float | None = None,
    breadth_50: float | None = None,
    breadth_200: float | None = None,
    cta_equity: float | None = None,
    best_sector: str | None = None,
    worst_sector: str | None = None,
    quotes_df: pd.DataFrame | None = None,
) -> str:
    """Build a structured market context string for the AI prompt."""
    ctx = [f"## Current Market Data ({datetime.now().strftime('%A %d %b %Y, %H:%M ET')})\n"]

    if macro_total is not None:
        ctx.append(f"**Macro Score:** {macro_total}/70 — {macro_label or ''}")

    if scores:
        ctx.append("\n**Macro Indicators:**")
        for s in scores:
            bar = s.breakdown() if hasattr(s, "breakdown") else s
            ctx.append(f"- {bar.get('name','')}: {bar.get('latest',0):.2f}  →  Score {bar.get('Total',0)}/10")

    if vix is not None:
        regime = "Extreme Fear" if vix > 30 else "Fear" if vix > 20 else "Normal" if vix > 15 else "Complacent"
        ctx.append(f"\n**VIX:** {vix:.2f} ({regime})")

    if spy_chg is not None:
        ctx.append(f"**S&P 500:** {spy_chg:+.2f}% today")
    if qqq_chg is not None:
        ctx.append(f"**Nasdaq 100:** {qqq_chg:+.2f}% today")

    if breadth_50 is not None:
        ctx.append(f"\n**Market Breadth:**")
        ctx.append(f"- {breadth_50:.0f}% of stocks above 50-day MA")
    if breadth_200 is not None:
        ctx.append(f"- {breadth_200:.0f}% of stocks above 200-day MA")

    if cta_equity is not None:
        regime_cta = "LONG" if cta_equity > 20 else "SHORT" if cta_equity < -20 else "NEUTRAL"
        ctx.append(f"\n**CTA Equity Exposure:** {cta_equity:+.0f} ({regime_cta})")

    if best_sector or worst_sector:
        ctx.append("\n**Sector Rotation:**")
        if best_sector:  ctx.append(f"- Best today: {best_sector}")
        if worst_sector: ctx.append(f"- Worst today: {worst_sector}")

    if quotes_df is not None and not quotes_df.empty:
        ctx.append("\n**Watchlist Performance:**")
        for _, row in quotes_df.dropna(subset=["Change %"]).iterrows():
            ctx.append(
                f"- {row['Ticker']}: ${row.get('Price', 0):,.2f}  {row['Change %']:+.2f}%"
            )

    return "\n".join(ctx)


def ask_ai(
    question: str,
    market_context: str = "",
    stream: bool = False,
) -> str:
    """
    Send a question to the routed model with market context.
    Returns the response text (or raises on error).
    """
    prompt = f"{market_context}\n\n---\n\n**User Question:** {question}" if market_context else question

    return llm_router.chat(
        [{"role": "user", "content": prompt}],
        system=_SYSTEM,
        max_tokens=1024,
    )


def generate_market_brief(market_context: str) -> str:
    """Auto-generate a morning market brief from current data."""
    prompt = (
        f"{market_context}\n\n---\n\n"
        "Generate a concise institutional morning market brief covering:\n"
        "1. **Macro Regime** — what the score tells us\n"
        "2. **Risk Sentiment** — VIX, breadth, positioning\n"
        "3. **Key Observations** — 3 notable data points\n"
        "4. **Watch List** — what to monitor\n\n"
        "Keep it under 300 words. Use a professional, analytical tone."
    )
    return llm_router.chat(
        [{"role": "user", "content": prompt}],
        system=_SYSTEM,
        max_tokens=1024,
    )


def analyze_ticker(ticker: str, fundamentals: dict, price_df: pd.DataFrame) -> str:
    """Generate AI analysis for a specific stock."""
    # Build context
    fund_str = []
    if fundamentals:
        for k, v in fundamentals.items():
            if v and k not in ("summary", "error"):
                fund_str.append(f"- {k}: {v}")
    fund_text = "\n".join(fund_str[:15])

    # Recent price action
    price_text = ""
    if not price_df.empty and "Close" in price_df.columns:
        recent = price_df["Close"].tail(5)
        chg_20d = float((price_df["Close"].iloc[-1] / price_df["Close"].iloc[-20] - 1) * 100) if len(price_df) >= 20 else None
        chg_50d = float((price_df["Close"].iloc[-1] / price_df["Close"].iloc[-50] - 1) * 100) if len(price_df) >= 50 else None
        price_text = (
            f"\nRecent close prices: {', '.join(f'${v:.2f}' for v in recent)}\n"
            f"20-day return: {chg_20d:+.2f}%" if chg_20d else ""
        )
        if chg_50d:
            price_text += f"\n50-day return: {chg_50d:+.2f}%"

    prompt = (
        f"Analyze {ticker} from an institutional perspective.\n\n"
        f"**Fundamentals:**\n{fund_text}\n"
        f"**Price Action:**\n{price_text}\n"
        f"**Business:** {fundamentals.get('summary','')}\n\n"
        "Provide:\n"
        "1. **Fundamental Summary** — key valuation and quality metrics\n"
        "2. **Price Action** — trend and momentum context\n"
        "3. **Bull Case** — 2-3 key positives\n"
        "4. **Bear Case** — 2-3 key risks\n"
        "5. **What to Watch** — key upcoming catalysts\n\n"
        "Under 350 words. No buy/sell recommendation."
    )
    return llm_router.chat(
        [{"role": "user", "content": prompt}],
        system=_SYSTEM,
        max_tokens=1024,
    )


def is_ai_available() -> bool:
    """True if the router has at least one usable key."""
    return llm_router.is_available()


def ai_backend() -> str:
    """Which transport the router will use: 'openrouter' | 'anthropic' | 'none'."""
    return llm_router.active_backend()


def ai_route_status() -> str:
    """Which model actually served the last call."""
    return llm_router.route_status()
