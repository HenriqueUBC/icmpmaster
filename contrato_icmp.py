"""Contrato de entrada independente de Streamlit e do dataset rotulado."""
from __future__ import annotations
from collections.abc import Mapping
import ipaddress
import math
import pandas as pd

CAMPOS = ("timestamp", "ip", "latencia_ms", "perda_pacotes_pct", "jitter_ms", "status_real")

def normalizar_medicao(registro: Mapping, origem: str = "sintetico") -> dict:
    """Adapta o contrato da professora; status_real é mantido SOMENTE para avaliação."""
    ausentes = set(CAMPOS[:5]) - set(registro)
    if ausentes:
        raise ValueError(f"Campos ausentes: {sorted(ausentes)}")
    ip = str(registro["ip"]).strip()
    try:
        ipaddress.ip_address(ip)
    except ValueError as exc:
        raise ValueError(f"IP inválido: {ip}") from exc
    timestamp = pd.to_datetime(registro["timestamp"], utc=True, errors="raise")
    if pd.isna(timestamp):
        raise ValueError("timestamp inválido")
    def numero(campo, permitir_nulo=False):
        valor = registro[campo]
        if valor is None or pd.isna(valor):
            if permitir_nulo:
                return float("nan")
            raise ValueError(f"{campo} obrigatório")
        v = float(valor)
        if not math.isfinite(v) or v < 0:
            raise ValueError(f"{campo} inválido")
        return v
    perda = numero("perda_pacotes_pct")
    if perda > 100:
        raise ValueError("perda_pacotes_pct > 100")
    latencia = numero("latencia_ms", permitir_nulo=True)
    jitter = numero("jitter_ms", permitir_nulo=True)
    if perda == 100:
        latencia, jitter = float("nan"), float("nan")
    elif math.isnan(latencia):
        raise ValueError("latencia_ms obrigatória quando há respostas")
    status = registro.get("status_real")
    if status is not None and not pd.isna(status):
        status = str(status).upper().strip()
        if status not in {"OK", "RISCO", "FALHA"}:
            raise ValueError("status_real deve ser OK, RISCO, FALHA ou vazio")
    else:
        status = None
    if origem not in {"sintetico", "ripe_atlas"}:
        raise ValueError("origem deve ser sintético ou RIPE Atlas")
    return {"timestamp": timestamp.isoformat(), "ip": ip,
            "fluxo_id": f"{origem}|{ip}", "rtt_medio_ms": latencia,
            "perda_pct": perda, "jitter_ms": jitter,
            "timeout_atual": int(perda == 100), "status_real": status,
            "origem": origem}


def converter_dataframe(dados: pd.DataFrame, origem: str = "sintetico") -> pd.DataFrame:
    return pd.DataFrame([normalizar_medicao(linha, origem) for linha in dados.to_dict("records")])
