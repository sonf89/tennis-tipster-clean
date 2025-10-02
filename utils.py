# === PATH: utils.py ===
import re
from typing import Dict, Optional, Tuple
import copy
import streamlit as st

# ============== OCR (opzionale; non blocca se assente) ==============
try:
    import pytesseract  # opzionale
    from PIL import Image
    _OCR_OK = True
    # Imposta binario tesseract se necessario (Streamlit Cloud)
    if not getattr(pytesseract.pytesseract, "tesseract_cmd", None):
        pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
except Exception:
    pytesseract = None
    Image = None
    _OCR_OK = False

# ============== Chiavi statistiche in uso ============================
STAT_KEYS = [
    "clutch",              # Pressure Points %
    "bp_won",              # Break Points Won %
    "bp_saved",            # Break Points Saved %
    "first_serve_pct",     # 1st Serve %
    "first_serve_won",     # 1st Serve Points Won %
    "second_serve_won",    # 2nd Serve Points Won %
    "service_games",       # Service Games Won %
    "return_games",        # Return Games Won %
]

# Varianti label EN/IT
LABELS = {
    "clutch": [
        "Pressure Points", "Pressure Points (Clutch)", "Punti pressione", "Punti pesanti"
    ],
    "bp_won": [
        "Break Points Won", "Palle Break Vinte", "BP Won"
    ],
    "bp_saved": [
        "Break Points Saved", "Palle Break Salvate", "BP Saved"
    ],
    "first_serve_pct": [
        "1st Serve %", "1st Serve%", "1^ Serve %", "1ª di Servizio", "1a di Servizio"
    ],
    "first_serve_won": [
        "1st Serve Points Won", "1st Serve Pts Won", "Punti vinti con 1ª", "Punti vinti con la 1ª"
    ],
    "second_serve_won": [
        "2nd Serve Points Won", "2nd Serve Pts Won", "Punti vinti con 2ª", "Punti vinti con la 2ª"
    ],
    "service_games": [
        "Service Games", "Service Games Won", "Game vinti al servizio"
    ],
    "return_games": [
        "Return Games", "Return Games Won", "Game vinti in risposta"
    ],
}

# Pesi per il verdetto
WEIGHTS = {
    "clutch": 3.0,
    "bp_won": 2.5,
    "bp_saved": 2.0,
    "second_serve_won": 2.0,
    "service_games": 1.7,
    "return_games": 1.7,
    "first_serve_won": 1.2,
    "first_serve_pct": 1.0,
}

# ============== Gestione stato (sessione) ============================
def blank_stat_block() -> Dict:
    return {"A": {k: None for k in STAT_KEYS},
            "B": {k: None for k in STAT_KEYS},
            "src": "manual"}

def ensure_session():
    if "stats" not in st.session_state:
        st.session_state.stats = {
            "general": blank_stat_block(),
            "set1": blank_stat_block(),
            "set2": blank_stat_block(),
            "set3": blank_stat_block(),
            "set4": blank_stat_block(),
            "set5": blank_stat_block(),
        }
    if "context" not in st.session_state:
        st.session_state.context = {
            "playerA": "", "playerB": "",
            "format": "BO3", "set_focus": 1,
            "score_sets": "", "game_score": "", "server": "A",
        }
    if "bycourt" not in st.session_state:
        st.session_state.bycourt = {"A": {}, "B": {}}

def reset_all():
    st.session_state.clear()
    ensure_session()

def get_block(section: str) -> Dict:
    ensure_session()
    # ritorna una copia modificabile per evitare side-effects strani
    blk = st.session_state.stats.get(section, blank_stat_block())
    return copy.deepcopy(blk)

def set_block(section: str, data: Dict):
    ensure_session()
    st.session_state.stats[section] = copy.deepcopy(data)

# ============== Parser TESTO (incolla) =====================================
PERCENT_RE = re.compile(r"(\d{1,3})\s*%")
RATIO_RE   = re.compile(r"(\d+)\s*/\s*(\d+)")
DASH_ONLY_RE = re.compile(r"^\s*[-–—]+\s*(?:\(\s*0\s*/\s*0\s*\))?\s*$")

