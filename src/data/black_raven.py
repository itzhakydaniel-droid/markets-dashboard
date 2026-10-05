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

# ── Master Watchlist — institutional ranking ─────────────────────────────────
# Tiers follow the desk protocol (insiders_club/knowledge/my_method.md §6).
# Entry types: sma50 / sma100 / sma200 → limit order at that moving average.
# "special" → discretionary structural rule (textual); 50-SMA shown as anchor.

MASTER_WATCHLIST: dict[str, dict] = {
    # ── TIER 1: Ultimate Conviction — monopolies, scarcity, pricing power ─────
    "NVDA":      {"tier": 1, "name": "Nvidia",              "sector": "GPU Compute",              "entry": "sma50",  "entry_note": "50-Day SMA"},
    "TSM":       {"tier": 1, "name": "Taiwan Semi",         "sector": "Foundry Monopoly",         "entry": "sma100", "entry_note": "100-Day SMA"},
    "ASML":      {"tier": 1, "name": "ASML",                "sector": "EUV Lithography",          "entry": "sma100", "entry_note": "100-Day SMA"},
    "MU":        {"tier": 1, "name": "Micron",              "sector": "High-Bandwidth Memory",    "entry": "sma100", "entry_note": "100-Day SMA"},
    "000660.KS": {"tier": 1, "name": "SK Hynix",            "sector": "HBM Leader",               "entry": "special","entry_note": "Deep intra-day pullbacks"},
    "VRT":       {"tier": 1, "name": "Vertiv",              "sector": "Thermal / Liquid Cooling", "entry": "sma50",  "entry_note": "50-Day SMA"},
    "ETN":       {"tier": 1, "name": "Eaton",               "sector": "Power Grid Infra",         "entry": "special","entry_note": "Bottom of rising channel"},
    "AVGO":      {"tier": 1, "name": "Broadcom",            "sector": "Custom Silicon / Network", "entry": "sma100", "entry_note": "100-Day SMA"},
    "MRVL":      {"tier": 2, "name": "Marvell",             "sector": "Silicon Photonics",        "entry": "sma200", "entry_note": "200-Day SMA"},
    "2327.TW":   {"tier": 1, "name": "Yageo",               "sector": "MLCC Passives",            "entry": "special","entry_note": "Breakout retests"},
    "MRAAY":     {"tier": 1, "name": "Murata",              "sector": "High-Reliability Passives","entry": "sma200", "entry_note": "200-Day SMA"},
    "TTDKY":     {"tier": 1, "name": "TDK",                 "sector": "HV Power Components",      "entry": "special","entry_note": "Scaled pullbacks"},
    "ASX":       {"tier": 1, "name": "ASE Technology",      "sector": "Advanced Packaging",       "entry": "sma50",  "entry_note": "50-Day SMA"},
    "AMKR":      {"tier": 2, "name": "Amkor",               "sector": "US Advanced Packaging",    "entry": "sma100", "entry_note": "100-Day SMA"},
    "ANET":      {"tier": 1, "name": "Arista Networks",     "sector": "Cloud Switching",          "entry": "sma50",  "entry_note": "50-Day SMA"},
    "LEU":       {"tier": 1, "name": "Centrus Energy",      "sector": "HALEU Enrichment Monopoly","entry": "sma50",  "entry_note": "50-Day SMA — ambush on panic/backlog disconnects",
                  "linked": ["CEG", "VST"],
                  "raven_override": ("RARE CAPACITY HOLDER — sole licensed US HALEU producer; watch CEG/VST LTA & NRC triggers", "#10b981")},
    "NEM":       {"tier": 1, "name": "Newmont",              "sector": "Macro Hedge / Gold FCF Machine", "entry": "special", "entry_note": "Limit orders on market pullbacks",
                  "raven_override": ("MACRO HEDGE — gold FCF machine; accumulate on broad-market flushes", "#f59e0b")},
    "CAT":       {"tier": 1, "name": "Caterpillar",          "sector": "Power Infra / Distributed Gen",  "entry": "special", "entry_note": "Limit orders on market pullbacks"},
    # ── TIER 2: High Conviction — test, measurement, optics, infra layer ──────
    "AMAT":      {"tier": 2, "name": "Applied Materials",   "sector": "Wafer Fab Equipment",      "entry": "sma100", "entry_note": "100-Day SMA"},
    "LRCX":      {"tier": 2, "name": "Lam Research",        "sector": "Memory Etch Equipment",    "entry": "special","entry_note": "Sector pullbacks"},
    "KLAC":      {"tier": 2, "name": "KLA Corp",            "sector": "Yield / Metrology",        "entry": "sma100", "entry_note": "100-Day SMA"},
    "TER":       {"tier": 2, "name": "Teradyne",            "sector": "SoC / AI Testing",         "entry": "sma200", "entry_note": "Strict limit at 200-Day SMA"},
    "COHU":      {"tier": 2, "name": "Cohu",                "sector": "Thermal Test / Handling",  "entry": "special","entry_note": "Short-term channel bottom"},
    "ONTO":      {"tier": 3, "name": "Onto Innovation",     "sector": "Packaging Metrology",      "entry": "special","entry_note": "10%+ pullback from highs"},
    "CAMT":      {"tier": 3, "name": "Camtek",              "sector": "3D Optical Inspection",    "entry": "sma100", "entry_note": "100-Day SMA support"},
    "FORM":      {"tier": 3, "name": "FormFactor",          "sector": "Probe Cards",              "entry": "special","entry_note": "Trading channel bottom"},
    "COHR":      {"tier": 2, "name": "Coherent",            "sector": "Optics / Lasers (GM 40.2%)","entry": "special","entry_note": "Extreme depth pullbacks",
                  "raven_override": ("PRICING POWER CONFIRMED — GM expansion to 40.2%, extreme DC transceiver demand", "#10b981")},
    "AAOI":      {"tier": 3, "name": "Applied Opto",        "sector": "800G Optical Transceivers","entry": "sma50",  "entry_note": "50-Day SMA"},
    "LITE":      {"tier": 2, "name": "Lumentum",            "sector": "Optical Routing",          "entry": "sma200", "entry_note": "200-Day SMA"},
    "CRDO":      {"tier": 2, "name": "Credo Technology",    "sector": "High-Speed AEC Cables",    "entry": "special","entry_note": "Volume confirmed breakout"},
    "FCX":       {"tier": 2, "name": "Freeport-McMoRan",     "sector": "Base Metals / Copper Electrification", "entry": "special", "entry_note": "Accumulate on macro dips"},
    "NET":       {"tier": 2, "name": "Cloudflare",           "sector": "AI Software / Cybersecurity", "entry": "special", "entry_note": "Support levels"},
    "ALAB":      {"tier": 2, "name": "Astera Labs",         "sector": "PCIe / Connectivity",      "entry": "special","entry_note": "Structural support zones"},
    "NVTS":      {"tier": 2, "name": "Navitas Semi",        "sector": "GaN Power Efficiency",     "entry": "special","entry_note": "Aggressive red days"},
    "ALGM":      {"tier": 2, "name": "Allegro Micro",       "sector": "Power ICs / Physical AI",  "entry": "sma200", "entry_note": "200-Day SMA"},
    "AIP":       {"tier": 2, "name": "Arteris",             "sector": "Custom Silicon & IP / NoC","entry": "sma50",  "entry_note": "50-Day SMA + Volume Confirmation",
                  "raven_override": ("MICRO-CAP LIQUIDITY WATCH — monitor volume spikes & VaR expansion", "#f59e0b")},
    "VICR":      {"tier": 2, "name": "Vicor",               "sector": "Point-of-Load Power Delivery", "entry": "special","entry_note": "Scaled limit orders at 50/100-Day SMA"},
    "WDC":       {"tier": 2, "name": "Western Digital",     "sector": "Nearline HDD / Cold-Storage Bottleneck", "entry": "sma50", "entry_note": "50-Day SMA",
                  "raven_override": ("STORAGE BOTTLENECK ALPHA — nearline HDD cold-data archive scarcity", "#10b981")},
    "STX":       {"tier": 2, "name": "Seagate",             "sector": "Nearline HDD Mass Storage","entry": "sma50",  "entry_note": "50-Day SMA",
                  "raven_override": ("STORAGE BOTTLENECK ALPHA — nearline HDD cold-data archive scarcity", "#10b981")},
    # ── Insiders Club portfolio additions (weekly summary 28/09–02/10/2026) ──
    "GLW":       {"tier": 2, "name": "Corning",             "sector": "Optical Fiber / Cable",    "entry": "sma50",  "entry_note": "50-Day SMA",
                  "raven_override": ("CONTRACTED DEMAND — $3B+ multi-year AT&T fiber deal (29/09)", "#10b981")},
    "SMTC":      {"tier": 2, "name": "Semtech",             "sector": "Copper/Optical DC Connectivity", "entry": "sma50", "entry_note": "50-Day SMA — no chase at 52w high"},
    "TSEM":      {"tier": 2, "name": "Tower Semi",          "sector": "Silicon Photonics Foundry","entry": "sma50",  "entry_note": "50-Day SMA"},
    "SNDK":      {"tier": 2, "name": "SanDisk",             "sector": "NAND / Enterprise SSD",    "entry": "sma50",  "entry_note": "50-Day SMA",
                  "raven_override": ("MEMORY CYCLE PEAK RISK — sell-the-news after MU print", "#f59e0b")},
    "SITM":      {"tier": 2, "name": "SiTime",              "sector": "MEMS Precision Timing",    "entry": "sma50",  "entry_note": "50-Day SMA"},
    "BE":        {"tier": 2, "name": "Bloom Energy",        "sector": "On-site Power / Time-to-Power", "entry": "sma50", "entry_note": "50-Day SMA — price above analyst target"},
    # ── TIER 3: Medium Conviction — policy beta, integration, hedges ──────────
    "POWL":      {"tier": 1, "name": "Powell Industries",   "sector": "Electrical Enclosures",    "entry": "sma50",  "entry_note": "50-Day SMA"},
    "NVT":       {"tier": 3, "name": "nVent Electric",      "sector": "Liquid Cooling Enclosures","entry": "sma100", "entry_note": "100-Day SMA"},
    "GEV":       {"tier": 3, "name": "GE Vernova",          "sector": "Grid Power Generation",    "entry": "special","entry_note": "Post-breakout consolidation",
                  "raven_override": ("PERMITTING & POWER GRID DELAY — verify approved interconnects vs. paper megawatts", "#f59e0b")},
    "PWR":       {"tier": 3, "name": "Quanta Services",     "sector": "Grid Contracting",         "entry": "special","entry_note": "Long-term accumulation",
                  "raven_override": ("PERMITTING & POWER GRID DELAY — verify approved interconnects vs. paper megawatts", "#f59e0b")},
    "MOD":       {"tier": 3, "name": "Modine",              "sector": "Thermal / HVAC",           "entry": "sma100", "entry_note": "100-Day SMA"},
    "MKSI":      {"tier": 3, "name": "MKS Instruments",     "sector": "Vacuum / Lasers WFE",      "entry": "sma200", "entry_note": "200-Day SMA"},
    "PENG":      {"tier": 3, "name": "Penguin Solutions",   "sector": "AI Infra Integration",     "entry": "sma100", "entry_note": "100-Day SMA"},
    "ARM":       {"tier": 3, "name": "Arm Holdings",        "sector": "Power-Efficient Arch",     "entry": "sma100", "entry_note": "100-Day SMA"},
    "AMD":       {"tier": 3, "name": "AMD",                 "sector": "Alt Compute Hedge",        "entry": "sma200", "entry_note": "200-Day SMA"},
    "QCOM":      {"tier": 3, "name": "Qualcomm",            "sector": "Edge AI Processing",       "entry": "special","entry_note": "Deep macro pullbacks"},
    "PLTR":      {"tier": 3, "name": "Palantir",            "sector": "AI Enterprise OS",         "entry": "sma50",  "entry_note": "50-Day SMA"},
    "PANW":      {"tier": 3, "name": "Palo Alto Networks",  "sector": "AI Cybersecurity / Observability", "entry": "sma50", "entry_note": "50-Day SMA"},
    # NOTE: AXTI (AXT Inc) is not in the latest pasted master-list spec — kept
    # here pending confirmation since it was a deliberate recent addition.
    "AXTI":      {"tier": 3, "name": "AXT Inc",             "sector": "Photonics Materials / Wafers", "entry": "sma200", "entry_note": "200-Day SMA — market flushes only",
                  "raven_override": ("HIGH VOLATILITY — Deep Value logic strictly during flushes", "#f59e0b")},
    "RKLB":      {"tier": 3, "name": "Rocket Lab",           "sector": "Space Economy Backlog",     "entry": "special", "entry_note": "Structural support — size for volatility",
                  "raven_override": ("EXECUTION RISK / EARNINGS VOLATILITY", "#f97316")},
    # ── Insiders Club portfolio additions (weekly summary 28/09–02/10/2026) ──
    "VIAV":      {"tier": 3, "name": "Viavi Solutions",     "sector": "Optical / 1.6T Network Test", "entry": "sma50", "entry_note": "50-Day SMA"},
    "VECO":      {"tier": 3, "name": "Veeco",               "sector": "Process Equipment (MOCVD/Ion Beam)", "entry": "sma50", "entry_note": "50-Day SMA"},
    "TTMI":      {"tier": 3, "name": "TTM Technologies",    "sector": "Advanced PCB / Defense RF", "entry": "sma50", "entry_note": "50-Day SMA",
                  "raven_override": ("DILUTION WATCH — $1.1B Epiq acquisition, FCF negative", "#f59e0b")},
    "AEHR":      {"tier": 3, "name": "Aehr Test Systems",   "sector": "Wafer-Level Burn-in Test", "entry": "sma50",  "entry_note": "50-Day SMA",
                  "raven_override": ("HIGH VOLATILITY — small-cap test, FCF negative", "#f59e0b")},
    "UCTT":      {"tier": 3, "name": "Ultra Clean",         "sector": "WFE Subsystems (Contract)", "entry": "sma200", "entry_note": "200-Day SMA only",
                  "raven_override": ("NO PRICING POWER — GM 16%, FCF negative (quality grade C)", "#f97316")},
    "SANM":      {"tier": 3, "name": "Sanmina",             "sector": "EMS / AI Rack Integration", "entry": "sma100", "entry_note": "100-Day SMA",
                  "raven_override": ("OEM MARGIN PROFILE — GM ~9%, contract manufacturer", "#f97316")},
    "AGX":       {"tier": 3, "name": "Argan",               "sector": "Power Plant EPC / Backlog", "entry": "sma200", "entry_note": "Wait for 200-Day SMA reclaim",
                  "raven_override": ("TREND BROKEN — below 200-SMA, RPO backlog shrinking YoY", "#f97316")},
    "FPS":       {"tier": 3, "name": "Forgent Power",       "sector": "Power Distribution Equipment", "entry": "special", "entry_note": "New listing — structural support only",
                  "raven_override": ("NEW LISTING — <1y price history, no 200-SMA anchor", "#f59e0b")},
    "GH":        {"tier": 3, "name": "Guardant Health",     "sector": "Liquid Biopsy (non-AI growth)", "entry": "sma50", "entry_note": "50-Day SMA",
                  "raven_override": ("OUTSIDE AI-INFRA THESIS — operating losses; club growth position", "#f59e0b")},
    # ── TIER 4: DANGER ZONE — spenders, leveraged cloud, no pricing power ─────
    "SMCI":      {"tier": 4, "name": "Super Micro",         "sector": "OEM Margin Collapse (GM 11.2%)", "entry": "avoid",  "entry_note": "Avoid / Short — split rally is not a thesis change",
                  "raven_override": ("LIQUIDITY ANOMALY / RETAIL FOMO TRAP — GM collapsed to 11.2%; 10-for-1 split rally ignored", "#ef4444")},
    "DELL":      {"tier": 4, "name": "Dell",                "sector": "ODM Bypass Risk",          "entry": "avoid",  "entry_note": "Underweight"},
    "HPE":       {"tier": 4, "name": "HP Enterprise",       "sector": "Legacy Server Margin",     "entry": "avoid",  "entry_note": "Avoid"},
    "META":      {"tier": 4, "name": "Meta Platforms",      "sector": "High CapEx / ROI Unproven","entry": "avoid",  "entry_note": "Underweight"},
    "GOOGL":     {"tier": 4, "name": "Alphabet",            "sector": "Infra Cost Compression",   "entry": "avoid",  "entry_note": "Neutral / Underweight"},
    "MSFT":      {"tier": 4, "name": "Microsoft",           "sector": "Premium Valuation",        "entry": "avoid",  "entry_note": "Underweight"},
    "AMZN":      {"tier": 4, "name": "Amazon",              "sector": "Utility / Power Costs",    "entry": "avoid",  "entry_note": "Pairs trading only"},
    "ORCL":      {"tier": 4, "name": "Oracle",              "sector": "Debt-Funded DC Buildout",  "entry": "avoid",  "entry_note": "Short-term trading only"},
    "MNDY":      {"tier": 4, "name": "monday.com",           "sector": "Legacy SaaS / AI Disintermediation", "entry": "avoid", "entry_note": "Underweight / Avoid"},
    "PEGA":      {"tier": 4, "name": "Pegasystems",          "sector": "Legacy SaaS / AI Disintermediation", "entry": "avoid", "entry_note": "Underweight / Avoid"},
    "ADBE":      {"tier": 4, "name": "Adobe",                "sector": "Legacy SaaS / AI Disintermediation", "entry": "avoid", "entry_note": "Underweight / Avoid"},
    "CRM":       {"tier": 4, "name": "Salesforce",           "sector": "Legacy SaaS / AI Disintermediation", "entry": "avoid", "entry_note": "Underweight / Avoid"},
}

