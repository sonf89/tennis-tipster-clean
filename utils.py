import re, math, io, json
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import streamlit as st
from PIL import Image
import pytesseract

# -------------------- UI BASICS --------------------

def app_header(title:str):
    st.markdown(f"## {title}")

def ensure_session():
    if "ctx" not in st.session_state:
        st.session_state.ctx = {
            "players": {"A":"Giocatore A", "B":"Giocatore B"},
            "format": "BO3",            # BO3 / BO5
            "set_in_focus": 1,
            "sets_score": "",           # e.g. "7-6, 2-1"
            "current_game": "",         # e.g. "40-30"
            "server_now": "A"           # "A"/"B"
        }
    if "general" not in st.session_state:
        st.session_state.general = empty_sidepair()
    if "sets" not in st.session_state:
        st.session_state.sets = {i: empty_sidepair() for i in range(1,6)}
    if "bycourt" not in st.session_state:
        st.session_state.bycourt = empty_bycourt()
    if "momentum" not in st.session_state:
        st.session_state.momentum = {"last10": None, "last5games": None}

def reset_all():
    for k in ["ctx","general","sets","bycourt","momentum"]:
        if k in st.session_state: del st.session_state[k]
    ensure_session()

# -------------------- DATA SHAPES --------------------

def empty_side():
    # 8 indicatori base: tutti opzionali
    return {
        "clutch": None,
        "br_won": None,
        "br_saved": None,
        "second_won": None,
        "first_won": None,
        "first_in": None,
        "srv_games": None,
        "ret_games": None,
    }

def empty_sidepair():
    return {"A": empty_side(), "B": empty_side()}

def empty_bycourt_side():
    return {
        "second_deuce": None, "second_ad": None,
        "br_saved_deuce": None, "br_saved_ad": None,
        "br_won_right": None, "br_won_left": None,
        "ret_rating_right": None, "ret_rating_left": None,
        "press_right": None, "press_left": None,
    }

def empty_bycourt():
    return {"A": empty_bycourt_side(), "B": empty_bycourt_side()}

# -------------------- HELPERS --------------------

_num = r"(?:(?:\d{1,3}(?:\.\d+)?)%)|(?:\d{1,3})"
def _to_num(x:str)->Optional[float]:
    if x is None: return None
    sx = x.strip().lower()
    if sx in {"x","nd","n/d","-","—","–"}: return None
    m = re.search(r"(\d{1,3}(?:\.\d+)?)", sx)
    if not m: return None
    v = float(m.group(1))
    if "%" in sx: return max(0,min(100,v))
    return v

def _blend_sets(general:dict, sets:Dict[int,dict])->dict:
    # Media pesata progressiva
    filled = [s for s in sets.values() if any(v is not None for v in s["A"].values()) or any(v is not None for v in s["B"].values())]
    if not filled:
        return general
    N = len(filled)
    w_set = max(0.5, 0.3 + 0.1*N)
    out = {"A":{}, "B":{}}
    for side in ["A","B"]:
        keys = set(general[side].keys())
        for k in keys:
            g = general[side].get(k)
            vals = [s[side].get(k) for s in filled if s[side].get(k) is not None]
            if vals:
                m = sum(vals)/len(vals)
                if g is None:
                    out[side][k] = m
                else:
                    out[side][k] = w_set*m + (1-w_set)*g
            else:
                out[side][k] = g
    return out

# -------------------- PARSER TESTO --------------------

# mapping label -> campo
MAP = {
    r"pressure\s*points": "clutch",
    r"break\s*points\s*won": "br_won",
    r"break\s*points\s*saved": "br_saved",
    r"2nd\s*serve\s*points\s*won|second\s*serve\s*points\s*won": "second_won",
    r"1st\s*serve\s*points\s*won|first\s*serve\s*points\s*won": "first_won",
    r"1st\s*serve\s*%|first\s*serve\s*%": "first_in",
    r"service\s*games": "srv_games",
    r"return\s*games": "ret_games",
}

