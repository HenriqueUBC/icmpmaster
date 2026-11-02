"""Relatório de comparação (Sprint 5): acurácia com dataset SINTÉTICO x log REAL.

Reaproveita o gerador e o pipeline do `experimento_sintetico.py` do grupo e a
árvore oficial V1. Não altera nenhum modelo salvo. Avalia em cruzado:

  V1        árvore oficial (Tarefa 4), treinada no log real
  Sintética árvore do experimento, treinada só em dados sintéticos
  Real*     MESMO algoritmo/hiperparâmetros da sintética, retreinado no log real

contra o teste sintético e o teste real (partição `teste`, Tarefa 5).
Uso:  python comparar_sintetico_real.py        (gera o .md e o .csv)
"""
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, recall_score
from sklearn.tree import DecisionTreeClassifier

import experimento_sintetico as ex
import modelo_icmp as mi
from baseline_sintetico import construir_baseline_sintetico
from contrato_icmp import converter_dataframe
from preditor_icmp import calcular_features

warnings.filterwarnings("ignore")
RAIZ = Path(__file__).resolve().parent
CLASSES = ["OK", "RISCO", "FALHA"]
HIPER = dict(max_depth=8, min_samples_leaf=4)      # os do experimento sintético


def preparar_real():
    d = pd.read_csv(RAIZ / "data/processed/dataset_rotulado_B.csv", parse_dates=["timestamp"])
    d = mi.adicionar_tendencia(d).sort_values(["fluxo_id", "timestamp"]).reset_index(drop=True)
    g = d.groupby("fluxo_id")
    d["alvo"] = g["classe"].shift(-3)
    dt = (g["timestamp"].shift(-3) - d["timestamp"]).dt.total_seconds()
    d["tem_alvo"] = (g["particao"].shift(-3) == d["particao"]) & dt.between(660, 780)
    d["atual"] = d["classe"]
    d = d[d["tem_alvo"]]
    return d[d["particao"] == "treino"], d[d["particao"] == "teste"]


def preparar_sintetico(seed=42):
    """Mesma montagem e mesmos cortes do experimento_sintetico.executar()."""
    bruto = ex.gerar(seed=seed)
    dados = converter_dataframe(bruto, origem="sintetico")
    base = construir_baseline_sintetico(dados.groupby("fluxo_id", group_keys=False).head(30))
    feats = mi.adicionar_tendencia(calcular_features(dados, base))
    dados["timestamp"] = pd.to_datetime(dados["timestamp"], utc=True)
    d = dados.drop(columns=["perda_pct", "timeout_atual"]).merge(
        feats, on=["fluxo_id", "timestamp"], how="inner")
    d = d.sort_values(["fluxo_id", "timestamp"]).reset_index(drop=True)
    d["alvo"] = d.groupby("fluxo_id")["status_real"].shift(-3)
    d["atual"] = d["status_real"]
    d["indice"] = d.groupby("fluxo_id").cumcount()
    ok = d["alvo"].notna()
    return (d[d["indice"].between(35, 119) & ok].copy(), d[d["indice"].between(123, 175) & ok].copy())


def _x(df, cols):
    return df[cols].replace([np.inf, -np.inf], np.nan).fillna(mi.SENTINELA)


def _metricas(y, pred):
    rec = recall_score(y, pred, labels=CLASSES, average=None, zero_division=0)
    return {"acuracia": accuracy_score(y, pred),
            "f1_macro": f1_score(y, pred, labels=CLASSES, average="macro", zero_division=0),
            "recall_risco": rec[1], "recall_falha": rec[2]}


def comparar():
    v1, cols = mi.carregar_modelo()
    tr_r, te_r = preparar_real()
    tr_s, te_s = preparar_sintetico()
    sint = DecisionTreeClassifier(random_state=42, **HIPER).fit(_x(tr_s, cols), tr_s["alvo"])
    real = DecisionTreeClassifier(random_state=42, **HIPER).fit(_x(tr_r, cols), tr_r["alvo"])
    modelos = {"V1 oficial (treinada no real)": v1,
               "Sintética (treinada no sintético)": sint,
               "Real* (mesmos hiperparâmetros, retreinada no real)": real}
    testes = {"teste SINTÉTICO": te_s, "teste REAL (Tarefa 5)": te_r}
    linhas = []
    for nt, te in testes.items():
        for nm, m in modelos.items():
            linhas.append({"teste": nt, "modelo": nm, "n": len(te),
                           **_metricas(te["alvo"], m.predict(_x(te, cols)))})
        linhas.append({"teste": nt, "modelo": "Persistência (repetir a classe atual)", "n": len(te),
                       **_metricas(te["alvo"], te["atual"])})
    return pd.DataFrame(linhas), (len(tr_s), len(te_s), len(tr_r), len(te_r))


