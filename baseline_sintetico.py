"""Baseline curto EXCLUSIVAMENTE para experimentos artificiais.

Não substitui o baseline histórico RIPE Atlas, nem é usado na inferência real.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def construir_baseline_sintetico(medicoes: pd.DataFrame, minimo_validos: int = 20) -> pd.DataFrame:
    obrigatorias = {"fluxo_id", "rtt_medio_ms", "jitter_ms"}
    faltantes = obrigatorias - set(medicoes.columns)
    if faltantes:
        raise ValueError(f"Medições sintéticas sem colunas: {sorted(faltantes)}")
    if minimo_validos < 1:
        raise ValueError("minimo_validos deve ser positivo")
    linhas = []
    for fluxo_id, grupo in medicoes.groupby("fluxo_id", sort=True):
        rtt = pd.to_numeric(grupo["rtt_medio_ms"], errors="coerce")
        rtt = rtt.where(np.isfinite(rtt) & rtt.ge(0)).dropna()
        jitter = pd.to_numeric(grupo["jitter_ms"], errors="coerce")
        jitter = jitter.where(np.isfinite(jitter) & jitter.ge(0)).dropna()
        mediana = float(rtt.median()) if len(rtt) else np.nan
        mad = float((rtt - mediana).abs().median()) if len(rtt) else np.nan
        linhas.append({
            "fluxo_id": fluxo_id,
            "status": "ok" if len(rtt) >= minimo_validos and mediana > 0 else "aquecimento",
            "mediana": mediana, "MAD": mad,
            "iqr": float(rtt.quantile(.75) - rtt.quantile(.25)) if len(rtt) else np.nan,
            "jitter_tipico": float(jitter.median()) if len(jitter) else np.nan,
            "n_rtt_validos": int(len(rtt)),
        })
    return pd.DataFrame(linhas)
