"""ICMPMASTER — painel operacional de medições RIPE Atlas e árvore V1.

Somente leitura dos CSVs criados pelo processo monitoramento_icmp.py.
Não modifica modelo, baseline, histórico ou resultados de coleta.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
PASTA = RAIZ / "data" / "monitoramento"
MEDICOES = PASTA / "medicoes_novas.csv"
PREVISOES = PASTA / "previsoes.csv"
BASELINE = RAIZ / "data" / "processed" / "baseline_por_fluxo.csv"
CLASSES = ("OK", "RISCO", "FALHA")
CORES = {"OK": "#15803d", "RISCO": "#b45309", "FALHA": "#b91c1c"}

st.set_page_config(page_title="ICMPMASTER | Monitoramento", page_icon="📡", layout="wide")
st.title("📡 Monitoramento automático — RIPE Atlas")
st.caption("Coleta periódica via RIPE Atlas • previsão V1: três rodadas (~12 minutos) à frente • horários em UTC")


def ler_csv(caminho: Path) -> pd.DataFrame:
    if not caminho.is_file() or caminho.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(caminho)
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
        st.warning(f"Não foi possível ler {caminho.name}: {exc}. Tentaremos novamente na próxima atualização.")
        return pd.DataFrame()


def preparar_medicoes(df: pd.DataFrame) -> pd.DataFrame:
    necessarias = {"fluxo_id", "timestamp", "rtt_medio_ms", "perda_pct", "jitter_ms"}
    if df.empty or not necessarias.issubset(df.columns):
        return pd.DataFrame()
    d = df.copy()
    d["fluxo_id"] = d["fluxo_id"].astype(str)
    d["timestamp"] = pd.to_datetime(d["timestamp"], utc=True, errors="coerce")
    for campo in ("rtt_medio_ms", "perda_pct", "jitter_ms"):
        d[campo] = pd.to_numeric(d[campo], errors="coerce")
    d = d.dropna(subset=["timestamp", "fluxo_id"])
    return d.sort_values("timestamp").drop_duplicates(["fluxo_id", "timestamp"], keep="last")


def preparar_previsoes(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or not {"fluxo_id", "timestamp", "previsao_12min"}.issubset(df.columns):
        return pd.DataFrame()
    d = df.copy()
    d["fluxo_id"] = d["fluxo_id"].astype(str)
    d["timestamp"] = pd.to_datetime(d["timestamp"], utc=True, errors="coerce")
    d["previsao_12min"] = d["previsao_12min"].astype(str).str.upper()
    return (d.dropna(subset=["timestamp"])
            .loc[lambda x: x["previsao_12min"].isin(CLASSES)]
            .sort_values("timestamp")
            .drop_duplicates(["fluxo_id", "timestamp"], keep="last"))


def classes_observadas(medicoes: pd.DataFrame) -> pd.DataFrame:
    """Reproduz as regras de classe do dataset B; não usa a previsão como rótulo.

    A janela de cinco é reiniciada quando o intervalo entre medições > 10 min.
    Exige cinco observações recentes para não avaliar classes com histórico parcial.
    """
    if medicoes.empty or not BASELINE.exists():
        return pd.DataFrame(columns=["fluxo_id", "timestamp", "classe_observada"])
    base = ler_csv(BASELINE)
    campos = {"fluxo_id", "status", "mediana", "MAD", "iqr", "jitter_tipico"}
    if not campos.issubset(base.columns):
        return pd.DataFrame(columns=["fluxo_id", "timestamp", "classe_observada"])
    base = base.loc[base["status"].eq("ok"), list(campos)].copy()
    base["fluxo_id"] = base["fluxo_id"].astype(str)
    if base["fluxo_id"].duplicated().any():
        st.warning("Baseline com fluxos duplicados: avaliação posterior indisponível.")
        return pd.DataFrame(columns=["fluxo_id", "timestamp", "classe_observada"])
    d = medicoes.merge(base, on="fluxo_id", how="inner", validate="many_to_one")
    if d.empty:
        return pd.DataFrame(columns=["fluxo_id", "timestamp", "classe_observada"])
    d = d.sort_values(["fluxo_id", "timestamp"]).copy()
    for col in ("mediana", "MAD", "iqr", "jitter_tipico"):
        d[col] = pd.to_numeric(d[col], errors="coerce")
    rtt = d["rtt_medio_ms"]
    dif = rtt - d["mediana"]
    denominador = np.where(d["MAD"] > 0, 1.4826 * d["MAD"], np.maximum(d["iqr"] / 1.349, 1.0))
    d["z"] = np.where(rtt.isna(), np.nan, np.where(dif == 0, 0.0, dif / denominador))
    d["aumento"] = np.where(rtt.isna(), np.nan, dif / d["mediana"] * 100)
    jt = d["jitter_tipico"]
    j = d["jitter_ms"]
    d["jrel"] = np.select(
        [(j.isna() | jt.isna()).to_numpy(), (jt == 0).to_numpy()],
        [np.nan, np.where(j == 0, 1.0, 3.0)],
        default=(j / jt.where(jt > 0)).to_numpy(),
    )
    d["timeout"] = (rtt.isna() | d["perda_pct"].eq(100)).astype(int)
    d["aumento80"] = d["aumento"].gt(80).astype(int)
    d["critico"] = (
        (d["z"].ge(2) & d["z"].lt(3.5))
        | (d["aumento"].ge(30) & d["aumento"].le(80))
        | d["jrel"].ge(3)
    ).astype(int)
    # Não misturar medições separadas por lacunas grandes.
    gap = d.groupby("fluxo_id")["timestamp"].diff()
    d["segmento"] = gap.gt(pd.Timedelta(minutes=10)).groupby(d["fluxo_id"]).cumsum()
    grupo = d.groupby(["fluxo_id", "segmento"], sort=False)
    for origem, destino in (("timeout", "n5_timeout"), ("aumento80", "n5_aumento80"), ("critico", "n5_risco")):
        d[destino] = grupo[origem].transform(lambda s: s.rolling(5, min_periods=1).sum())
    falha = d["perda_pct"].ge(10) | d["n5_timeout"].ge(3) | d["z"].ge(3.5) | d["n5_aumento80"].ge(2)
    risco = d["critico"].eq(1) & d["n5_risco"].ge(2)
    d["classe_observada"] = np.select([falha, risco], ["FALHA", "RISCO"], default="OK")
    d["amostras_segmento"] = grupo.cumcount() + 1
    d.loc[d["amostras_segmento"].lt(5), "classe_observada"] = pd.NA
    return d[["fluxo_id", "timestamp", "classe_observada"]]


def avaliar_previsoes(medicoes: pd.DataFrame, previsoes: pd.DataFrame) -> pd.DataFrame:
    """Compara previsão em t com terceira medição POSTERIOR do mesmo fluxo.

    Apenas quando a terceira medição estiver a 8–16 minutos de t, e quando
    a classe observada tiver contexto recente completo. Não usa rótulos futuros
    na inferência; esta função é apenas avaliação retrospectiva.
    """
    if medicoes.empty or previsoes.empty:
        return pd.DataFrame()
    observadas = classes_observadas(medicoes)
    if observadas.empty:
        return pd.DataFrame()
    resultados = []
    for fluxo, grupo in observadas.groupby("fluxo_id"):
        serie = grupo.sort_values("timestamp").reset_index(drop=True)
        previsoes_fluxo = previsoes.loc[previsoes["fluxo_id"].eq(fluxo)]
        if previsoes_fluxo.empty:
            continue
        tempos = serie["timestamp"].to_numpy(dtype="datetime64[ns]")
        for previsao in previsoes_fluxo.itertuples(index=False):
            t = pd.Timestamp(previsao.timestamp)
            # searchsorted(right) garante estritamente posteriores.
            idx = int(np.searchsorted(tempos, t.to_datetime64(), side="right")) + 2
            if idx >= len(serie):
                continue
            futuro = serie.iloc[idx]
            atraso = (futuro["timestamp"] - t).total_seconds() / 60
            if not (8 <= atraso <= 16) or pd.isna(futuro["classe_observada"]):
                continue
            resultados.append({
                "fluxo_id": fluxo,
                "timestamp_previsao": t,
                "previsao_12min": previsao.previsao_12min,
                "timestamp_observado": futuro["timestamp"],
                "classe_observada": futuro["classe_observada"],
                "intervalo_min": round(atraso, 1),
                "classe_atual": serie.iloc[idx - 3]["classe_observada"],
                "acertou": previsao.previsao_12min == futuro["classe_observada"],
            })
    return pd.DataFrame(resultados)


def grafico_serie(serie: pd.DataFrame, campo: str, titulo: str, unidade: str) -> None:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=serie["timestamp"], y=serie[campo], mode="lines+markers", name=titulo))
    fig.update_layout(title=titulo, xaxis_title="Horário (UTC)", yaxis_title=unidade,
                      height=315, margin=dict(l=10, r=10, t=55, b=10))
    st.plotly_chart(fig, use_container_width=True)


def painel() -> None:
    medicoes = preparar_medicoes(ler_csv(MEDICOES))
    previsoes = preparar_previsoes(ler_csv(PREVISOES))
    if medicoes.empty:
        st.warning("Aguardando medições. Execute monitoramento_icmp.py em outro terminal.")
        return

    ultimas = pd.DataFrame()
    if not previsoes.empty:
        ultimas = (previsoes.sort_values("timestamp")
                   .drop_duplicates("fluxo_id", keep="last")
                   .sort_values("timestamp", ascending=False))
    contagens = ultimas["previsao_12min"].value_counts() if not ultimas.empty else pd.Series(dtype=int)
    st.caption("Atualização automática a cada 30 segundos. O coletor deve continuar aberto em outro terminal.")
    a, b, c, d, e, f = st.columns(6)
    a.metric("Medições", f"{len(medicoes):,}")
    b.metric("Fluxos com dados", medicoes["fluxo_id"].nunique())
    c.metric("Previsões registradas", f"{len(previsoes):,}")
    d.metric("🟢 OK", int(contagens.get("OK", 0)))
    e.metric("🟡 RISCO", int(contagens.get("RISCO", 0)))
    f.metric("🔴 FALHA", int(contagens.get("FALHA", 0)))
    ultima_medicao = medicoes["timestamp"].max()
    st.caption(f"Última medição disponível: {ultima_medicao.strftime('%d/%m/%Y %H:%M:%S UTC')}")
    idade = (pd.Timestamp.now(tz="UTC") - ultima_medicao).total_seconds() / 60
    if idade > 20:
        st.warning(f"Dados possivelmente desatualizados: última medição há {idade:.0f} minutos. Confira o terminal do coletor.")

    st.subheader("🚨 Alertas de previsão por fluxo")
    if ultimas.empty:
        st.info("Ainda não há previsões. O coletor aguarda histórico recente por fluxo.")
    else:
        alertas = ultimas.loc[ultimas["previsao_12min"].isin(["RISCO", "FALHA"])].copy()
        if alertas.empty:
            st.success("Nenhum fluxo com última previsão RISCO ou FALHA entre os fluxos que possuem previsão.")
        else:
            for linha in alertas.head(15).itertuples(index=False):
                texto = f"{linha.fluxo_id} — {linha.previsao_12min} (medição {linha.timestamp:%d/%m %H:%M} UTC)"
                if linha.previsao_12min == "FALHA":
                    st.error("🔴 " + texto)
                else:
                    st.warning("🟡 " + texto)
            if len(alertas) > 15:
                st.caption(f"Exibindo 15 de {len(alertas)} alertas. Consulte a tabela abaixo para os demais.")
        st.caption("Alertas são previsões do modelo, não falhas confirmadas. A tabela mostra a última previsão de cada fluxo, inclusive se estiver antiga.")
        tabela = ultimas.copy()
        tabela["status"] = tabela["previsao_12min"].map({"OK": "🟢 OK", "RISCO": "🟡 RISCO", "FALHA": "🔴 FALHA"})
        colunas = ["status", "fluxo_id", "timestamp", "measurement_id", "coletado_em_utc"]
        st.dataframe(tabela[[c for c in colunas if c in tabela.columns]], use_container_width=True, hide_index=True)

    st.subheader("📈 Evolução das medições por fluxo")
    fluxos = sorted(medicoes["fluxo_id"].unique())
    padrao = str(ultimas.iloc[0]["fluxo_id"]) if not ultimas.empty else fluxos[0]
    escolhido = st.selectbox("Selecione o fluxo", fluxos, index=fluxos.index(padrao), key="fluxo_monitoramento")
    serie = medicoes.loc[medicoes["fluxo_id"].eq(escolhido)].sort_values("timestamp").tail(250)
    g1, g2 = st.columns(2)
    with g1:
        grafico_serie(serie, "rtt_medio_ms", "Latência média", "ms")
    with g2:
        grafico_serie(serie, "perda_pct", "Perda de pacotes", "%")
    grafico_serie(serie, "jitter_ms", "Jitter", "ms")
    if not previsoes.empty:
        ps = previsoes.loc[previsoes["fluxo_id"].eq(escolhido)].sort_values("timestamp")
        if not ps.empty:
            fig = go.Figure()
            mapa = {"OK": 0, "RISCO": 1, "FALHA": 2}
            for classe in CLASSES:
                trecho = ps.loc[ps["previsao_12min"].eq(classe)]
                if not trecho.empty:
                    fig.add_trace(go.Scatter(x=trecho["timestamp"], y=[mapa[classe]] * len(trecho),
                                             mode="markers", name=classe,
                                             marker=dict(color=CORES[classe], size=10)))
            fig.update_layout(title="Histórico de previsões V1", height=300,
                              yaxis=dict(tickvals=[0, 1, 2], ticktext=list(CLASSES), range=[-0.4, 2.4]),
                              xaxis_title="Horário da medição (UTC)")
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("🔎 Verificação posterior das previsões")
    st.caption("Compara a previsão em t com a classe calculada pelas regras do projeto na terceira medição posterior "
               "do mesmo fluxo, desde que ocorra entre 8 e 16 minutos depois. Não é validação com falhas externas confirmadas.")
    if previsoes.empty:
        st.info("Sem previsões para avaliar.")
    else:
        avaliadas = avaliar_previsoes(medicoes, previsoes)
        if avaliadas.empty:
            st.info("Ainda não há previsões com três medições posteriores e contexto recente suficiente para comparação.")
        else:
            total = len(avaliadas)
            acertos = int(avaliadas["acertou"].sum())
            x, y, z = st.columns(3)
            x.metric("Previsões avaliáveis", total)
            y.metric("Correspondências", acertos)
            z.metric("Taxa de correspondência", f"{acertos / total:.1%}")
            st.caption("Taxa descritiva apenas das previsões avaliáveis; não equivale à acurácia validada do modelo em produção.")

            # Referência simples: repetir a classe observada no instante da previsão.
            # Isso ajuda a identificar se a árvore acrescenta valor à persistência.
            comparaveis = avaliadas.dropna(subset=["classe_atual"]).copy()
            if not comparaveis.empty:
                comparaveis["acerto_persistencia"] = (
                    comparaveis["classe_atual"] == comparaveis["classe_observada"]
                )
                st.markdown("#### Árvore V1 × persistência da classe atual")
                c1, c2, c3 = st.columns(3)
                taxa_arvore = comparaveis["acertou"].mean()
                taxa_persistencia = comparaveis["acerto_persistencia"].mean()
                c1.metric("Acerto V1 (mesma amostra)", f"{taxa_arvore:.1%}")
                c2.metric("Acerto persistência", f"{taxa_persistencia:.1%}")
                c3.metric("Diferença V1 − persistência", f"{(taxa_arvore - taxa_persistencia) * 100:+.1f} p.p.")
                st.caption("A persistência prevê que a classe continuará igual à classe observada no momento da previsão. "
                           "Ambas são avaliadas nas mesmas observações elegíveis.")

            st.markdown("#### Matriz de confusão — previsões avaliáveis")
            matriz = pd.crosstab(
                pd.Categorical(avaliadas["classe_observada"], categories=CLASSES),
                pd.Categorical(avaliadas["previsao_12min"], categories=CLASSES),
                dropna=False,
            )
            matriz.index = pd.Index(CLASSES, name="Observado")
            matriz.columns = pd.Index(CLASSES, name="Previsto")
            st.dataframe(matriz, use_container_width=True)

            st.markdown("#### Precisão, recall e F1 por classe")
            linhas_metricas = []
            for classe in CLASSES:
                tp = int(((avaliadas["previsao_12min"] == classe) &
                          (avaliadas["classe_observada"] == classe)).sum())
                fp = int(((avaliadas["previsao_12min"] == classe) &
                          (avaliadas["classe_observada"] != classe)).sum())
                fn = int(((avaliadas["previsao_12min"] != classe) &
                          (avaliadas["classe_observada"] == classe)).sum())
                suporte = tp + fn
                precisao = tp / (tp + fp) if tp + fp else 0.0
                recall = tp / suporte if suporte else 0.0
                f1 = 2 * precisao * recall / (precisao + recall) if precisao + recall else 0.0
                linhas_metricas.append({"Classe": classe, "Suporte": suporte,
                                       "Precisão": round(precisao, 3),
                                       "Recall": round(recall, 3), "F1": round(f1, 3)})
            tabela_metricas = pd.DataFrame(linhas_metricas)
            st.dataframe(tabela_metricas, use_container_width=True, hide_index=True)
            st.metric("F1 macro (3 classes)", f"{tabela_metricas['F1'].mean():.3f}")
            st.caption("Quando não há exemplos suficientes de uma classe, sua métrica pode ser zero "
                       "por ausência de suporte. Amostras consecutivas do mesmo fluxo são correlacionadas.")

            st.markdown("#### Cobertura da avaliação")
            st.write(f"{total} de {len(previsoes)} previsões registradas possuem três medições "
                     "posteriores em 8–16 minutos e classe observada calculável "
                     f"({total / len(previsoes):.1%} de cobertura).")
            st.dataframe(avaliadas.sort_values("timestamp_previsao", ascending=False),
                         use_container_width=True, hide_index=True)
            st.download_button("⬇️ Exportar avaliações (CSV)",
                               data=avaliadas.to_csv(index=False).encode("utf-8-sig"),
                               file_name="avaliacao_monitoramento_icmp.csv",
                               mime="text/csv")

    with st.expander("Consultar registros completos"):
        st.markdown("**Histórico de previsões**")
        if not previsoes.empty:
            st.dataframe(previsoes.sort_values("timestamp", ascending=False), use_container_width=True, hide_index=True)
        st.markdown("**Medições recebidas (últimas 500)**")
        st.dataframe(medicoes.sort_values("timestamp", ascending=False).head(500),
                     use_container_width=True, hide_index=True)


st.info("O coletor roda separadamente. Esta página apenas lê os CSVs de monitoramento, sem modificar o modelo ou os dados históricos.")
if st.button("🔄 Atualizar agora"):
    st.rerun()

# Streamlit >= 1.37: atualização nativa por fragmento, sem thread extra.
if hasattr(st, "fragment"):
    @st.fragment(run_every="30s")
    def painel_automatico():
        painel()
    painel_automatico()
else:
    st.warning("Sua versão do Streamlit não suporta atualização automática por fragmentos. "
               "Atualize o Streamlit ou use o botão Atualizar agora.")
    painel()
