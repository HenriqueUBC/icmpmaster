"""Gera/valida o pacote da árvore V1 sem retreinar nem sobrescrever entrega existente.

Uso (na raiz do repositório):
    .\\.venv\\Scripts\\python.exe empacotar_modelo.py
    .\\.venv\\Scripts\\python.exe empacotar_modelo.py --destino pacote_modelo_novo

Por segurança, se os 3 arquivos já existem, SOMENTE valida e preserva seus bytes.
Para regenerar, forneça outro diretório vazio com --destino.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import joblib
import pandas as pd

import modelo_icmp as mi

RAIZ = Path(__file__).resolve().parent
NOMES = ("modelo.joblib", "metadados.json", "baseline.csv")


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


def _gerar_pacote_novo(destino: Path, arvore, features: list[str]) -> None:
    """Só é chamado se NENHUM arquivo do pacote existir no destino."""
    config = json.loads(mi.ARQ_CONFIG.read_text(encoding="utf-8"))
    destino.mkdir(parents=True, exist_ok=True)
    pacote = {
        "modelo": arvore,
        "features": features,
        "familia": "DecisionTreeClassifier",
        "params": arvore.get_params(),
    }
    joblib.dump(pacote, destino / "modelo.joblib")
    shutil.copy2(RAIZ / "data/processed/baseline_por_fluxo.csv", destino / "baseline.csv")
    metadados = {
        "origem": "Tarefa 4 — árvore oficial V1, sem retreinamento",
        "features": features,
        "horizonte_rodadas": config.get("horizonte_rodadas", 3),
        "horizonte_min_estimado": config.get("horizonte_min", 12),
        "baseline": "baseline.csv; apenas fluxos RIPE Atlas com status=ok",
        "sentinela": mi.SENTINELA,
        "classes": list(mi.CLASSES),
        "status_real": "exclusivamente avaliação, nunca feature",
    }
    (destino / "metadados.json").write_text(
        json.dumps(metadados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _validar(destino: Path, arvore, features: list[str]) -> int:
    pacote = joblib.load(destino / "modelo.joblib")
    if not isinstance(pacote, dict) or not {"modelo", "features", "familia", "params"}.issubset(pacote):
        raise ValueError("modelo.joblib não contém o dicionário esperado")
    if list(pacote["features"]) != features:
        raise ValueError("Ordem das 11 features do pacote difere do modelo oficial")
    if pacote["modelo"].n_features_in_ != len(features):
        raise ValueError("Quantidade de features do estimador incompatível")

    metadados = json.loads((destino / "metadados.json").read_text(encoding="utf-8"))
    features_meta = metadados.get("features_ordem_exata", metadados.get("features"))
    if features_meta is None or list(features_meta) != features:
        raise ValueError("metadados.json diverge da ordem das features da árvore")

    baseline = pd.read_csv(destino / "baseline.csv")
    colunas_minimas = {"fluxo_id", "status", "mediana", "MAD", "iqr", "jitter_tipico"}
    if not colunas_minimas.issubset(baseline.columns):
        raise ValueError("baseline.csv sem colunas essenciais")
    if baseline["fluxo_id"].duplicated().any():
        raise ValueError("baseline.csv com fluxo_id duplicado")
    if not baseline["status"].eq("ok").any():
        raise ValueError("baseline.csv sem fluxos com status=ok")

    # Mantém a mesma comparação entre a árvore em uso e a árvore empacotada.
    teste = RAIZ / "data/processed/dataset_rotulado_B.csv"
    if not teste.is_file():
        raise FileNotFoundError(f"Base necessária para validação não encontrada: {teste}")
    amostra = pd.read_csv(teste, nrows=20)
    amostra = mi.adicionar_tendencia(amostra)
    referencia = mi.prever_12min(amostra, arvore, features)
    empacotada = mi.prever_12min(amostra, pacote["modelo"], pacote["features"])
    if not referencia.equals(empacotada):
        raise ValueError("Pacote alterou as previsões em comparação à árvore original")
    return len(referencia)


def empacotar(destino: Path | None = None) -> None:
    destino = (destino or (RAIZ / "pacote_modelo")).resolve()
    arvore, features = mi.carregar_modelo()
    caminhos = [destino / nome for nome in NOMES]
    existentes = [caminho for caminho in caminhos if caminho.exists()]

    if existentes and len(existentes) != len(NOMES):
        raise RuntimeError(
            "Pacote incompleto no destino; para não sobrescrever dados, use "
            "--destino com outro diretório vazio, ou complete o pacote manualmente."
        )
    preservado = len(existentes) == len(NOMES)
    antes = {c.name: sha256(c) for c in caminhos} if preservado else {}
    if not preservado:
        _gerar_pacote_novo(destino, arvore, features)

    n = _validar(destino, arvore, features)
    depois = {c.name: sha256(c) for c in caminhos}
    if preservado and antes != depois:
        raise RuntimeError("Arquivos do pacote existente foram alterados inesperadamente")
    print("Pacote EXISTENTE preservado e validado." if preservado else "Novo pacote gerado e validado.")
    print(f"Comparação de previsões: {n} linhas; sem divergências")
    print(f"Destino: {destino}")
    for nome, hash_hex in depois.items():
        print(f"SHA-256 {nome}: {hash_hex}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destino", type=Path, default=RAIZ / "pacote_modelo")
    args = parser.parse_args()
    empacotar(args.destino)
