
"""Alerta auxiliar de FALHA nova ~12 min no futuro para o ICMPMASTER.

NÃO substitui o classificador multiclasse da Tarefa 4.
Modelo selecionado na validação; não afirmar ganho comprovado em dados independentes.

Instalação: colocar na raiz ao lado de app.py e do diretório modelos/.
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import streamlit as st

import modelo_icmp as mi

RAIZ = Path(__file__).resolve().parent
ARQUIVO_AUXILIAR = RAIZ / "modelos" / "alerta_antecipado.joblib"
ARQUIVO_METADATA = RAIZ / "modelos" / "alerta_antecipado_meta.json"
CLASSES_ATUAIS_ELEGIVEIS = ("OK", "RISCO")


@st.cache_resource(show_spinner=False)
def carregar_alerta_auxiliar(caminho: str, modificado_em_ns: int) -> dict:
    """Carrega artefato local confiável; mtime força recarga se atualizado."""
    del modificado_em_ns
    with warnings.catch_warnings():
        from sklearn.exceptions import InconsistentVersionWarning
        warnings.simplefilter("error", InconsistentVersionWarning)
        pacote = joblib.load(caminho)

    if not isinstance(pacote, dict):
        raise ValueError("O artefato auxiliar não é um dicionário.")

    obrigatorios = {"modelo", "features", "limiar", "sentinela"}
    faltantes = obrigatorios - set(pacote)

    if faltantes:
        raise ValueError(f"Artefato auxiliar incompleto: {sorted(faltantes)}")

    modelo = pacote["modelo"]
    features = pacote["features"]

    if not isinstance(features, list) or len(features) != 11 or len(set(features)) != 11:
        raise ValueError("O auxiliar deve possuir as 11 features do treinamento.")

    _, features_oficiais = mi.carregar_modelo()

    if features != features_oficiais:
        raise ValueError("Ordem/features divergentes entre modelos oficial e auxiliar.")

    if getattr(modelo, "n_features_in_", None) != len(features):
        raise ValueError("Número de features incompatível com o classificador auxiliar.")

    if not hasattr(modelo, "predict_proba") or 1 not in list(modelo.classes_):
        raise ValueError("Modelo auxiliar binário inválido: classe positiva 1 ausente.")

    limiar = float(pacote["limiar"])

    if not (0.0 < limiar <= 1.0):
        raise ValueError("Limiar auxiliar deve estar entre 0 (exclusivo) e 1.")

    return pacote


def prever_alerta_auxiliar(dados: pd.DataFrame, pacote: dict) -> pd.DataFrame:
    """Produz alerta apenas para linhas com estado atual OK ou RISCO.

    Não consulta rótulos FUTUROS, `particao` nem y_fut para predizer.
    `classe` é o estado ATUAL, necessário para delimitar o público-alvo.
    """
    features = pacote["features"]

    colunas_obrigatorias = {"classe", "fluxo_id", "timestamp"} | set(features)
    faltantes = colunas_obrigatorias - set(dados.columns)

    if faltantes:
        raise ValueError(f"Colunas obrigatórias ausentes: {sorted(faltantes)}")

    resultado = dados[["fluxo_id", "timestamp", "classe"]].copy()
    resultado["classe"] = resultado["classe"].astype("string").str.strip().str.upper()

    resultado["alerta_falha_nova_12min"] = pd.Series(
        pd.NA, index=resultado.index, dtype="boolean"
    )
    resultado["pontuacao_falha_nova"] = np.nan

    elegiveis = resultado["classe"].isin(CLASSES_ATUAIS_ELEGIVEIS).fillna(False)
    elegiveis &= resultado["fluxo_id"].notna()

    if not elegiveis.any():
        return resultado

    x = dados.loc[elegiveis, features].apply(
        pd.to_numeric, errors="coerce"
    )
    x = x.replace([np.inf, -np.inf], np.nan).fillna(
        float(pacote["sentinela"])
    )

    proba = pacote["modelo"].predict_proba(x.to_numpy())
    indice_positivo = list(pacote["modelo"].classes_).index(1)
    pontuacao = proba[:, indice_positivo]

    alertas = pontuacao >= float(pacote["limiar"])

    resultado.loc[elegiveis, "pontuacao_falha_nova"] = pontuacao
    resultado.loc[elegiveis, "alerta_falha_nova_12min"] = alertas

    return resultado


def renderizar_painel_alerta(dados: pd.DataFrame) -> None:
    """Painel separado do dashboard oficial, sem sobrescrever sua previsão."""
    st.divider()
    st.header("Alerta antecipado de FALHA nova")

    st.caption(
        "Funcionalidade experimental: busca avisar se uma conexão que está "
        "em OK/RISCO poderá entrar em FALHA em aproximadamente 12 minutos. "
        "Os registros exibidos são HISTÓRICOS, não monitoramento em tempo real."
    )

    if not ARQUIVO_AUXILIAR.is_file():
        st.info(
            "Modelo auxiliar ainda não instalado em "
            "modelos/alerta_antecipado.joblib."
        )
        return

    with st.expander("Exibir análise exploratória de alertas", expanded=False):
        st.warning(
            "Na validação usada para selecionar o modelo, houve mais antecipações "
            "de falhas, mas também mais falsos alarmes. O ganho não foi confirmado "
            "em um conjunto de teste independente. Não utilizar para alertas operacionais."
        )

        try:
            pacote = carregar_alerta_auxiliar(
                str(ARQUIVO_AUXILIAR),
                ARQUIVO_AUXILIAR.stat().st_mtime_ns
            )

            dados_preparados = dados

            if not set(
                ("z_delta1", "z_media3_ant", "z_inclin5")
            ).issubset(dados.columns):
                dados_preparados = mi.adicionar_tendencia(dados)

            alertas = prever_alerta_auxiliar(dados_preparados, pacote)

        except Exception as exc:
            st.error("Não foi possível carregar ou executar o alerta auxiliar.")
            st.code(f"{type(exc).__name__}: {exc}")
            return

        elegiveis = alertas["alerta_falha_nova_12min"].notna()
        positivos = alertas["alerta_falha_nova_12min"].fillna(False)

        a, b, c = st.columns(3)

        a.metric(
            "Registros elegíveis (histórico)",
            f"{int(elegiveis.sum()):,}".replace(",", ".")
        )

        b.metric(
            "Alertas retrospectivos",
            f"{int(positivos.sum()):,}".replace(",", ".")
        )

        c.metric(
            "Limiar configurado",
            f"{float(pacote['limiar']):.0%}"
        )

        tabela = alertas.loc[
            positivos,
            ["timestamp", "fluxo_id", "classe", "pontuacao_falha_nova"]
        ].copy()

        tabela["timestamp"] = pd.to_datetime(
            tabela["timestamp"], utc=True, errors="coerce"
        )

        tabela = tabela.sort_values(
            "timestamp", ascending=False
        ).head(200)

        tabela = tabela.rename(columns={
            "classe": "estado_atual",
            "pontuacao_falha_nova": "pontuacao_modelo_nao_calibrada",
        })

        st.dataframe(
            tabela,
            use_container_width=True,
            hide_index=True
        )

        st.caption(
            "Mostrando até 200 alertas históricos mais recentes. A pontuação não "
            "é uma probabilidade calibrada. Esta seção não altera a coluna "
            "'prevista_12min' da árvore oficial."
        )

        if ARQUIVO_METADATA.is_file():
            with st.expander("Parâmetros e limitações do experimento"):
                st.json(
                    json.loads(
                        ARQUIVO_METADATA.read_text(encoding="utf-8")
                    )
                )
