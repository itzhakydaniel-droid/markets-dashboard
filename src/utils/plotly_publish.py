"""
Plotly Chart Studio integration — publish dashboard charts to the
user's Plotly account for permanent shareable / embeddable URLs.

Credentials (from https://chart-studio.plotly.com/settings/api):
  PLOTLY_USERNAME  — your Plotly username
  PLOTLY_API_KEY   — your Chart Studio API key
Set them in .env (local) or Streamlit Cloud secrets.
"""
from __future__ import annotations

import os


def is_configured() -> bool:
    u = os.getenv("PLOTLY_USERNAME", "")
    k = os.getenv("PLOTLY_API_KEY", "")
    return bool(u) and bool(k) and "your_plotly" not in (u + k).lower()


def publish_figure(fig, filename: str, public: bool = True) -> str:
    """
    Push a plotly figure to the user's Chart Studio account.
    Returns the permanent chart URL. Raises on failure.
    """
    import chart_studio
    import chart_studio.plotly as py

    chart_studio.tools.set_credentials_file(
        username=os.getenv("PLOTLY_USERNAME", ""),
        api_key=os.getenv("PLOTLY_API_KEY", ""),
    )
    url = py.plot(
        fig, filename=filename, auto_open=False,
        sharing="public" if public else "private",
    )
    return str(url)