def parse_stats_from_text(txt:str)->dict:
    """
    Accetta blocchi a due colonne (A e B). Estrae le 8 metriche, tollera testo extra.
    Ritorna {"A":{..}, "B":{..}} (solo i campi trovati).
    """
    res = {"A":{}, "B":{}}
    if not txt: 
        return res
    lines = [l.strip() for l in txt.splitlines() if l.strip()]
    # costruisci coppie label -> (A,B) cercando righe con numeri nelle 2 successive
    i = 0
    while i < len(lines)-2:
        label = lines[i].lower()
        a = lines[i+1]; b = lines[i+2]
        if re.search(r"\d", a) and re.search(r"\d", b):
            for pat, field in MAP.items():
                if re.search(pat, label):
                    res["A"][field] = _to_num(a)
                    res["B"][field] = _to_num(b)
                    break
            i += 3
        else:
            i += 1
    return res

# -------------------- BY-COURT: PARSER & OCR --------------------

def parse_bycourt_text(raw:str)->dict:
    """
    Si aspetta blocchi LEFT/RIGHT per: 
     - 2nd Serve Points Won, Break Points Saved, Break Points Won, Return Rating, Pressure Points.
    Ritorna {"A":{...}, "B":{...}} con chiavi second_deuce/ad etc.
    Si può incollare per A e per B separatamente (usa due chiamate).
    """
    if not raw: 
        return {}
    L = raw.lower()
    # prendi la prima colonna "left" e la seconda "right" trovando la riga valore successiva
    def grab(key):
        # cerca percentuali o numeri subito dopo il label
        pat = rf"{key}\s*{_num}.*?{_num}"
        m = re.search(pat, L, re.S)
        if m:
            nums = re.findall(r"(\d{1,3}(?:\.\d+)?)%?", m.group(0))
            if len(nums)>=2:
                left = float(nums[0]); right = float(nums[1])
                # clamp 0-100
                return max(0,min(100,left)), max(0,min(100,right))
        return None

    out = {}
    # 2nd serve points won
    s = grab(r"2nd\s*serve\s*points\s*won|second\s*serve\s*points\s*won")
    if s: out["second_ad"], out["second_deuce"] = s[0], s[1]  # AD=sinistra, DEUCE=destra

    s = grab(r"break\s*points\s*saved")
    if s: out["br_saved_left"], out["br_saved_right"] = s

    s = grab(r"break\s*points\s*won")
    if s: out["br_won_left"], out["br_won_right"] = s

    s = grab(r"return\s*rating")
    if s: out["ret_rating_left"], out["ret_rating_right"] = s

    s = grab(r"pressure\s*points")
    if s: out["press_left"], out["press_right"] = s

    # normalizza nomi ai nostri campi ufficiali
    norm = {}
    norm["second_ad"] = out.get("second_ad")
    norm["second_deuce"] = out.get("second_deuce")
    norm["br_saved_ad"] = out.get("br_saved_left")
    norm["br_saved_deuce"] = out.get("br_saved_right")
    norm["br_won_left"] = out.get("br_won_left")
    norm["br_won_right"] = out.get("br_won_right")
    norm["ret_rating_left"] = out.get("ret_rating_left")
    norm["ret_rating_right"] = out.get("ret_rating_right")
    norm["press_left"] = out.get("press_left")
    norm["press_right"] = out.get("press_right")
    return norm

def ocr_image_to_text(uploaded_file)->str:
    img = Image.open(uploaded_file).convert("L")
    img = img.point(lambda x: 0 if x < 160 else 255)  # binarizzazione semplice
    txt = pytesseract.image_to_string(img)
    return txt

# -------------------- MOTORE REGOLE / SCORING --------------------

def logistic(x): 
    return 1/(1+math.exp(-x))

def _val(v, default=None): 
    return v if (v is not None) else default

