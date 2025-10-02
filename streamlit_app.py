import streamlit as st
from utils import ensure_session, reset_all

st.set_page_config(
    page_title="Prediction Tennis Live",
    page_icon="🎾",
    layout="centered",
    initial_sidebar_state="collapsed",
)

ensure_session()

with st.sidebar:
    st.header("⚙️ Utility")
    if st.button("🔄 Reset TOTALE", use_container_width=True):
        reset_all()
        st.success("Sessione azzerata.")

st.title("🎾 Prediction Tennis Live")
st.caption("Usa le pagine in alto a sinistra (☰) per inserire i dati. "
           "Ordine consigliato: **Match Generale → Set (1..5) → Contesto Live → BY-COURT → Analisi & Verdetti**.")
st.info("I dati restano in memoria tra le pagine. Usa **Reset TOTALE** per ricominciare.")
