from __future__ import annotations
import re
from typing import Dict, Tuple
import streamlit as st

# ==============
# SESSIONE
# ==============

def ensure_session() -> None:
    """Inizializza la sessione con tutte le strutture necessarie."""
    ss = st.session_state
    ss.setdefault("general", {"A": {}, "B": {}})
    ss.setdefault("sets", {i: {"A": {}, "B": {}} for i in range(1, 6)})
    ss.setdefault("live", {
        "playerA": "", "playerB": "",
        "format": "BO3", "focus_set": 1,
        "score": "", "game": "", "server": "A"
    })
    ss.setdefault("bycourt", {"A": {}, "B": {}})

def reset_all() -> None:
    for k in ("general", "sets", "live", "bycourt"):
        if k in st.session_state:
            del st.session_state[k]
    ensure_session()


# ==============
# NORMALIZZATORI
# ==============

def _to_number_generic(s: str) -> float | None:
    """Gestisce %, (a/b), numeri semplici, '-', '(0/0)', 'x', 'N/D'."""
    if s is None:
        return None
    t = s.strip().replace("—","-").replace("–","-")
    if t.lower() in {"", "x", "n/d", "nd"}:
        return None
    if t in {"-", "- (0/0)"}:
        return 0.0

    m = re.search(r"(\d+(?:\.\d+)?)\s*%", t)
    if m:
        return float(m.group(1))

    m = re.search(r"\((\d+)\s*/\s*(\d+)\)", t)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if b == 0:
            return 0.0
        return round(100.0 * a / b, 2)

    if re.fullmatch(r"\d+(?:\.\d+)?", t):
        return float(t)

    return None

def _clean_pair(a: str, b: str) -> Tuple[float|None, float|None]:
    return _to_number_generic(a), _to_number_generic(b)


# ==============
# PARSER TESTO – MATCH / SET (8 metriche)
# ==============

# Etichette attese e mappate alle nostre chiavi interne
_STAT_KEYS = {
    "Pressure Points":               "clutch",
    "Break Points Won":              "br_won",
    "Break Points Saved":            "br_saved",
    "1st Serve %":                   "first_in",
    "1st Serve Points Won":          "first_won",
    "2nd Serve Points Won":          "second_won",
    "Service Games":                 "srv_games",      # se presente come % games vinti al servizio
    "Service Games Won":             "srv_games",
    "Return Games":                  "ret_games",      # % games di risposta vinti
    "Return Games Won":              "ret_games",
    "Service Games %":               "srv_games",
    "Return Games %":                "ret_games",
}

def parse_stats_from_text(txt: str) -> Dict[str, Dict[str, float]]:
    """
    Legge un blocco 2-colonne (giocatore A/B) come Live-Tennis.eu.
    Ritorna {"A": {..}, "B": {..}} con solo le 8 metriche utili se presenti.
    """
    if not txt or not txt.strip():
        return {"A": {}, "B": {}}

    lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
    outA: Dict[str, float] = {}
    outB: Dict[str, float] = {}

    # Scorri cercando le etichette chiave: dopo l’etichetta ci aspettiamo due righe (A, B)
    i = 0
    while i < len(lines):
        name = lines[i]
        if name in _STAT_KEYS and i + 2 < len(lines):
            a_val, b_val = _clean_pair(lines[i+1], lines[i+2])
            key = _STAT_KEYS[name]
            if a_val is not None: outA[key] = a_val
            if b_val is not None: outB[key] = b_val
            i += 3
        else:
            i += 1

    return {"A": outA, "B": outB}


# ==============
# PARSER BY-COURT – LEFT/RIGHT → AD/DEUCE
# ==============

_BYC_STAT_MAP = {
    "2nd Serve Points Won": "second",     # percentuale
    "Break Points Saved":   "br_saved",   # percentuale
    "Break Points Won":     "br_won",     # percentuale
    "Return Rating":        "ret_rating", # numero
    "Pressure Points":      "press",      # percentuale (facoltativa)
}

