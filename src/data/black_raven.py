"""
Black Raven Protocol v1.0 — Core Analytical Engine
Institutional quantitative framework: K-Economy / Physical AI Infrastructure / Kill Zone Execution
"""
from __future__ import annotations

import json
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

# ── Universe Definition ───────────────────────────────────────────────────────

TIER_UNIVERSE: dict[int, dict[str, str]] = {
    1: {
        "TSM":  "TSMC — Sole EUV Wafer Foundry, 92% advanced-node monopoly",
        "ASML": "ASML — Only EUV lithography machine supplier on Earth",
        "NVDA": "NVIDIA — GPU/Accelerator monopoly, H100/B200 perpetual backlog",
        "VRT":  "Vertiv — Mission-critical power & liquid cooling for hyperscaler DC",
        "POWL": "Powell Industries — High-voltage electrical switchgear, DC power",
    },
    2: {
        "GLW":  "Corning — Glass substrates, optical fiber, AI interconnect",
        "AMAT": "Applied Materials — CVD/PVD deposition equipment, gate-all-around",
        "LRCX": "Lam Research — Etch/deposition, EUV mask blank monopoly",
        "CEG":  "Constellation Energy — Nuclear baseload for hyperscaler PPAs",
        "VST":  "Vistra — Natural gas + nuclear peaker, signed DC power contracts",
        "ETN":  "Eaton — Power management / UPS for AI data centers",
        "NVT":  "nVent Electric — Thermal management, liquid cooling enclosures",
    },
    3: {
        "ONTO": "Onto Innovation — Advanced packaging inspection, metrology",
        "AMD":  "AMD — EPYC CPUs, MI300X GPU challenger, custom AI silicon",
        "MRVL": "Marvell — Custom AI ASIC (Google TPU), optical interconnect",
        "CAMT": "Camtek — Wafer bump inspection for advanced packaging",
        "LITE": "Lumentum — Optical transceivers, 800G data center interconnect",
    },
    4: {
        "MSFT": "AVOID — AI CapEx consumer (renting NVDA GPUs), not a producer",
        "ORCL": "AVOID — Cloud margin erosion, AI software execution risk",
        "PLTR": "AVOID — AI software dream, no physical moat, valuation stretched",
        "GOOG": "AVOID — Renting NVDA GPUs ($920M+/mo), structural CapEx drag",
        "SMCI": "AVOID — Margin collapse, audit risk, commoditised server assembly",
        "INTC": "AVOID — Structural fab market-share loss, execution uncertainty",
    },
}

MACRO_INSTRUMENTS: dict[str, str] = {
    "US 10Y":   "^TNX",
    "US 2Y":    "^IRX",
    "WTI Oil":  "CL=F",
    "DXY":      "DX-Y.NYB",
    "Gold":     "GC=F",
    "HYG":      "HYG",      # Credit spread proxy
    "XLE":      "XLE",      # Energy hedge instrument
    "SPY":      "SPY",      # Market regime anchor
}

# ── Position sizing (% of portfolio per tier) ─────────────────────────────────
POSITION_SIZING: dict[int, tuple[int, int]] = {
    1: (5, 8),   # Max conviction
    2: (3, 5),   # High conviction
    3: (1, 3),   # Medium conviction
    4: (0, 0),   # AVOID
}

# ── Kill Zone classification ──────────────────────────────────────────────────
KILL_ZONE_THRESHOLDS = [
    (-999, -5,  "DEEP VALUE",    "#06b6d4", "ACCUMULATE — Max size"),
    (-5,    0,  "KILL ZONE ●",  "#10b981", "BUY NOW — Place Limit at 50SMA"),
    ( 0,    3,  "APPROACHING",   "#84cc16", "PLACE LIMIT — Pre-position"),
    ( 3,    8,  "ELEVATED",      "#f59e0b", "WATCH — Set GTC limit at 50SMA"),
    ( 8,   15,  "EXTENDED",      "#f97316", "NO BUY — Wait for flush"),
    (15,  999,  "CHASE ZONE ✗", "#ef4444", "STRICT AVOID — Overbought"),
]

CATALYSTS_FILE = Path(__file__).parent.parent.parent / "data" / "catalysts.json"


def classify_kill_zone(dist_pct: float) -> tuple[str, str, str]:
    """Returns (zone_label, color_hex, action_string)."""
    for lo, hi, label, color, action in KILL_ZONE_THRESHOLDS:
        if lo <= dist_pct < hi:
            return label, color, action
    return "CHASE ZONE ✗", "#ef4444", "STRICT AVOID"