# Insiders Club stock portfolio — the most up-to-date list (weekly summary,
# channel יומן-מסחר-וסיכום-שבוע). Synced by the daily insiders-club study task.
CLUB_PORTFOLIO: tuple[str, ...] = (
    "AGX", "VIAV", "AEHR", "TER", "TTMI", "ARM", "POWL", "VICR", "SMTC", "AAOI",
    "SANM", "AMKR", "UCTT", "AIP", "VECO", "GLW", "ALGM", "PENG", "TSEM", "SNDK",
    "BE", "SITM", "FPS", "CRDO", "GH",
)

# Backwards-compatible tier→{ticker: "Name — sector"} view used by fetch_tier_radar
TIER_UNIVERSE: dict[int, dict[str, str]] = {}
for _tk, _m in MASTER_WATCHLIST.items():
    TIER_UNIVERSE.setdefault(_m["tier"], {})[_tk] = f"{_m['name']} — {_m['sector']}"

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


# ── BLACK RAVEN master dashboard — 6-column institutional table ───────────────

def _raven_alert(d: dict, vix_up: bool) -> tuple[str, str]:
    """
    Classify the real-time algorithmic alert status for one stock.
    Priority-ordered: risk events first, then entries, then state.
    Returns (alert_text, color_hex).
    """
    price   = d["price"]
    ret_1d  = d["ret_1d"]
    ret_5d  = d["ret_5d"]
    atr_pct = d["atr_pct"] or 1.5
    sma20, sma50, sma100, sma200 = d["sma20"], d["sma50"], d["sma100"], d["sma200"]
    entry_px = d["entry_px"]

    # 1. VaR-style shock: one-day move beyond 2.5× normal range
    if ret_1d <= -2.5 * atr_pct or ret_1d <= -7:
        return ("VaR LIMIT BREACHED — forced de-risking flow", "#ef4444")

    # 2. CTA de-grossing: below 20/50/100 SMA stack with momentum bleed
    below = sum(1 for m in (sma20, sma50, sma100) if m and price < m)
    if below == 3 and ret_5d < -4:
        return ("CTA DE-GROSSING — trend models flipping short", "#ef4444")

    # 3. Illiquidity trap: violent move vs its own normal range
    if abs(ret_1d) >= 2.0 * atr_pct and abs(ret_1d) >= 4:
        return ("ILLIQUIDITY TRAP — thin book, violent tape", "#f97316")

    # 4. Spot Up / Vol Up anomaly: stock rallying while VIX rises
    if vix_up and ret_1d >= 1.5:
        return ("SPOT UP / VOL UP — hedged rally, tactical warning", "#f59e0b")

    # 5. 200-SMA lost (structure break, not yet capitulation)
    if sma200 and price < sma200 and ret_5d > -4:
        return ("200-SMA LOST — long-term structure broken", "#f97316")

    # 6. Limit order zone: within ±1.5% of designated entry SMA
    if entry_px and abs(price / entry_px - 1) * 100 <= 1.5:
        return (f"LIMIT ORDER TRIGGERED @ {d['entry_note']}", "#10b981")

    # 7. Kill zone: 1.5–5% below entry level → accumulation window
    if entry_px and price < entry_px and (entry_px / price - 1) * 100 <= 5:
        return ("KILL ZONE — accumulate with limits", "#06b6d4")

    # 8. Extended: >12% above entry level → chase risk
    if entry_px and (price / entry_px - 1) * 100 >= 12:
        return ("EXTENDED — no chase, wait for flush", "#f59e0b")

    return ("SAFE / STRUCTURAL MONOPOLY", "#10b981")


