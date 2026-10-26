
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

import modelo_icmp as mi


# ============================================================
# CONFIGURAÇÃO
# ============================================================

st.set_page_config(
    page_title="ICMPMASTER | Dashboard",
    page_icon="📡",
    layout="wide",
)

RAIZ = Path(__file__).resolve().parent
ARQUIVO = RAIZ / "data" / "processed" / "dataset_rotulado_B.csv"

CLASSES = ["OK", "RISCO", "FALHA"]


# ============================================================
# CABEÇALHO
# ============================================================

st.title("📡 ICMPMASTER")
st.subheader("Dashboard de análise de rede")

st.info(
    "Modo histórico com árvore de decisão: os dados já foram coletados e "
    "processados, e a árvore da Tarefa 4 classifica o estado esperado em "
    "12 minutos de cada medição. Ainda não há monitoramento ao vivo. "
    "Use a página Simulador de eventos (menu lateral) para testar OK, "
    "RISCO e FALHA."
)


# ============================================================
# CARREGAMENTO DOS DADOS
# ============================================================

@st.cache_data
def carregar_dados(caminho):
    """Lê o dataset rotulado e acrescenta a previsão da árvore (12 min)."""
    dados = pd.read_csv(caminho)
    dados["timestamp"] = pd.to_datetime(dados["timestamp"], errors="coerce", utc=True)
    if mi.ARQ_ARVORE.exists() and {"fluxo_id", "z_robusto"} <= set(dados.columns):
        arvore, colunas = mi.carregar_modelo()
        dados = mi.adicionar_tendencia(dados)
        dados["prevista_12min"] = mi.prever_12min(dados, arvore, colunas)
    return dados


if not ARQUIVO.exists():
    st.error(f"Arquivo não encontrado: {ARQUIVO}")
    st.info(
        "Confirme se o arquivo dataset_rotulado_B.csv "
        "está na pasta data/processed."
    )
    st.stop()

try:
    df = carregar_dados(str(ARQUIVO))
except Exception as erro:
    st.error(f"Não foi possível carregar o dataset: {erro}")
    st.stop()


# ============================================================
# VALIDAÇÃO DAS COLUNAS
# ============================================================

colunas_obrigatorias = {
    "timestamp",
    "fluxo_id",
    "z_robusto",
    "classe",
}

colunas_ausentes = colunas_obrigatorias - set(df.columns)

if colunas_ausentes:
    st.error(
        "O dataset não possui as colunas obrigatórias: "
        + ", ".join(sorted(colunas_ausentes))
    )
    st.write("Colunas encontradas:", list(df.columns))
    st.stop()


# ============================================================
# PREPARAÇÃO DOS DADOS
# ============================================================

df["timestamp"] = pd.to_datetime(
    df["timestamp"],
    errors="coerce",
    utc=True,
)

df["classe"] = df["classe"].astype("string").str.strip().str.upper()

colunas_numericas = [
    "z_robusto",
    "aumento_pct",
    "jitter_relativo",
    "perda_pct",
    "timeout_atual",
    "n5_timeout",
    "n5_aumento80",
    "n5_risco",
]

for coluna in colunas_numericas:
    if coluna in df.columns:
        df[coluna] = pd.to_numeric(
            df[coluna],
            errors="coerce",
        )


# ============================================================
# FILTROS LATERAIS
# ============================================================

st.sidebar.header("Filtros")

classes_disponiveis = [
    classe
    for classe in CLASSES
    if classe in df["classe"].dropna().unique()
]

classes_selecionadas = st.sidebar.multiselect(
    "Classificações",
    options=classes_disponiveis,
    default=classes_disponiveis,
)

fluxos_disponiveis = sorted(
    df["fluxo_id"].dropna().astype(str).unique()
)

fluxos_selecionados = st.sidebar.multiselect(
    "Fluxos",
    options=fluxos_disponiveis,
    default=[],
    help="Deixe vazio para incluir todos os fluxos.",
)

datas_validas = df["timestamp"].dropna()

periodo = None

if not datas_validas.empty:
    data_minima = datas_validas.min().date()
    data_maxima = datas_validas.max().date()

    periodo = st.sidebar.date_input(
        "Período (UTC)",
        value=(data_minima, data_maxima),
        min_value=data_minima,
        max_value=data_maxima,
    )


# ============================================================
# APLICAÇÃO DOS FILTROS
# ============================================================

filtrado = df[
    df["classe"].isin(classes_selecionadas)
].copy()

if fluxos_selecionados:
    filtrado = filtrado[
        filtrado["fluxo_id"].astype(str).isin(
            fluxos_selecionados
        )
    ]

if periodo and len(periodo) == 2:
    data_inicio = pd.Timestamp(periodo[0], tz="UTC")
    data_fim = (
        pd.Timestamp(periodo[1], tz="UTC")
        + pd.Timedelta(days=1)
    )

    filtrado = filtrado[
        filtrado["timestamp"].ge(data_inicio)
        & filtrado["timestamp"].lt(data_fim)
    ]


# ============================================================
# INDICADORES GERAIS
# ============================================================

st.divider()
st.header("Visão geral")

total_medicoes = len(filtrado)
total_fluxos = filtrado["fluxo_id"].nunique()

total_falhas = int(
    (filtrado["classe"] == "FALHA").sum()
)

total_riscos = int(
    (filtrado["classe"] == "RISCO").sum()
)

z_validos = filtrado["z_robusto"].dropna()

