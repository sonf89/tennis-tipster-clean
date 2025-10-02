import streamlit as st
from utils import ensure_session, reset_all, render_stats_editor

ensure_session()
st.title("🟣 Set 4")
if st.button("🔄 Reset TOTALE", use_container_width=True):
    reset_all(); st.success("Azzerato."); st.stop()

render_stats_editor("set4", "Set 4")
