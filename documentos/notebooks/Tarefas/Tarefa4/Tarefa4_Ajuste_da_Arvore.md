# Diário da Tarefa 4 — Ajuste da árvore a partir do erro

**Período:** 05/10/2026 a 11/10/2026  
**Projeto:** Preditor de degradação de rede com RTT normalizado (independente da rota)

**Equipe:** ICMPMASTER  
**Scrum Master da tarefa:** `[GRUPO]`  
**Repositório GitHub:** https://github.com/sgntgifc0c/icmpmaster

> O rótulo e o baseline da Tarefa 2 continuam. O corte temporal continua. Esta tarefa **não troca o algoritmo**: ajusta a mesma árvore de decisão com o que a Tarefa 3 errou.
>
> Ajuste permitido: profundidade, mínimo de amostras na folha, critério (Gini ou entropia) e poda. Se entrar coluna nova, ela tem de ser outra métrica **relativa ao baseline** (tendência do `z_robusto` nas janelas anteriores, por exemplo). País, IP, rota e RTT absoluto continuam fora.

### Contrato desta tarefa

| | Artefato | Origem / destino |
|---|---|---|
| **Entra** | Árvore da Tarefa 3, matriz e erros | Tarefa 3 |
| **Entra** | Mesmo baseline, mesmo rótulo, mesmo corte | Tarefa 2 |
| **Sai** | Árvore ajustada e tabela Tarefa 3 → Tarefa 4 (F1 macro e recall de FALHA na validação) | Tarefa 5 usa **esta** árvore como ponto de partida |
| **Sai** | Regras novas em português | Tarefa 5 |
| **Sai** | Dicionário v0.3, se nasceu coluna relativa nova | Tarefa 5 |

**Não sai daqui:** outro tipo de modelo, mudança do teste, recálculo do baseline com o Período B.

- [x] O corte é o da Tarefa 2 (coluna `particao` lida sem alteração; o alvo a 12 min nunca cruza de um bloco para outro)
- [x] Nenhuma coluna de rota entrou (o notebook tem um `assert` contra classe, `fluxo_id`, RTT, mediana, rota, IP e país)

---

## 1. O que o erro pediu

- [x] Citar os erros da Tarefa 3 (classe confundida, caminho longo ou curto, pico isolado virando FALHA, RISCO sumindo)
- [x] Cada mudança da árvore responde a um desses erros
- [x] Parâmetros escolhidos na validação

**Ponto de partida.** Com o alvo da Tarefa 3 (classe da própria rodada) a árvore tinha F1 macro 0,9999 e só 2 erros na validação, ambos FALHA classificada como OK por 0,0002 e 0,0014 acima do limiar 3,5. Ela só redescobriu a regra do rótulo, então não havia erro real a corrigir. O RFC define o preditor como o estado **12 minutos à frente**. Por isso o alvo desta tarefa é a classe da rodada 3 posições depois (3 × 240 s), no mesmo fluxo e no mesmo bloco. O rótulo, o baseline e o corte da Tarefa 2 não mudam. Nesse alvo (validação, N = 31.909), a árvore da Tarefa 3, sem retreinar, tem F1 macro 0,687, recall de FALHA 0,694 e recall de RISCO 0,455.

**Erro da Tarefa 3 → mudança na árvore:**

