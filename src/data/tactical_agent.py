"""
Black Raven Protocol v1.0 — Tactical AI Agent
Interactive command-center chatbot with live dashboard context injection.

Architecture:
  AGENT_SYSTEM_PROMPT  — hardcoded institutional persona (static, prompt-cached)
  build_live_context() — serializes live dashboard state (sector rotation,
                         51-stock raven sweep, macro matrix, yields, VIX, COT)
                         into a compact context block injected on every turn
  ask_tactical_agent() — Claude API call (anthropic SDK)
"""
from __future__ import annotations

import os
import pandas as pd

MODEL_ID = "claude-opus-4-8"

# ── Step 3: hardcoded system prompt ───────────────────────────────────────────
AGENT_SYSTEM_PROMPT = """You are the Tactical AI Agent of Black Raven Protocol v1.0 — a cold, calculating institutional quantitative strategist embedded in a live markets dashboard.

IDENTITY & TONE
- You are a Lead Quantitative Analyst at a top-tier trading desk. Ruthless, mathematical, devoid of emotion or hype.
- You NEVER give generic retail advice ("diversify", "invest for the long term", "consult an advisor" as content). If asked for retail-style tips, refuse curtly and redirect to protocol analytics.
- Every market view is expressed through TWO paradigms only:
  1. K-ECONOMY: the consumer is breaking under sticky inflation and high credit costs → structural penalty on Consumer Discretionary, retail, and consumer-dependent cyclicals.
  2. ECONOMY OF SHORTAGE (Physical AI): institutional CapEx flows into hardware bottlenecks — silicon, advanced packaging, optics, MLCC passives, thermal/liquid cooling, power delivery, grid → structural premium on XLK, XLU, XLE, XLI and Tier 1/2 hardware names.

THE 4-TIER HIERARCHY (non-negotiable)
- TIER 1 (Ultimate Conviction — aggressively favored): NVDA, TSM, VRT, ASML, POWL and the other Tier 1 monopolies/bottlenecks. These are the core. When capital deployment is discussed, these names come first.
- TIER 2 (High Conviction): test/measurement, optics, packaging, infrastructure layer (incl. AIP with its permanent micro-cap liquidity watch).
- TIER 3 (Medium): policy beta, integration, defensive hedges.
- TIER 4 (DANGER ZONE — reject): SMCI, DELL, HPE, META, GOOGL, MSFT, AMZN, ORCL. Spenders/funders with CapEx fatigue and no hardware pricing power. NEVER recommend longs in Tier 4. Only mention them as underweights, avoids, or short legs in pairs structures.

EXECUTION DOCTRINE
- All entries are expressed as GTC BUY LIMIT orders at algorithmic support zones (50/100/200-SMA per each stock's designated entry rule) — never market orders, never chasing breakouts in thin liquidity.
- Respect CTA mechanics: MA breaks (20/50/100/200), VaR limits, the volatility feedback loop (drop → VIX spike → forced de-grossing).
- Flag "Spot Up / Vol Up" as a tactical warning. Watch COT positioning extremes (max short = squeeze fuel, max long = crowded unwind risk).
- Scenario requests ("if QQQ drops 2%…") get cold if-then execution plans: trigger level → affected tiers → specific GTC limit levels from the live data → sizing per tier (T1 5-8%, T2 3-5%, T3 1-3%, T4 0%) → invalidation/stop conditions.

DATA DISCIPLINE
- A live dashboard snapshot is injected below in <live_dashboard_context>. Ground EVERY number you cite in it. Never invent prices or levels. If a needed number is missing from context, say so explicitly.
- Cite exact figures: prices, SMA distances, RS scores, spreads, percentiles.
- Format: tight markdown. Tables for multi-name output. Bold key levels. No pleasantries, no filler.

COMPLIANCE LINE
- You produce quantitative protocol analytics, not personalized investment advice. When output resembles trade instructions, it is a hypothetical execution framework per Black Raven Protocol rules. End scenario/execution responses with: "— Protocol analytics. Not financial advice."
"""


def _fmt(v, fmt="{:+.1f}"):
    return fmt.format(v) if isinstance(v, (int, float)) and v == v else "—"


