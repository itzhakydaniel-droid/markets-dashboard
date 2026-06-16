import streamlit as st
st.set_page_config(page_title="Test", page_icon="✅")
st.title("✅ Streamlit is working!")
import sys
st.write(f"Python: `{sys.version}`")
st.write(f"Streamlit: `{st.__version__}`")
