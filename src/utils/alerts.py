"""
Price alert engine + webhook dispatcher.
Sends alerts to Make.com webhook → Discord.
"""
from __future__ import annotations

import os
import json
import requests
import pandas as pd
from datetime import datetime
from dataclasses import dataclass, asdict


@dataclass
class PriceAlert:
    ticker: str
    condition: str        # "above" | "below"
    threshold: float
    note: str = ""
    triggered: bool = False
    triggered_at: str = ""


def check_alerts(
    alerts: list[PriceAlert],
    current_prices: pd.DataFrame,
) -> list[PriceAlert]:
    """Check all alerts against current prices. Returns list of newly triggered alerts."""
    if current_prices.empty:
        return []
    price_map = dict(zip(current_prices["Ticker"], current_prices["Price"]))
    triggered = []
    for alert in alerts:
        if alert.triggered:
            continue
        price = price_map.get(alert.ticker.upper())
        if price is None:
            continue
        hit = (alert.condition == "above" and price >= alert.threshold) or \
              (alert.condition == "below" and price <= alert.threshold)
        if hit:
            alert.triggered = True
            alert.triggered_at = datetime.now().isoformat()
            triggered.append(alert)
    return triggered


def send_webhook(alert: PriceAlert, current_price: float) -> bool:
    """
    Fire a Make.com webhook with the alert payload.
    Make.com scenario should: receive JSON → format → post to Discord.
    """
    url = os.getenv("MAKE_WEBHOOK_URL", "")
    discord_url = os.getenv("DISCORD_WEBHOOK_URL", "")

    payload = {
        "event": "price_alert",
        "ticker": alert.ticker,
        "condition": alert.condition,
        "threshold": alert.threshold,
        "current_price": current_price,
        "note": alert.note,
        "triggered_at": alert.triggered_at,
        "dashboard": "MacroDashboard",
    }

    success = False

    # ── Try Make.com first ────────────────────────────────────────────────────
    if url and url != "https://hook.make.com/your_webhook_id_here":
        try:
            r = requests.post(url, json=payload, timeout=5)
            r.raise_for_status()
            success = True
        except Exception as e:
            print(f"[WARN] Make.com webhook failed: {e}")

    # ── Fallback: post directly to Discord ────────────────────────────────────
    if discord_url and discord_url != "https://discord.com/api/webhooks/your_webhook_here":
        direction = "🚀" if alert.condition == "above" else "🔻"
        msg = {
            "embeds": [{
                "title": f"{direction} ALERT: {alert.ticker} {alert.condition.upper()} ${alert.threshold}",
                "description": (
                    f"**Current Price:** ${current_price:.2f}\n"
                    f"**Threshold:** ${alert.threshold}\n"
                    f"**Note:** {alert.note or 'N/A'}\n"
                    f"**Time:** {alert.triggered_at}"
                ),
                "color": 0xe74c3c if alert.condition == "below" else 0x2ecc71,
            }]
        }
        try:
            r = requests.post(discord_url, json=msg, timeout=5)
            r.raise_for_status()
            success = True
        except Exception as e:
            print(f"[WARN] Discord direct webhook failed: {e}")

    return success


def send_daily_summary(
    macro_score: int,
    interpretation: dict,
    top_movers: pd.DataFrame,
    vix_level: float,
) -> bool:
    """Send a daily macro summary to Discord via Make.com."""
    url = os.getenv("MAKE_WEBHOOK_URL", "")
    discord_url = os.getenv("DISCORD_WEBHOOK_URL", "")

    movers_text = ""
    if not top_movers.empty:
        for _, row in top_movers.head(5).iterrows():
            chg = row.get("Change %", 0)
            arrow = "▲" if chg >= 0 else "▼"
            movers_text += f"• **{row['Ticker']}** {arrow}{abs(chg):.2f}%\n"

    payload = {
        "event": "daily_summary",
        "macro_score": macro_score,
        "macro_label": interpretation["label"],
        "vix": vix_level,
        "top_movers": movers_text,
        "timestamp": datetime.now().isoformat(),
    }

    if url and url != "https://hook.make.com/your_webhook_id_here":
        try:
            r = requests.post(url, json=payload, timeout=5)
            r.raise_for_status()
            return True
        except Exception as e:
            print(f"[WARN] Daily summary webhook failed: {e}")

    if discord_url and discord_url != "https://discord.com/api/webhooks/your_webhook_here":
        embed = {
            "embeds": [{
                "title": f"📊 Daily Macro Summary — {datetime.now().strftime('%Y-%m-%d')}",
                "description": (
                    f"**Macro Score:** {macro_score}/70 {interpretation['emoji']}\n"
                    f"**Regime:** {interpretation['label']}\n"
                    f"**VIX:** {vix_level:.1f}\n\n"
                    f"**Top Movers:**\n{movers_text}"
                ),
                "color": int(interpretation["color"].replace("#", ""), 16),
            }]
        }
        try:
            r = requests.post(discord_url, json=embed, timeout=5)
            r.raise_for_status()
            return True
        except Exception as e:
            print(f"[WARN] Discord daily summary failed: {e}")

    return False