def _byc_key(stat_label: str, side: str) -> str | None:
    # LEFT  → AD (sinistra)   …_ad
    # RIGHT → DEUCE (destra)  …_deuce
    tag = _BYC_STAT_MAP.get(stat_label)
    if not tag:
        return None
    if tag in {"ret_rating", "press"}:
        return f"{tag}_{'left' if side=='left' else 'right'}"
    suffix = "ad" if side == "left" else "deuce"
    return f"{tag}_{suffix}"

def parse_bycourt_text(raw_text: str) -> Dict[str, float]:
    if not raw_text or not raw_text.strip():
        return {}
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    out: Dict[str, float] = {}
    headers = {"SERVICE", "RETURN", "POINTS WON", "LEFT", "RIGHT"}
    i = 0
    n = len(lines)
    while i < n:
        name = lines[i]
        if name.upper() in headers:
            i += 1
            continue
        if name in _BYC_STAT_MAP and i+2 < n:
            left, right = _to_number_generic(lines[i+1]), _to_number_generic(lines[i+2])
            k_left  = _byc_key(name, "left")
            k_right = _byc_key(name, "right")
            if k_left  and left  is not None:  out[k_left]  = left
            if k_right and right is not None:  out[k_right] = right
            i += 3
            continue
        i += 1
    return out


# ==============
# OCR (BY-COURT da immagine)
# ==============

def ocr_image_to_text(uploaded_file) -> str:
    from PIL import Image
    import pytesseract
    img = Image.open(uploaded_file).convert("RGB")
    txt = pytesseract.image_to_string(img)
    # pulizia di base
    txt = "\n".join(ln.rstrip() for ln in txt.splitlines())
    return txt


# ==============
# SALVATAGGI
# ==============

def save_general_stats(data: Dict[str, Dict[str, float]]) -> None:
    ensure_session()
    st.session_state["general"]["A"] |= data.get("A", {})
    st.session_state["general"]["B"] |= data.get("B", {})

def save_set_stats(set_no: int, data: Dict[str, Dict[str, float]]) -> None:
    ensure_session()
    st.session_state["sets"][set_no]["A"] |= data.get("A", {})
    st.session_state["sets"][set_no]["B"] |= data.get("B", {})

def merge_weighted_stats() -> Dict[str, Dict[str, float]]:
    """
    Media pesata: 50% Match Generale + 50% media dei set compilati.
    Se non ci sono set → 100% generale.
    """
    ensure_session()
    gen = st.session_state["general"]
    sets = st.session_state["sets"]

    accA: Dict[str, float] = {}
    accB: Dict[str, float] = {}
    count = 0
    for i in range(1, 6):
        if st.session_state["sets"][i]["A"] or st.session_state["sets"][i]["B"]:
            for k, v in st.session_state["sets"][i]["A"].items():
                accA[k] = accA.get(k, 0.0) + v
            for k, v in st.session_state["sets"][i]["B"].items():
                accB[k] = accB.get(k, 0.0) + v
            count += 1

    if count > 0:
        for k in accA:
            accA[k] = accA[k] / count
        for k in accB:
            accB[k] = accB[k] / count
        # blend 50/50
        outA = {}
        outB = {}
        keys = set(gen["A"].keys()) | set(accA.keys())
        for k in keys:
            ga = gen["A"].get(k)
            sa = accA.get(k)
            if ga is not None and sa is not None:
                outA[k] = 0.5 * ga + 0.5 * sa
            elif ga is not None:
                outA[k] = ga
            elif sa is not None:
                outA[k] = sa
        keys = set(gen["B"].keys()) | set(accB.keys())
        for k in keys:
            gb = gen["B"].get(k)
            sb = accB.get(k)
            if gb is not None and sb is not None:
                outB[k] = 0.5 * gb + 0.5 * sb
            elif gb is not None:
                outB[k] = gb
            elif sb is not None:
                outB[k] = sb
        return {"A": outA, "B": outB}
    else:
        return {"A": gen["A"].copy(), "B": gen["B"].copy()}


# ==============
# VERDETTO / SUGGERIMENTI
# ==============

