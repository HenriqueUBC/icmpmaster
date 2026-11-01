"""
Simulador de eventos de rede do ICMPMASTER.

Gera medições SINTÉTICAS de latência, perda de pacotes e jitter,
utilizando como referência os baselines reais do RIPE Atlas.

Cenários:
    OK
    RISCO
    FALHA

As medições simuladas são processadas pela árvore ICMP V1 original,
por meio do preditor_icmp.py.

IMPORTANTE:
- Não realiza ping direto.
- Não consulta a API do RIPE Atlas.
- Não modifica o baseline.
- Não modifica o modelo treinado.
- Não mistura dados sintéticos com medições reais.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from preditor_icmp import prever_medicao


RAIZ = Path(__file__).resolve().parent

CAMINHO_BASELINE = (
    RAIZ / "data" / "processed" / "baseline_por_fluxo.csv"
)

CENARIOS = ("OK", "RISCO", "FALHA")


def carregar_baseline() -> pd.DataFrame:
    """Carrega o baseline histórico do RIPE Atlas."""

    if not CAMINHO_BASELINE.exists():
        raise FileNotFoundError(
            f"Baseline não encontrado: {CAMINHO_BASELINE}"
        )

    baseline = pd.read_csv(CAMINHO_BASELINE)

    obrigatorias = {
        "fluxo_id",
        "status",
        "mediana",
        "MAD",
        "iqr",
        "jitter_tipico",
    }

    faltantes = obrigatorias - set(baseline.columns)

    if faltantes:
        raise ValueError(
            f"Baseline sem colunas: {sorted(faltantes)}"
        )

    return baseline


def selecionar_fluxo(
    baseline: pd.DataFrame,
    fluxo_id: str | None = None,
) -> pd.Series:
    """Seleciona um fluxo com baseline válido."""

    validos = baseline.loc[
        baseline["status"].eq("ok")
    ].copy()

    validos["mediana"] = pd.to_numeric(
        validos["mediana"],
        errors="coerce",
    )

    validos["jitter_tipico"] = pd.to_numeric(
        validos["jitter_tipico"],
        errors="coerce",
    )

    validos = validos.loc[
        validos["mediana"].gt(0)
        & validos["mediana"].notna()
    ]

    if fluxo_id is not None:
        validos = validos.loc[
            validos["fluxo_id"].astype(str).eq(str(fluxo_id))
        ]

    if validos.empty:
        raise ValueError(
            "Nenhum fluxo com baseline válido foi encontrado."
        )

    return validos.iloc[0]


def gerar_medicoes_sinteticas(
    fluxo: pd.Series,
    cenario: str,
    quantidade: int = 12,
    intervalo_minutos: int = 4,
    semente: int = 42,
) -> pd.DataFrame:
    """
    Gera uma sequência sintética para um fluxo RIPE Atlas.

    O cenário descreve o comportamento injetado.
    Não representa uma classificação real observada.
    """

    cenario = cenario.upper()

    if cenario not in CENARIOS:
        raise ValueError(
            f"Cenário inválido: {cenario}. "
            f"Escolha entre {CENARIOS}."
        )

    if quantidade < 6:
        raise ValueError(
            "A quantidade mínima é de 6 medições."
        )

    if intervalo_minutos <= 0:
        raise ValueError(
            "O intervalo deve ser positivo."
        )

    rng = np.random.default_rng(semente)

    fluxo_id = str(fluxo["fluxo_id"])

    if "|" not in fluxo_id:
        raise ValueError(
            "fluxo_id deve seguir o formato probe_id|ip."
        )

    probe_id, ip = fluxo_id.split("|", 1)

    mediana = float(fluxo["mediana"])

    jitter_tipico = pd.to_numeric(
        fluxo["jitter_tipico"],
        errors="coerce",
    )

    if pd.isna(jitter_tipico):
        jitter_tipico = 1.0

    jitter_tipico = max(float(jitter_tipico), 0.5)

    # Datas fixas tornam o experimento reproduzível.
    inicio = pd.Timestamp(
        "2026-01-01T12:00:00Z"
    )

    registros = []

    for indice in range(quantidade):

        progresso = indice / max(quantidade - 1, 1)

        if cenario == "OK":

            fator_latencia = 1.0
            fator_jitter = 1.0
            perda = 0.0

        elif cenario == "RISCO":

            fator_latencia = 1.0 + 0.9 * progresso
            fator_jitter = 1.0 + 3.0 * progresso
            perda = min(15.0, 15.0 * progresso)

        else:  # FALHA

            fator_latencia = 1.0 + 2.5 * progresso
            fator_jitter = 1.0 + 6.0 * progresso
            perda = min(100.0, 100.0 * progresso)

        ruido_latencia = rng.normal(
            loc=0.0,
            scale=0.025,
        )

        ruido_jitter = rng.normal(
            loc=0.0,
            scale=0.05,
        )

        latencia = max(
            0.0,
            mediana * fator_latencia * (1 + ruido_latencia),
        )

        jitter = max(
            0.0,
            jitter_tipico * fator_jitter * (1 + ruido_jitter),
        )

        # Simula timeout completo quando a perda chega a 100%.
        if perda >= 100:
            latencia = np.nan
            jitter = np.nan

        timestamp = inicio + pd.Timedelta(
            minutes=indice * intervalo_minutos
        )

        registros.append(
            {
                "timestamp": timestamp.isoformat(),
                "measurement_id": "SIMULACAO",
                "probe_id": probe_id,
                "dst_addr": ip,
                "fluxo_id": fluxo_id,
                "rtt_medio_ms": latencia,
                "perda_pct": perda,
                "jitter_ms": jitter,
                "timeout_atual": int(perda == 100),
                "origem": "SINTETICO",
                "cenario_simulado": cenario,
            }
        )

    return pd.DataFrame(registros)


def executar_simulacao(
    cenario: str,
    fluxo_id: str | None = None,
    quantidade: int = 12,
    semente: int = 42,
) -> pd.DataFrame:
    """
    Executa o cenário e obtém previsões da árvore V1.

    O histórico utilizado é exclusivamente sintético.
    O baseline permanece real e congelado.
    """

    baseline = carregar_baseline()

    fluxo = selecionar_fluxo(
        baseline,
        fluxo_id,
    )

    medicoes = gerar_medicoes_sinteticas(
        fluxo=fluxo,
        cenario=cenario,
        quantidade=quantidade,
        semente=semente,
    )

    medicoes["previsao_12min"] = None
    medicoes["estado_previsao"] = "HISTORICO_INSUFICIENTE"

    for indice in range(len(medicoes)):

        # Exige cinco medições recentes, incluindo a atual.
        if indice < 4:
            continue

        historico = medicoes.iloc[:indice].copy()

        atual = medicoes.iloc[indice].to_dict()

        try:
            resultado = prever_medicao(
                atual,
                historico,
                baseline,
            )

            medicoes.at[
                indice,
                "previsao_12min",
            ] = resultado["previsao_12min"]

            medicoes.at[
                indice,
                "estado_previsao",
            ] = "PREVISAO_DISPONIVEL"

        except (ValueError, KeyError) as erro:

            medicoes.at[
                indice,
                "estado_previsao",
            ] = f"ERRO: {erro}"

    return medicoes


def main() -> None:
    """Permite executar a simulação pelo terminal."""

    parser = argparse.ArgumentParser(
        description="Simulador de eventos do ICMPMASTER"
    )

    parser.add_argument(
        "--cenario",
        choices=CENARIOS,
        default="RISCO",
        help="Cenário sintético a executar.",
    )

    parser.add_argument(
        "--fluxo-id",
        default=None,
        help="Fluxo RIPE Atlas no formato probe_id|ip.",
    )

    parser.add_argument(
        "--quantidade",
        type=int,
        default=12,
        help="Quantidade de medições sintéticas.",
    )

    parser.add_argument(
        "--semente",
        type=int,
        default=42,
        help="Semente para reprodução do experimento.",
    )

    args = parser.parse_args()

    resultado = executar_simulacao(
        cenario=args.cenario,
        fluxo_id=args.fluxo_id,
        quantidade=args.quantidade,
        semente=args.semente,
    )

    colunas = [
        "timestamp",
        "fluxo_id",
        "rtt_medio_ms",
        "perda_pct",
        "jitter_ms",
        "cenario_simulado",
        "previsao_12min",
        "estado_previsao",
    ]

    print("\n=== SIMULAÇÃO ICMPMASTER ===")
    print(f"Cenário: {args.cenario}")
    print(f"Fluxo: {resultado['fluxo_id'].iloc[0]}")
    print("Origem: DADOS SINTÉTICOS\n")

    print(
        resultado[colunas].to_string(
            index=False
        )
    )

    print("\nResumo das previsões:")

    print(
        resultado["previsao_12min"]
        .dropna()
        .value_counts()
        .to_string()
    )


if __name__ == "__main__":
    main()