def _norm(s: str) -> str:
    s = s.replace("–","-").replace("—","-")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _ratio_to_pct(t: str) -> Optional[int]:
    m = RATIO_RE.search(t)
    if not m:
        return None
    a, b = int(m.group(1)), int(m.group(2))
    if b == 0:
        return 0
    return max(0, min(100, round(100*a/b)))

def _two_values_after(lines, i, look_ahead=12):
    """Cerca due valori (A,B) entro ~12 righe dopo la label.
       Supporta: "67% (10/15)", "10/15", numero secco 0..100, "-" → 0."""
    vals = []
    # considera ANCHE la riga della label (alcuni layout hanno i valori lì)
    for j in range(i, min(i+1+look_ahead, len(lines))):
        raw = _norm(lines[j])
        if not raw:
            continue
        if DASH_ONLY_RE.match(raw):
            vals.append(0)
        else:
            allp = PERCENT_RE.findall(raw)
            if len(allp) >= 2:
                vals.append(int(allp[0])); vals.append(int(allp[1]))
            elif len(allp) == 1:
                vals.append(int(allp[0]))
            else:
                pr = _ratio_to_pct(raw)
                if pr is not None:
                    vals.append(pr)
                else:
                    m = re.search(r"\b(\d{1,3})\b", raw)
                    if m:
                        v = int(m.group(1))
                        if 0 <= v <= 100:
                            vals.append(v)
        if len(vals) >= 2:
            break
    while len(vals) < 2:
        vals.append(None)
    vals = [None if v is None else max(0, min(100, int(v))) for v in vals]
    return vals[0], vals[1]

def _find_label(lines, variants):
    for i, ln in enumerate(lines):
        low = _norm(ln).lower()
        for v in variants:
            if v.lower() in low:
                return i
    return None

def parse_stats_from_text(txt: str) -> Dict:
    """Ritorna {'A':{..}, 'B':{..}, 'src':'pasted'} con 8 metriche (0..100 o None)."""
    if not txt:
        return {"A":{k:None for k in STAT_KEYS},
                "B":{k:None for k in STAT_KEYS}, "src":"pasted"}
    lines = [l for l in (ln.strip() for ln in txt.splitlines()) if l.strip()]
    A = {k: None for k in STAT_KEYS}
    B = {k: None for k in STAT_KEYS}
    for key in STAT_KEYS:
        idx = _find_label(lines, LABELS[key])
        if idx is None:
            continue
        a, b = _two_values_after(lines, idx)
        A[key], B[key] = a, b
    return {"A": A, "B": B, "src": "pasted"}

# ============== OCR (best-effort) ==========================================
def parse_image_to_text(img, lang: str = "eng+ita") -> Tuple[str, bool]:
    """img: PIL.Image | bytes | numpy array. Ritorna (testo, ok)."""
    if not _OCR_OK:
        return "", False
    try:
        if Image and not isinstance(img, Image.Image):
            # converte in PIL se possibile
            img = Image.fromarray(img) if hasattr(img, "shape") else Image.open(img)
        txt = pytesseract.image_to_string(img, lang=lang)
        return txt, True
    except Exception:
        return "", False

# ============== Verdetto ====================================================
def _score_side(S: Dict[str, Optional[int]]) -> float:
    tot = 0.0
    for k, w in WEIGHTS.items():
        v = S.get(k)
        if isinstance(v, int):
            tot += w * v
    return tot

