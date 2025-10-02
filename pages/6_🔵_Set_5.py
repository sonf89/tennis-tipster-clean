import streamlit as st
from shim import ensure_session, render_match_or_set_form

ensure_session()
render_match_or_set_form(st.session_state.sets[5], "Set 5")
