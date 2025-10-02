import streamlit as st
from utils import ensure_session, reset_all, parse_image_to_text, parse_stats_from_text

ensure_session()
st.title("🖼️ BY COURT · OCR / Incolla")
if st.button("🔄 Reset TOTALE", use_container_width=True):
    reset_all(); st.success("Azzerato."); st.stop()

st.caption("Se OCR non disponibile nel cloud, incolla sotto il testo estratto dal tuo screenshot.")

c1, c2 = st.columns(2)
with c1:
    upA = st.file_uploader("Immagine BY-COURT · Giocatore A", type=["png","jpg","jpeg"], key="byc_A")
    if upA:
        try:
            from PIL import Image
            img = Image.open(upA)
            txt, ok = parse_image_to_text(img)
            st.text_area("Testo OCR (A)", value=(txt if ok else ""), height=180, key="byc_txt_A_ocr")
            if not ok: st.warning("OCR non disponibile. Usa la sezione 'Incolla testo' sotto.")
        except Exception:
            st.warning("Anteprima ok. OCR non disponibile qui.")
with c2:
    upB = st.file_uploader("Immagine BY-COURT · Giocatore B", type=["png","jpg","jpeg"], key="byc_B")
    if upB:
        try:
            from PIL import Image
            img = Image.open(upB)
            txt, ok = parse_image_to_text(img)
            st.text_area("Testo OCR (B)", value=(txt if ok else ""), height=180, key="byc_txt_B_ocr")
            if not ok: st.warning("OCR non disponibile. Usa 'Incolla testo'.")
        except Exception:
            st.warning("Anteprima ok. OCR non disponibile qui.")

st.markdown("---")
st.subheader("✂️ Incolla BY-COURT")
txtA = st.text_area("Testo grezzo · Giocatore A", height=160, key="byc_txt_A")
txtB = st.text_area("Testo grezzo · Giocatore B", height=160, key="byc_txt_B")

if st.button("📥 Leggi (campi utili)", use_container_width=True):
    pa = parse_stats_from_text(txtA or "")
    pb = parse_stats_from_text(txtB or "")
    st.session_state.bycourt["A"] = pa["A"]
    st.session_state.bycourt["B"] = pb["B"]
    st.success("BY-COURT aggiornato ✅")
    st.json(st.session_state.bycourt)