def verdict_engine(A: Dict[str, Optional[int]], B: Dict[str, Optional[int]], context: Dict) -> Dict:
    sa, sb = _score_side(A), _score_side(B)
    diff = sa - sb
    used = sum(1 for k in STAT_KEYS if isinstance(A.get(k), int) or isinstance(B.get(k), int))
    conf = min(100, max(5, int(abs(diff) / max(1, used) * 1.7)))
    winner = "A" if diff > 0 else ("B" if diff < 0 else "Equilibrio")

    notes = []
    def v(x): return x if isinstance(x, int) else None

    Acl, Bcl = v(A.get("clutch")), v(B.get("clutch"))
    if Acl is not None and Bcl is not None:
        if Acl >= 60 and Bcl < 60: notes.append("A domina i **punti pesanti** (≥60%).")
        if Bcl >= 60 and Acl < 60: notes.append("B domina i **punti pesanti** (≥60%).")

    As2, Bs2 = v(A.get("second_serve_won")), v(B.get("second_serve_won"))
    if As2 is not None:
        notes.append("A **regge la pressione** sulla 2ª (≥50%)." if As2 >= 50 else
                     "A può **regalare break** se cala (2ª <40%)." if As2 < 40 else "")
    if Bs2 is not None:
        notes.append("B **regge la pressione** sulla 2ª (≥50%)." if Bs2 >= 50 else
                     "B può **regalare break** se cala (2ª <40%)." if Bs2 < 40 else "")

    Abpw, Bbpw = v(A.get("bp_won")), v(B.get("bp_won"))
    Abs,  Bbs  = v(A.get("bp_saved")), v(B.get("bp_saved"))
    if Abpw and Abs and Abpw >= 50 and Abs >= 60:
        notes.append("A **decide i game critici** (BP vinti ≥50% e salvati ≥60%).")
    if Bbpw and Bbs and Bbpw >= 50 and Bbs >= 60:
        notes.append("B **decide i game critici** (BP vinti ≥50% e salvati ≥60%).")

    notes = [n for n in notes if n]

    return {
        "winner": winner,
        "confidence": conf,
        "scoreA": sa,
        "scoreB": sb,
        "notes": notes,
    }

# ============== UI helper per editor =======================================
def _norm_int(s: str) -> Optional[int]:
    if s is None:
        return None
    s = s.strip().lower()
    if s in {"", "x"}:
        return None
    if s.isdigit():
        v = int(s)
        return max(0, min(100, v))
    return None

def render_stats_editor(block_key: str, title: str):
    st.subheader(title)

    with st.expander("📋 Incolla testo (opzionale)"):
        txt = st.text_area("Incolla Key Stats (label su una riga, valori sotto). '-' = 0%", height=200, key=f"paste_{block_key}")
        if st.button("📥 Leggi testo e compila", key=f"btn_paste_{block_key}"):
            parsed = parse_stats_from_text(txt or "")
            blk = get_block(block_key)
            for side in ("A","B"):
                for k in STAT_KEYS:
                    val = parsed[side].get(k)
                    if isinstance(val, int) or val is None:
                        blk[side][k] = val
            blk["src"] = "pasted"; set_block(block_key, blk)
            st.success("Dati compilati dove riconosciuti ✅")

    st.caption("Inserisci **0–100** oppure **x** se N/D.")
    blk = get_block(block_key)

    LABELS_SHOWN = {
        "clutch": "Pressure Points (Clutch) %",
        "bp_won": "Break Points Won %",
        "bp_saved": "Break Points Saved %",
        "first_serve_pct": "1st Serve %",
        "first_serve_won": "1st Serve Points Won %",
        "second_serve_won": "2nd Serve Points Won %",
        "service_games": "Service Games Won %",
        "return_games": "Return Games Won %",
    }

    col_lab, colA, colB = st.columns([2,1,1])
    with col_lab: st.markdown("**Statistica**")
    with colA:    st.markdown("**Giocatore A**")
    with colB:    st.markdown("**Giocatore B**")

    for key, nice in LABELS_SHOWN.items():
        with col_lab: st.write(nice)
        with colA:
            va = st.text_input(f"{block_key}_A_{key}",
                               value=("" if blk["A"][key] is None else str(blk["A"][key])),
                               placeholder="0–100 o x", label_visibility="collapsed")
        with colB:
            vb = st.text_input(f"{block_key}_B_{key}",
                               value=("" if blk["B"][key] is None else str(blk["B"][key])),
                               placeholder="0–100 o x", label_visibility="collapsed")
        blk["A"][key] = _norm_int(va)
        blk["B"][key] = _norm_int(vb)

    set_block(block_key, blk)

    res = verdict_engine(blk["A"], blk["B"], st.session_state.context)
    st.markdown("---")
    st.markdown(f"**🧠 Verdetto rapido · {title}**")
    if res["winner"] == "Equilibrio":
        st.info("Equilibrio. Servono più dati.")
    else:
        st.success(f"Favorito: **{res['winner']}** · Confidenza ~ **{res['confidence']}%**")
    if res["notes"]:
        st.markdown("**Chiavi di lettura:**")
        for n in res["notes"]:
            st.markdown(f"- {n}")
