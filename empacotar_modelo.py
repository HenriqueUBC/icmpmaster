"""Empacota a árvore oficial SEM retreinar e sem substituir artefatos históricos."""
from __future__ import annotations
from pathlib import Path
import json
import shutil
import joblib
import pandas as pd
import modelo_icmp as mi

RAIZ = Path(__file__).resolve().parent
DESTINO = RAIZ / "pacote_modelo"

def empacotar():
    arvore, features = mi.carregar_modelo()
    cfg = json.loads(mi.ARQ_CONFIG.read_text(encoding="utf-8"))
    DESTINO.mkdir(exist_ok=True)
    pacote = {"modelo": arvore, "features": features, "familia": "DecisionTreeClassifier", "params": arvore.get_params()}
    joblib.dump(pacote, DESTINO / "modelo.joblib")
    shutil.copy2(RAIZ / "data" / "processed" / "baseline_por_fluxo.csv", DESTINO / "baseline.csv")
    metadados = {"origem": "Tarefa 4 — árvore oficial V1, sem retreinamento",
        "features": features, "horizonte_rodadas": cfg.get("horizonte_rodadas", 3),
        "horizonte_min_estimado": cfg.get("horizonte_min", 12),
        "baseline": "baseline.csv; fluxos RIPE Atlas, válido somente para fluxos RIPE Atlas cadastrados",
        "sentinela": mi.SENTINELA, "classes": list(mi.CLASSES),
        "status_real": "exclusivamente avaliação, nunca feature"}
    (DESTINO / "metadados.json").write_text(json.dumps(metadados, indent=2, ensure_ascii=False), encoding="utf-8")
    carregado = joblib.load(DESTINO / "modelo.joblib")
    assert carregado["features"] == features
    assert carregado["modelo"].n_features_in_ == len(features)
    amostra = pd.read_csv(RAIZ / "data" / "processed" / "dataset_rotulado_B.csv", nrows=20)
    amostra = mi.adicionar_tendencia(amostra)
    a = mi.prever_12min(amostra, arvore, features)
    b = mi.prever_12min(amostra, carregado["modelo"], carregado["features"])
    assert a.equals(b), "Pacote alterou as previsões"
    print(f"Pacote validado em {len(a)} linhas: {DESTINO}")

if __name__ == "__main__":
    empacotar()