def escrever(df, tamanhos):
    f = lambda x: f"{x:.3f}".replace(".", ",")
    s = df.copy()
    for c in ["acuracia", "f1_macro", "recall_risco", "recall_falha"]:
        s[c] = s[c].map(f)
    s.columns = ["Teste", "Modelo", "N", "Acurácia", "F1 macro", "Recall RISCO", "Recall FALHA"]
    tab = "| " + " | ".join(s.columns) + " |\n|" + "---|" * len(s.columns) + "\n" + "\n".join(
        "| " + " | ".join(map(str, r)) + " |" for r in s.values)
    g = lambda t, m, c: df[(df.teste == t) & (df.modelo.str.startswith(m))][c].iloc[0]
    ts, tr = "teste SINTÉTICO", "teste REAL (Tarefa 5)"
    texto = f"""# Relatório de comparação: dataset sintético × log real

Gerado por `python comparar_sintetico_real.py` (semente 42). Alvo = classe 3 rodadas (~12 min) à frente.
Treino/teste sintético: {tamanhos[0]}/{tamanhos[1]} linhas. Treino/teste real: {tamanhos[2]}/{tamanhos[3]} linhas.

{tab}

## Leitura

- **Árvore sintética no teste sintético:** acurácia {f(g(ts,'Sint','acuracia'))} (F1 macro {f(g(ts,'Sint','f1_macro'))}). **No teste real:** acurácia {f(g(tr,'Sint','acuracia'))}, mas F1 macro {f(g(tr,'Sint','f1_macro'))} (a acurácia sobe só porque o real tem mais OK).
- **Árvore V1 no teste real:** acurácia {f(g(tr,'V1','acuracia'))} (F1 macro {f(g(tr,'V1','f1_macro'))}). **No teste sintético:** {f(g(ts,'V1','acuracia'))}.
- **Retreino no log real** (Real*, mesmo algoritmo da sintética): acurácia {f(g(tr,'Real','acuracia'))} no real, contra {f(g(tr,'Sint','acuracia'))} da árvore treinada só no sintético.
- **Transferência:** a árvore treinada só no sintético acerta {f(g(tr,'Sint','acuracia'))} no real (recall de FALHA {f(g(tr,'Sint','recall_falha'))}), contra {f(g(tr,'Real','acuracia'))} (recall de FALHA {f(g(tr,'Real','recall_falha'))}) do retreino no log real: é o motivo de retreinar com dados reais na Sprint 5.
- A persistência (repetir a classe atual) alcança {f(g(ts,'Pers','acuracia'))} no sintético e {f(g(tr,'Pers','acuracia'))} no real: é a referência que a árvore precisa superar.

## Cuidados

1. Os rótulos sintéticos vêm de regras artificiais do gerador (blocos de RISCO e FALHA); os reais, das regras da Tarefa 2. Acurácias entre conjuntos diferentes **não são equivalentes**: servem para comparar o comportamento do método.
2. Distribuições diferentes (o sintético tem muito mais RISCO e FALHA que o real); por isso o F1 macro e o recall por classe importam mais que a acurácia isolada.
3. Nenhum modelo salvo foi alterado: a V1 oficial é só carregada.
"""
    (RAIZ / "documentos").mkdir(exist_ok=True)
    (RAIZ / "documentos" / "RELATORIO_SINTETICO_VS_REAL.md").write_text(texto, encoding="utf-8")
    (RAIZ / "resultados_sinteticos").mkdir(exist_ok=True)
    df.to_csv(RAIZ / "resultados_sinteticos" / "comparacao_sintetico_real.csv", index=False)
    return tab


if __name__ == "__main__":
    resultado, tam = comparar()
    print(escrever(resultado, tam))
