import streamlit as st
from app_utils import ensure_session, reset_all, app_header

st.set_page_config(page_title="Prediction Tennis Live", page_icon="🎾", layout="centered")

ensure_session()
app_header("Home")

st.success("Benvenuto! Usa le pagine a sinistra. Compila **Match Generale** e i **Set** che hai. "
           "Aggiungi (extra) il **BY-COURT** con screenshot o testo. Alla fine vai su **Analisi & Verdetti**.")

c1,c2 = st.columns(2)
with c1:
    if st.button("🔄 Reset TOTALE", type="secondary"):
        reset_all()
        st.experimental_rerun()
with c2:
    st.write("")

st.caption("Suggerimento: i campi accettano **percentuali 0–100** o `x`/`-` per N/D. Il parser da testo è libero e tollerante.")