# ── Step 2: dynamic context injection ─────────────────────────────────────────
def build_live_context(
    raven_df: pd.DataFrame | None = None,
    rotation_df: pd.DataFrame | None = None,
    macro_matrix: dict | None = None,
    yield_curve: dict | None = None,
    vix_value: float | None = None,
    cot: dict | None = None,
) -> str:
    """Serialize live dashboard state into a compact text block the LLM sees each turn."""
    parts: list[str] = ["<live_dashboard_context>"]

    if vix_value is not None and vix_value == vix_value:
        parts.append(f"VIX: {vix_value:.2f}")

    if yield_curve and yield_curve.get("latest") is not None:
        l = yield_curve["latest"]
        s2510 = yield_curve.get("spread_2s10s")
        s2510v = float(s2510.iloc[-1]) if s2510 is not None and len(s2510) else None
        parts.append(
            "US TREASURY YIELDS (official, as of {}): 3M {:.2f}% | 2Y {:.2f}% | 10Y {:.2f}% | 30Y {:.2f}% | "
            "2s10s spread {}pp".format(
                yield_curve.get("asof", "—"), l.get("3 Mo", float("nan")), l.get("2 Yr", float("nan")),
                l.get("10 Yr", float("nan")), l.get("30 Yr", float("nan")), _fmt(s2510v, "{:+.2f}"),
            )
        )

    if macro_matrix:
        mm = []
        for k, d in macro_matrix.items():
            if isinstance(d, dict) and "value" in d:
                mm.append(f"{k} {d['value']:.2f} ({_fmt(d.get('change_pct'), '{:+.2f}')}%)")
        if mm:
            parts.append("MACRO MATRIX (1d chg): " + " | ".join(mm))

    if cot:
        rows = [
            f"{m['Market']}: net {m['Net']:+,} ({m['Net_pct_OI']:+.1f}% OI, {m['Pctile_3y']:.0f}th pctile 3y) — {m['Regime']}"
            for m in cot.values()
        ]
        parts.append("REAL CTA/FUND POSITIONING (CFTC COT, weekly):\n" + "\n".join(rows))

    if rotation_df is not None and not rotation_df.empty:
        lines = ["SECTOR ROTATION SCORECARD (RS math × macro overlays, score/12):"]
        for _, r in rotation_df.iterrows():
            lines.append(
                f"{r['Sector']} ({r['ETF']}): {r['Final_Score']:.1f} [{r['Tier']}] | "
                f"RS 1W {_fmt(r['RS_1W'])} 1M {_fmt(r['RS_1M'])} 3M {_fmt(r['RS_3M'])} "
                f"6M {_fmt(r['RS_6M'])} 1Y {_fmt(r['RS_1Y'])} | slope: {r['Slope_State']} | "
                f"ambush 50SMA ${r['Ambush_50SMA']:.2f} (px {_fmt(r['Dist_Ambush%'])}% away)"
            )
        parts.append("\n".join(lines))

    if raven_df is not None and not raven_df.empty:
        lines = ["MASTER WATCHLIST — 51 STOCKS (live BLACK RAVEN sweep):"]
        for _, r in raven_df.iterrows():
            entry = f"${r['Entry_Price']:.2f}" if isinstance(r["Entry_Price"], (int, float)) and r["Entry_Price"] == r["Entry_Price"] else "—"
            lines.append(
                f"T{r['Tier']} {r['Ticker']} ({r['Company']}, {r['Sector']}): px ${r['Price']:.2f} "
                f"({_fmt(r['Ret_1d%'], '{:+.2f}')}% 1d) | entry {r['Entry_Rule']} @ {entry} "
                f"(dist {_fmt(r['Dist_Entry%'])}%) | RAVEN: {r['RAVEN']}"
            )
        parts.append("\n".join(lines))

    parts.append("</live_dashboard_context>")
    return "\n\n".join(parts)


def is_agent_available() -> bool:
    key = os.getenv("ANTHROPIC_API_KEY", "")
    return bool(key) and "your_anthropic" not in key


def ask_tactical_agent(question: str, history: list[dict], live_context: str) -> str:
    """
    One agent turn. `history` = [{"role": "user"|"assistant", "content": str}, ...]
    (prior turns only). The static system prompt is prompt-cached; the volatile
    live context rides in a second system block after the cache breakpoint.
    """
    import anthropic

    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY from env

    messages = [{"role": m["role"], "content": m["content"]} for m in history[-12:]]
    messages.append({"role": "user", "content": question})

    response = client.messages.create(
        model=MODEL_ID,
        max_tokens=2048,
        system=[
            {"type": "text", "text": AGENT_SYSTEM_PROMPT,
             "cache_control": {"type": "ephemeral"}},   # static — cached
            {"type": "text", "text": live_context},      # volatile — after breakpoint
        ],
        messages=messages,
    )
    if response.stop_reason == "refusal":
        return "Request declined by model safety systems. Rephrase within protocol scope."
    return "".join(b.text for b in response.content if b.type == "text")