def compute_rsi(series: pd.Series, period: int = 14) -> float:
    """Compute RSI from price series. Returns last value."""
    delta = series.diff().dropna()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1]) if not rsi.empty else float("nan")


def fetch_tier_radar() -> pd.DataFrame:
    """
    Fetch current price vs 50SMA / 20EMA for all Tier 1-4 stocks in parallel.
    Returns DataFrame with kill zone classification and execution parameters.
    """
    from src.data.price_fetcher import fetch_history_robust
    from concurrent.futures import ThreadPoolExecutor, as_completed

    start = (datetime.now() - timedelta(days=260)).strftime("%Y-%m-%d")

    # Flatten all (tier, ticker, desc) tuples for parallel dispatch
    tasks = [
        (tier, ticker, desc)
        for tier, stocks in TIER_UNIVERSE.items()
        for ticker, desc in stocks.items()
    ]

    def _fetch_one(task):
        tier, ticker, desc = task
        try:
            s = fetch_history_robust(ticker, start)
            if s is None or s.empty or len(s) < 52:
                return None
            s = s.dropna()

            price  = float(s.iloc[-1])
            sma50  = float(s.tail(50).mean())
            sma200 = float(s.tail(200).mean()) if len(s) >= 200 else None
            ema20  = float(s.ewm(span=20, adjust=False).mean().iloc[-1])
            rsi14  = compute_rsi(s.tail(60))

            ret_1d  = (price / float(s.iloc[-2])  - 1) * 100 if len(s) >= 2  else 0
            ret_5d  = (price / float(s.iloc[-6])  - 1) * 100 if len(s) >= 6  else 0
            ret_20d = (price / float(s.iloc[-21]) - 1) * 100 if len(s) >= 21 else 0

            dist_50  = (price - sma50)  / sma50  * 100
            dist_200 = (price - sma200) / sma200 * 100 if sma200 else None

            zone, color, action = classify_kill_zone(dist_50)
            trend = "UPTREND" if (sma200 and price > sma200) else "DOWNTREND"

            limit_price = round(sma50, 2)
            stop_loss   = round(sma50 * 0.92, 2)
            target_1    = round(sma50 * 1.15, 2)
            risk_reward = round((target_1 - limit_price) / (limit_price - stop_loss), 2) if (limit_price - stop_loss) > 0 else 0

            min_sz, max_sz = POSITION_SIZING[tier]

            return {
                "Tier":         tier,
                "Ticker":       ticker,
                "Description":  desc.split(" — ")[0],
                "Thesis":       desc.split(" — ")[1] if " — " in desc else desc,
                "Price":        round(price, 2),
                "50SMA":        round(sma50, 2),
                "20EMA":        round(ema20, 2),
                "200SMA":       round(sma200, 2) if sma200 else None,
                "Dist_50SMA%":  round(dist_50, 2),
                "Dist_200SMA%": round(dist_200, 2) if dist_200 else None,
                "RSI14":        round(rsi14, 1) if not np.isnan(rsi14) else None,
                "Ret_1d%":      round(ret_1d, 2),
                "Ret_5d%":      round(ret_5d, 2),
                "Ret_20d%":     round(ret_20d, 2),
                "Trend":        trend,
                "Zone":         zone,
                "ZoneColor":    color,
                "Action":       action,
                "Limit_Price":  limit_price,
                "Stop_Loss":    stop_loss,
                "Target_1":     target_1,
                "RR_Ratio":     risk_reward,
                "Min_Size%":    min_sz,
                "Max_Size%":    max_sz,
            }
        except Exception:
            return None

    rows = []
    with ThreadPoolExecutor(max_workers=min(16, len(tasks))) as ex:
        for result in ex.map(_fetch_one, tasks):
            if result is not None:
                rows.append(result)

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["Tier", "Dist_50SMA%"], ascending=[True, True])
    return df


