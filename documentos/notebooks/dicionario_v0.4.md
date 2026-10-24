# Dicionário de Dados v0.4

*Projeto:* Preditor de degradação de rede com RTT normalizado  
*Tarefa:* Tarefa 5 — Árvore final e teste único

Continuam valendo o [dicionário v0.2](dicionario_v0.2.md) (bruto, ficha, métricas e classe) e o [dicionário v0.3](dicionario_v0.3.md) (colunas de tendência e alvo). Nesta versão **não nasceu coluna nova**: a Tarefa 5 mede a árvore da Tarefa 4 sem retreinar. Este documento lista exatamente as 11 colunas que a árvore usa, o alvo e as colunas só descritivas do notebook da Tarefa 5.

## 1. Colunas de entrada da árvore final (11)

Todas relativas ao baseline do fluxo (Período A, congelado) e calculadas só com a rodada atual e rodadas passadas. Valor vazio vira o sentinela −999 só na entrada da árvore (nunca 0).

### Do dataset rotulado (`data/processed/dataset_rotulado_B.csv`)

| Campo | Tipo | Unidade | Descrição |
|---|---|---|---|
| z_robusto | decimal | desvios robustos | `(RTT − mediana) / (1,4826 × MAD)`. Se `MAD` = 0: denominador `max(iqr / 1,349; 1 ms)`. Vazio sem RTT. |
| aumento_pct | decimal | % | `(RTT − mediana) / mediana × 100`. Vazio sem RTT. |
| jitter_relativo | decimal | — | `jitter_ms / jitter_tipico`. Com `jitter_tipico` = 0: vale 1 se o jitter é 0 e 3 se é maior que 0. Vazio sem jitter atual. |
| perda_pct | decimal | % | `(enviados − recebidos) / enviados × 100`. Vazio se `enviados` = 0. |
| timeout_atual | 0 ou 1 | — | 1 se não há RTT ou `perda_pct` = 100; senão 0. |
| n5_timeout | inteiro | 0 a 5 | Timeouts nas últimas 5 medições do fluxo, incluindo a atual. |
| n5_aumento80 | inteiro | 0 a 5 | Quantas das últimas 5 têm `aumento_pct` > 80. |
| n5_risco | inteiro | 0 a 5 | Quantas das últimas 5 cumprem o critério da linha 5 da tabela de rótulo da Tarefa 2. |

### Calculadas no notebook da Tarefa 4 (definidas na v0.3)

| Campo | Tipo | Unidade | Descrição |
|---|---|---|---|
| z_delta1 | decimal | desvios robustos | `z_robusto` atual − `z_robusto` da rodada anterior. Vazio na primeira rodada ou se um dos dois não tem RTT. |
| z_media3_ant | decimal | desvios robustos | Média do `z_robusto` das 3 rodadas anteriores (mínimo de 2 válidas). Não inclui a rodada atual. |
| z_inclin5 | decimal | desvios robustos por rodada | Inclinação da reta ajustada ao `z_robusto` das últimas 5 rodadas, incluindo a atual. Vazio se alguma das 5 não tem RTT. |

## 2. Alvo

| Campo | Descrição |
|---|---|
| y_fut | Classe (OK, RISCO ou FALHA, do rótulo da Tarefa 2) da rodada 3 posições depois, no mesmo fluxo (3 × 240 s = 12 min). Só vale se a rodada futura cai no mesmo bloco (`particao`) e a distância fica entre 660 e 780 s. Não é gravada em arquivo. |

## 3. Colunas só descritivas (não entram na árvore)

| Campo | Onde aparece | Descrição |
|---|---|---|
| particao | `dataset_rotulado_B.csv` | `treino`, `validacao` ou `teste`: recorte temporal 50/20/30 por fluxo dentro do Período B (da Tarefa 2, sem alteração). O teste é o bloco `teste`. |
| caminho | notebook da Tarefa 5 | `longo` se a `mediana` do baseline do fluxo é maior ou igual à mediana das fichas; senão `curto`. Serve só para descrever acertos e erros. |
| pred | notebook da Tarefa 5 | Classe prevista pela árvore para o estado a 12 min. |

## 4. Saídas da Tarefa 5 (`saida_tarefa5/`)

| Arquivo | Conteúdo |
|---|---|
| matriz_teste.csv | Matriz 3×3 do teste, em contagem (linhas = real, colunas = previsto). |
| relatorio_teste.csv | Precisão, recall, F1 e suporte de OK, RISCO e FALHA no teste. |
| comparacao_persistencia_teste.csv | F1 macro e recalls da árvore contra “repetir a classe atual”. |
| fluxo_novo.csv | Resultado por fluxo nos 6 `fluxo_id` separados, com árvore auxiliar. |
| resultado_teste.json | F1 macro, recall de FALHA, N do teste, parâmetros e colunas. |

## 5. Continuam proibidas

País, IP, `rota_id`, `fluxo_id`, RTT absoluto, mediana do baseline como entrada e a própria classe. A `mediana` só é usada no notebook para separar `caminho` curto de longo, nunca como coluna da árvore.

## Observações

- A árvore usa exatamente as 11 colunas da seção 1. Nenhuma outra entra.
- Fluxo com `baseline_insuficiente` (menos de 1.500 RTT válidos no Período A) não recebe classe e não é avaliado.
- A árvore auxiliar usada no fluxo não visto tem os mesmos hiperparâmetros e as mesmas colunas, mas foi treinada sem os 6 fluxos separados. Não é a árvore oficial.

---

## Fonte

*Fonte dos dados:* RIPE Atlas (somente `GET`, sem criar medição)  
*Tipo de coleta:* medições públicas de ping ICMP  
*Formato original:* JSON
