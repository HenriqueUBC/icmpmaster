"""
Página 3 — Simulador de Eventos do ICMPMASTER.

Gera medições sintéticas com base nos baselines do RIPE Atlas
e utiliza a árvore de decisão V1 para prever a qualidade
da rede aproximadamente 12 minutos à frente.

Não executa ping direto.
Não modifica o modelo ou os dados históricos.
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Permite importar módulos da raiz do projeto.
RAIZ = Path(__file__).resolve().parent.parent

if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from simulador_icmp import (
    carregar_baseline,
    executar_simulacao,
)


# ---------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# ---------------------------------------------------------

st.set_page_config(
    page_title="Simulador de Eventos | ICMPMASTER",
    page_icon="🧪",
    layout="wide",
)

st.title("🧪 Simulador de Eventos de Rede")

st.markdown(
    """
    Simule condições de funcionamento normal, degradação e falha
    de rede utilizando **baselines reais do RIPE Atlas**.

    As medições geradas são **100% sintéticas** e processadas
    pela **árvore de decisão V1**, sem retreinamento.
    """
)

st.info(
    "Esta página não realiza ping direto nem consulta a API "
    "do RIPE Atlas. As simulações utilizam somente os "
    "baselines históricos já existentes no projeto."
)


# ---------------------------------------------------------
# CARREGAMENTO DO BASELINE
# ---------------------------------------------------------

@st.cache_data
def obter_baseline():
    return carregar_baseline()


try:
    baseline = obter_baseline()

except (FileNotFoundError, ValueError, OSError) as erro:
    st.error(f"Não foi possível carregar o baseline: {erro}")
    st.stop()


fluxos_validos = baseline.loc[
    baseline["status"].eq("ok")
].copy()

fluxos_validos["mediana"] = pd.to_numeric(
    fluxos_validos["mediana"],
    errors="coerce",
)

fluxos_validos = fluxos_validos.loc[
    fluxos_validos["mediana"].gt(0)
]

fluxos_validos = fluxos_validos.drop_duplicates(
    subset=["fluxo_id"]
)

if fluxos_validos.empty:
    st.warning(
        "Nenhum fluxo com baseline válido foi encontrado."
    )
    st.stop()


# ---------------------------------------------------------
# CONFIGURAÇÃO DA SIMULAÇÃO
# ---------------------------------------------------------

st.subheader("⚙️ Configuração da simulação")

col1, col2 = st.columns(2)

with col1:

    fluxo_id = st.selectbox(
        "Selecione um fluxo do RIPE Atlas",
        options=fluxos_validos["fluxo_id"].astype(str).tolist(),
        help=(
            "Cada fluxo representa uma combinação "
            "entre sonda RIPE Atlas e endereço de destino."
        ),
    )

    cenario = st.selectbox(
        "Selecione o cenário",
        options=["OK", "RISCO", "FALHA"],
        index=1,
    )

with col2:

    quantidade = st.slider(
        "Quantidade de medições sintéticas",
        min_value=6,
        max_value=40,
        value=12,
        step=1,
    )

    semente = st.number_input(
        "Semente aleatória",
        min_value=0,
        max_value=999999,
        value=42,
        step=1,
        help="Utilize a mesma semente para reproduzir o experimento.",
    )


# ---------------------------------------------------------
# EXIBIÇÃO DO BASELINE
# ---------------------------------------------------------

fluxo_selecionado = fluxos_validos.loc[
    fluxos_validos["fluxo_id"].astype(str).eq(fluxo_id)
].iloc[0]

st.markdown("#### 📍 Referência histórica do fluxo")

base1, base2, base3 = st.columns(3)

with base1:
    st.metric(
        "Latência mediana",
        f"{float(fluxo_selecionado['mediana']):.2f} ms",
    )

with base2:
    jitter_tipico = pd.to_numeric(
        fluxo_selecionado["jitter_tipico"],
        errors="coerce",
    )

    st.metric(
        "Jitter típico",
        (
            f"{float(jitter_tipico):.2f} ms"
            if pd.notna(jitter_tipico)
            else "Indisponível"
        ),
    )

with base3:
    st.metric(
        "Cenário selecionado",
        cenario,
    )


# ---------------------------------------------------------
# EXECUÇÃO
# ---------------------------------------------------------

st.divider()

executar = st.button(
    "▶️ Executar simulação",
    type="primary",
    use_container_width=True,
)

if executar:

    with st.spinner(
        "Gerando medições e executando a árvore V1..."
    ):

        try:
            resultado = executar_simulacao(
                cenario=cenario,
                fluxo_id=fluxo_id,
                quantidade=int(quantidade),
                semente=int(semente),
            )

        except (
            ValueError,
            KeyError,
            FileNotFoundError,
            OSError,
        ) as erro:

            st.error(
                f"Erro ao executar a simulação: {erro}"
            )

            st.stop()

    st.session_state["resultado_simulacao"] = resultado

    st.session_state["config_simulacao"] = {
        "fluxo_id": fluxo_id,
        "cenario": cenario,
        "quantidade": quantidade,
        "semente": semente,
    }


# ---------------------------------------------------------
# RESULTADOS
# ---------------------------------------------------------

if "resultado_simulacao" not in st.session_state:

    st.info(
        "Configure os parâmetros e clique em "
        "'Executar simulação' para visualizar os resultados."
    )

    st.stop()


resultado = st.session_state["resultado_simulacao"].copy()

config = st.session_state.get(
    "config_simulacao",
    {},
)

st.subheader("📊 Resultados da simulação")

st.caption(
    "Origem: DADOS SINTÉTICOS | "
    f"Cenário: {config.get('cenario', 'N/D')} | "
    f"Fluxo: {config.get('fluxo_id', 'N/D')}"
)

previsoes_validas = resultado[
    "previsao_12min"
].dropna()

total_previsoes = len(previsoes_validas)

ultima_previsao = (
    str(previsoes_validas.iloc[-1])
    if total_previsoes > 0
    else "Indisponível"
)

erros = resultado[
    "estado_previsao"
].astype(str).str.startswith("ERRO:").sum()

met1, met2, met3, met4 = st.columns(4)

met1.metric(
    "Medições sintéticas",
    len(resultado),
)

met2.metric(
    "Previsões geradas",
    total_previsoes,
)

met3.metric(
    "Última previsão",
    ultima_previsao,
)

met4.metric(
    "Erros de inferência",
    int(erros),
)

if erros:
    st.warning(
        "Algumas medições não puderam ser processadas. "
        "Consulte a tabela para verificar os motivos."
    )


# ---------------------------------------------------------
# GRÁFICO DE LATÊNCIA
# ---------------------------------------------------------

resultado["timestamp"] = pd.to_datetime(
    resultado["timestamp"],
    utc=True,
)

fig_latencia = go.Figure()

fig_latencia.add_trace(
    go.Scatter(
        x=resultado["timestamp"],
        y=resultado["rtt_medio_ms"],
        mode="lines+markers",
        name="Latência sintética",
    )
)

fig_latencia.add_hline(
    y=float(fluxo_selecionado["mediana"]),
    line_dash="dash",
    annotation_text="Baseline RIPE Atlas",
)

fig_latencia.update_layout(
    title="Evolução da latência",
    xaxis_title="Instante simulado",
    yaxis_title="Latência (ms)",
    height=380,
)

st.plotly_chart(
    fig_latencia,
    use_container_width=True,
)


# ---------------------------------------------------------
# GRÁFICOS DE PERDA E JITTER
# ---------------------------------------------------------

graf1, graf2 = st.columns(2)

with graf1:

    fig_perda = go.Figure()

    fig_perda.add_trace(
        go.Scatter(
            x=resultado["timestamp"],
            y=resultado["perda_pct"],
            mode="lines+markers",
            name="Perda de pacotes",
        )
    )

    fig_perda.update_layout(
        title="Perda de pacotes",
        xaxis_title="Instante simulado",
        yaxis_title="Perda (%)",
        yaxis_range=[0, 100],
        height=350,
    )

    st.plotly_chart(
        fig_perda,
        use_container_width=True,
    )

with graf2:

    fig_jitter = go.Figure()

    fig_jitter.add_trace(
        go.Scatter(
            x=resultado["timestamp"],
            y=resultado["jitter_ms"],
            mode="lines+markers",
            name="Jitter sintético",
        )
    )

    fig_jitter.update_layout(
        title="Evolução do jitter",
        xaxis_title="Instante simulado",
        yaxis_title="Jitter (ms)",
        height=350,
    )

    st.plotly_chart(
        fig_jitter,
        use_container_width=True,
    )


# ---------------------------------------------------------
# PREVISÕES DA ÁRVORE
# ---------------------------------------------------------

st.subheader("🌳 Previsões da árvore V1")

contagem = (
    previsoes_validas
    .astype(str)
    .value_counts()
    .reindex(
        ["OK", "RISCO", "FALHA"],
        fill_value=0,
    )
)

fig_previsoes = go.Figure()

fig_previsoes.add_trace(
    go.Bar(
        x=contagem.index.tolist(),
        y=contagem.values.tolist(),
        text=contagem.values.tolist(),
        textposition="auto",
    )
)

fig_previsoes.update_layout(
    title="Distribuição das previsões",
    xaxis_title="Classe prevista",
    yaxis_title="Quantidade",
    height=350,
)

st.plotly_chart(
    fig_previsoes,
    use_container_width=True,
)

st.info(
    "O cenário escolhido representa a degradação artificial "
    "injetada nas medições. A previsão exibida é produzida "
    "pela árvore V1 e representa a condição estimada "
    "aproximadamente 12 minutos à frente."
)


# ---------------------------------------------------------
# TABELA DETALHADA
# ---------------------------------------------------------

st.subheader("📋 Medições e previsões")

colunas_exibicao = [
    "timestamp",
    "fluxo_id",
    "rtt_medio_ms",
    "perda_pct",
    "jitter_ms",
    "cenario_simulado",
    "previsao_12min",
    "estado_previsao",
]

st.dataframe(
    resultado[colunas_exibicao],
    use_container_width=True,
    hide_index=True,
)


# ---------------------------------------------------------
# EXPORTAÇÃO
# ---------------------------------------------------------

st.subheader("📥 Exportar resultados")

csv = resultado.to_csv(
    index=False
).encode("utf-8-sig")

st.download_button(
    label="Baixar resultados sintéticos (CSV)",
    data=csv,
    file_name=(
        f"simulacao_icmpmaster_"
        f"{config.get('cenario', 'cenario').lower()}.csv"
    ),
    mime="text/csv",
    use_container_width=True,
)

st.caption(
    "Os resultados exportados são exclusivamente sintéticos. "
    "Eles não representam medições reais nem devem ser "
    "misturados aos datasets históricos do RIPE Atlas."
)