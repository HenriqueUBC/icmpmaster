# Dicionário de Dados v0.3

*Projeto:* Preditor de degradação de rede com RTT normalizado  
*Tarefa:* Tarefa 4 — Ajuste da árvore a partir do erro

Continua valendo o [dicionário v0.2](dicionario_v0.2.md) (bruto, ficha, métricas e classe). Aqui entram só as colunas novas e o alvo a 12 minutos.

## 1. Colunas novas (relativas ao baseline, só rodadas passadas)

Calculadas no notebook da Tarefa 4 a partir do `z_robusto` do `dataset_rotulado_B.csv`, dentro de cada `fluxo_id`, em ordem de tempo. Não alteram o dataset da Tarefa 2.

| Campo | Tipo | Unidade | Descrição |
|---|---|---|---|
| z_delta1 | decimal | desvios robustos | `z_robusto` atual − `z_robusto` da rodada anterior. Vazio na primeira rodada ou se um dos dois não tem RTT. |
| z_media3_ant | decimal | desvios robustos | Média do `z_robusto` das 3 rodadas anteriores (mínimo de 2 válidas). Não inclui a rodada atual. |
| z_inclin5 | decimal | desvios robustos por rodada | Inclinação da reta ajustada ao `z_robusto` das últimas 5 rodadas, incluindo a atual. Vazio se alguma das 5 não tem RTT. |

Valor vazio vira o sentinela −999 só na entrada da árvore (nunca 0).

## 2. Alvo

| Campo | Descrição |
|---|---|
| y_fut | Classe (OK, RISCO ou FALHA, do rótulo da Tarefa 2) da rodada 3 posições depois, no mesmo fluxo (3 × 240 s = 12 min). Só vale se a rodada futura cai no mesmo bloco (`particao`) e a distância fica entre 660 e 780 s. Não é gravada em arquivo. |

## 3. Colunas de entrada da árvore ajustada (11)

`z_robusto`, `aumento_pct`, `jitter_relativo`, `perda_pct`, `timeout_atual`, `n5_timeout`, `n5_aumento80`, `n5_risco`, `z_delta1`, `z_media3_ant`, `z_inclin5`.

## 4. Continuam proibidas

País, IP, `rota_id`, `fluxo_id`, RTT absoluto, mediana do baseline e a própria classe. `z_anterior` aparece no notebook só para descrever erros e não é entrada da árvore.
