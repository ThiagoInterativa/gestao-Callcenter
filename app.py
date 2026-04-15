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
# PEGAR AGENTES (COM DEBUG)
# ==============================
def get_agentes(session):
    r = session.get(MONITOR_URL)

    # ==========================
    # 🔍 PASSO 1 - VER HTML
    # ==========================
    st.subheader("🔎 DEBUG HTML (primeiros 3000 caracteres)")
    st.text(r.text[:3000])

    soup = BeautifulSoup(r.text, "html.parser")

    tabela = soup.find("table")
    agentes = []

    if not tabela:
        st.error("Tabela não encontrada!")
        return []

    # ==========================
    # 🔍 PASSO 2 - DEBUG LINHAS
    # ==========================
    st.subheader("🔎 DEBUG LINHAS")

    for linha in tabela.find_all("tr"):
    cols = linha.find_all("td")

    if len(cols) >= 1:
        valores = [c.get_text(" ", strip=True) for c in cols]
        
            
            # DEBUG linha completa
            st.write("COLUNAS:", valores)  # 👈 DEBUG REAL

            # Limpeza
            linha_texto = linha_texto.replace("ultima chamada", "")

            # Classificação
            if "pausa" in linha_texto:
                status = "pausa"

            elif any(x in linha_texto for x in ["ocupado", "falando", "em chamada"]):
                status = "ocupado"

            elif any(x in linha_texto for x in ["livre", "disponivel", "online"]):
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
st.title("🧪 DEBUG CALL CENTER")

# sessão persistente
if "session" not in st.session_state:
    st.session_state.session = login()

session = st.session_state.session

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

# DEBUG contagem
st.subheader("🔢 DEBUG CONTAGEM")
st.write("Livres:", livres)
st.write("Ocupados:", ocupados)
st.write("Pausa:", pausa)

# salvar histórico
st.session_state.historico.append({
    "time": datetime.now(),
    "livres": livres,
    "ocupados": ocupados
})

df_hist = pd.DataFrame(st.session_state.historico)

# ==============================
# GRÁFICO
# ==============================
st.subheader("📈 Gráfico")

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