def _score_base(p:dict, phase:str)->float:
    # default 50 su mancanti
    clutch     = _val(p.get("clutch"), 50)
    br_won     = _val(p.get("br_won"), 50)
    br_saved   = _val(p.get("br_saved"), 50)
    second_won = _val(p.get("second_won"), 50)
    first_won  = _val(p.get("first_won"), 55)
    first_in   = _val(p.get("first_in"), 60)
    srv_games  = _val(p.get("srv_games"), 55)
    ret_games  = _val(p.get("ret_games"), 45)

    w = dict(clutch=1.00, br_won=1.00, br_saved=0.80, second_won=1.20,
             first_won=0.60, first_in=0.30, srv_games=1.00, ret_games=1.00)
    if phase=="early":
        w["clutch"]*=0.8; w["br_won"]*=0.9; w["br_saved"]*=0.9; w["first_won"]*=0.7
    elif phase=="late":
        w["clutch"]*=1.4; w["br_won"]*=1.3; w["br_saved"]*=1.2; w["second_won"]*=1.2; w["first_in"]*=0.2
    # mid = base
    s = (w["clutch"]*clutch + w["br_won"]*br_won + w["br_saved"]*br_saved + 
         w["second_won"]*second_won + w["first_won"]*first_won + w["first_in"]*first_in + 
         w["srv_games"]*srv_games + w["ret_games"]*ret_games)
    return s/ (sum(w.values()))  # normalizza 0-100

def _bycourt_bonus(p_b:Sdict, opp_b:Sdict, phase:str)->float:
    # p_b e opp_b sono i dizionari bycourt per il player e per l’avversario
    if p_b is None: return 0.0
    bonus = 0.0
    sd = p_b.get("second_deuce"); sa = p_b.get("second_ad")
    if sa is not None and sa < 35: bonus -= 8 if phase=="late" else 6
    if sd is not None and sd < 35: bonus -= 8 if phase=="late" else 6
    for k in ("ret_rating_left","ret_rating_right"):
        v = opp_b.get(k) if opp_b else None
        if v is not None and v > 200: bonus += 4
    for k in ("press_left","press_right"):
        v = p_b.get(k)
        if v is not None and v > 65: bonus += 2
    return bonus

def _phase_from_context()->str:
    # prova a dedurre dalla score del set in focus
    score = st.session_state.ctx.get("sets_score","")
    # fallback: usa "late" se contiene 5-5 / 6-6
    if re.search(r"\b5-5\b|\b6-6\b", score): return "late"
    return "mid"

Sdict = Dict[str, Optional[float]]

def evaluate_all()->dict:
    """
    Calcola tutto e ritorna un pacchetto con probabilità e spiegazioni.
    """
    ctx = st.session_state.ctx
    general = st.session_state.general
    sets = st.session_state.sets
    byc = st.session_state.bycourt

    phase = _phase_from_context()
    blend = _blend_sets(general, sets)

    # score base
    sA = _score_base(blend["A"], phase)
    sB = _score_base(blend["B"], phase)

    # by-court bonus
    bA = _bycourt_bonus(byc["A"], byc["B"], phase)
    bB = _bycourt_bonus(byc["B"], byc["A"], phase)

    scoreA = sA + bA
    scoreB = sB + bB

    # momentum (semplice opzionale)
    M = st.session_state.momentum
    adjA=adjB=0.0
    if M.get("last10") is not None or M.get("last5games") is not None:
        p = ( (M.get("last10") or 0)*60 + (M.get("last5games") or 0)*40 )
        if p>40: adjA += 5
        if p<-40: adjB += 5
    scoreA += adjA; scoreB += adjB

    # sostenibilità: se leader molto fragile in second_won o total points bassi
    if scoreA>scoreB and _val(blend["A"].get("second_won"),50)<35: scoreA -= 5
    if scoreB>scoreA and _val(blend["B"].get("second_won"),50)<35: scoreB -= 5

    # set prob
    pA_set = logistic((scoreA - scoreB)/12)

    # match prob (semplificata ma coerente)
    if ctx["format"]=="BO3":
        pA_match = pA_set
    else:
        pA_match = pA_set  # nel decider si equivale; per semplicità manteniamo

    # prossimo game (serve_now)
    serve = ctx.get("server_now","A")
    p_hold, expl_hold = hold_probability(serve=serve, blend=blend, byc=byc, phase=phase)
    p_break = 1-p_hold

    # tie-break
    p_tb, fav_tb, tb_conf = tie_break_module(blend, byc)

    # confidenza
    conf = confidence(blend, scoreA, scoreB)

    # suggerimenti
    sugg = suggestions(serve, blend, byc, phase, p_break, fav_tb, p_tb, pA_set)

    return {
        "scoreA":scoreA, "scoreB":scoreB,
        "pA_set":pA_set, "pA_match":pA_match,
        "p_hold":p_hold, "p_break":p_break, "hold_expl":expl_hold,
        "p_tb":p_tb, "fav_tb":fav_tb, "tb_conf":tb_conf,
        "conf": conf,
        "suggestions": sugg
    }

