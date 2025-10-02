import streamlit as st
from shim import ensure_session, reset_all, app_header

st.set_page_config(page_title="Prediction Tennis Live", page_icon="🎾", layout="centered")

ensure_session()
app_header("Home")

st.success("Benvenuto! Compila **Match Generale** e i **Set**. "
           "Aggiungi (extra) il **BY-COURT**. Poi vai su **Analisi & Verdetti**.")

col1, col2 = st.columns(2)
with col1:
    if st.button("🔄 Reset TOTALE", type="secondary"):
        reset_all()
        st.experimental_rerun()

st.caption("I campi accettano percentuali 0–100 oppure `x`/`-` per N/D. "
           "Il parser testo è tollerante.")