def fetch_raven_dashboard() -> pd.DataFrame:
    """
    Build the mandatory 6-column BLACK RAVEN dashboard table for the
    61-stock master watchlist:
      Ticker | Company | Tier | Hardware Sector | Optimal Entry | BLACK RAVEN
    All prices computed from ~1y of daily bars, fetched in parallel.
    """
    from src.data.price_fetcher import fetch_history_robust
    from concurrent.futures import ThreadPoolExecutor

    start = (datetime.now() - timedelta(days=330)).strftime("%Y-%m-%d")

    # Market-level Spot/Vol context (VIX day change)
    vix_up = False
    try:
        vix = fetch_history_robust("^VIX", (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d"))
        if vix is not None and len(vix) >= 2:
            vix_up = float(vix.iloc[-1]) > float(vix.iloc[-2]) * 1.03
    except Exception:
        pass

    def _one(item):
        ticker, meta = item
        try:
            s = fetch_history_robust(ticker, start)
            if s is None or s.empty or len(s) < 30:
                return None
            s = s.dropna().sort_index()
            price = float(s.iloc[-1])

            def _sma(n):
                return float(s.tail(n).mean()) if len(s) >= n else None

            sma20, sma50, sma100, sma200 = _sma(20), _sma(50), _sma(100), _sma(200)
            daily = s.pct_change().dropna()
            atr_pct = round(float(daily.tail(20).abs().mean()) * 100, 2) if len(daily) >= 20 else None

            entry_map = {"sma50": sma50, "sma100": sma100, "sma200": sma200}
            entry_px = entry_map.get(meta["entry"], sma50 if meta["entry"] == "special" else None)

            d = {
                "price": price,
                "ret_1d": round((price / float(s.iloc[-2]) - 1) * 100, 2) if len(s) >= 2 else 0.0,
                "ret_5d": round((price / float(s.iloc[-6]) - 1) * 100, 2) if len(s) >= 6 else 0.0,
                "atr_pct": atr_pct,
                "sma20": sma20, "sma50": sma50, "sma100": sma100, "sma200": sma200,
                "entry_px": entry_px, "entry_note": meta["entry_note"],
            }

            if "raven_override" in meta:
                # permanent risk-profile tag mandated by the protocol (e.g. AIP)
                alert, color = meta["raven_override"]
            elif meta["tier"] == 4:
                alert, color = (f"DANGER ZONE — {meta['entry_note'].upper()}", "#ef4444")
            else:
                alert, color = _raven_alert(d, vix_up)

            dist = round((price / entry_px - 1) * 100, 1) if entry_px else None
            return {
                "Ticker":      ticker,
                "Company":     meta["name"],
                "Tier":        meta["tier"],
                "Sector":      meta["sector"],
                "Entry_Rule":  meta["entry_note"],
                "Entry_Price": round(entry_px, 2) if entry_px else None,
                "Price":       round(price, 2),
                "Dist_Entry%": dist,
                "Ret_1d%":     d["ret_1d"],
                "RAVEN":       alert,
                "RavenColor":  color,
            }
        except Exception:
            return None

    rows = []
    with ThreadPoolExecutor(max_workers=16) as ex:
        for r in ex.map(_one, MASTER_WATCHLIST.items()):
            if r is not None:
                rows.append(r)

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["Tier", "Dist_Entry%"], ascending=[True, True], na_position="last")
    return df


# ── AUTOMATED ENTRY MATRIX — absolute execution logic gates ───────────────────

def _entry_matrix_gates(tier: int, price: float, sma50: float,
                        sma100: float | None, sma200: float | None) -> tuple[float, str, str]:
    """
    Black Raven Protocol v1.0 — Automated Entry Matrix logic gates.
    Returns (dist_50_pct, zone_status, execution_target).
    """
    dist_50 = (price - sma50) / sma50 * 100.0

    if dist_50 >= 0.0:                       # GATE 1 — ELEVATED ZONE
        return dist_50, "Elevated", "Hold / No Order"

    if dist_50 >= -5.0:                      # GATE 2 — KILL ZONE (standard ambush)
        return dist_50, "Kill Zone", f"${sma50:,.2f}"

    # GATE 3 — DEEP VALUE (the flush)
    if tier == 1:
        tgt = f"${sma100:,.2f}" if sma100 else "100SMA n/a"
    else:                                    # Tier 2 or 3
        tgt = f"${sma200:,.2f}" if sma200 else "200SMA n/a"
    return dist_50, "Deep Value", tgt


def fetch_entry_matrix() -> pd.DataFrame:
    """
    Run the Automated Entry Matrix across Tiers 1-3 of the master watchlist.
    Output columns match the protocol directive exactly:
      Ticker | Tier | Current Price | Dist. 50SMA (%) | Zone Status | Execution Target
    """
    from src.data.price_fetcher import fetch_history_robust
    from concurrent.futures import ThreadPoolExecutor

    start = (datetime.now() - timedelta(days=330)).strftime("%Y-%m-%d")
    universe = [(t, m) for t, m in MASTER_WATCHLIST.items() if m["tier"] in (1, 2, 3)]

    def _one(item):
        ticker, meta = item
        try:
            s = fetch_history_robust(ticker, start)
            if s is None or s.empty or len(s) < 50:
                return None
            s = s.dropna().sort_index()
            price  = float(s.iloc[-1])
            sma50  = float(s.tail(50).mean())
            sma100 = float(s.tail(100).mean()) if len(s) >= 100 else None
            sma200 = float(s.tail(200).mean()) if len(s) >= 200 else None
            dist, zone, target = _entry_matrix_gates(meta["tier"], price, sma50, sma100, sma200)
            return {
                "Ticker":           ticker,
                "Tier":             meta["tier"],
                "Current Price":    round(price, 2),
                "Dist. 50SMA (%)":  round(dist, 2),
                "Zone Status":      zone,
                "Execution Target": target,
            }
        except Exception:
            return None

    rows = []
    with ThreadPoolExecutor(max_workers=16) as ex:
        for r in ex.map(_one, universe):
            if r is not None:
                rows.append(r)

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["Tier", "Dist. 50SMA (%)"]).reset_index(drop=True)
    return df


