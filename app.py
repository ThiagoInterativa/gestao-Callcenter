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

# Credenciais para os novos sistemas (adicione no seu secrets do streamlit!)
# KANBAN_USER / KANBAN_PASS / WHATSFLUX_USER / WHATSFLUX_PASS
# Caso usem o mesmo login do PABX, altere para EMAIL e SENHA.

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

# ----- 🟢 NOVO: SCRAPING WHATSFLUX -----
def get_whatsflux_status():
    """
    Faz a requisição e extrai o nome do técnico e se ele está Online ou Offline.
    Ajuste as classes/IDs do BeautifulSoup conforme a estrutura real do WhatsFlux.
    """
    session = requests.Session()
    try:
        # Exemplo hipotético de autenticação do WhatsFlux (ajuste se necessário)
        # Se for aberto ou usar Cookie persistente, carregue aqui.
        payload = {
            "email": st.secrets.get("WHATSFLUX_USER", EMAIL),
            "password": st.secrets.get("WHATSFLUX_PASS", SENHA)
        }
        # Simulando acesso e leitura de status
        r = session.get(WHATSFLUX_URL, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        
        # --- SUBSTÍTUA ESTA LÓGICA PELO SELETOR HTML REAL DO SEU WHATSFLUX ---
        # Exemplo genérico procurando classe 'user-name' e 'status-online'
        nome_tecnico = "Técnico de Plantão" 
        tecnico_elem = soup.find("span", class_="user-profile-name") # Substitua pela classe real
        if tecnico_elem:
            nome_tecnico = tecnico_elem.get_text(strip=True)
            
        is_online = False
        # Supondo que procure um indicador de status ativo ou verde
        if soup.find(class_="status-online") or "online" in r.text.lower():
            is_online = True
            
        return nome_tecnico, "online" if is_online else "offline"
    except Exception as e:
        # Fallback caso falhe a requisição ao WhatsFlux
        return "Técnico WhatsFlux", "offline"


# ----- 🟢 NOVO: SCRAPING KANBAN -----
def get_kanban_tasks():
    """
    Acessa o Kanban e retorna uma lista com os IDs ou nomes das tarefas abertas.
    """
    session = requests.Session()
    try:
        # Se o Kanban exigir login, você precisará fazer a autenticação aqui primeiro.
        # Exemplo de requisição GET direta (caso use autenticação básica ou cookie de sessão pública)
        r = session.get(KANBAN_URL, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        
        # Encontra as tarefas no Kanban (geralmente tags com classe "task-board" ou "kanban-task")
        # --- ADAPTE ESTE SELETOR PARA O HTML DO SEU KANBAN (ex: Kanboard usa classe 'task-board') ---
        tarefas = []
        elementos_tarefas = soup.find_all("div", class_="task-board") # Seletor padrão do Kanboard
        
        for elem in elementos_tarefas:
            # Pega o ID único da tarefa para monitorar se surgiu alguma nova
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
# 🟢 INTEGRAÇÃO WHATSFLUX (TECNICO LOGADO)
# ==============================
nome_tecnico, status_whats = get_whatsflux_status()

status_badge = (
    '<span class="status-badge badge-online">🟢 ONLINE</span>'
    if status_whats == "online"
    else '<span class="status-badge badge-offline">🔴 OFFLINE</span>'
)

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

# Se for a primeira execução, apenas salva as tarefas atuais
if st.session_state.ultimo_kanban_tasks is None:
    st.session_state.ultimo_kanban_tasks = tarefas_atuais
else:
    # Verifica se existem novos IDs que não estavam na verificação anterior
    novas_tarefas = [t for t in tarefas_atuais if t not in st.session_state.ultimo_kanban_tasks]
    
    if novas_tarefas:
        # Salva o dia e horário do alerta
        st.session_state.ultima_notificacao_kanban = agora_br.strftime("%d/%m/%Y às %H:%M:%S")
        st.session_state.ultimo_kanban_tasks = tarefas_atuais
        
        # Dispara o Áudio
        play_sound()

# Exibe o alerta do Kanban caso uma notificação recente tenha ocorrido
if st.session_state.ultima_notificacao_kanban:
    st.markdown(f"""
    <div class="kanban-alert">
        🔔 <strong>Nova tarefa criada no Kanban!</strong><br>
        Identificada em: <span style="color: #6366f1; font-weight: bold;">{st.session_state.ultima_notificacao_kanban}</span>
    </div>
    """, unsafe_allow_html=True)

# ==============================
# AUTO ATUALIZAÇÃO
# ==============================
time.sleep(REFRESH)
st.rerun()
