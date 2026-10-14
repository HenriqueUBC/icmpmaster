#!/usr/bin/env python3
"""
Tarefa 3 - Primeira árvore de decisão (ICMPMASTER)

Lê os artefatos da Tarefa 2 (sem recalcular nada), treina a árvore oficial
(só métricas relativas), avalia na VALIDAÇÃO, extrai regras e treina a árvore
de contraste. Gera `saida_tarefa3/resultado_tarefa3.md` com os números prontos
para colar no diário.

Uso:
    python tarefa3_arvore.py
    (ajuste a seção CONFIG se os nomes dos arquivos/colunas da Tarefa 2 forem outros)
"""
import json
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, f1_score, accuracy_score
from sklearn.tree import DecisionTreeClassifier, export_text, plot_tree

# ============================== CONFIG ======================================
DATASET_B = "dataset_rotulado_B.csv"      # saída da Tarefa 2
BASELINE = "baseline_por_fluxo.csv"       # saída da Tarefa 2
SAIDA = Path("saida_tarefa3")

COL_FLUXO, COL_TS, COL_CLASSE = "fluxo_id", "timestamp", "classe"
COL_SPLIT = "particao"         # 'treino'/'validacao'/'teste'. Se não existir, recria 50/20/30 por fluxo
COL_RTT = "rtt_ms"             # NÃO vem no dataset: é reconstruído = mediana*(1+aumento_pct/100). Só p/ contraste
COL_ROTA = "rota_id"           # só para a árvore de contraste (opcional)
COL_MEDIANA = "mediana"        # coluna da ficha de baseline (só para separar curto/longo)

FEATURES = ["z_robusto", "aumento_pct", "jitter_relativo", "perda_pct",
            "timeout_atual", "n5_timeout", "n5_aumento80", "n5_risco"]
CLASSES = ["OK", "RISCO", "FALHA"]

SEED = 42
GRID_CRITERIO = ["gini", "entropy"]
GRID_DEPTH = [2, 3, 4, 5, 6, 8, 10, None]
GRID_LEAF = [1, 5, 10, 20, 50, 100]
SENTINELA = -999.0             # RTT/jitter ausente: valor fora do domínio, NUNCA 0
MEDIR_TESTE = False            # o teste fica fechado até a Tarefa 5
# ============================================================================


def carregar():
    df = pd.read_csv(DATASET_B)
    if pd.api.types.is_numeric_dtype(df[COL_TS]):
        df[COL_TS] = pd.to_datetime(df[COL_TS], unit="s", utc=True)
    else:
        df[COL_TS] = pd.to_datetime(df[COL_TS], utc=True)
    if COL_RTT not in df.columns and "aumento_pct" in df.columns:
        med = pd.read_csv(BASELINE).set_index(COL_FLUXO)[COL_MEDIANA]
        df[COL_RTT] = df[COL_FLUXO].map(med) * (1 + df["aumento_pct"] / 100)  # vazio no timeout
    df = df[df[COL_CLASSE].isin(CLASSES)].copy()   # baseline_insuficiente não tem classe
    df = df.sort_values([COL_FLUXO, COL_TS]).reset_index(drop=True)

    if COL_SPLIT not in df.columns:
        # mesmo corte da Tarefa 2: por fluxo, em ordem de tempo, 50/20/30
        pos = df.groupby(COL_FLUXO).cumcount()
        n = df.groupby(COL_FLUXO)[COL_FLUXO].transform("size")
        frac = pos / n
        df[COL_SPLIT] = np.where(frac < 0.5, "treino", np.where(frac < 0.7, "validacao", "teste"))
    return df


def X_de(df, cols):
    return df[cols].astype(float).fillna(SENTINELA)


def f1m(y, p):
    return f1_score(y, p, labels=CLASSES, average="macro", zero_division=0)