def _score_from_stats(A: Dict[str, float], B: Dict[str, float]) -> Tuple[float,float]:
    """Heuristica semplice ma solida: somma pesata di indicatori chiave."""
    # pesi (regolabili)
    w = dict(
        clutch=1.2, br_won=1.1, br_saved=0.9,
        second_won=1.0, first_won=0.6, first_in=0.4,
        srv_games=1.0, ret_games=1.0
    )
    def s(x: Dict[str, float]) -> float:
        val = 0.0
        for k, ww in w.items():
            if k in x:
                val += ww * x[k]
        return val
    return s(A), s(B)

def _apply_bycourt_modifiers(scoreA: float, scoreB: float,
                             byA: Dict[str,float], byB: Dict[str,float]) -> Tuple[float,float]:
    """Applica bonus/malus da BY-COURT."""
    # vulnerabilità 2^
    for side in ("ad","deuce"):
        if byA.get(f"second_{side}", 100) < 35:
            scoreA -= 6
        if byB.get(f"second_{side}", 100) < 35:
            scoreB -= 6
    # return rating devastante
    if byA.get("ret_rating_left", 0) > 200:  scoreA += 4
    if byA.get("ret_rating_right", 0) > 200: scoreA += 4
    if byB.get("ret_rating_left", 0) > 200:  scoreB += 4
    if byB.get("ret_rating_right", 0) > 200: scoreB += 4
    # pressure by-side
    if byA.get("press_left", 50) > 65:  scoreA += 2
    if byA.get("press_right",50) > 65:  scoreA += 2
    if byB.get("press_left", 50) > 65:  scoreB += 2
    if byB.get("press_right",50) > 65:  scoreB += 2
    return scoreA, scoreB

def verdict_engine() -> Dict[str, any]:
    ensure_session()
    pooled = merge_weighted_stats()
    A, B = pooled["A"], pooled["B"]
    scoreA, scoreB = _score_from_stats(A, B)
    scoreA, scoreB = _apply_bycourt_modifiers(scoreA, scoreB,
                                              st.session_state["bycourt"]["A"],
                                              st.session_state["bycourt"]["B"])
    total = max(scoreA+scoreB, 1e-6)
    pA = round(100*scoreA/total, 1)
    pB = round(100*scoreB/total, 1)
    winner = "A" if pA >= pB else "B"
    return {"pA": pA, "pB": pB, "winner": winner, "A": A, "B": B}

def next_game_bullets() -> list[str]:
    byA = st.session_state["bycourt"]["A"]
    byB = st.session_state["bycourt"]["B"]
    tips = []

    # 2^ per lato (regole pratiche)
    def sec_tip(tag, side_name, v):
        if v is None: return
        if 30 <= v < 40: tips.append(f"{tag}: 2ª da {side_name} tra 30–40% → lato fragile (~50% rischio).")
        if v < 30:      tips.append(f"{tag}: 2ª da {side_name} <30% → lato molto vulnerabile (break >65%).")
        if v > 50:      tips.append(f"{tag}: 2ª da {side_name} >50% → lato relativamente sicuro.")

    sec_tip("A","SINISTRA (AD)",   byA.get("second_ad"))
    sec_tip("A","DESTRA (DEUCE)",  byA.get("second_deuce"))
    sec_tip("B","SINISTRA (AD)",   byB.get("second_ad"))
    sec_tip("B","DESTRA (DEUCE)",  byB.get("second_deuce"))

    # Return rating
    def ret_tip(tag, side_name, v):
        if v is None: return
        if v > 200: tips.append(f"{tag}: Return rating da {side_name} >200 → zona break favorita.")
        elif v <= 120: tips.append(f"{tag}: Return rating da {side_name} ≤120 → poco impatto da questo lato.")

    ret_tip("A","SINISTRA (AD)", byA.get("ret_rating_left"))
    ret_tip("A","DESTRA (DEUCE)",byA.get("ret_rating_right"))
    ret_tip("B","SINISTRA (AD)", byB.get("ret_rating_left"))
    ret_tip("B","DESTRA (DEUCE)",byB.get("ret_rating_right"))

    return tips


# ==============
# RENDERERS PAGINE (riutilizzabili)
# ==============

