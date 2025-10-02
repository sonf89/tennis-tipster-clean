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
    st.header("⚙️ Azioni")
    if st.button("🔄 Reset TOT", use_container_width=True):
        reset_all()
        st.success("Tutti i dati sono stati azzerati.")

st.title("🎾 Prediction Tennis Live")
st.markdown("""
Usa le pagine a sinistra:

1) **🏟️ Match Generale** → dati complessivi (o inizio match)   
2) **🟡/🟠/🔴/🟣/🔵 Set 1..5** → dati per set  
3) **🥎 Contesto Live** → formato, set in focus, score, server  
4) **🖼️ BY COURT · OCR/Incolla** → screenshot o testo by-court  
5) **🧠 Analisi & Verdetti** → verdettone combinato

Suggerimento: nelle pagine Match/Set puoi **incollare** il blocco “KEY STATS”.
Il parser riconosce le 8 metriche chiave (EN/IT) e compila le caselle.
""")
