# app_utils.py — core dell’app (sessione, UI, parsing, regole, verdetti)

import re
from copy import deepcopy
from typing import Dict, Optional, Tuple

import streamlit as st

# -----------------------
# SESSIONE & SCHEMI BASE
# -----------------------
STAT_KEYS = [
    "clutch",           # Pressure Points %
    "bp_won",           # Break Points Won %
    "bp_saved",         # Break Points Saved %
    "spw1",             # 1st Serve Points Won %
    "spw2",             # 2nd Serve Points Won %
    "rpw1",             # 1st Return Points Won %
    "rpw2"              # 2nd Return Points Won %
]

BYC_KEYS = [
    "second_deuce", "second_ad",
    "br_saved_deuce", "br_saved_ad",
    "ret_rating_left", "ret_rating_right",
    "br_won_left", "br_won_right",
    "press_left", "press_right"
]

def _blank_stats():
    return {k: None for k in STAT_KEYS}

def _blank_bycourt():
    return {k: None for k in BYC_KEYS}

def _blank_match_block():
    return {
        "meta": {
            "playerA": "",
            "playerB": "",
            "format": "BO3",
            "set_focus": 1,
            "score_str": "",
            "game_str": "",
            "server": "A",
        },
        "A": _blank_stats(),
        "B": _blank_stats(),
    }

def ensure_session():
    if "general" not in st.session_state:
        st.session_state.general = _blank_match_block()
    if "sets" not in st.session_state:
        st.session_state.sets = {i: {"A": _blank_stats(), "B": _blank_stats()} for i in range(1, 6)}
    if "context" not in st.session_state:
        st.session_state.context = {
            "playerA": "", "playerB": "",
            "format": "BO3", "set_focus": 1,
            "score_str": "", "game_str": "", "server": "A"
        }
    if "bycourt" not in st.session_state:
        st.session_state.bycourt = {"A": _blank_bycourt(), "B": _blank_bycourt()}

def reset_all():
    st.session_state.clear()
    ensure_session()

# -----------------------
# UTILI UI & PARSING
# -----------------------
def app_header(title: str):
    st.markdown(f"## {title}")

