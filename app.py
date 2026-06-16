"""
DIAGNOSTIC VERSION — find what crashes on Streamlit Cloud
"""
import sys, os, traceback

results = []

def check(label, fn):
    try:
        fn()
        results.append(("✅", label, ""))
    except Exception as e:
        results.append(("❌", label, traceback.format_exc()))

# Step 1: basic stdlib
check("sys/os/datetime", lambda: __import__("datetime"))
check("pandas", lambda: __import__("pandas"))
check("numpy", lambda: __import__("numpy"))
check("plotly", lambda: __import__("plotly"))
check("requests", lambda: __import__("requests"))
check("dotenv", lambda: __import__("dotenv"))
check("yfinance", lambda: __import__("yfinance"))
check("fredapi", lambda: __import__("fredapi"))
check("anthropic", lambda: __import__("anthropic"))
check("bs4", lambda: __import__("bs4"))
check("lxml", lambda: __import__("lxml"))

# Step 2: src modules
sys.path.insert(0, os.path.dirname(__file__))
check("src.data.price_fetcher", lambda: __import__("src.data.price_fetcher"))
check("src.data.market_data",   lambda: __import__("src.data.market_data"))
check("src.data.macro_data",    lambda: __import__("src.data.macro_data"))
check("src.data.black_raven",   lambda: __import__("src.data.black_raven"))
check("src.data.cta_proxy",     lambda: __import__("src.data.cta_proxy"))
check("src.data.smart_money",   lambda: __import__("src.data.smart_money"))
check("src.data.ai_engine",     lambda: __import__("src.data.ai_engine"))
check("src.utils.scoring",      lambda: __import__("src.utils.scoring"))
check("src.utils.alerts",       lambda: __import__("src.utils.alerts"))
check("src.components.charts",  lambda: __import__("src.components.charts"))

# Now render with Streamlit
import streamlit as st

st.set_page_config(page_title="Diag", page_icon="🔍", layout="wide")
st.title("🔍 Diagnostic Report")
st.write(f"Python: `{sys.version}`")
st.write(f"Platform: `{sys.platform}`")

any_fail = False
for icon, label, tb in results:
    if icon == "✅":
        st.success(f"{icon} `{label}`")
    else:
        any_fail = True
        st.error(f"{icon} **{label}** FAILED")
        st.code(tb, language="python")

if not any_fail:
    st.balloons()
    st.success("**All imports OK!** The crash must be in app logic, not imports.")
