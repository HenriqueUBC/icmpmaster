"""Monitoramento ao vivo: ping real em 1-2 IPs + botão "Simular evento"."""
import math
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ao_vivo as av  # noqa: E402

COR = {"OK": "#2ca02c", "RISCO": "#f2b705", "FALHA": "#d62728"}
EMOJI = {"OK": "🟢", "RISCO": "🟡", "FALHA": "🔴"}

st.set_page_config(page_title="ICMPMASTER | Ao vivo", page_icon="📡", layout="wide")
st.title("📡 Monitoramento ao vivo")

if not av.ARQ_ARVORE.exists():
    st.error(f"Árvore não encontrada: {av.ARQ_ARVORE}")
    st.stop()

S = st.session_state
S.setdefault("estado", {})

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("Alvos")
    h1 = st.text_input("IP/host 1", value="192.168.0.1")
    h2 = st.text_input("IP/host 2 (opcional)", value="8.8.8.8")
    intervalo = st.slider("Intervalo entre medições (s)", 3, 30, 5)
    n_aquec = st.slider("Medições para montar o baseline", 10, 60, av.MIN_RTT_AO_VIVO)
    usar_salvo = st.checkbox("Reaproveitar baseline salvo", value=True)
    st.toggle("Monitorar ao vivo", key="rodando")
    if st.button("Zerar histórico e baseline"):
        S.estado = {}

hosts = []
for h in (h1.strip(), h2.strip()):
    if not h or h in hosts:
        continue
    if not av._RE_HOST.match(h):
        st.error(f"Host inválido: {h!r}")
        st.stop()
    hosts.append(h)
if not hosts:
    st.info("Informe ao menos um IP na barra lateral.")
    st.stop()

for h in hosts:
    if h not in S.estado:
        b = av.carregar_baseline(h) if usar_salvo else None
        S.estado[h] = {"aquec": [], "fluxo": av.FluxoAoVivo(h, b) if b else None,
                       "hist": [], "sim": None}

st.info(
    "**Status (árvore)** = classe que a árvore da Tarefa 4 atribui a cada nova medição "
    "(estimativa para 3 rodadas à frente). **Regra** = estado atual pela tabela da Tarefa 2. "
    "Medições **reais** (ping ao vivo) aparecem como círculos; **simuladas**, como losangos."
)

# ---------------------------------------------------------------- simulador
st.subheader("Simulador de eventos")
c = st.columns([2, 3, 1, 2])
host_alvo = c[0].selectbox("Dispositivo", hosts)
nome_cen = c[1].selectbox("Evento", list(av.CENARIOS))
rodadas = c[2].number_input("Rodadas", min_value=5, max_value=15, value=6)
if c[3].button("⚠️ SIMULAR EVENTO", type="primary"):
    est = S.estado[host_alvo]
    cenario = av.CENARIOS[nome_cen]
    if est["fluxo"] is None:
        st.warning("Aguarde o baseline do dispositivo antes de simular.")
    elif cenario == "RISCO" and not av.risco_simulavel(est["fluxo"].baseline):
        st.error("Baseline com resolução grossa (ex.: ping do Windows, 1 ms): RISCO não é simulável "
                 "neste alvo. Use um alvo com RTT maior ou o evento de FALHA.")
    else:
        est["sim"] = {"cenario": cenario, "restantes": int(rodadas)}
st.caption(
    "RISCO precisa de ~5 rodadas seguidas para a árvore reconhecer. Em 'perda total', a regra da "
    "Tarefa 2 marca FALHA, mas a árvore costuma responder OK (limitação conhecida: casos FALHA→OK "
    "do teste da Tarefa 5)."
)


# ------------------------------------------------------------------- coleta
def coletar():
    with ThreadPoolExecutor(max_workers=len(hosts)) as ex:
        medicoes = list(ex.map(av.medir_ping, hosts))
    for h, med in zip(hosts, medicoes):
        est = S.estado[h]
        if est["fluxo"] is None:
            est["aquec"].append(med)
            ok = [m for m in est["aquec"] if not math.isnan(m["rtt_medio_ms"])]
            if len(ok) >= n_aquec:
                b = av.calcular_baseline([m["rtt_medio_ms"] for m in ok],
                                         [m["jitter_ms"] for m in ok])
                try:
                    av.salvar_baseline(h, b)
                except OSError:
                    pass
                est["fluxo"], est["aquec"] = av.FluxoAoVivo(h, b), []
            continue
        sim = est["sim"]
        if sim and sim["restantes"] > 0:
            med = av.simular_medicao(med, sim["cenario"], est["fluxo"].baseline)
            sim["restantes"] -= 1
        est["hist"] = (est["hist"] + [est["fluxo"].processar(med)])[-300:]


def grafico(h, df, baseline):
    fig = go.Figure()
    y = df["rtt_medio_ms"].where(df["rtt_medio_ms"].notna(), 0)   # timeout plotado em 0
    fig.add_trace(go.Scatter(x=df["timestamp"], y=y, mode="lines",
                             line=dict(color="lightgray"), showlegend=False))
    for classe in av.CLASSES:
        for origem, simbolo in (("real", "circle"), ("simulada", "diamond")):
            sub = df[(df["classe_arvore"] == classe) & (df["origem"] == origem)]
            if sub.empty:
                continue
            fig.add_trace(go.Scatter(
                x=sub["timestamp"], y=y.loc[sub.index], mode="markers",
                marker=dict(color=COR[classe], symbol=simbolo, size=11),
                name=f"{classe} · {origem}"))
    fig.add_hline(y=baseline.mediana, line_dash="dot", annotation_text="mediana do baseline")
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10),
                      yaxis_title="RTT (ms)", xaxis_title="")
    return fig


def mostrar():
    for h in hosts:
        est = S.estado[h]
        st.markdown(f"### {h}")
        if est["fluxo"] is None:
            n = sum(not math.isnan(m["rtt_medio_ms"]) for m in est["aquec"])
            st.progress(min(n / n_aquec, 1.0), text=f"Montando baseline: {n}/{n_aquec} medições")
            if not S.get("rodando"):
                st.info("Ative **Monitorar ao vivo** na barra lateral.")
            continue
        if not est["hist"]:
            st.info("Aguardando a primeira medição…")
            continue
        df = pd.DataFrame(est["hist"])
        u = est["hist"][-1]
        m = st.columns(5)
        m[0].metric("Status (árvore)", f"{EMOJI[u['classe_arvore']]} {u['classe_arvore']}")
        m[1].metric("Regra (estado atual)", f"{EMOJI[u['classe_regra']]} {u['classe_regra']}")
        m[2].metric("Origem da medição", "SIMULADA" if u["origem"] == "simulada" else "REAL")
        rtt = u["rtt_medio_ms"]
        m[3].metric("RTT (ms)", "timeout" if math.isnan(rtt) else f"{rtt:.2f}")
        m[4].metric("Perda (%)", f"{u['perda_pct']:.0f}")
        st.plotly_chart(grafico(h, df.tail(60).reset_index(drop=True), est["fluxo"].baseline),
                        use_container_width=True, key=f"graf_{h}")
        tabela = df.tail(15).iloc[::-1][["timestamp", "origem", "cenario", "rtt_medio_ms",
                                         "perda_pct", "z_robusto", "classe_regra", "classe_arvore"]]
        st.dataframe(tabela, use_container_width=True, hide_index=True)


@st.fragment(run_every=intervalo if S.get("rodando") else None)
def painel():
    if S.get("rodando"):
        coletar()
    mostrar()


painel()
