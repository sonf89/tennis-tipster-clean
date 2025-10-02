st.set_page_config(..., layout="wide", initial_sidebar_state="collapsed")
...
if st.button("🔄 Reset TOT", use_container_width=True):
    reset_all()
    st.success("Tutti i dati sono stati azzerati.")
    st.rerun()
