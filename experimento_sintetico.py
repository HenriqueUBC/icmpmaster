"""Experimento reproduzível EXCLUSIVAMENTE sintético; nunca altera a árvore V1."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score, f1_score, classification_report
from baseline_local import construir_baseline
from preditor_icmp import calcular_features
import modelo_icmp as mi

RAIZ = Path(__file__).resolve().parent
DESTINO = RAIZ / "resultados_sinteticos"

def gerar(seed=42, fluxos=12, amostras=180):
    rng = np.random.default_rng(seed)
    linhas = []
    for fluxo in range(fluxos):
        ip = f"198.51.100.{fluxo + 1}"
        base = rng.uniform(20, 90)
        for i in range(amostras):
            # 0..29: aquecimento saudável; eventos por blocos após o aquecimento.
            modo = "OK" if i < 30 else ("FALHA" if i % 47 in range(31, 38) else
                                         "RISCO" if i % 37 in range(20, 29) else "OK")
            lat = max(.1, base + rng.normal(0, 1.2))
            perda = 0.0
            jitter = abs(rng.normal(.9, .3))
            if modo == "RISCO":
                lat *= rng.uniform(1.3, 1.8)
                jitter *= rng.uniform(3, 5)
            if modo == "FALHA":
                lat *= rng.uniform(2, 4)
                perda = float(rng.choice([12, 25, 50, 100]))
            linhas.append({"timestamp": (pd.Timestamp("2026-01-01", tz="UTC") + pd.Timedelta(minutes=i * 4)).isoformat(),
                          "ip": ip, "latencia_ms": None if perda == 100 else lat,
                          "perda_pacotes_pct": perda,
                          "jitter_ms": None if perda == 100 else jitter,
                          "status_real": modo})
    return pd.DataFrame(linhas)

def executar(seed=42):
    from contrato_icmp import converter_dataframe
    bruto = gerar(seed=seed)
    dados = converter_dataframe(bruto, origem="sintetico")
    base = construir_baseline(dados.groupby("fluxo_id", group_keys=False).head(30))
    features = mi.adicionar_tendencia(calcular_features(dados, base))
    dados["timestamp"] = pd.to_datetime(dados["timestamp"], utc=True)
    d = dados.drop(columns=["perda_pct", "timeout_atual"]).merge(features, on=["fluxo_id", "timestamp"], how="inner")
    d = d.sort_values(["fluxo_id", "timestamp"]).reset_index(drop=True)
    # Avaliação usa rótulo sintético explícito (não vazamento nas features).
    d["alvo_futuro"] = d.groupby("fluxo_id")["status_real"].shift(-3)
    d["indice"] = d.groupby("fluxo_id").cumcount()
    # Separação temporal por fluxo com lacuna de 3 rodadas.
    treino = d.loc[d["indice"].between(35, 119) & d["alvo_futuro"].notna()].copy()
    teste = d.loc[d["indice"].between(123, 175) & d["alvo_futuro"].notna()].copy()
    cols = mi.carregar_modelo()[1]
    def x(df):
        return df[cols].replace([np.inf, -np.inf], np.nan).fillna(mi.SENTINELA)
    modelo = DecisionTreeClassifier(max_depth=8, random_state=seed, min_samples_leaf=4)
    modelo.fit(x(treino), treino["alvo_futuro"])
    pred = modelo.predict(x(teste))
    persistencia = teste["status_real"].to_numpy()
    y = teste["alvo_futuro"].to_numpy()
    rel = {"origem": "SINTETICA: regras artificiais; NÃO validação em rede real",
           "seed": seed, "treino": len(treino), "teste": len(teste),
           "arvore_sintetica": {"acuracia": float(accuracy_score(y, pred)),
                                  "f1_macro": float(f1_score(y, pred, average="macro", zero_division=0))},
           "persistencia": {"acuracia": float(accuracy_score(y, persistencia)),
                             "f1_macro": float(f1_score(y, persistencia, average="macro", zero_division=0))},
           "comparacao_ripe_atlas": "Comparar apenas metodologia; métricas não são diretamente equivalentes aos dados RIPE Atlas."}
    DESTINO.mkdir(exist_ok=True)
    bruto.to_csv(DESTINO / "medicoes_sinteticas.csv", index=False)
    pd.DataFrame({"fluxo_id": teste["fluxo_id"], "timestamp": teste["timestamp"],
                  "real_futuro": y, "previsto_arvore_sintetica": pred,
                  "persistencia": persistencia}).to_csv(DESTINO / "predicoes_teste.csv", index=False)
    (DESTINO / "relatorio.json").write_text(json.dumps(rel, indent=2, ensure_ascii=False), encoding="utf-8")
    return rel

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(executar(args.seed), indent=2, ensure_ascii=False))
