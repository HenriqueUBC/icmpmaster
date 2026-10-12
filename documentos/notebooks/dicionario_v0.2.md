# Dicionário de Dados v0.2

## Projeto

*Projeto:* Preditor de degradação de rede com RTT normalizado  
*Tarefa:* Tarefa 2 — Baseline do fluxo e rotulagem OK, RISCO, FALHA

Os campos brutos da API (`fw`, `mver`, `result` etc.) continuam descritos no [dicionário v0.1](dicionario_v0.1.md). Este documento descreve as tabelas que saem da Tarefa 1 e da Tarefa 2.

---

## 1. Bruto tratado (`data/interim/medicoes.csv`)

Uma linha por rodada de ping. Sem classe. O JSON original em `raw/` não é alterado.

| Campo | Tipo | Unidade | Descrição |
|---|---|---|---|
| timestamp | data e hora | UTC | Instante da rodada. |
| measurement_id | inteiro | — | Identificador da medição no RIPE Atlas (`msm_id`). |
| probe_id | inteiro | — | Probe de origem (`prb_id`). |
| dst_addr | texto | — | Endereço de destino. |
| fluxo_id | texto | — | `probe_id\|dst_addr`. Só identifica o fluxo. |
| rtt_medio_ms | decimal | ms | Média dos RTT com resposta na rodada. Vazio se não houve resposta. Nunca 0. |
| rtt_min_ms | decimal | ms | Menor RTT da rodada. Vazio se não houve resposta. |
| rtt_max_ms | decimal | ms | Maior RTT da rodada. Vazio se não houve resposta. |
| enviados | inteiro | pacotes | Pacotes enviados na rodada. |
| recebidos | inteiro | pacotes | Pacotes recebidos na rodada. |
| perda_pct | decimal | % | `(enviados − recebidos) / enviados × 100`. Vazio se `enviados` = 0. |
| jitter_ms | decimal | ms | Desvio-padrão amostral dos RTT da rodada. Só com 2 ou mais respostas; senão, vazio. |
| timeout_atual | 0 ou 1 | — | 1 se não há RTT ou `perda_pct` = 100; senão 0. |

## 2. Ficha de baseline (`data/processed/baseline_por_fluxo.csv`)

Uma linha por `fluxo_id`, calculada só com o Período A e congelada.

| Campo | Tipo | Unidade | Descrição |
|---|---|---|---|
| fluxo_id | texto | — | Identificador do fluxo. |
| mediana | decimal | ms | Mediana dos RTT válidos de A. |
| MAD | decimal | ms | `mediana(\|RTT − mediana\|)` nos RTT válidos de A. |
| iqr | decimal | ms | Q3 − Q1 dos RTT válidos de A. Usado só quando `MAD` = 0. |
| jitter_tipico | decimal | ms | Mediana do `jitter_ms` de A, onde existe. |
| perda_tipica | decimal | % | Mediana do `perda_pct` de A, inclusive timeout. |
| prop_resposta | decimal | 0 a 1 | RTT válidos ÷ medições de A. |
| n_medicoes_A | inteiro | — | Medições do fluxo em A. |
| n_rtt_validos_A | inteiro | — | RTT válidos do fluxo em A. |
| status | texto | — | `ok`, ou `baseline_insuficiente` (menos de 1.500 RTT válidos em A). Neste caso os campos de estatística ficam vazios e o fluxo não recebe classe. |

## 3. Métricas e classe (`data/processed/dataset_rotulado_B.csv`)

Uma linha por rodada do Período B, de fluxos com `status` = `ok`.

| Campo | Tipo | Unidade | Descrição |
|---|---|---|---|
| fluxo_id | texto | — | Identificador do fluxo. Serve para ordenar e cortar; não é variável do modelo. |
| timestamp | data e hora | UTC | Instante da rodada. |
| z_robusto | decimal | — | `(RTT − mediana) / (1,4826 × MAD)`. Se `MAD` = 0: denominador `max(iqr / 1,349; 1 ms)`. Vazio sem RTT. |
| aumento_pct | decimal | % | `(RTT − mediana) / mediana × 100`. Vazio sem RTT. |
| jitter_relativo | decimal | — | `jitter_ms / jitter_tipico`. Com `jitter_tipico` = 0: vale 1 se o jitter é 0 e 3 se é maior que 0. Vazio sem jitter atual. |
| perda_pct | decimal | % | Perda da rodada (mesma definição da seção 1). |
| timeout_atual | 0 ou 1 | — | 1 se não há RTT ou `perda_pct` = 100. |
| n5_timeout | inteiro | 0 a 5 | Timeouts nas últimas 5 medições do fluxo, incluindo a atual. |
| n5_aumento80 | inteiro | 0 a 5 | Quantas das últimas 5 têm `aumento_pct` > 80. |
| n5_risco | inteiro | 0 a 5 | Quantas das últimas 5 cumprem o critério da linha 5 da tabela de rótulo. |
| classe | texto | — | `OK`, `RISCO` ou `FALHA`, pela tabela da Tarefa 2 (primeira linha verdadeira). |
| particao | texto | — | `treino`, `validacao` ou `teste`: recorte temporal 50/20/30 por fluxo dentro de B. |

As janelas `n5_*` usam só linhas de B. No começo de B a janela tem menos de 5 medições.

## 4. Colunas proibidas na árvore

| Coluna | Onde existe | Motivo |
|---|---|---|
| País de origem e de destino | `data/interim/probes_paises.csv` | Só auditoria de diversidade. A falha não pode depender de geografia. |
| IP (`dst_addr`) | `medicoes.csv` | Identifica a rota, não a degradação. |
| `rota_id` / nome da rota | não existe nas tabelas | Fora do projeto. |
| `fluxo_id` | `medicoes.csv`, ficha e dataset B | Só identificador. |
| RTT absoluto (`rtt_medio_ms`, `rtt_min_ms`, `rtt_max_ms`) | `medicoes.csv` | Não substitui as métricas relativas. RTT alto não é falha. |
| `timestamp`, `particao`, `classe` | dataset B | Ordenação, corte e alvo; não são variáveis de entrada. |

## 5. Observações

- O Período A não é rotulado e não entra no dataset B.
- Fluxo com `baseline_insuficiente` não recebe classe e não aparece no dataset B.
- Timeout fica no dataset como evento (`timeout_atual` = 1); nunca vira RTT 0.
- Medições com `enviados` = 0 (erro de envio) têm `perda_pct` vazia e contam como timeout.
- Os 30 CSVs pequenos antigos entram sem `enviados`, `recebidos`, `rtt_min_ms`, `rtt_max_ms` e `jitter_ms` (fórmula de jitter diferente). Estão fora dos Períodos A e B e não recebem ficha nem classe.

---

## Fonte

*Fonte dos dados:* RIPE Atlas (somente `GET`, sem criar medição)  
*Tipo de coleta:* medições públicas de ping ICMP  
*Formato original:* JSON