desvio_medio = (
    f"{z_validos.mean():.2f}"
    if not z_validos.empty
    else "Sem dados"
)

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Medições",
    f"{total_medicoes:,}".replace(",", "."),
)

c2.metric(
    "Fluxos",
    f"{total_fluxos:,}".replace(",", "."),
)

c3.metric(
    "Registros de falha",
    f"{total_falhas:,}".replace(",", "."),
)

c4.metric(
    "Desvio robusto médio",
    desvio_medio,
)

if filtrado.empty:
    st.warning(
        "Nenhum registro corresponde aos filtros selecionados."
    )
    st.stop()


# ============================================================
# GRÁFICO HISTÓRICO
# ============================================================

st.divider()
st.header("Histórico das medições")

serie = (
    filtrado.dropna(
        subset=["timestamp", "z_robusto"]
    )
    .sort_values("timestamp")
)

if not serie.empty:
    fig_historico = px.line(
        serie,
        x="timestamp",
        y="z_robusto",
        color="fluxo_id",
        title="Evolução do desvio robusto por fluxo",
        labels={
            "timestamp": "Data e hora (UTC)",
            "z_robusto": "Desvio robusto (z)",
            "fluxo_id": "Fluxo",
        },
    )

    st.plotly_chart(
        fig_historico,
        use_container_width=True,
    )
else:
    st.warning(
        "Não existem valores válidos para o gráfico histórico."
    )


# ============================================================
# DISTRIBUIÇÃO DAS CLASSIFICAÇÕES
# ============================================================

st.divider()
st.header("Análise das classificações")

coluna_esquerda, coluna_direita = st.columns(2)

with coluna_esquerda:
    contagem_classes = (
        filtrado["classe"]
        .value_counts()
        .reindex(CLASSES, fill_value=0)
        .rename_axis("Classe")
        .reset_index(name="Quantidade")
    )

    fig_classes = px.bar(
        contagem_classes,
        x="Classe",
        y="Quantidade",
        color="Classe",
        title="Distribuição das classificações",
        category_orders={"Classe": CLASSES},
    )

    st.plotly_chart(
        fig_classes,
        use_container_width=True,
    )

with coluna_direita:
    resumo_classes = pd.DataFrame({
        "Classificação": CLASSES,
        "Quantidade": [
            int((filtrado["classe"] == classe).sum())
            for classe in CLASSES
        ],
    })

    fig_pizza = px.pie(
        resumo_classes,
        names="Classificação",
        values="Quantidade",
        title="Proporção das classificações",
        hole=0.4,
    )

    st.plotly_chart(
        fig_pizza,
        use_container_width=True,
    )


# ============================================================
# FALHAS E RISCOS POR FLUXO
# ============================================================

st.divider()
st.header("Falhas e riscos por fluxo")

resumo_fluxos = (
    filtrado.groupby("fluxo_id", as_index=False)
    .agg(
        Medições=("classe", "size"),
        Falhas=(
            "classe",
            lambda valores: (valores == "FALHA").sum(),
        ),
        Riscos=(
            "classe",
            lambda valores: (valores == "RISCO").sum(),
        ),
    )
)

fig_fluxos = px.bar(
    resumo_fluxos,
    x="fluxo_id",
    y=["Falhas", "Riscos"],
    barmode="group",
    title="Quantidade de falhas e riscos por fluxo",
    labels={
        "fluxo_id": "Fluxo",
        "value": "Quantidade",
        "variable": "Classificação",
    },
)

st.plotly_chart(
    fig_fluxos,
    use_container_width=True,
)


# ============================================================
# PREVISÃO DA ÁRVORE (ESTADO ESPERADO EM 12 MIN)
# ============================================================

st.divider()
st.header("Previsão da árvore de decisão")

if "prevista_12min" in filtrado.columns:
    st.caption(
        "Classe atual = tabela de rotulagem da Tarefa 2. "
        "Prevista em 12 min = árvore ajustada da Tarefa 4 (11 colunas "
        "relativas ao baseline). No teste da Tarefa 5 ela ficou muito "
        "próxima de repetir a classe atual, então o entregável é um "
        "detector, não um preditor."
    )
    cruzado = (
        pd.crosstab(
            filtrado["classe"].rename("Classe atual"),
            filtrado["prevista_12min"].rename("Prevista em 12 min"),
        )
        .reindex(index=CLASSES, columns=CLASSES, fill_value=0)
    )
    st.dataframe(cruzado, use_container_width=True)
else:
    st.warning(
        "Árvore não encontrada em "
        "documentos/notebooks/Arvore/saida_tarefa4/arvore_ajustada.joblib."
    )


# ============================================================
# TABELA DE REGISTROS
# ============================================================

st.divider()
st.header("Registros filtrados")

colunas_tabela = [
    coluna
    for coluna in [
        "timestamp",
        "fluxo_id",
        "z_robusto",
        "aumento_pct",
        "jitter_relativo",
        "perda_pct",
        "timeout_atual",
        "n5_timeout",
        "n5_aumento80",
        "n5_risco",
        "classe",
        "prevista_12min",
        "particao",
    ]
    if coluna in filtrado.columns
]

tabela = filtrado[colunas_tabela].sort_values(
    "timestamp",
    ascending=False,
)

st.dataframe(
    tabela,
    use_container_width=True,
    hide_index=True,
)

st.caption(
    "ICMPMASTER — dashboard de análise histórica. "
    "A coluna classe é a do dataset rotulado (Tarefa 2); "
    "prevista_12min vem da árvore da Tarefa 4. "
    "Sem monitoramento ao vivo."
)
