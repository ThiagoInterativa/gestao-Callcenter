import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import unicodedata
import altair as alt  
import json
import os

# ==============================
# CONFIG
# ==============================
st.set_page_config(layout="wide", page_title="NOC Call Center")

LOGIN_URL = "https://pabx.evence.com.br/login"
MONITOR_URL = "https://pabx.evence.com.br/callcenter/monitoramentoAgentes/detalhes?agentes=46,47,49,50,52,53"

KANBAN_LOGIN_URL = "https://kanban.interativanet.com.br/?controller=AuthController&action=check"
KANBAN_URL = "https://kanban.interativanet.com.br/?controller=ProjectOverviewController&action=show&project_id=1&search=status%3Aopen"

EMAIL = st.secrets["EMAIL"]
SENHA = st.secrets["SENHA"]
KANBAN_USER = st.secrets["KANBAN_USER"]
KANBAN_PASS = st.secrets["KANBAN_PASS"]

REFRESH = 30  # segundos
TAREFAS_FILE = "tarefas_pendentes.json"

# ==============================
# CSS NOC + EFEITOS
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

.kanban-card {
    background-color: #1e293b;
    border-left: 5px solid #3b82f6;
    padding: 15px;
    border-radius: 8px;
    margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)

# Audio de Alerta (Som de Notificação moderno via Base64/HTML)
def play_sound():
    # Usando um áudio público de notificação limpo
    audio_url = "https://assets.mixkit.co/active_storage/sfx/2869/2869-500.wav"
    sound_html = f"""
    <iframe src="{audio_url}" allow="autoplay" style="display:none" id="iframeAudio"></iframe>
    <audio autoplay><source src="{audio_url}" type="audio/wav"></audio>
    """
    st.markdown(sound_html, unsafe_allow_html=True)