def _norm_num(s: str) -> Optional[float]:
    """Accetta 0–100, 'x', '-' -> None."""
    if s is None:
        return None
    s = str(s).strip()
    if s == "" or s.lower() in {"x", "-", "n/d", "nd"}:
        return None
    # prendi solo la parte numerica iniziale (permite '67% (14/20)')
    m = re.search(r"-?\d+(\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except:
        return None

def _num_input(label: str, key: str, value: Optional[float]):
    ph = "0–100 o x"
    v = st.text_input(label, value="" if value is None else str(value), key=key, placeholder=ph)
    return _norm_num(v)

def _num_input_rr(label: str, key: str, value: Optional[float]):
    ph = "numero o x"
    v = st.text_input(label, value="" if value is None else str(value), key=key, placeholder=ph)
    return _norm_num(v)

# -----------------------
# FORM: MATCH/SET
# -----------------------
def render_match_or_set_form(state_block: Dict, title: str):
    app_header(title)

    is_general = "meta" in state_block

    if is_general:
        st.subheader("Meta")
        c1, c2 = st.columns(2)
        with c1:
            state_block["meta"]["playerA"] = st.text_input("Nome Giocatore A", state_block["meta"]["playerA"])
        with c2:
            state_block["meta"]["playerB"] = st.text_input("Nome Giocatore B", state_block["meta"]["playerB"])

        c3, c4, c5 = st.columns(3)
        with c3:
            state_block["meta"]["format"] = st.selectbox("Formato", ["BO3", "BO5"], index=0 if state_block["meta"]["format"]!="BO5" else 1)
        with c4:
            state_block["meta"]["set_focus"] = st.number_input("Set in focus (1–5)", 1, 5, value=int(state_block["meta"]["set_focus"]))
        with c5:
            state_block["meta"]["server"] = st.selectbox("Chi serve ora?", ["A","B"], index=0 if state_block["meta"]["server"]!="B" else 1)

        state_block["meta"]["score_str"] = st.text_input("Score set (es. '7-6, 2-2')", state_block["meta"]["score_str"])
        state_block["meta"]["game_str"]  = st.text_input("Game corrente (es. '40-30')", state_block["meta"]["game_str"])

    st.subheader("Statistiche (0–100 oppure x)")
    for side in ("A","B"):
        st.markdown(f"**Giocatore {side}**")
        for k,label in [
            ("clutch","Pressure Points (Clutch) %"),
            ("bp_won","Break Points Won %"),
            ("bp_saved","Break Points Saved %"),
            ("spw1","1ª Serve Points Won %"),
            ("spw2","2ª Serve Points Won %"),
            ("rpw1","1ª Return Points Won %"),
            ("rpw2","2ª Return Points Won %"),
        ]:
            val = state_block[side][k]
            newv = _num_input(label, key=f"{title}_{side}_{k}", value=val)
            state_block[side][k] = newv

    st.success("Dati salvati in sessione.")

# -----------------------
# FORM: CONTESTO LIVE
# -----------------------
def render_context_page():
    app_header("Contesto live")
    c = st.session_state.context
    c["playerA"] = st.text_input("Nome Giocatore A", c["playerA"])
    c["playerB"] = st.text_input("Nome Giocatore B", c["playerB"])
    c["format"]  = st.selectbox("Formato", ["BO3","BO5"], index=0 if c["format"]!="BO5" else 1)
    c["set_focus"] = st.number_input("Set in focus (1–5)", 1, 5, value=int(c["set_focus"]))
    c["score_str"] = st.text_input("Score set (es. '7-6, 2-2')", c["score_str"])
    c["game_str"]  = st.text_input("Game corrente (es. '40-30')", c["game_str"])
    c["server"]    = st.selectbox("Chi serve ora?", ["A","B"], index=0 if c["server"]!="B" else 1)
    st.info("Il contesto non sovrascrive i dati, ma aiuta l'analisi finale.")

# -----------------------
# BY-COURT: OCR / INCOLLA
# -----------------------
def _parse_bycourt_free(text: str) -> Dict[str, Optional[float]]:
    """
    Parser tollerante per blocchi BY-COURT: prende numeri rilevanti ovunque compaiano.
    Accetta 'x'/'-' come N/D (None). Percentuali vengono “spelate” in numeri.
    """
    text = (text or "").replace(",", ".")
    # pattern: cerca prima coppie "LEFT/RIGHT" riga dopo riga
    # fallback: estrai in ordine numeri “sensati” quando appaiono parole chiave.
    out = {k: None for k in BYC_KEYS}

    # mappa chiavi -> etichette plausibili
    lbl = {
        "second_deuce":   ["2nd Serve Points Won", "Second Serve Points Won"],
        "second_ad":      ["2nd Serve Points Won", "Second Serve Points Won"],
        "br_saved_deuce": ["Break Points Saved"],
        "br_saved_ad":    ["Break Points Saved"],
        "ret_rating_left":["Return Rating"],
        "ret_rating_right":["Return Rating"],
        "br_won_left":    ["Break Points Won"],
        "br_won_right":   ["Break Points Won"],
        "press_left":     ["Pressure Points"],
        "press_right":    ["Pressure Points"],
    }

    # funzione: prendi prima occorrenza “sensata” dopo label, lato LEFT/RIGHT
    def find_after(label_words, side):
        # side "LEFT" o "RIGHT"
        patt = r"(?is)" + r"|".join([re.escape(w) for w in label_words]) + r".*?\b" + side + r"\b.*?([\-\dxX]+|\d+(\.\d+)?)"
        m = re.search(patt, text)
        if m:
            return _norm_num(m.group(1))
        return None

    # rating risposta (numeri, non %)
    out["ret_rating_left"]  = find_after(lbl["ret_rating_left"], "LEFT")
    out["ret_rating_right"] = find_after(lbl["ret_rating_right"], "RIGHT")

    # pressure points (%)
    out["press_left"]  = find_after(lbl["press_left"], "LEFT")
    out["press_right"] = find_after(lbl["press_right"], "RIGHT")

    # break salvati e vinti (%)
    out["br_saved_deuce"] = find_after(lbl["br_saved_deuce"], "LEFT")
    out["br_saved_ad"]    = find_after(lbl["br_saved_ad"], "RIGHT")
    out["br_won_left"]    = find_after(lbl["br_won_left"], "LEFT")
    out["br_won_right"]   = find_after(lbl["br_won_right"], "RIGHT")

    # seconda vinta (%)
    out["second_deuce"] = find_after(lbl["second_deuce"], "LEFT")
    out["second_ad"]    = find_after(lbl["second_ad"], "RIGHT")

    return out

def render_bycourt_page():
    app_header("+ OCR/Incolla")
    if st.button("🔄 Reset TOTALE"):
        reset_all()
        st.experimental_rerun()

    st.write("Compila **solo** ciò che hai. % = 0–100, Return Rating = numero. Usa `x` per N/D.")

    st.markdown("### Giocatore A · Giocatore B")
    for side in ("A","B"):
        st.markdown(f"**Giocatore {side}**")
        bc = st.session_state.bycourt[side]
        bc["second_deuce"]   = _num_input("2ª vinta da DEUCE (destra) %",   f"bc_{side}_second_deuce", bc["second_deuce"])
        bc["second_ad"]      = _num_input("2ª vinta da AD (sinistra) %",    f"bc_{side}_second_ad", bc["second_ad"])
        bc["br_saved_deuce"] = _num_input("BR salvate da DEUCE %",          f"bc_{side}_br_saved_deuce", bc["br_saved_deuce"])
        bc["br_saved_ad"]    = _num_input("BR salvate da AD %",             f"bc_{side}_br_saved_ad", bc["br_saved_ad"])
        bc["ret_rating_left"]= _num_input_rr("Return rating da AD (sinistra)", f"bc_{side}_retL", bc["ret_rating_left"])
        bc["ret_rating_right"]=_num_input_rr("Return rating da DEUCE (destra)",f"bc_{side}_retR", bc["ret_rating_right"])
        bc["br_won_left"]    = _num_input("BR vinte da AD %",               f"bc_{side}_br_won_left", bc["br_won_left"])
        bc["br_won_right"]   = _num_input("BR vinte da DEUCE %",            f"bc_{side}_br_won_right", bc["br_won_right"])
        bc["press_left"]     = _num_input("Pressure points da AD %",        f"bc_{side}_pressL", bc["press_left"])
        bc["press_right"]    = _num_input("Pressure points da DEUCE %",     f"bc_{side}_pressR", bc["press_right"])

    st.markdown("---")
    st.markdown("### Oppure incolla testo grezzo BY-COURT (LEFT/RIGHT)")
    taA = st.text_area("Testo grezzo · A", height=160)
    taB = st.text_area("Testo grezzo · B", height=160)

    if st.button("📥 Leggi testo BY-COURT e unisci"):
        if taA.strip():
            parsA = _parse_bycourt_free(taA)
            st.session_state.bycourt["A"].update({k: parsA.get(k, None) for k in BYC_KEYS})
        if taB.strip():
            parsB = _parse_bycourt_free(taB)
            st.session_state.bycourt["B"].update({k: parsB.get(k, None) for k in BYC_KEYS})
        st.success("BY-COURT letto e unito ai dati.")
        st.json(st.session_state.bycourt)

    st.info("Suggerimenti game/minibreak (da BY-COURT):")
    st.markdown(_bycourt_hints(st.session_state.bycourt))

def _bycourt_hints(bc: Dict) -> str:
    A, B = bc["A"], bc["B"]
    lines = []
    def sec_risk(x):
        if x is None: return None
        if x < 30: return "⚠️ molto fragile (<30%)"
        if x < 40: return "⚠️ fragile (30–40%)"
        if x > 50: return "✅ sicuro (>50%)"
        return "OK"
    if A["second_ad"] is not None:
        lines.append(f"- **A**: 2ª **da SINISTRA (AD)** {A['second_ad']}% → {sec_risk(A['second_ad'])}.")
    if B["second_ad"] is not None:
        lines.append(f"- **B**: 2ª **da SINISTRA (AD)** {B['second_ad']}% → {sec_risk(B['second_ad'])}.")
    if B["ret_rating_left"] and B["ret_rating_left"] > 200:
        lines.append("- **B**: Return rating **da SINISTRA (AD)** >200 → zona break favorita.")
    if A["ret_rating_left"] and A["ret_rating_left"] > 200:
        lines.append("- **A**: Return rating **da SINISTRA (AD)** >200 → zona break favorita.")
    return "\n".join(lines) if lines else "_Inserisci BY-COURT per vedere consigli mirati._"

# -----------------------
# VERDETTO
# -----------------------
WEIGHTS = {
    "clutch": 0.20,
    "bp_won": 0.15,
    "bp_saved": 0.10,
    "spw1": 0.15,
    "spw2": 0.20,
    "rpw1": 0.10,
    "rpw2": 0.10
}

def _score_side(stats: Dict[str, Optional[float]]) -> Tuple[float,int]:
    s = 0.0
    n = 0
    for k,w in WEIGHTS.items():
        v = stats.get(k, None)
        if v is None: 
            continue
        s += (v/100.0) * w
        n += 1
    return s, n

def evaluate_all() -> Dict:
    """Combina Match Generale + media set + BY-COURT per un verdetto semplice."""
    g = st.session_state.general
    sets = st.session_state.sets
    bc = st.session_state.bycourt

    # base: match generale
    sA, nA = _score_side(g["A"])
    sB, nB = _score_side(g["B"])

    # media set disponibili
    totA, totB, c = 0.0, 0.0, 0
    for i in range(1,6):
        sA_i, nA_i = _score_side(sets[i]["A"])
        sB_i, nB_i = _score_side(sets[i]["B"])
        if nA_i+nB_i>0:
            totA += sA_i
            totB += sB_i
            c += 1
    if c>0:
        sA = 0.6*sA + 0.4*(totA/c)
        sB = 0.6*sB + 0.4*(totB/c)

    # by-court boost/punish sulla seconda
    def bc_adj(side):
        s = 0.0
        v_ad = bc[side]["second_ad"]
        v_de = bc[side]["second_deuce"]
        for v in (v_ad, v_de):
            if v is None: 
                continue
            if v < 30: s -= 0.06
            elif v < 40: s -= 0.03
            elif v > 55: s += 0.02
        return s

    sA += bc_adj("A")
    sB += bc_adj("B")

    # normalizza in 0–1
    sA = max(0.0, min(1.0, sA))
    sB = max(0.0, min(1.0, sB))
    if sA + sB == 0:
        pA = pB = 0.5
    else:
        pA = sA / (sA + sB)
        pB = 1 - pA

    fav = "A" if pA>=pB else "B"
    conf = abs(pA-pB)

    return {
        "pA": round(pA*100),
        "pB": round(pB*100),
        "favorite": fav,
        "confidence": round(conf*100),
        "explain": {
            "general_A": round(sA*100,1),
            "general_B": round(sB*100,1),
            "bycourt_used": any(v is not None for v in bc["A"].values()) or any(v is not None for v in bc["B"].values()),
        }
    }

def verdict_card(v: Dict):
    if v["favorite"]=="A":
        st.success(f"**Favorito: Giocatore A** · Probabilità {v['pA']}% · Confidenza {v['confidence']}%")
    else:
        st.success(f"**Favorito: Giocatore B** · Probabilità {v['pB']}% · Confidenza {v['confidence']}%")

    with st.expander("Perché questo verdetto?"):
        st.write("- Ponderazione: clutch, 2ª di servizio, ritorno, break (vinte/salvate).")
        if v["explain"]["bycourt_used"]:
            st.write("- BY-COURT: applicato bonus/malus sulla **2ª** per lato.")
        else:
            st.write("- BY-COURT non inserito: nessun aggiustamento extra.")
        st.json(v)
