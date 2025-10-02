# === PATH: utils.py ===
import streamlit as st

DEFAULT_STATE = {
    "match": {},
    "sets": {i: {} for i in range(1, 6)},
    "context": {},
    "ocr": {"raw_text": "", "images": []},
}

def ensure_session():
    """Inizializza st.session_state con le chiavi minime."""
    for k, v in DEFAULT_STATE.items():
        if k not in st.session_state:
            # deepcopy light
            st.session_state[k] = v if not isinstance(v, dict) else {kk: (vv.copy() if isinstance(vv, dict) else vv) for kk, vv in v.items()}

def reset_all():
    """Azzera tutto lo stato dell'app."""
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    ensure_session()
