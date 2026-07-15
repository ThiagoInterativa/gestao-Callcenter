import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import unicodedata
import altair as alt  

# ==============================
# DIAGNÓSTICO TEMPORÁRIO (Remova depois)
# ==============================
st.write("---")
st.write("### 🛠️ Diagnóstico do Secrets:")
st.write("Chaves que o Streamlit consegue ver atualmente:", list(st.secrets.keys()))
st.write("---")

# ==============================
# CONFIG
# ==============================
st.set_page_config(layout="wide", page_title="NOC Call Center")

LOGIN_URL = "https://pabx.evence.com.br/login"
MONITOR_URL = "https://pabx.evence.com.br/callcenter/monitoramentoAgentes/detalhes?agentes=46,47,49,50,52,53"

# URLs novas solicitadas
KANBAN_URL = "https://kanban.interativanet.com.br/?controller=ProjectOverviewController&action=show&project_id=1&search=status%3Aopen"
WHATSFLUX_URL = "https://app.whatsflux.com.br/"

EMAIL = st.secrets["EMAIL"]
SENHA = st.secrets["SENHA"]

REFRESH = 30  # segundos

# Som de notificação (URL pública de um "Ping" limpo e profissional)
AUDIO_PING_URL = "https://assets.mixkit.co/active_storage/sfx/2869/2869-84.wav"

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

.tech-status-container {
    background-color: #1e293b;
    padding: 15px;
    border-radius: 8px;
    margin-bottom: 20px;
    border: 1px solid #334155;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.status-badge {
    padding: 5px 12px;
    border-radius: 20px;
    font-weight: bold;
    font-size: 14px;
}