# ── DATA INTEGRITY & AUDIT PROTOCOL ───────────────────────────────────────────

_ZONE_RULES = [
    (lambda d: d >= 0.0,              "Elevated"),
    (lambda d: -5.0 <= d < 0.0,       "Kill Zone"),
    (lambda d: d < -5.0,              "Deep Value"),
]


def audit_entry_matrix(df: pd.DataFrame | None = None) -> tuple[pd.DataFrame, list[dict]]:
    """
    Chief Data Validation Architect routine. Independently recomputes every
    Dist_SMA from raw price feeds, cross-references the zone logic gates,
    validates execution-target/tier alignment, and screens for bad ticks.

    Returns (validated_df, correction_log). Any discrepancy is OVERRIDDEN
    with the mathematically correct value and recorded in the log.
    """
    from src.data.price_fetcher import fetch_history_robust
    from concurrent.futures import ThreadPoolExecutor

    if df is None:
        df = fetch_entry_matrix()
    if df.empty:
        return df, [{"ticker": "—", "check": "FEED", "detail": "empty matrix — no data ingested"}]

    start = (datetime.now() - timedelta(days=330)).strftime("%Y-%m-%d")

    def _truth(ticker: str):
        """Independent recomputation straight from the raw series."""
        try:
            s = fetch_history_robust(ticker, start)
            if s is None or s.empty or len(s) < 50:
                return ticker, None
            s = s.dropna().sort_index()
            px = float(s.iloc[-1])
            return ticker, {
                "price":  px,
                "sma50":  float(s.tail(50).mean()),
                "sma100": float(s.tail(100).mean()) if len(s) >= 100 else None,
                "sma200": float(s.tail(200).mean()) if len(s) >= 200 else None,
                "ret_1d": (px / float(s.iloc[-2]) - 1) * 100 if len(s) >= 2 else 0.0,
            }
        except Exception:
            return ticker, None

    truth: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=16) as ex:
        for tk, t in ex.map(_truth, df["Ticker"].tolist()):
            if t:
                truth[tk] = t

    log: list[dict] = []
    rows = []

    for _, r in df.iterrows():
        tk   = r["Ticker"]
        tier = int(r["Tier"])
        row  = dict(r)
        t    = truth.get(tk)

        if t is None:
            log.append({"ticker": tk, "check": "FEED",
                        "detail": "raw series unavailable — row held, execution suspended"})
            row["Zone Status"] = "DATA ANOMALY"
            row["Execution Target"] = "EXECUTION SUSPENDED"
            rows.append(row)
            continue

        # ── CHECK 1: mathematical verification of Dist_50 ─────────────────────
        dist_true = round((t["price"] - t["sma50"]) / t["sma50"] * 100.0, 2)
        if abs(float(r["Dist. 50SMA (%)"]) - dist_true) > 0.01:
            log.append({"ticker": tk, "check": "MATH",
                        "detail": f"Dist_50 {r['Dist. 50SMA (%)']:+.2f}% → recomputed {dist_true:+.2f}% (OVERRIDDEN)"})
            row["Dist. 50SMA (%)"] = dist_true
        if abs(float(r["Current Price"]) - round(t["price"], 2)) > 0.01:
            log.append({"ticker": tk, "check": "FEED",
                        "detail": f"price ${r['Current Price']:,.2f} → ${t['price']:,.2f} (OVERRIDDEN)"})
            row["Current Price"] = round(t["price"], 2)

        # ── CHECK 4: anomaly detection (fat finger / bad tick) ────────────────
        if tier in (1, 2) and t["ret_1d"] <= -20.0:
            log.append({"ticker": tk, "check": "ANOMALY",
                        "detail": f"1-day move {t['ret_1d']:+.1f}% on Tier {tier} with no Grade A/B catalyst — EXECUTION SUSPENDED"})
            row["Zone Status"] = "DATA ANOMALY"
            row["Execution Target"] = "EXECUTION SUSPENDED"
            rows.append(row)
            continue

        # ── CHECK 2: logic gate cross-reference ──────────────────────────────
        zone_true = next(label for pred, label in _ZONE_RULES if pred(dist_true))
        if r["Zone Status"] != zone_true:
            log.append({"ticker": tk, "check": "GATE",
                        "detail": f"zone '{r['Zone Status']}' contradicts Dist_50 {dist_true:+.2f}% → '{zone_true}' (OVERRIDDEN)"})
            row["Zone Status"] = zone_true

        # ── CHECK 3: execution-target / tier alignment ───────────────────────
        if zone_true == "Elevated":
            tgt_true = "Hold / No Order"
        elif zone_true == "Kill Zone":
            tgt_true = f"${t['sma50']:,.2f}"
        else:
            ma = t["sma100"] if tier == 1 else t["sma200"]
            tgt_true = f"${ma:,.2f}" if ma else ("100SMA n/a" if tier == 1 else "200SMA n/a")
        if str(r["Execution Target"]) != tgt_true:
            log.append({"ticker": tk, "check": "TARGET",
                        "detail": f"target '{r['Execution Target']}' → '{tgt_true}' "
                                  f"(T{tier} {zone_true} must target "
                                  f"{'50SMA' if zone_true=='Kill Zone' else ('100SMA' if tier==1 else '200SMA') if zone_true=='Deep Value' else 'no order'}) (OVERRIDDEN)"})
            row["Execution Target"] = tgt_true

        rows.append(row)

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["Tier", "Dist. 50SMA (%)"]).reset_index(drop=True)
    return out, log
