"""Inferência da árvore ICMP V1 com medições novas, sem retreinamento.

Entrada: registro normalizado do coletor, histórico anterior do mesmo fluxo,
         baseline congelado e modelo_icmp.py oficial.
"""
from pathlib import Path
from collections.abc import Mapping
import numpy as np
import pandas as pd
import modelo_icmp as mi

COLS = ["z_robusto", "aumento_pct", "jitter_relativo", "perda_pct",
        "timeout_atual", "n5_timeout", "n5_aumento80", "n5_risco"]
KEY = ["fluxo_id", "timestamp"]

def calcular_features(medicoes: pd.DataFrame, baseline: pd.DataFrame) -> pd.DataFrame:
    """Replica a célula de métricas do notebook Baseline_dos_dados.ipynb.

    Recebe exclusivamente medições do período B, com histórico completo do período.
    """
    campos = {"fluxo_id", "timestamp", "rtt_medio_ms", "perda_pct", "jitter_ms"}
    faltam = campos - set(medicoes.columns)
    if faltam:
        raise ValueError(f"Medições sem colunas: {sorted(faltam)}")
    campos_base = {"fluxo_id", "status", "mediana", "MAD", "iqr", "jitter_tipico"}
    faltam = campos_base - set(baseline.columns)
    if faltam:
        raise ValueError(f"Baseline sem colunas: {sorted(faltam)}")
    if baseline["fluxo_id"].duplicated().any():
        raise ValueError("Baseline contém fluxo_id duplicado")

    b = medicoes.copy()
    b["timestamp"] = pd.to_datetime(b["timestamp"], errors="coerce", utc=True)
    if b["timestamp"].isna().any():
        raise ValueError("Timestamp inválido")
    ficha = baseline.loc[baseline["status"].eq("ok"),
                          ["fluxo_id", "mediana", "MAD", "iqr", "jitter_tipico"]]
    b = b.merge(ficha, on="fluxo_id", how="inner", validate="many_to_one")
    b = b.sort_values(KEY, kind="stable").reset_index(drop=True)
    for c in ["rtt_medio_ms", "perda_pct", "jitter_ms", "mediana", "MAD", "iqr", "jitter_tipico"]:
        b[c] = pd.to_numeric(b[c], errors="coerce")

    rtt, dif = b["rtt_medio_ms"], b["rtt_medio_ms"] - b["mediana"]
    den = np.where(b["MAD"] > 0, 1.4826 * b["MAD"], np.maximum(b["iqr"] / 1.349, 1.0))
    b["z_robusto"] = np.where(rtt.isna(), np.nan, np.where(dif == 0, 0.0, dif / den))
    b["aumento_pct"] = np.where(rtt.isna(), np.nan, dif / b["mediana"] * 100)
    jt, j = b["jitter_tipico"], b["jitter_ms"]
    b["jitter_relativo"] = np.select(
        [(j.isna() | jt.isna()).to_numpy(), (jt == 0).to_numpy()],
        [np.nan, np.where(j == 0, 1.0, 3.0)],
        default=(j / jt.where(jt > 0)).to_numpy(),
    )
    b["timeout_atual"] = (rtt.isna() | (b["perda_pct"] == 100)).astype(int)
    crit5 = (((b["z_robusto"] >= 2) & (b["z_robusto"] < 3.5))
             | ((b["aumento_pct"] >= 30) & (b["aumento_pct"] <= 80))
             | (b["jitter_relativo"] >= 3))
    ind = pd.DataFrame({
        "n5_timeout": b["timeout_atual"],
        "n5_aumento80": (b["aumento_pct"] > 80).astype(int),
        "n5_risco": crit5.astype(int),
    })
    for c in ind:
        b[c] = ind[c].groupby(b["fluxo_id"]).transform(
            lambda s: s.rolling(5, min_periods=1).sum()
        ).astype(int)
    return b[KEY + COLS]