FIELDS_ORDER = [
    ("clutch",       "Pressure Points (Clutch) %"),
    ("br_won",       "Break Points Won %"),
    ("br_saved",     "Break Points Saved %"),
    ("first_in",     "1st Serve %"),
    ("first_won",    "1st Serve Points Won %"),
    ("second_won",   "2nd Serve Points Won %"),
    ("srv_games",    "Service Games Won %"),
    ("ret_games",    "Return Games Won %"),
]

def _percent_input(label: str, key: str):
    v = st.text_input(label, value=st.session_state.get(key,""), key=key, placeholder="0–100 o x")
    v = v.strip()
    if v.lower() in {"x","n/d","nd",""}:
        return None
    return float(v)

def render_match_page():
    ensure_session()
    st.title("🏟️ Match generale")
    col = st.container()
    col.subheader("📋 Incolla testo (opzionale)")
    txt = col.text_area("Blocchi Live-Tennis (facoltativo)", height=200, placeholder="Incolla qui…")
    if col.button("📥 Leggi testo e salva"):
        parsed = parse_stats_from_text(txt)
        save_general_stats(parsed)
        st.success("Dati (se trovati) salvati nel Match Generale.")

    st.subheader("✍️ Inserimento manuale")
    a, b = st.columns(2)
    with a:
        st.markdown("**Giocatore A**")
        for k, label in FIELDS_ORDER:
            val = _percent_input(label, f"GA_{k}")
            if val is not None: st.session_state["general"]["A"][k] = val
    with b:
        st.markdown("**Giocatore B**")
        for k, label in FIELDS_ORDER:
            val = _percent_input(label, f"GB_{k}")
            if val is not None: st.session_state["general"]["B"][k] = val

    st.caption("Usa **x** per N/D. 0 è un valore valido.")

def render_set_page(set_no: int, title: str):
    ensure_session()
    st.title(title)
    txt = st.text_area("📋 Incolla testo del set (facoltativo)", height=200, key=f"set_txt_{set_no}")
    if st.button("📥 Leggi testo del set e salva", key=f"read_set_{set_no}", use_container_width=True):
        parsed = parse_stats_from_text(txt)
        save_set_stats(set_no, parsed)
        st.success(f"Dati Set {set_no} salvati (se trovati).")

    st.subheader("✍️ Inserimento manuale")
    a, b = st.columns(2)
    with a:
        st.markdown("**Giocatore A**")
        for k, label in FIELDS_ORDER:
            val = _percent_input(label, f"S{set_no}_A_{k}")
            if val is not None: st.session_state["sets"][set_no]["A"][k] = val
    with b:
        st.markdown("**Giocatore B**")
        for k, label in FIELDS_ORDER:
            val = _percent_input(label, f"S{set_no}_B_{k}")
            if val is not None: st.session_state["sets"][set_no]["B"][k] = val

def render_live_context():
    ensure_session()
    st.title("🎾 Contesto live")
    lv = st.session_state["live"]
    lv["playerA"] = st.text_input("Nome Giocatore A", value=lv.get("playerA",""))
    lv["playerB"] = st.text_input("Nome Giocatore B", value=lv.get("playerB",""))
    lv["format"]  = st.selectbox("Formato", ["BO3","BO5"], index=0 if lv.get("format","BO3")=="BO3" else 1)
    lv["focus_set"] = st.number_input("Set in focus (1–5)", min_value=1, max_value=5, step=1, value=int(lv.get("focus_set",1)))
    lv["score"] = st.text_input("Score set (es. 7-6, 2-2)", value=lv.get("score",""))
    lv["game"]  = st.text_input("Game corrente (es. 40-30)", value=lv.get("game",""))
    lv["server"]= st.selectbox("Chi serve ora?", ["A","B"], index=0 if lv.get("server","A")=="A" else 1)
    st.success("Contesto salvato in memoria.")

