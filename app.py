import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime
import unicodedata

# ==============================
# CONFIG
# ==============================
st.set_page_config(layout="wide", page_title="NOC Call Center")

LOGIN_URL = "https://pabx.evence.com.br/login"
MONITOR_URL = "https://pabx.evence.com.br/callcenter/monitoramentoAgentes/detalhes?agentes=46,47,49,50,52,53"

EMAIL = st.secrets["EMAIL"]
SENHA = st.secrets["SENHA"]

REFRESH = 30  # segundos

# ==============================
# CSS NOC (VISUAL PROFISSIONAL)
# ==============================
st.markdown("""
<style>
body {
    background-color: #0e1117;
    color: white;
}

.big-card {
    padding: 30px;
    border-radius: 12px;
    text-align: center;
    font-size: 28px;
    font-weight: bold;
}

.green { background-color: #16a34a; }
.red { background-color: #dc2626; }
.yellow { background-color: #eab308; }

.title {
    text-align: center;
    font-size: 40px;
    font-weight: bold;
    margin-bottom: 20px;
}

</style>
""", unsafe_allow_html=True)

# ==============================
# UTILS
# ==============================
def remover_acentos(txt):
    return ''.join(
        c for c in unicodedata.normalize('NFD', txt)
        if unicodedata.category(c) != 'Mn'
    )

# ==============================
# LOGIN
# ==============================
def login():
    session = requests.Session()
    r = session.get(LOGIN_URL)
    soup = BeautifulSoup(r.text, "html.parser")
    token = soup.find("input", {"name": "_token"})["value"]

    payload = {
        "login": EMAIL,
        "senha": SENHA,
        "_token": token
    }

    res = session.post(LOGIN_URL, data=payload)

    return session if res.url != LOGIN_URL else None

# ==============================
# PEGAR AGENTES
# ==============================

def get_agentes(session):
    r = session.get(MONITOR_URL)
    soup = BeautifulSoup(r.text, "html.parser")

    tabela = soup.find("table")
    agentes = []

    for linha in tabela.find_all("tr"):
        cols = linha.find_all("td")

        if len(cols) >= 2:

            nome = cols[0].get_text(" ", strip=True)

            # 🔥 pega TODOS os textos da linha (não depende da coluna)
            linha_texto = remover_acentos(linha.get_text(" ", strip=True).lower())

            # DEBUG (remova depois)
            # st.write(linha_texto)

            if "pausa" in linha_texto:
                status = "pausa"
            elif any(x in linha_texto for x in ["ocupado", "falando", "chamada", "busy"]):
                status = "ocupado"
            elif any(x in linha_texto for x in ["livre", "disponivel", "online", "ready"]):
                status = "livre"
            else:
                status = "offline"

            if nome:
                agentes.append((nome, status))

    return agentes

# ==============================
# HISTÓRICO
# ==============================
if "historico" not in st.session_state:
    st.session_state.historico = []

# ==============================
# APP
# ==============================
st.markdown('<div class="title">📡 NOC CALL CENTER</div>', unsafe_allow_html=True)

session = login()

if not session:
    st.error("Erro no login")
    st.stop()

agentes = get_agentes(session)

# ==============================
# CONTADORES
# ==============================
livres = sum(1 for _, s in agentes if s == "livre")
ocupados = sum(1 for _, s in agentes if s == "ocupado")
pausa = sum(1 for _, s in agentes if s == "pausa")

# salvar histórico
st.session_state.historico.append({
    "time": datetime.now(),
    "livres": livres,
    "ocupados": ocupados
})

df_hist = pd.DataFrame(st.session_state.historico)

# ==============================
# CARDS (NOC)
# ==============================
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(f'<div class="big-card green">🟢 {livres}<br>Livres</div>', unsafe_allow_html=True)

with col2:
    st.markdown(f'<div class="big-card red">🔴 {ocupados}<br>Ocupados</div>', unsafe_allow_html=True)

with col3:
    st.markdown(f'<div class="big-card yellow">🟡 {pausa}<br>Pausa</div>', unsafe_allow_html=True)

# ==============================
# GRÁFICO
# ==============================
st.subheader("📈 Atendimentos ao longo do tempo")
if len(df_hist) > 1:
    st.line_chart(df_hist.set_index("time"))

# ==============================
# TABELA
# ==============================
st.subheader("👨‍💻 Agentes")

df = pd.DataFrame(agentes, columns=["Nome", "Status"])
st.dataframe(df, use_container_width=True)

# ==============================
# AUTO REFRESH
# ==============================
time.sleep(REFRESH)
st.rerun()