# ==============================
# PERSISTÊNCIA DAS TAREFAS
# ==============================
def carregar_tarefas_salvas():
    if os.path.exists(TAREFAS_FILE):
        try:
            with open(TAREFAS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def salvar_tarefas(tarefas):
    with open(TAREFAS_FILE, "w", encoding="utf-8") as f:
        json.dump(tarefas, f, indent=4, ensure_ascii=False)

# Inicializar no session_state
if "tarefas_kanban" not in st.session_state:
    st.session_state.tarefas_kanban = carregar_tarefas_salvas()

if "play_alert" not in st.session_state:
    st.session_state.play_alert = False

# ==============================
# UTILS
# ==============================
def remover_acentos(txt):
    return ''.join(
        c for c in unicodedata.normalize('NFD', txt)
        if unicodedata.category(c) != 'Mn'
    )

# ==============================
# LOGIN PABX
# ==============================
def login():
    session = requests.Session()
    try:
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
    except Exception:
        return None

# ==============================
# LOGIN KANBAN
# ==============================
def login_kanban():
    session = requests.Session()
    try:
        # Pega a página de login para iniciar cookies/CSRF se houver
        r = session.get("https://kanban.interativanet.com.br/?controller=AuthController&action=login")
        soup = BeautifulSoup(r.text, "html.parser")
        
        # Procura token CSRF se o Kanban exigir
        csrf_token = soup.find("input", {"name": "csrf_token"})
        
        payload = {
            "username": KANBAN_USER,
            "password": KANBAN_PASS
        }
        if csrf_token:
            payload["csrf_token"] = csrf_token["value"]

        res = session.post(KANBAN_LOGIN_URL, data=payload)
        return session
    except Exception:
        return None

# ==============================
# PEGAR AGENTES
# ==============================
def get_agentes(session):
    try:
        r = session.get(MONITOR_URL)
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
# RASPAGEM E ATUALIZAÇÃO KANBAN
# ==============================
def atualizar_kanban(session_kb):
    if not session_kb:
        return
    
    try:
        r = session_kb.get(KANBAN_URL)
        soup = BeautifulSoup(r.text, "html.parser")
        
        atividades = soup.find_all("div", class_="activity-content")
        
        tarefas_atuais = st.session_state.tarefas_kanban.copy()
        houve_alteracao = False
        disparar_som = False

        # Processar da atividade mais antiga para a mais recente
        for atividade in reversed(atividades):
            title_p = atividade.find("p", class_="activity-title")
            if not title_p:
                continue
                
            texto_acao = title_p.get_text(" ", strip=True)
            link_task = title_p.find("a")
            date_span = title_p.find("small", class_="activity-date")
            
            if not link_task or not date_span:
                continue
                
            task_id = link_task.get_text(strip=True) # Ex: "#5127"
            data_atividade = date_span.get_text(strip=True)
            
            desc_div = atividade.find("div", class_="activity-description")
            titulo_tarefa = desc_div.find("p", class_="activity-task-title").get_text(strip=True) if desc_div else "Sem título"

            # Caso 1: Criou a tarefa
            if "criou a tarefa" in texto_acao:
                if task_id not in tarefas_atuais:
                    tarefas_atuais[task_id] = {
                        "titulo": titulo_tarefa,
                        "data_criacao": data_atividade,
                        "status": "Pendente"
                    }
                    houve_alteracao = True
                    disparar_som = True

            # Caso 2: Finalizou a tarefa (Remove da lista)
            elif "finalizou a tarefa" in texto_acao:
                if task_id in tarefas_atuais:
                    del tarefas_atuais[task_id]
                    houve_alteracao = True

        if houve_alteracao:
            st.session_state.tarefas_kanban = tarefas_atuais
            salvar_tarefas(tarefas_atuais)
            if disparar_som:
                st.session_state.play_alert = True

    except Exception as e:
        st.sidebar.error(f"Erro ao ler Kanban: {e}")

# ==============================
# EXECUÇÃO DO FLUXO DO APP
# ==============================
st.markdown('<div class="title">📡 Gestor de Call Center & NOC</div>', unsafe_allow_html=True)

# Tocar som se houver flag ativa na sessão
if st.session_state.play_alert:
    play_sound()
    st.session_state.play_alert = False  # Reseta para não dar loop infinito de som

# Sessão persistente PABX
if "session" not in st.session_state or not st.session_state.session:
    st.session_state.session = login()

# Sessão persistente Kanban
if "session_kanban" not in st.session_state or not st.session_state.session_kanban:
    st.session_state.session_kanban = login_kanban()

session = st.session_state.session
session_kb = st.session_state.session_kanban

if not session:
    st.error("Erro no login do PABX")
    st.stop()

# Coleta de dados
agentes = get_agentes(session)
atualizar_kanban(session_kb)

# ==============================
# CONTADORES
# ==============================
livres = sum(1 for _, s in agentes if s == "livre")
ocupados = sum(1 for _, s in agentes if s == "ocupado")
pausa = sum(1 for _, s in agentes if s == "pausa")

agora_br = datetime.now(ZoneInfo("America/Sao_Paulo"))

# Salvar histórico de NOC
registro = {
    "time": agora_br,
    "livres": int(livres),
    "ocupados": int(ocupados),
    "pausa": int(pausa)
}
st.session_state.historico.append(registro)

# ==============================
# LAYOUT PRINCIPAL: DASHBOARD & KANBAN
# ==============================
col_noc, col_kanban = st.columns([2, 1])

with col_noc:
    st.subheader("📊 Status dos Agentes")
    card1, card2, card3 = st.columns(3)
    with card1:
        st.markdown(f'<div class="big-card green">🟢 {livres}<br>Livres</div>', unsafe_allow_html=True)
    with card2:
        st.markdown(f'<div class="big-card red">🔴 {ocupados}<br>Ocupados</div>', unsafe_allow_html=True)
    with card3:
        st.markdown(f'<div class="big-card yellow">🟡 {pausa}<br>Pausa</div>', unsafe_allow_html=True)

    # Gráfico Histórico
    df_hist = pd.DataFrame(st.session_state.historico)
    if not df_hist.empty:
        df_hist["time"] = pd.to_datetime(df_hist["time"], errors="coerce")
        df_hist = df_hist.dropna(subset=["time"]).sort_values("time")
        
        for col in ["livres", "ocupados", "pausa"]:
            if col not in df_hist.columns:
                df_hist[col] = 0
        df_hist[["livres", "ocupados", "pausa"]] = df_hist[["livres", "ocupados", "pausa"]].fillna(0).astype(int)

        series = ["livres", "ocupados"]
        if df_hist["pausa"].sum() > 0:
            series.append("pausa")

        df_plot = df_hist.copy()
        for col in ["livres", "ocupados"]:
            df_plot[col] = df_plot[col].replace(0, None)

        df_melt = df_plot.melt(id_vars=["time"], value_vars=series, var_name="Status", value_name="Quantidade")
        color_map = {"livres": "#22c55e", "ocupados": "#ef4444", "pausa": "#eab308"}
        color_scale = alt.Scale(domain=list(color_map.keys()), range=list(color_map.values()))

        chart = alt.Chart(df_melt).mark_line(point=True).encode(
            x=alt.X("time:T", axis=alt.Axis(format="%H:%M"), title="Horário (Brasil)"),
            y=alt.Y("Quantidade:Q", scale=alt.Scale(domain=[0, 9]), axis=alt.Axis(tickMinStep=1)),
            color=alt.Color("Status:N", scale=color_scale),
            tooltip=["time:T", "Status", "Quantidade"]
        ).properties(height=300)
        
        st.altair_chart(chart, use_container_width=True)

with col_kanban:
    st.subheader("🔔 Tarefas Kanban Ativas")
    
    tarefas_exibidas = st.session_state.tarefas_kanban
    if tarefas_exibidas:
        for t_id, info in tarefas_exibidas.items():
            st.markdown(f"""
            <div class="kanban-card">
                <strong>Tarefa {t_id} Criada {info['data_criacao']}</strong><br>
                <small>Assunto: {info['titulo']}</small><br>
                <span style="color:#f59e0b; font-weight:bold;">Status: {info['status']}</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Nenhuma tarefa pendente no momento.")

# ==============================
# TABELA DE AGENTES (Fundo)
# ==============================
st.write("---")
st.subheader("👨‍💻 Agentes de Plantão")
df_agentes = pd.DataFrame(agentes, columns=["Nome", "Status"])
st.dataframe(df_agentes, use_container_width=True)

# ==============================
# AUTO REFRESH
# ==============================
time.sleep(REFRESH)
st.rerun()