def render_bycourt_page():
    ensure_session()
    st.title("+ OCR/Incolla — BY-COURT")

    st.caption("Compila **solo** ciò che hai. `%` = 0–100, Return Rating = numero. Usa **x** per N/D. "
               "LEFT=AD (sinistra) • RIGHT=DEUCE (destra)")

    st.subheader("🖼️ Screenshot BY-COURT")
    upA = st.file_uploader("Screenshot BY-COURT · A", type=["png","jpg","jpeg"])
    upB = st.file_uploader("Screenshot BY-COURT · B", type=["png","jpg","jpeg"])
    rawA = st.text_area("Testo grezzo · A", height=160, placeholder="SERVICE\nLEFT\nRIGHT\n…")
    rawB = st.text_area("Testo grezzo · B", height=160, placeholder="SERVICE\nLEFT\nRIGHT\n…")
    if st.button("📩 Leggi testo BY-COURT (libero) e unisci", use_container_width=True):
        txtA = rawA or (ocr_image_to_text(upA) if upA else "")
        txtB = rawB or (ocr_image_to_text(upB) if upB else "")
        parsedA = parse_bycourt_text(txtA)
        parsedB = parse_bycourt_text(txtB)
        st.session_state["bycourt"]["A"] |= parsedA
        st.session_state["bycourt"]["B"] |= parsedB
        st.success("Dati BY-COURT importati.")
        with st.expander("📦 JSON A"):
            st.json(st.session_state["bycourt"]["A"])
        with st.expander("📦 JSON B"):
            st.json(st.session_state["bycourt"]["B"])

    st.divider()
    st.subheader("✍️ Inserimento manuale (BY-COURT)")

    def _by_input(tag, label, key):
        v = st.text_input(label, value=st.session_state.get(key,""), key=key, placeholder="0–100, numero o x")
        v = v.strip()
        return _to_number_generic(v)

    colA, colB = st.columns(2)
    with colA:
        st.markdown("**Giocatore A**")
        mappingA = {
            "second_deuce": "2ª vinta da DEUCE (destra) %",
            "second_ad":    "2ª vinta da AD (sinistra) %",
            "br_saved_deuce":"BR salvate da DEUCE %",
            "br_saved_ad":   "BR salvate da AD %",
            "br_won_left":   "BR vinte da AD %",
            "br_won_right":  "BR vinte da DEUCE %",
            "ret_rating_left":  "Return rating da AD (sinistra)",
            "ret_rating_right": "Return rating da DEUCE (destra)",
            "press_left": "Pressure points da AD %",
            "press_right":"Pressure points da DEUCE %",
        }
        for k,label in mappingA.items():
            val = _by_input("A", label, f"A_by_{k}")
            if val is not None:
                st.session_state["bycourt"]["A"][k] = val

    with colB:
        st.markdown("**Giocatore B**")
        mappingB = {
            "second_deuce": "2ª vinta da DEUCE (destra) %",
            "second_ad":    "2ª vinta da AD (sinistra) %",
            "br_saved_deuce":"BR salvate da DEUCE %",
            "br_saved_ad":   "BR salvate da AD %",
            "br_won_left":   "BR vinte da AD %",
            "br_won_right":  "BR vinte da DEUCE %",
            "ret_rating_left":  "Return rating da AD (sinistra)",
            "ret_rating_right": "Return rating da DEUCE (destra)",
            "press_left": "Pressure points da AD %",
            "press_right":"Pressure points da DEUCE %",
        }
        for k,label in mappingB.items():
            val = _by_input("B", label, f"B_by_{k}")
            if val is not None:
                st.session_state["bycourt"]["B"][k] = val

def render_analysis_page():
    ensure_session()
    st.title("🧠 Analisi & Verdetti")

    # Riepilogo rapido
    res = verdict_engine()
    Aname = st.session_state["live"].get("playerA","Giocatore A")
    Bname = st.session_state["live"].get("playerB","Giocatore B")
    labA  = f"{Aname} (A)"
    labB  = f"{Bname} (B)"

    st.subheader("🧮 Probabilità complessive (blend Match+Set+BY-COURT)")
    c1,c2 = st.columns(2)
    c1.metric(labA, f"{res['pA']}%")
    c2.metric(labB, f"{res['pB']}%")
    st.success(f"**Favorito:** {'🅰️ '+labA if res['winner']=='A' else '🅱️ '+labB}")

    st.divider()
    st.subheader("🎯 Prossimo game/minibreak")
    for tip in next_game_bullets():
        st.markdown(f"- {tip}")

    st.divider()
    with st.expander("📊 Dati usati (A/B)"):
        st.write("A", res["A"])
        st.write("B", res["B"])
