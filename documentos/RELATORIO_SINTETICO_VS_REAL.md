# Relatório de comparação: dataset sintético × log real

Gerado por `python comparar_sintetico_real.py` (semente 42). Alvo = classe 3 rodadas (~12 min) à frente.
Treino/teste sintético: 1020/636 linhas. Treino/teste real: 80209/47890 linhas.

| Teste | Modelo | N | Acurácia | F1 macro | Recall RISCO | Recall FALHA |
|---|---|---|---|---|---|---|
| teste SINTÉTICO | V1 oficial (treinada no real) | 636 | 0,640 | 0,468 | 0,000 | 0,763 |
| teste SINTÉTICO | Sintética (treinada no sintético) | 636 | 0,593 | 0,470 | 0,125 | 0,346 |
| teste SINTÉTICO | Real* (mesmos hiperparâmetros, retreinada no real) | 636 | 0,643 | 0,461 | 0,000 | 0,712 |
| teste SINTÉTICO | Persistência (repetir a classe atual) | 636 | 0,736 | 0,676 | 0,500 | 0,615 |
| teste REAL (Tarefa 5) | V1 oficial (treinada no real) | 47890 | 0,882 | 0,677 | 0,229 | 0,687 |
| teste REAL (Tarefa 5) | Sintética (treinada no sintético) | 47890 | 0,686 | 0,380 | 0,482 | 0,045 |
| teste REAL (Tarefa 5) | Real* (mesmos hiperparâmetros, retreinada no real) | 47890 | 0,884 | 0,671 | 0,207 | 0,680 |
| teste REAL (Tarefa 5) | Persistência (repetir a classe atual) | 47890 | 0,845 | 0,669 | 0,383 | 0,714 |

## Leitura

- **Árvore sintética no teste sintético:** acurácia 0,593 (F1 macro 0,470). **No teste real:** acurácia 0,686, mas F1 macro 0,380 (a acurácia sobe só porque o real tem mais OK).
- **Árvore V1 no teste real:** acurácia 0,882 (F1 macro 0,677). **No teste sintético:** 0,640.
- **Retreino no log real** (Real*, mesmo algoritmo da sintética): acurácia 0,884 no real, contra 0,686 da árvore treinada só no sintético.
- **Transferência:** a árvore treinada só no sintético acerta 0,686 no real (recall de FALHA 0,045), contra 0,884 (recall de FALHA 0,680) do retreino no log real: é o motivo de retreinar com dados reais na Sprint 5.
- A persistência (repetir a classe atual) alcança 0,736 no sintético e 0,845 no real: é a referência que a árvore precisa superar.

## Cuidados

1. Os rótulos sintéticos vêm de regras artificiais do gerador (blocos de RISCO e FALHA); os reais, das regras da Tarefa 2. Acurácias entre conjuntos diferentes **não são equivalentes**: servem para comparar o comportamento do método.
2. Distribuições diferentes (o sintético tem muito mais RISCO e FALHA que o real); por isso o F1 macro e o recall por classe importam mais que a acurácia isolada.
3. Nenhum modelo salvo foi alterado: a V1 oficial é só carregada.