| Erro observado | Mudança (profundidade, folha, critério ou métrica relativa nova) |
|---|---|
| **Classe confundida / detector que decorou o rótulo:** F1 0,9999 só porque as colunas são as da tabela de rotulagem. Neste alvo a Tarefa 3 confunde muito: 1.193 FALHA previstas como OK e 1.127 OK previstos como FALHA. | Alvo passa a ser a classe 12 min à frente (horizonte do RFC). Não é troca de algoritmo nem de rótulo. |
| **Pico isolado virando FALHA:** dos 1.497 falsos alarmes de FALHA da Tarefa 3, 710 são pico isolado (`z_robusto` ≥ 3,5 com a rodada anterior < 2). Dos 862 picos isolados da validação, só 17,5% viram FALHA 12 min depois. | Três colunas novas, relativas ao baseline e só com rodadas passadas: `z_delta1`, `z_media3_ant`, `z_inclin5` (dicionário v0.3). |
| **RISCO sumindo:** 986 dos 2.487 RISCO da validação previstos como OK (recall 0,455). | Poda e hiperparâmetros escolhidos na validação (critério, profundidade, folha mínima e `ccp_alpha`). A árvore ficou menor (20 folhas), mas o recall de RISCO **piorou** (0,342). Isto não está resolvido. |
| **Caminho longo ou curto:** a Tarefa 3 acerta igual nos dois (84,1% curto e 84,5% longo), mas o recall de FALHA é menor no curto (0,629 contra 0,742). | Nenhuma mudança. Nenhuma coluna de distância entra. Fica para acompanhar na Tarefa 5. |

## 2. Árvore ajustada

- [x] Mesmas colunas relativas, mais o que a tabela acima acrescentou
- [x] Profundidade, folhas e três regras em português
- [x] Fit só no treino

**Parâmetros finais candidatos (ainda não é o teste):** critério **gini**; `max_depth` = **8** (profundidade obtida 8); `min_samples_leaf` = **1**; `ccp_alpha` = **0,0005** (poda); **20 folhas**; `random_state` = 42. Grade de 150 combinações (2 critérios × 5 profundidades × 5 folhas mínimas × 3 podas), escolha pelo maior F1 macro na validação e, em empate, menos folhas. Colunas (11): `z_robusto`, `aumento_pct`, `jitter_relativo`, `perda_pct`, `timeout_atual`, `n5_timeout`, `n5_aumento80`, `n5_risco`, `z_delta1`, `z_media3_ant`, `z_inclin5`. Importância: `z_robusto` 0,611; `n5_risco` 0,174; `z_media3_ant` 0,117; `n5_aumento80` 0,042; `n5_timeout` 0,025; `z_inclin5` 0,012; `z_delta1` 0,010; `aumento_pct` 0,010. Árvore em `documentos/notebooks/Arvore/saida_tarefa4/`.  
**Regras** (as maiores folhas de cada classe, copiadas de `regras_arvore.txt`):

1. **OK** (n = 38.596 no treino, pureza 96%): se `z_robusto` ≤ 3,06, não há timeout nem aumento acima de 80% nas últimas 5 rodadas, nenhuma das últimas 5 é suspeita (`n5_risco` = 0) e o `z_robusto` não caiu bruscamente (`z_delta1` > −2,4), então o estado em 12 min é OK.
2. **RISCO** (n = 1.507, pureza 91%): se `z_robusto` ≤ 4,0 e as 5 últimas rodadas são todas suspeitas (`n5_risco` = 5), então o estado em 12 min é RISCO.
3. **FALHA** (n = 7.868, pureza 96%): se `z_robusto` > 4,0, a média do `z_robusto` das 3 rodadas anteriores é > 2,49 (o fluxo já vinha alto) e a inclinação das últimas 5 é ≤ 0,99, então o estado em 12 min é FALHA.

## 3. Comparação na validação

| | F1 macro | Recall de FALHA | Recall de RISCO |
|---|---|---|---|
| Árvore da Tarefa 3 (sem retreinar, alvo 12 min) | 0,6872 | 0,6944 | 0,4548 |
| Árvore desta tarefa | 0,7143 | 0,6825 | 0,3422 |

- [x] Se não houve ganho, dizer o que foi tentado e descartado
- [x] Matriz 3×3 da árvore desta tarefa, na validação

**Matriz 3×3 (validação, linhas = real, colunas = previsto):**

| | prev OK | prev RISCO | prev FALHA |
|---|---|---|---|
| **real OK** | 23.887 | 195 | 442 |
| **real RISCO** | 1.345 | 851 | 291 |
| **real FALHA** | 1.424 | 131 | 3.343 |