def fetch_macro_matrix() -> dict:
    """
    Fetch macro & liquidity instruments for the Macro Paradigm overlay.
    Returns dict with current values, 1-day change, and regime signal.
    """
    from src.data.price_fetcher import fetch_history_robust

    out = {}
    start = (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d")

    for label, ticker in MACRO_INSTRUMENTS.items():
        try:
            s = fetch_history_robust(ticker, start)
            if s is None or len(s) < 2:
                continue
            s = s.dropna()
            cur  = float(s.iloc[-1])
            prev = float(s.iloc[-2])
            chg  = cur - prev
            chgp = chg / prev * 100 if prev else 0
            out[label] = {
                "ticker":     ticker,
                "value":      cur,
                "change":     chg,
                "change_pct": chgp,
            }
        except Exception:
            pass

    # Derive regime signals
    signals = []
    ten_y = out.get("US 10Y", {}).get("value")
    oil   = out.get("WTI Oil", {}).get("value")
    hyg   = out.get("HYG", {})

    if ten_y and ten_y > 4.5:
        signals.append(("⚠️ 10Y > 4.5%", "Yield danger zone — Fed tightening risk", "#ef4444"))
    if ten_y and ten_y < 3.5:
        signals.append(("✅ 10Y < 3.5%", "Rate easing — Risk-on for Tier 1/2", "#10b981"))
    if oil and oil > 90:
        signals.append(("⚠️ OIL > $90", "Black Swan risk — Activate XLE hedge", "#8b5cf6"))
    if oil and oil > 100:
        signals.append(("🚨 OIL > $100", "Grade C Black Swan — Max XLE call hedge", "#ef4444"))
    if hyg.get("change_pct") and hyg["change_pct"] < -0.5:
        signals.append(("⚠️ HYG DROP", "Credit spreads widening — Risk-off signal", "#f59e0b"))

    out["_signals"] = signals
    return out


def score_catalyst(headline: str, body: str = "", source: str = "manual") -> dict:
    """
    Score a news catalyst through the Narrative Execution Filter.
    Returns grade, urgency, investability, and tier affinity.
    """
    text = (headline + " " + body).lower()
    ts   = datetime.now().isoformat()

    # ── Grade A: Macro regime shifts + Tier 1/2 CapEx events ────────────────
    grade_a_terms = [
        "cpi", "core pce", "nfp", "payrolls", "fomc", "fed rate decision",
        "earnings beat", "capex guidance", "order intake", "backlog increase",
        "book-to-bill", "hyperscaler contract", "10-year yield",
        "tsm", "tsmc", "asml", "nvidia", "vertiv", "powell industries",
        "data center contract", "signed agreement", "purchase order",
        "4.5%", "5%",
    ]
    # ── Grade B: Sector catalysts ─────────────────────────────────────────────
    grade_b_terms = [
        "chips act", "semiconductor", "tariff", "supply chain disruption",
        "fab expansion", "euv", "gate-all-around", "advanced packaging",
        "nuclear ppa", "power grid", "liquid cooling", "copper demand",
        "glass substrate", "optical transceiver", "800g", "lam research",
        "applied materials", "corning", "constellation energy", "eaton",
    ]
    # ── Grade C: Black Swan / macro shock ────────────────────────────────────
    grade_c_terms = [
        "iran", "middle east", "strait of hormuz", "oil spike", "opec cut",
        "bank failure", "credit crunch", "systemic risk", "fed emergency",
        "taiwan strait", "china invade", "black swan",
    ]

    is_a = any(t in text for t in grade_a_terms)
    is_b = any(t in text for t in grade_b_terms)
    is_c = any(t in text for t in grade_c_terms)

    # Narrative Execution Filter
    capex_real_terms = [
        "signed contract", "awarded", "purchase agreement", "order backlog",
        "book-to-bill", "supply agreement", "construction permit",
        "capital expenditure", "capex allocation", "committed spending",
        "data center build", "fab groundbreaking",
    ]
    ai_dream_terms = [
        "exploring partnership", "plans to integrate", "ai vision",
        "strategic alliance", "collaboration announced", "roadmap",
        "software platform", "generative ai", "ai copilot",
    ]

    capex_real = any(t in text for t in capex_real_terms)
    ai_dream   = any(t in text for t in ai_dream_terms)

    if ai_dream and not capex_real:
        narrative = "AI DREAM ✗"
        investable = False
    elif capex_real:
        narrative = "CAPEX REAL ✓"
        investable = True
    else:
        narrative = "NEUTRAL —"
        investable = None

    # Identify tier affinity
    tier_affinity = []
    for tier, stocks in TIER_UNIVERSE.items():
        for ticker in stocks:
            if ticker.lower() in text or stocks[ticker].lower().split(" — ")[0].lower() in text:
                tier_affinity.append(f"T{tier}:{ticker}")

    if is_c:
        grade, urgency, color = "C", "🚨 BLACK SWAN — Activate full hedge protocol NOW", "#8b5cf6"
    elif is_a:
        grade, urgency, color = "A", "⚡ IMMEDIATE — Execute or hedge within current session", "#ef4444"
    elif is_b:
        grade, urgency, color = "B", "🔔 HIGH — Review position and limits within 2 hours", "#f59e0b"
    else:
        grade, urgency, color = "D", "📋 MONITOR — Log for pattern recognition", "#6b7280"

    return {
        "timestamp":    ts,
        "headline":     headline,
        "body":         body,
        "source":       source,
        "grade":        grade,
        "urgency":      urgency,
        "color":        color,
        "narrative":    narrative,
        "investable":   investable,
        "tier_affinity": tier_affinity,
    }


def load_catalysts() -> list[dict]:
    """Load catalyst feed from JSON file (written by Make.com webhook)."""
    CATALYSTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not CATALYSTS_FILE.exists():
        return []
    try:
        with open(CATALYSTS_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def save_catalyst(catalyst: dict) -> None:
    """Append a catalyst to the JSON feed."""
    CATALYSTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing = load_catalysts()
    existing.insert(0, catalyst)
    existing = existing[:100]   # keep last 100
    with open(CATALYSTS_FILE, "w") as f:
        json.dump(existing, f, indent=2)


def compute_hedge_params(
    vix: float | None,
    spy_rsi: float | None,
    breadth_50: float | None,
    oil: float | None,
) -> dict:
    """
    Compute asymmetric hedge recommendation:
    - Primary: QQQ Bear Put Spread (complacency / overbought)
    - Secondary: XLE Calls (oil shock)
    - Baseline: 5% cash reserve (always)
    """
    overbought   = (spy_rsi or 0) > 70
    low_vol      = (vix or 20) < 15
    extreme_fear = (vix or 20) > 30
    oil_shock    = (oil or 70) > 90
    breadth_weak = (breadth_50 or 60) < 45

    hedges = []

    if overbought and low_vol:
        hedges.append({
            "priority":    "PRIMARY",
            "instrument":  "QQQ Bear Put Spread",
            "structure":   "Buy ATM Put / Sell 5% OTM Put  •  30 DTE  •  GTC",
            "size":        "15% of portfolio notional",
            "rationale":   "RSI overbought + VIX complacency — maximum asymmetric risk",
            "color":       "#ef4444",
            "urgency":     "HIGH — Open position before close",
        })
    elif overbought or low_vol:
        hedges.append({
            "priority":    "PRIMARY",
            "instrument":  "QQQ Bear Put Spread (light)",
            "structure":   "Buy ATM Put / Sell 7% OTM Put  •  45 DTE  •  GTC",
            "size":        "8% of portfolio notional",
            "rationale":   "Single stress signal — partial hedge",
            "color":       "#f59e0b",
            "urgency":     "MODERATE — Set limit and monitor",
        })

    if oil_shock:
        hedges.append({
            "priority":    "SECONDARY",
            "instrument":  "XLE Call Options",
            "structure":   "Buy 2% OTM Calls on XLE  •  60 DTE  •  GTC",
            "size":        "3% of portfolio notional",
            "rationale":   f"WTI > $90 — Energy shock hedge activated",
            "color":       "#8b5cf6",
            "urgency":     "OIL SHOCK PROTOCOL",
        })

    if extreme_fear and not overbought:
        hedges.append({
            "priority":    "OPPORTUNITY",
            "instrument":  "Increase Tier 1 Limits",
            "structure":   "Move all GTC limits to 50SMA price — flush likely",
            "size":        "Deploy up to 80% of cash reserve",
            "rationale":   "VIX > 30: retail panic = institutional buy zone",
            "color":       "#10b981",
            "urgency":     "BUYING OPPORTUNITY — Activate kill zone orders",
        })

    if not hedges:
        hedges.append({
            "priority":    "BASELINE",
            "instrument":  "5% Cash Reserve",
            "structure":   "Maintain minimum cash  •  No options needed",
            "size":        "5% minimum",
            "rationale":   "No active stress signals detected",
            "color":       "#10b981",
            "urgency":     "MINIMAL — Monitor breadth and yields",
        })

    return {
        "hedges":        hedges,
        "overbought":    overbought,
        "low_vol":       low_vol,
        "extreme_fear":  extreme_fear,
        "oil_shock":     oil_shock,
        "breadth_weak":  breadth_weak,
        "regime_signal": "BUY FLUSH" if extreme_fear else ("HEDGE" if (overbought or low_vol) else "NEUTRAL"),
    }