.badge-online { background-color: #16a34a; color: white; }
.badge-offline { background-color: #dc2626; color: white; }

.kanban-alert {
    background-color: #1e1b4b;
    border: 1px solid #4338ca;
    padding: 15px;
    border-radius: 8px;
    margin-bottom: 20px;
    text-align: center;
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

# Toca um som discretamente usando HTML5 no Streamlit
def play_sound():
    sound_html = f"""
    <audio autoplay style="display:none;">
        <source src="{AUDIO_PING_URL}" type="audio/wav">
    </audio>
    """
    st.markdown(sound_html, unsafe_allow_html=True)

# ==============================
# LOGINS E SCRAPINGS
# ==============================
def login_pabx():
    session = requests.Session()
    try:
        r = session.get(LOGIN_URL, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        token = soup.find("input", {"name": "_token"})["value"]

        payload = {
            "login": EMAIL,
            "senha": SENHA,
            "_token": token
        }
        res = session.post(LOGIN_URL, data=payload, timeout=10)
        return session if res.url != LOGIN_URL else None
    except Exception:
        return None

# ----- 🟢 AJUSTADO: LOGIN SEGURO WHATSFLUX -----

def login_e_get_status_whatsflux():
    # Rota onde o frontend geralmente busca a API de login
    login_api_url = "https://app.whatsflux.com.br/api/login" 
    dashboard_url = "https://app.whatsflux.com.br/"
    
    session = requests.Session()
    
    # Imitando perfeitamente o comportamento de um navegador moderno acessando uma API React
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8",
        "Referer": "https://app.whatsflux.com.br/login",
        "Origin": "https://app.whatsflux.com.br"
    }
    session.headers.update(headers)
    
    try:
        email_whats = st.secrets["WHATSFLUX_EMAIL"]
        senha_whats = st.secrets["WHATSFLUX_SENHA"]
    except KeyError:
        return "Configure o Secrets", "offline"

    try:
        # payload estruturado em JSON
        payload = {
            "email": email_whats,
            "password": senha_whats
        }

        # 1. Tentativa de Login enviando JSON direto para a rota de API mais comum
        res_login = session.post(login_api_url, json=payload, timeout=10)
        
        # Caso a API de login seja na rota raiz sem o sufixo /api
        if res_login.status_code == 404:
            alt_login_url = "https://app.whatsflux.com.br/login"
            res_login = session.post(alt_login_url, json=payload, timeout=10)

        # Se ainda assim falhar
        if res_login.status_code not in [200, 201, 302]:
            return f"Falha Auth (HTTP {res_login.status_code})", "offline"

        # 2. Se a API retornou um Token JWT na resposta, nós o adicionamos na sessão
        try:
            dados_resposta = res_login.json()
            token = dados_resposta.get("token") or dados_resposta.get("access_token")
            if token:
                session.headers.update({"Authorization": f"Bearer {token}"})
        except Exception:
            pass # Caso o site use apenas cookies normais de sessão

        # 3. Acessa o dashboard logado
        r_dash = session.get(dashboard_url, timeout=10)
        soup = BeautifulSoup(r_dash.text, "html.parser")

        # 4. Procura o técnico "Gabriel" na tabela
        celulas = soup.find_all("td", class_="MuiTableCell-root MuiTableCell-body")
        
        nome_tecnico = "Gabriel"
        status = "offline"

        if not celulas:
            return "Painel Vazio / Login Falhou", "offline"

        for td in celulas:
            texto = td.get_text(strip=True)
            if texto == "Gabriel":
                linha = td.find_parent("tr")
                if linha:
                    svg = linha.find("svg")
                    if svg:
                        path = svg.find("path")
                        if path and "M12 2C6.48" in path.get("d", ""):
                            status = "online"
                        else:
                            status = "offline"
                break

        return nome_tecnico, status

    except Exception as e:
        return f"Erro de Conexão ({str(e)[:20]})", "offline"

# ----- 🟢 NOVO: SCRAPING KANBAN -----
def get_kanban_tasks():
    session = requests.Session()
    try:
        r = session.get(KANBAN_URL, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        
        tarefas = []
        elementos_tarefas = soup.find_all("div", class_="task-board")
        
        for elem in elementos_tarefas:
            task_id = elem.get("data-task-id") or elem.text.strip()
            if task_id:
                tarefas.append(task_id)
                
        return tarefas
    except Exception:
        return []


# ==============================
# PEGAR AGENTES (PABX)
# ==============================
def get_agentes(session):
    try:
        r = session.get(MONITOR_URL, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        tabela = soup.find("table")
        agentes = []

        if not tabela:
            return []

        for linha in tabela.find_all("tr"):
            cols = linha.find_all("td")

            if len(cols) >= 3:
                nome = cols[0].get_text(" ", strip=True).split("Última chamada")[0].strip()
                status_txt = remover_acentos(cols[2].get_text(strip=True).lower())

                if "pausa" in status_txt:
                    status = "pausa"
                elif "ocupado" in status_txt or "falando" in status_txt:
                    status = "ocupado"
                elif "livre" in status_txt:
                    status = "livre"
                elif "indisponivel" in status_txt:
                    status = "offline"
                else:
                    status = "offline"

                if nome:
                    agentes.append((nome, status))
        return agentes
    except Exception:
        return []

# ==============================
# HISTÓRICO E ESTADOS PERSISTENTES
# ==============================
if "historico" not in st.session_state:
    st.session_state.historico = []

if "ultimo_kanban_tasks" not in st.session_state:
    st.session_state.ultimo_kanban_tasks = None

if "ultima_notificacao_kanban" not in st.session_state:
    st.session_state.ultima_notificacao_kanban = None

# ==============================
# APP - HEADER E TÍTULO
# ==============================
st.markdown('<div class="title">📡 Gestor de Call Center - Intercom</div>', unsafe_allow_html=True)

# sessão persistente PABX
if "session" not in st.session_state:
    st.session_state.session = login_pabx()

session = st.session_state.session

if not session:
    st.error("Erro no login do PABX")
    st.stop()

# ==============================
# 🟢 INTEGRAÇÃO WHATSFLUX (TECNICO LOGADO)
# ==============================
nome_tecnico, status_whats = login_e_get_status_whatsflux()

# Trata a exibição do status dinâmico
if status_whats == "online":
    status_badge = '<span class="status-badge badge-online">🟢 ONLINE</span>'
elif "Erro" in nome_tecnico:
    status_badge = f'<span class="status-badge badge-offline">⚠️ {nome_tecnico}</span>'
    nome_tecnico = "WhatsFlux"
else:
    status_badge = '<span class="status-badge badge-offline">🔴 OFFLINE</span>'

st.markdown(f"""
<div class="tech-status-container">
    <div><strong>Suporte Técnico (WhatsFlux):</strong> {nome_tecnico}</div>
    <div>{status_badge}</div>
</div>
""", unsafe_allow_html=True)

# ==============================
# 🔔 MONITORAMENTO DO KANBAN (EFEITO SONORO + DATA/HORA)
# ==============================
tarefas_atuais = get_kanban_tasks()
agora_br = datetime.now(ZoneInfo("America/Sao_Paulo"))

if st.session_state.ultimo_kanban_tasks is None:
    st.session_state.ultimo_kanban_tasks = tarefas_atuais
else:
    novas_tarefas = [t for t in tarefas_atuais if t not in st.session_state.ultimo_kanban_tasks]
    
    if novas_tarefas:
        st.session_state.ultima_notificacao_kanban = agora_br.strftime("%d/%m/%Y às %H:%M:%S")
        st.session_state.ultimo_kanban_tasks = tarefas_atuais
        play_sound()

if st.session_state.ultima_notificacao_kanban:
    st.markdown(f"""
    <div class="kanban-alert">
        🔔 <strong>Nova tarefa criada no Kanban!</strong><br>
        Identificada em: <span style="color: #6366f1; font-weight: bold;">{st.session_state.ultima_notificacao_kanban}</span>
    </div>
    """, unsafe_allow_html=True)


# ==============================
# DADOS PRINCIPAIS (AGENTES)
# ==============================
agentes = get_agentes(session)

livres = sum(1 for _, s in agentes if s == "livre")
ocupados = sum(1 for _, s in agentes if s == "ocupado")
pausa = sum(1 for _, s in agentes if s == "pausa")

# salvar histórico
registro = {
    "time": agora_br,
    "livres": int(livres),
    "ocupados": int(ocupados),
    "pausa": int(pausa)
}
st.session_state.historico.append(registro)

# ==============================
# CARDS
# ==============================
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(f'<div class="big-card green">🟢 {livres}<br>Livres</div>', unsafe_allow_html=True)

with col2:
    st.markdown(f'<div class="big-card red">🔴 {ocupados}<br>Ocupados</div>', unsafe_allow_html=True)

with col3:
    st.markdown(f'<div class="big-card yellow">🟡 {pausa}<br>Pausa</div>', unsafe_allow_html=True)


# ==============================
# 📊 HISTÓRICO 
# ==============================
df_hist = pd.DataFrame(st.session_state.historico)

if df_hist.empty:
    st.info("Aguardando dados do histórico...")
    st.stop()

# limpeza segura dos dados
df_hist["time"] = pd.to_datetime(df_hist["time"], errors="coerce")
df_hist = df_hist.dropna(subset=["time"])
df_hist = df_hist.sort_values("time")

for col in ["livres", "ocupados", "pausa"]:
    if col not in df_hist.columns:
        df_hist[col] = 0

df_hist[["livres", "ocupados", "pausa"]] = df_hist[
    ["livres", "ocupados", "pausa"]
].fillna(0).astype(int)

series = ["livres", "ocupados"]
if df_hist["pausa"].sum() > 0:
    series.append("pausa")

df_plot = df_hist.copy()
for col in ["livres", "ocupados"]:
    df_plot[col] = df_plot[col].replace(0, None)

# ==============================
# 📈 GRÁFICO
# ==============================
st.subheader("📈 Atendimentos ao longo do tempo")

df_melt = df_plot.melt(
    id_vars=["time"],
    value_vars=series,
    var_name="Status",
    value_name="Quantidade"
)

color_map = {
    "livres": "#22c55e",
    "ocupados": "#ef4444",
    "pausa": "#eab308"
}

color_scale = alt.Scale(
    domain=list(color_map.keys()),
    range=list(color_map.values())
)

chart = alt.Chart(df_melt).mark_line(point=True).encode(
    x=alt.X("time:T", axis=alt.Axis(format="%H:%M"), title="Horário (Brasil)"),
    y=alt.Y(
        "Quantidade:Q",
        scale=alt.Scale(domain=[0, 9]),
        axis=alt.Axis(tickMinStep=1)
    ),
    color=alt.Color("Status:N", scale=color_scale),
    tooltip=["time:T", "Status", "Quantidade"]
).properties(height=400)

st.altair_chart(chart, use_container_width=True)

# ==============================
# TABELA
# ==============================
st.subheader("👨‍💻 Agentes")

df = pd.DataFrame(agentes, columns=["Nome", "Status"])
st.dataframe(df, use_container_width=True)

# ==============================
# AUTO ATUALIZAÇÃO
# ==============================
time.sleep(REFRESH)
st.rerun()