def hold_probability(serve:str, blend:dict, byc:dict, phase:str)->Tuple[float,str]:
    S = blend[serve]; R = blend["B" if serve=="A" else "A"]
    Sb = byc[serve]; Rb = byc["B" if serve=="A" else "A"]
    first_in = _val(S.get("first_in"),60)/100.0
    first_won= _val(S.get("first_won"),55)/100.0
    second_won=_val(S.get("second_won"),50)/100.0
    p_point = first_in*first_won + (1-first_in)*second_won
    base = 1/(1+math.exp(-12*(p_point-0.5)))
    # rischio per lato medio
    risk = 0.0
    def V(second, rr, brs, brw):
        v=0.0
        if second is not None: v += (50-second)
        if rr is not None: v += (rr-150)/5
        if brs is not None: v += max(0,50-brs)/1.5
        if brw is not None: v += max(0, brw-50)/1.5
        return max(0,v)
    v_ad = V( _val(Sb.get("second_ad"),50), _val(Rb.get("ret_rating_left"),150),
              _val(Sb.get("br_saved_ad"),50), _val(Rb.get("br_won_left"),50) )
    v_de = V( _val(Sb.get("second_deuce"),50), _val(Rb.get("ret_rating_right"),150),
              _val(Sb.get("br_saved_deuce"),50), _val(Rb.get("br_won_right"),50) )
    risk = 0.5*v_ad + 0.5*v_de
    w2 = max(0.25, 1-first_in)
    p_hold = min(0.95, max(0.05, base - w2*(risk/100)))
    expl = f"base={base:.2f}, risk={risk:.1f}, w2={w2:.2f}"
    return p_hold, expl

def tie_break_module(blend:dict, byc:dict)->Tuple[float,str,float]:
    # propensione al TB e favorito
    A,B = blend["A"], blend["B"]
    prop = 0.35
    if _val(A.get("first_won"),0)>=72 and _val(B.get("first_won"),0)>=72 and \
       _val(A.get("ret_games"),50)<=25 and _val(B.get("ret_games"),50)<=25:
        prop = 0.65
    clutchA, clutchB = _val(A.get("clutch"),50), _val(B.get("clutch"),50)
    secondA, secondB = _val(A.get("second_won"),50), _val(B.get("second_won"),50)
    rrA = max(_val(byc["A"].get("ret_rating_left"),150), _val(byc["A"].get("ret_rating_right"),150))
    rrB = max(_val(byc["B"].get("ret_rating_left"),150), _val(byc["B"].get("ret_rating_right"),150))
    tbA = 0.6*clutchA + 0.2*secondA + 0.2*_val(A.get("first_won"),55) + 0.1*(rrA/3)
    tbB = 0.6*clutchB + 0.2*secondB + 0.2*_val(B.get("first_won"),55) + 0.1*(rrB/3)
    pA = logistic((tbA-tbB)/15)
    fav = "A" if pA>=0.5 else "B"
    conf = abs(pA-0.5)*2  # 0..1
    return prop, fav, conf