**Tentado e descartado:** (A) só hiperparâmetros e poda, com as 8 colunas da Tarefa 3: F1 macro 0,6953, recall de FALHA 0,646 e de RISCO 0,342. O ganho foi menor, e a coluna de tendência acrescentou +0,019 de F1 macro sobre isso. A grade completa das duas tentativas está em `saida_tarefa4/grade_A_so_hiperparametros.csv` e `grade_B_com_tendencia.csv`. O teste não foi medido.

**Leitura do ganho (ou da falta de ganho):** o ganho é pequeno e misto. O F1 macro sobe de 0,687 para 0,714 (+0,027), e os falsos alarmes de FALHA caem pela metade (1.497 para 733), porque a tendência separa pico isolado de degradação sustentada. Em troca, o recall de FALHA cai um pouco (0,694 para 0,683) e o de RISCO cai bastante (0,455 para 0,342): 1.345 RISCO viram OK, contra 986 antes. A escolha pelo F1 macro favorece a precisão de OK e FALHA. Como o RFC trata errar FALHA como o erro mais caro, vale o grupo e o docente decidirem se a Tarefa 5 passa a priorizar o recall de FALHA e de RISCO. Os números não são comparáveis aos 0,9999 da Tarefa 3, que era outro alvo (a rodada atual).

## 4. Revisão com o docente

**O que foi mostrado:** `[GRUPO]`  
**O que foi pedido para ajustar antes da Tarefa 5:** `[GRUPO]`

## 5. Scrum e diário

- [x] Board atualizado — [Trello](https://trello.com/b/75gwQNwl/estrutura-de-dados-ii)


| Integrante | O que fiz nesta tarefa | Dificuldades | O que pretendo manter/ajustar |
|---|---|---|---|
| Eduardo Quintino Filho | Contribuí para compreender a mudança do objetivo para prever a classe da rede com antecedência de 12 minutos. | Entender como avaliar uma previsão futura sem utilizar informações que ainda não estariam disponíveis. | Manter o horizonte de previsão documentado e verificar se as variáveis respeitam a ordem temporal. |
| Felipe Veiga da Silva | Contribuí para acompanhar o uso de atributos históricos e a avaliação da árvore ajustada. | Garantir que as janelas de análise utilizassem apenas medições anteriores ao instante previsto. | Manter a separação temporal e revisar as métricas de cada classe. |
| Henrique de Aguiar Fernandes | Contribuí para organizar o acompanhamento das mudanças necessárias após os resultados da árvore inicial. | Alinhar as alterações do experimento com o objetivo de previsão futura definido no projeto. | Manter o histórico das decisões e verificar se as alterações atendem aos requisitos. |
| Niccolas Lupetti dos Santos | Contribuí para compreender os novos atributos históricos, como variação recente, média anterior e inclinação das métricas. | Interpretar quais padrões passados poderiam ajudar a antecipar uma degradação futura. | Manter atributos calculados somente com dados passados e analisar sua contribuição para o modelo. |
| Tharik Lima da Silva | Contribuí para acompanhar a análise de erros e a investigação de alarmes que não correspondiam a falhas futuras

---

## Rubrica — Tarefa 4 (0 a 4,0)

| Critério | Peso | Nota máxima | Nota | Observações |
|---|---|---|---|---|
| Ajuste ligado ao erro | 1,5 | Cada mudança da árvore cita um erro da Tarefa 3; continua árvore de decisão | | |
| Rota fora do modelo | 1,0 | Nenhuma coluna de rota, país, IP ou RTT absoluto; baseline da Tarefa 2 intacto | | |
| Tabela Tarefa 3 → Tarefa 4 | 1,0 | F1 macro e recall de FALHA e de RISCO na validação, com leitura | | |
| Revisão + diário | 0,5 | Incremento mostrado ao docente; diário de todos | | |
| **Total** | **4,0** | | **___ / 4,0** | |