def escolher_hiperparametros(tr, va):
    """Escolha olhando SÓ a validação. Empate: árvore mais simples (menos folhas)."""
    linhas = []
    for crit in GRID_CRITERIO:
        for d in GRID_DEPTH:
            for leaf in GRID_LEAF:
                m = DecisionTreeClassifier(criterion=crit, max_depth=d, min_samples_leaf=leaf,
                                           random_state=SEED)
                m.fit(X_de(tr, FEATURES), tr[COL_CLASSE])
                p = m.predict(X_de(va, FEATURES))
                linhas.append(dict(criterio=crit, max_depth=d, min_samples_leaf=leaf,
                                   f1_macro_val=f1m(va[COL_CLASSE], p),
                                   folhas=m.get_n_leaves(), prof_real=m.get_depth()))
    g = pd.DataFrame(linhas)
    g["f1_r"] = g["f1_macro_val"].round(4)
    g = g.sort_values(["f1_r", "folhas"], ascending=[False, True]).reset_index(drop=True)
    return g


def regras_da_arvore(model, cols):
    t = model.tree_
    saida = []

    def desce(no, conds):
        if t.children_left[no] == -1:
            cont = t.value[no][0]
            cls = model.classes_[int(np.argmax(cont))]
            n = int(t.n_node_samples[no])
            pureza = cont.max() / cont.sum()
            saida.append((n, cls, pureza, conds))
            return
        nome, lim = cols[t.feature[no]], t.threshold[no]
        desce(t.children_left[no], conds + [f"{nome} <= {lim:.3f}"])
        desce(t.children_right[no], conds + [f"{nome} > {lim:.3f}"])

    desce(0, [])
    saida.sort(key=lambda r: -r[0])
    return saida


def texto_regra(r):
    n, cls, pureza, conds = r
    cond = " e ".join(conds) if conds else "(sempre)"
    return f"se {cond} então {cls}  (n={n}, pureza={pureza:.0%})"


