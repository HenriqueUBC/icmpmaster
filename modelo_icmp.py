"""Integração da árvore de decisão da Tarefa 4 com o dashboard ICMPMASTER.

Reproduz o preparo das 11 features usado no notebook
`documentos/notebooks/Arvore/Tarefa5_Arvore_Final.ipynb`.

Este módulo não treina nem altera o modelo salvo. A previsão se refere
à classe estimada três rodadas (~12 min) à frente, sob a hipótese de
cadência de quatro minutos das medições originais.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


RAIZ = Path(__file__).resolve().parent
PASTA_MODELO = RAIZ / "documentos" / "notebooks" / "Arvore" / "saida_tarefa4"
ARQ_ARVORE = PASTA_MODELO / "arvore_ajustada.joblib"
ARQ_CONFIG = PASTA_MODELO / "config_modelo.json"

CLASSES = ("OK", "RISCO", "FALHA")
SENTINELA = -999
COLUNAS_TENDENCIA = ("z_delta1", "z_media3_ant", "z_inclin5")


@lru_cache(maxsize=1)
def carregar_modelo():
    """Carrega a árvore existente e a ordem *exata* de features do treino.

    Retorna (arvore, colunas) conforme a interface esperada pelo app.py.
    """
    if not ARQ_ARVORE.is_file():
        raise FileNotFoundError(f"Modelo treinado não encontrado: {ARQ_ARVORE}")
    if not ARQ_CONFIG.is_file():
        raise FileNotFoundError(f"Configuração de features não encontrada: {ARQ_CONFIG}")

    with ARQ_CONFIG.open("r", encoding="utf-8") as arquivo:
        config = json.load(arquivo)

    colunas = config.get("features")
    if not isinstance(colunas, list) or not colunas or not all(
        isinstance(nome, str) for nome in colunas
    ):
        raise ValueError("O config_modelo.json não contém uma lista válida de features.")
    if len(colunas) != len(set(colunas)):
        raise ValueError("Há features duplicadas no config_modelo.json.")

    arvore = joblib.load(ARQ_ARVORE)  # Carregue apenas arquivos do repositório confiável.
    quantidade = getattr(arvore, "n_features_in_", None)
    if quantidade != len(colunas):
        raise ValueError(
            f"Modelo espera {quantidade} features, mas a configuração contém "
            f"{len(colunas)}. Verifique se ambos são da Tarefa 4."
        )

    return arvore, colunas


def adicionar_tendencia(dados: pd.DataFrame) -> pd.DataFrame:
    """Calcula as 3 features temporais idênticas às do notebook da Tarefa 5.

    Para preservar o DataFrame usado pelo dashboard, linhas sem classe
    OK/RISCO/FALHA permanecem na saída, mas não entram no histórico.
    O cálculo é feito por fluxo e em ordem cronológica, sem olhar o futuro.
    As features calculadas são devolvidas às posições originais.
    """
    necessarias = {"fluxo_id", "timestamp", "z_robusto"}
    ausentes = sorted(necessarias - set(dados.columns))
    if ausentes:
        raise ValueError("Colunas necessárias para tendência ausentes: " + ", ".join(ausentes))

    saida = dados.copy()
    for coluna in COLUNAS_TENDENCIA:
        saida[coluna] = np.nan

    # O treino/teste da Tarefa 5 exclui linhas sem classe válida antes dos lags.
    validas = saida["fluxo_id"].notna()
    if "classe" in saida.columns:
        classe_normalizada = saida["classe"].astype("string").str.strip().str.upper()
        validas &= classe_normalizada.isin(CLASSES).fillna(False)

    if not validas.any():
        return saida

    # Índice temporário evita erros de alinhamento quando o índice de entrada
    # não é único e garante a volta à ordem original.
    historico = saida.loc[validas, ["fluxo_id", "timestamp", "z_robusto"]].copy()
    historico["_posicao_original"] = np.flatnonzero(validas.to_numpy())
    historico["timestamp"] = pd.to_datetime(historico["timestamp"], errors="coerce", utc=True)
    historico["z_robusto"] = pd.to_numeric(historico["z_robusto"], errors="coerce")
    historico = historico.sort_values(["fluxo_id", "timestamp"], kind="stable").reset_index(drop=True)

    grupo = historico.groupby("fluxo_id")["z_robusto"]
    anteriores = {k: grupo.shift(k) for k in range(1, 5)}

    historico["z_delta1"] = historico["z_robusto"] - anteriores[1]

    ultimas_tres = pd.concat(
        [anteriores[1], anteriores[2], anteriores[3]], axis=1
    )
    historico["z_media3_ant"] = ultimas_tres.mean(axis=1).where(
        ultimas_tres.notna().sum(axis=1) >= 2
    )

    inclinacao = (
        -2 * anteriores[4]
        - anteriores[3]
        + anteriores[1]
        + 2 * historico["z_robusto"]
    ) / 10
    historico["z_inclin5"] = inclinacao.where(
        anteriores[1].notna()
        & anteriores[2].notna()
        & anteriores[3].notna()
        & anteriores[4].notna()
    )

    posicoes = historico["_posicao_original"].to_numpy()
    for coluna in COLUNAS_TENDENCIA:
        saida.iloc[posicoes, saida.columns.get_loc(coluna)] = historico[coluna].to_numpy()

    return saida


def prever_12min(dados: pd.DataFrame, arvore, colunas: list[str]) -> pd.Series:
    """Prevê OK/RISCO/FALHA nas linhas com classe atual válida.

    Espera `dados` já processado por `adicionar_tendencia`.
    Respeita a ordem de `colunas` e usa -999 para ausências, como no treino.
    Retorna série alinhada ao DataFrame recebido; linhas não classificáveis
    continuam com <NA>.
    """
    ausentes = sorted(set(colunas) - set(dados.columns))
    if ausentes:
        raise ValueError("Features necessárias à previsão ausentes: " + ", ".join(ausentes))

    saida = pd.Series(pd.NA, index=dados.index, dtype="string", name="prevista_12min")
    validas = pd.Series(True, index=dados.index)
    if "classe" in dados.columns:
        validas &= dados["classe"].astype("string").str.strip().str.upper().isin(CLASSES).fillna(False)
    if "fluxo_id" in dados.columns:
        validas &= dados["fluxo_id"].notna()

    if not validas.any():
        return saida

    matriz = dados.loc[validas, colunas].apply(pd.to_numeric, errors="coerce")
    matriz = matriz.replace([np.inf, -np.inf], np.nan).fillna(SENTINELA).to_numpy()
    previstas = arvore.predict(matriz)
    # Atribuição posicional funciona também em DataFrames com índice duplicado.
    saida.iloc[np.flatnonzero(validas.to_numpy())] = previstas
    return saida
