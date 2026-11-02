"""Exporta o log no CONTRATO DE DADOS do Kickoff.

    timestamp, ip, latencia_ms, perda_pacotes_pct, jitter_ms, status_real

Fonte: data/interim/medicoes.csv (medições do RIPE Atlas) + `classe` do
data/processed/dataset_rotulado_B.csv (rótulo da Tarefa 2, Período B).

Saídas (em data/processed/):
  log_rede.csv           amostra BALANCEADA (N por classe, semente 42) -> entregável
  log_rede_completo.csv  todas as medições rotuladas (só com --completo)

Uso:  python exportar_log_rede.py [--por-classe 1000] [--completo]
"""
import argparse
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent
COLUNAS = ["timestamp", "ip", "latencia_ms", "perda_pacotes_pct", "jitter_ms", "status_real"]


def montar(raiz: Path = RAIZ) -> pd.DataFrame:
    med = pd.read_csv(
        raiz / "data" / "interim" / "medicoes.csv",
        usecols=["timestamp", "fluxo_id", "dst_addr", "rtt_medio_ms", "perda_pct", "jitter_ms"],
        parse_dates=["timestamp"],
    )
    rot = pd.read_csv(
        raiz / "data" / "processed" / "dataset_rotulado_B.csv",
        usecols=["fluxo_id", "timestamp", "classe"],
        parse_dates=["timestamp"],
    )
    df = rot.merge(med, on=["fluxo_id", "timestamp"], how="left", validate="one_to_one")
    if df["dst_addr"].isna().any():
        raise RuntimeError("Há linhas rotuladas sem medição correspondente em medicoes.csv.")
    out = pd.DataFrame({
        "timestamp": df["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ip": df["dst_addr"],
        "latencia_ms": df["rtt_medio_ms"].round(4),     # vazio = timeout (sem RTT)
        "perda_pacotes_pct": df["perda_pct"],
        "jitter_ms": df["jitter_ms"].round(4),
        "status_real": df["classe"],
    })
    return out.sort_values("timestamp", kind="stable").reset_index(drop=True)[COLUNAS]


def balancear(df: pd.DataFrame, por_classe: int, semente: int = 42) -> pd.DataFrame:
    partes = [g.sample(n=min(por_classe, len(g)), random_state=semente)
              for _, g in df.groupby("status_real")]
    return pd.concat(partes).sort_values("timestamp", kind="stable").reset_index(drop=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--por-classe", type=int, default=1000)
    ap.add_argument("--completo", action="store_true")
    a = ap.parse_args()

    destino = RAIZ / "data" / "processed"
    completo = montar()
    bal = balancear(completo, a.por_classe)
    bal.to_csv(destino / "log_rede.csv", index=False)
    if a.completo:
        completo.to_csv(destino / "log_rede_completo.csv", index=False)
    print(f"log_rede.csv: {len(bal)} linhas\n{bal['status_real'].value_counts().to_string()}")
