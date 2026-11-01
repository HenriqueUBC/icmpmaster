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
pytest -q tests             # testes unitários e integração offline
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
- Há coleta periódica RIPE Atlas; não há ping direto. A coleta depende da API e não garante resultados instantâneos.

## Complementação — monitoramento e contrato (2026-11)

- **RIPE Atlas:** `monitoramento_icmp.py` (coleta periódica existente), painel `pages/2_Monitoramento_automatico.py`.
- **Simulação artificial:** `.\.venv\Scripts\python.exe simulador_icmp.py --cenario FALHA` (ou `OK` / `RISCO`). Não realiza tráfego real.
- **Dados sintéticos:** `.\.venv\Scripts\python.exe experimento_sintetico.py` cria `resultados_sinteticos/` e relatório exclusivo de dados sintéticos.
- **Empacotamento:** `.\.venv\Scripts\python.exe empacotar_modelo.py` gera e verifica `pacote_modelo/modelo.joblib`, `metadados.json`, `baseline.csv`.
- **Testes:** `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`.
- **Interface:** `.\.venv\Scripts\python.exe -m streamlit run app.py` e páginas de monitoramento no menu lateral.

Consulte `documentos/IMPLEMENTACAO_COMPLEMENTAR.md` para limitações, campos do contrato e separação entre predição, observação e simulação.

**Nota:** a seção histórica acima que diz que ainda não há monitoramento ao vivo descreve o estado anterior do projeto. A coleta periódica RIPE Atlas foi adicionada posteriormente. A coleta não é instantânea; depende da API e das sondas. O simulador utiliza dados artificiais, sem tráfego de rede.

## Revisão técnica (novembro de 2026)

- Fonte exclusiva de **medições reais**: RIPE Atlas. `ping_local.py` e `baseline_local.py` não fazem parte desta versão.
- `baseline_sintetico.py` é usado **somente** no experimento artificial, sem tocar no baseline oficial.
- O simulador usa a árvore V1 original, mas as classes previstas podem diferir do cenário artificial selecionado.
- O experimento `experimento_sintetico.py` treina **outra árvore** exclusivamente com dados artificiais; não mede o desempenho da árvore V1.
- Os modelos serializados foram produzidos com `scikit-learn==1.9.1`; valide-os nessa versão.
- Consulte `documentos/RELATORIO_REVISAO_2026-11.md` para resultados e pendências.