def prever_medicao(nova: Mapping, historico: pd.DataFrame,
                   baseline: pd.DataFrame) -> dict:
    """Prevê um registro novo. Não altera DataFrames nem escreve arquivos.

    nova: timestamp, fluxo_id (ou probe_id e dst_addr), rtt_medio_ms,
          perda_pct e jitter_ms. RTT/jitter podem ser nulos em timeout.
    historico: medições normalizadas anteriores (sem a nova medição).
    baseline: baseline_por_fluxo.csv congelado.
    """
    registro = dict(nova)
    if not registro.get("fluxo_id"):
        if pd.isna(registro.get("probe_id")) or not registro.get("dst_addr"):
            raise ValueError("Informe fluxo_id ou probe_id + dst_addr.")
        registro["fluxo_id"] = f"{registro['probe_id']}|{registro['dst_addr']}"
    obrigatorios = {"timestamp", "fluxo_id", "rtt_medio_ms", "perda_pct", "jitter_ms"}
    faltantes = obrigatorios - registro.keys()
    if faltantes:
        raise ValueError(f"Medição sem campos: {sorted(faltantes)}")
    registro["timestamp"] = pd.to_datetime(registro["timestamp"], utc=True, errors="raise")
    if pd.isna(registro["timestamp"]):
        raise ValueError("Timestamp inválido")
    for campo in ("rtt_medio_ms", "perda_pct", "jitter_ms"):
        valor = registro[campo]
        registro[campo] = np.nan if pd.isna(valor) else float(valor)
        if not pd.isna(registro[campo]) and (not np.isfinite(registro[campo]) or registro[campo] < 0):
            raise ValueError(f"{campo} inválido")
    if pd.isna(registro["perda_pct"]) or registro["perda_pct"] > 100:
        raise ValueError("perda_pct deve estar entre 0 e 100")
    if not {"fluxo_id", "timestamp", "rtt_medio_ms", "perda_pct", "jitter_ms"}.issubset(historico.columns):
        raise ValueError("Histórico não possui as colunas normalizadas necessárias")
    ficha = baseline.loc[baseline["fluxo_id"].astype(str).eq(str(registro["fluxo_id"]))].copy()
    if len(ficha) != 1 or ficha.iloc[0]["status"] != "ok":
        raise ValueError("Fluxo sem baseline válido e único")
    anterior = historico.loc[historico["fluxo_id"].astype(str).eq(str(registro["fluxo_id"]))].copy()
    anterior["timestamp"] = pd.to_datetime(anterior["timestamp"], utc=True, errors="raise")
    if (anterior["timestamp"] >= registro["timestamp"]).any():
        raise ValueError("Histórico contém medição no mesmo instante ou no futuro")
    if anterior["timestamp"].duplicated().any():
        raise ValueError("Histórico contém timestamps duplicados")
    serie = pd.concat([anterior, pd.DataFrame([registro])], ignore_index=True)
    features = mi.adicionar_tendencia(calcular_features(serie, ficha))
    atual = features.iloc[[-1]].copy()
    if atual["timestamp"].iloc[0] != registro["timestamp"]:
        raise ValueError("Falha ao localizar a nova medição")
    arvore, colunas = mi.carregar_modelo()
    if len(colunas) != 11 or set(colunas) != set(COLS + ["z_delta1", "z_media3_ant", "z_inclin5"]):
        raise ValueError("Modelo não corresponde às 11 features oficiais")
    previsao = mi.prever_12min(atual, arvore, colunas).iloc[0]
    return {
        "fluxo_id": str(registro["fluxo_id"]),
        "timestamp": registro["timestamp"].isoformat(),
        "previsao_12min": str(previsao),
        "features": {c: (None if pd.isna(atual[c].iloc[0]) else float(atual[c].iloc[0]))
                     for c in colunas},
    }


def carregar_dados_locais(raiz: str | Path = ".") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Lê histórico e baseline existentes, sem modificar os arquivos."""
    raiz = Path(raiz)
    historico = pd.read_csv(raiz / "data/interim/medicoes.csv")
    baseline = pd.read_csv(raiz / "data/processed/baseline_por_fluxo.csv")
    return historico, baseline
