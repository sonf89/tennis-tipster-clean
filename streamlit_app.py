import streamlit as st
from app_utils import ensure_session, reset_all

st.set_page_config(page_title="Prediction Tennis Live", page_icon="🎾", layout="wide")

ensure_session()

st.title("🎾 Prediction Tennis Live")
st.caption("Home • usa le pagine a sinistra in ordine: 1) Match Generale → 7) Contesto Live → 8) BY-COURT (opz.) → 9) Analisi & Verdetti")

col1, col2 = st.columns(2)
with col1:
    if st.button("🔁 Rerun app"):
        st.experimental_rerun()
with col2:
    if st.button("🧹 Reset TOTALE (tutte le pagine)"):
        reset_all()
        st.success("Fatto. Tutto azzerato.")
