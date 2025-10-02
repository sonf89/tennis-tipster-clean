import streamlit as st
from shim import ensure_session, evaluate_all, verdict_card, app_header

ensure_session()
app_header("Analisi & Verdetti (auto)")
v = evaluate_all()
verdict_card(v)
