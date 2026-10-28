# ICMPMASTER

## Objetivo

Software para analisar os testes de ICMP e recomendar ações para os sistemas de rede.
Classifica cada fluxo (`probe_id|dst_addr`) em **OK**, **RISCO** ou **FALHA** pelo desvio
do RTT em relação ao baseline do próprio fluxo, com uma árvore de decisão.

## Integrantes do grupo

- Eduardo Quintino Filho
- Felipe Veiga da Silva
- Henrique de Aguiar Fernandes
- Niccolas Lupetti dos Santos
- Tharik Lima da Silva

## Como rodar

```
pip install -r requirements.txt
streamlit run app.py        # dashboard histórico + página "Simulador de eventos"
pytest -q tests             # testes dos cenários OK, RISCO e FALHA
```

## Estrutura

| Pasta / arquivo | Conteúdo |
|---|---|
| `config/` | `coleta.py` e `coleta_config.json` (coleta no RIPE Atlas, somente `GET`) |
| `data/` | `interim/` (bruto tratado) e `processed/` (ficha de baseline e dataset rotulado) |
| `documentos/notebooks/` | diários das Tarefas 1 a 5, RFC, dicionários v0.1 a v0.4 e notebooks |
| `documentos/notebooks/Arvore/saida_tarefa4/` | árvore ajustada (`arvore_ajustada.joblib`) e regras |
| `documentos/notebooks/Arvore/saida_tarefa5/` | resultado do teste único |
| `documentos/Diagramas/` | diagramas de classe, caso de uso, atividade e sequência |
| `modelo_icmp.py` | integração da árvore: colunas de tendência, rótulo atual e previsão a 12 min |
| `app.py` e `pages/` | dashboard e simulador de eventos (Streamlit) |
| `tests/` | testes integrados |

## Estado do projeto

- A árvore é um **detector** do estado atual: no teste (Tarefa 5) ela ficou praticamente igual a
  "repetir a classe atual" (F1 macro 0,6772 contra 0,6695).
- Fluxo sem ficha de baseline (menos de 1.500 RTT válidos no Período A) não é classificado.
- Ainda não há monitoramento ao vivo.