def confidence(blend:dict, sA:float, sB:float)->int:
    # Copertura dati
    keys = list(blend["A"].keys())
    haveA = sum(1 for k in keys if blend["A"][k] is not None)
    haveB = sum(1 for k in keys if blend["B"][k] is not None)
    cov = (haveA+haveB)/(2*len(keys))
    c1 = 40 if cov>=0.8 else 25 if cov>=0.5 else 10
    # Coerenza
    diffs = []
    for k in keys:
        a,b = blend["A"].get(k), blend["B"].get(k)
        if a is not None and b is not None:
            diffs.append(abs(a-b))
    avgd = sum(diffs)/len(diffs) if diffs else 0
    c2 = 25 if avgd<6 else 15 if avgd<12 else 5
    # Margine
    pA = logistic((sA-sB)/12)
    gap = abs(pA-0.5)*100*2
    c3 = 25 if gap>=15 else 15 if gap>=8 else 5
    # Sostenibilità
    red = 0
    if _val(blend["A"].get("second_won"),50)<35 or _val(blend["B"].get("second_won"),50)<35: red+=1
    c4 = 10 if red==0 else 5 if red==1 else 0
    return min(100, int(c1+c2+c3+c4))

def suggestions(serve, blend, byc, phase, p_break, fav_tb, p_tb, pA_set):
    out=[]
    if p_break>=0.60:
        out.append("**Break probabile** sul server attuale (p≈{:.0f}%).".format(p_break*100))
    elif p_break>=0.45:
        out.append("**Pericolo break** nel prossimo game (p≈{:.0f}%).".format(p_break*100))
    out.append("Tie-break: p≈{:.0f}% · favorito **{}**".format(p_tb*100, fav_tb))
    fav_set = "A" if pA_set>=0.5 else "B"
    out.append("Set favorito: **{}** (p≈{:.0f}%).".format(fav_set, max(pA_set,1-pA_set)*100))
    return out

# -------------------- UI: FORM GENERICI --------------------

def _percent_input(lbl,key,initial=""):
    v = st.text_input(lbl, value=initial, key=key, placeholder="0–100 o x")
    return _to_num(v)

def render_match_or_set_form(storage:dict, title:str):
    app_header(title)
    st.caption("Compila **solo** ciò che hai. Usa `x` o `-` per N/D. Oppure incolla testo grezzo e premi **Leggi testo**.")

    # PASTE
    pasted = st.text_area("📋 Incolla testo (KEY STATS a due colonne)", height=180, key=f"{title}-paste")
    if st.button("📥 Leggi testo e compila", key=f"{title}-btn"):
        parsed = parse_stats_from_text(pasted)
        for side in ["A","B"]:
            for k,v in parsed.get(side,{}).items():
                storage[side][k] = v
        st.success("Dati letti. Completa a mano se vuoi.")

    st.markdown("#### Statistiche")
    st.markdown("**Giocatore A**")
    for k,label in [
        ("clutch","Pressure Points (Clutch) %"),
        ("br_won","Break Points Won %"),
        ("br_saved","Break Points Saved %"),
        ("second_won","2ª Serve Points Won %"),
        ("first_won","1ª Serve Points Won %"),
        ("first_in","1ª di Servizio in campo %"),
        ("srv_games","Service Games Won %"),
        ("ret_games","Return Games Won %"),
    ]:
        storage["A"][k] = _percent_input(label, key=f"{title}-A-{k}", initial=str(storage["A"].get(k) or ""))

    st.markdown("**Giocatore B**")
    for k,label in [
        ("clutch","Pressure Points (Clutch) %"),
        ("br_won","Break Points Won %"),
        ("br_saved","Break Points Saved %"),
        ("second_won","2ª Serve Points Won %"),
        ("first_won","1ª Serve Points Won %"),
        ("first_in","1ª di Servizio in campo %"),
        ("srv_games","Service Games Won %"),
        ("ret_games","Return Games Won %"),
    ]:
        storage["B"][k] = _percent_input(label, key=f"{title}-B-{k}", initial=str(storage["B"].get(k) or ""))

    st.info("Salvato in memoria. Vai pure su altre pagine.")