def main():
    SAIDA.mkdir(exist_ok=True)
    df = carregar()
    tr, va, te = (df[df[COL_SPLIT] == s] for s in ("treino", "validacao", "teste"))
    assert not set(FEATURES) & {COL_CLASSE, COL_FLUXO, COL_RTT, COL_ROTA}, "feature proibida!"
    for nome, b in (("treino", tr), ("validacao", va), ("teste", te)):
        print(f"{nome}: N={len(b)}  {b[COL_CLASSE].value_counts().to_dict()}")
    faltando = [c for c in CLASSES if c not in va[COL_CLASSE].unique()]
    if faltando:
        print(f"ATENÇÃO: validação sem a classe {faltando}. Registre no diário / ajuste o corte (Tarefa 2).")

    # ---------- 2. árvore oficial ----------
    grade = escolher_hiperparametros(tr, va)
    grade.drop(columns="f1_r").to_csv(SAIDA / "grade_validacao.csv", index=False)
    b = grade.iloc[0]
    depth = None if pd.isna(b.max_depth) else int(b.max_depth)
    modelo = DecisionTreeClassifier(criterion=b.criterio, max_depth=depth,
                                    min_samples_leaf=int(b.min_samples_leaf), random_state=SEED)
    modelo.fit(X_de(tr, FEATURES), tr[COL_CLASSE])           # fit SÓ no treino
    joblib.dump(modelo, SAIDA / "arvore_oficial.joblib")

    txt = export_text(modelo, feature_names=FEATURES)
    (SAIDA / "arvore_oficial.txt").write_text(txt, encoding="utf-8")
    fig, ax = plt.subplots(figsize=(22, 10))
    plot_tree(modelo, feature_names=FEATURES, class_names=list(modelo.classes_),
              filled=True, rounded=True, fontsize=7, ax=ax, max_depth=4)
    fig.savefig(SAIDA / "arvore_oficial.png", dpi=130, bbox_inches="tight")
    plt.close(fig)

    regras = regras_da_arvore(modelo, FEATURES)
    # as 3 primeiras regras: maior folha de cada classe presente (cobre OK, RISCO e FALHA)
    destaque = []
    for c in CLASSES:
        cand = [r for r in regras if r[1] == c]
        if cand:
            destaque.append(cand[0])
    (SAIDA / "regras_arvore.txt").write_text("\n".join(texto_regra(r) for r in regras), encoding="utf-8")

    # ---------- 3. leitura do erro (validação) ----------
    yv = va[COL_CLASSE]
    pv = modelo.predict(X_de(va, FEATURES))
    cm = pd.DataFrame(confusion_matrix(yv, pv, labels=CLASSES),
                      index=[f"real_{c}" for c in CLASSES], columns=[f"prev_{c}" for c in CLASSES])
    cm.to_csv(SAIDA / "matriz_validacao.csv")
    rel = pd.DataFrame(classification_report(yv, pv, labels=CLASSES, output_dict=True,
                                             zero_division=0)).T.round(4)
    rel.to_csv(SAIDA / "metricas_validacao.csv")
    f1_macro = f1m(yv, pv)
    acc = accuracy_score(yv, pv)

    # erros concretos: longo estável OK->FALHA; curto FALHA->OK
    erros = pd.DataFrame()
    va = va.assign(pred=pv)
    try:
        ficha = pd.read_csv(BASELINE)[[COL_FLUXO, COL_MEDIANA]]
        va = va.merge(ficha, on=COL_FLUXO, how="left")
        corte = ficha[COL_MEDIANA].median()      # só para descrever "curto"/"longo"; não é rótulo
        va["caminho"] = np.where(va[COL_MEDIANA] >= corte, "longo", "curto")
    except Exception as e:  # sem ficha: descreve sem curto/longo
        print("Aviso: sem ficha de baseline para separar curto/longo:", e)
        va["caminho"] = "n/d"
    cols_show = [COL_FLUXO, COL_TS, "caminho"] + FEATURES + [COL_CLASSE, "pred"]
    e1 = va[(va[COL_CLASSE] == "OK") & (va.pred == "FALHA") & (va.caminho != "curto")]
    e2 = va[(va[COL_CLASSE] == "FALHA") & (va.pred == "OK")]
    erros = pd.concat([e1.head(5).assign(tipo="longo_estavel_OK->FALHA"),
                       e2.head(5).assign(tipo="FALHA->OK")])
    if len(erros):
        erros[["tipo"] + cols_show].to_csv(SAIDA / "erros_concretos.csv", index=False)

    # ---------- 4. árvore de contraste ----------
    contraste_cols = list(FEATURES)
    extras = [c for c in (COL_RTT, COL_MEDIANA) if c in df.columns]
    trc = tr.copy()
    if COL_MEDIANA not in trc.columns:
        try:
            trc = trc.merge(pd.read_csv(BASELINE)[[COL_FLUXO, COL_MEDIANA]], on=COL_FLUXO, how="left")
            extras = [c for c in (COL_RTT, COL_MEDIANA) if c in trc.columns]
        except Exception:
            pass
    contraste_cols += extras
    if COL_ROTA in trc.columns:
        trc["rota_cod"] = trc[COL_ROTA].astype("category").cat.codes
        contraste_cols.append("rota_cod")
    mc = DecisionTreeClassifier(criterion=b.criterio, max_depth=depth,
                                min_samples_leaf=int(b.min_samples_leaf), random_state=SEED)
    mc.fit(X_de(trc, contraste_cols), trc[COL_CLASSE])
    raiz = contraste_cols[mc.tree_.feature[0]]
    lim = mc.tree_.threshold[0]
    imp = pd.Series(mc.feature_importances_, index=contraste_cols).sort_values(ascending=False).round(4)
    (SAIDA / "arvore_contraste.txt").write_text(export_text(mc, feature_names=contraste_cols),
                                                encoding="utf-8")

    # contraste auxiliar: só grandezas absolutas (o "atalho da distância" em estado puro)
    abs_cols = [c for c in (COL_RTT, COL_MEDIANA) if c in trc.columns]
    aux_txt = "n/d"
    if abs_cols:
        ma = DecisionTreeClassifier(criterion=b.criterio, max_depth=depth,
                                    min_samples_leaf=int(b.min_samples_leaf), random_state=SEED)
        ma.fit(X_de(trc, abs_cols), trc[COL_CLASSE])
        vac = va.copy()
        if COL_RTT not in vac.columns:
            vac[COL_RTT] = np.nan
        pa = ma.predict(X_de(vac, abs_cols))
        aux_txt = (f"colunas={abs_cols}; raiz=`{abs_cols[ma.tree_.feature[0]]} <= {ma.tree_.threshold[0]:.3f}`; "
                   f"F1 macro validação={f1m(yv, pa):.4f}; recall FALHA="
                   f"{((pa == 'FALHA') & (yv.values == 'FALHA')).sum() / max((yv == 'FALHA').sum(), 1):.4f}")
        (SAIDA / "arvore_contraste_so_absoluto.txt").write_text(
            export_text(ma, feature_names=abs_cols), encoding="utf-8")

    # ---------- teste (opcional, fechado por padrão) ----------
    teste_txt = "Teste não medido nesta tarefa (fica fechado até a Tarefa 5)."
    if MEDIR_TESTE:
        pt = modelo.predict(X_de(te, FEATURES))
        teste_txt = f"F1 macro no teste (apenas registro, não usado p/ escolher nada): {f1m(te[COL_CLASSE], pt):.4f}"

    # ---------- relatório pronto para colar no diário ----------
    imp_of = pd.Series(modelo.feature_importances_, index=FEATURES).sort_values(ascending=False).round(4)
    L = []
    L.append("## Resultado automático — Tarefa 3\n")
    L.append(f"**Colunas usadas:** {', '.join(FEATURES)}\n")
    L.append(f"**Recorte:** treino N={len(tr)} | validação N={len(va)} | teste N={len(te)} "
             f"(semente={SEED})\n")
    L.append(f"**Critério, profundidade pedida, profundidade obtida, folhas:** critério={b.criterio}; "
             f"max_depth={depth}; min_samples_leaf={int(b.min_samples_leaf)}; "
             f"profundidade obtida={modelo.get_depth()}; folhas={modelo.get_n_leaves()}; "
             f"F1 macro validação={b.f1_macro_val:.4f}\n")
    L.append("**Importância das colunas (árvore oficial):**\n```\n" + imp_of.to_string() + "\n```\n")
    L.append("**Regras lidas da árvore (maior folha de cada classe):**\n")
    for i, r in enumerate(destaque, 1):
        L.append(f"{i}. {texto_regra(r)}")
    L.append("\n**Matriz 3×3 (validação, linhas = real, colunas = previsto):**\n```\n"
             + cm.to_string() + "\n```\n")
    L.append("**Precisão / recall / F1 (validação):**\n```\n" + rel.to_string() + "\n```\n")
    L.append(f"**F1 macro (validação): {f1_macro:.4f}** — acurácia: {acc:.4f} "
             f"(a acurácia não decide: maioria OK).\n")
    L.append("**Erros concretos:**\n")
    if len(erros):
        L.append("```\n" + erros[["tipo"] + cols_show].to_string(index=False) + "\n```\n")
    else:
        L.append("Nenhum caso de caminho longo estável em FALHA nem de FALHA curta em OK "
                 "apareceu na validação.\n")
    L.append(f"**Árvore de contraste — raiz:** `{raiz} <= {lim:.3f}`\n")
    L.append("Importâncias (contraste):\n```\n" + imp.head(6).to_string() + "\n```\n")
    L.append(f"Colunas do contraste: {contraste_cols}\n")
    L.append(f"**Contraste auxiliar (só absoluto):** {aux_txt}\n")
    L.append(teste_txt + "\n")
    L.append("**Grade testada na validação (top 5):**\n```\n"
             + grade.drop(columns="f1_r").head(5).to_string(index=False) + "\n```\n")
    (SAIDA / "resultado_tarefa3.md").write_text("\n".join(L), encoding="utf-8")
    json.dump(dict(criterio=b.criterio, max_depth=depth, min_samples_leaf=int(b.min_samples_leaf),
                   seed=SEED, f1_macro_val=float(f1_macro), raiz_contraste=raiz),
              open(SAIDA / "config_modelo.json", "w"), indent=2)
    print("\n".join(L))
    print(f"\nArquivos gerados em: {SAIDA.resolve()}")


if __name__ == "__main__":
    main()