def render_bycourt_page():
    app_header("+ OCR/Incolla")
    if st.button("🔄 Reset TOTALE"):
        reset_all(); st.experimental_rerun()

    st.caption("Compila solo ciò che hai. `%` = 0–100, Return Rating = numero. Usa `x`/`-` per N/D.")

    st.subheader("Upload Screenshot BY-COURT · A")
    imgA = st.file_uploader("Screenshot BY-COURT · A", type=["png","jpg","jpeg"], key="byA")
    txtA = st.text_area("Testo grezzo · A")
    st.subheader("Upload Screenshot BY-COURT · B")
    imgB = st.file_uploader("Screenshot BY-COURT · B", type=["png","jpg","jpeg"], key="byB")
    txtB = st.text_area("Testo grezzo · B")

    if st.button("📬 Leggi testo BY-COURT (libero) e unisci"):
        upd = {"A":{}, "B":{}}
        if imgA: 
            try: upd["A"].update(parse_bycourt_text(ocr_image_to_text(imgA)))
            except: pass
        if imgB:
            try: upd["B"].update(parse_bycourt_text(ocr_image_to_text(imgB)))
            except: pass
        if txtA: upd["A"].update(parse_bycourt_text(txtA))
        if txtB: upd["B"].update(parse_bycourt_text(txtB))
        for s in ["A","B"]:
            st.session_state.bycourt[s].update(upd[s])
        st.success("BY-COURT acquisito.")
    st.json(st.session_state.bycourt)

def render_context_page():
    app_header("Contesto live")
    ctx = st.session_state.ctx
    ctx["players"]["A"] = st.text_input("Nome Giocatore A", value=ctx["players"]["A"])
    ctx["players"]["B"] = st.text_input("Nome Giocatore B", value=ctx["players"]["B"])
    ctx["format"] = st.selectbox("Formato", ["BO3","BO5"], index=0 if ctx["format"]=="BO3" else 1)
    ctx["set_in_focus"] = st.number_input("Set in focus (1–5)", 1, 5, value=ctx["set_in_focus"])
    ctx["sets_score"] = st.text_input("Score set (es. 7-6, 2-2)", value=ctx["sets_score"])
    ctx["current_game"] = st.text_input("Game corrente (es. 40-30)", value=ctx["current_game"])
    ctx["server_now"] = st.selectbox("Chi serve ora?", ["A","B"], index=0 if ctx["server_now"]=="A" else 1)
    st.success("Contesto aggiornato.")

def verdict_card(v:dict):
    A = st.session_state.ctx["players"]["A"]
    B = st.session_state.ctx["players"]["B"]
    st.subheader("🧠 Verdetto dal Match")
    pA = v["pA_match"]; pS = v["pA_set"]
    fav_match = f"**{A}**" if pA>=0.5 else f"**{B}**"
    fav_set   = f"**{A}**" if pS>=0.5 else f"**{B}**"
    st.markdown(f"- Set: favorito {fav_set} (p≈{max(pS,1-pS)*100:.0f}%)")
    st.markdown(f"- Match: favorito {fav_match} (p≈{max(pA,1-pA)*100:.0f}%)")
    st.markdown(f"- Prossimo game: hold p≈{v['p_hold']*100:.0f}%, break p≈{v['p_break']*100:.0f}%")
    st.markdown(f"- Tie-break: p≈{v['p_tb']*100:.0f}% · favorito **{v['fav_tb']}** (conf≈{v['tb_conf']*100:.0f}%)")
    st.markdown(f"- Confidenza complessiva: **{v['conf']}**/100")
    st.markdown("**Suggerimenti:**")
    for s in v["suggestions"]:
        st.markdown(f"• {s}")
