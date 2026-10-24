# Diário da Tarefa 5 — Árvore final e teste único

**Período:** 12/10/2026 a 25/10/2026  
**Projeto:** Preditor de degradação de rede com RTT normalizado (independente da rota)

**Equipe:** ICMPMASTER  
**Scrum Master da tarefa:** `[GRUPO]`  
**Repositório GitHub:** https://github.com/HenriqueUBC/icmpmaster

> A árvore que entra aqui é a da Tarefa 4. O baseline e o rótulo são os da Tarefa 2. O teste, guardado desde a Tarefa 2, foi medido **uma vez**.

### Contrato desta tarefa

| | Artefato | Origem / destino |
|---|---|---|
| **Entra** | Corte da Tarefa 2 e ficha de baseline | Tarefa 2 |
| **Entra** | Árvore ajustada e regras | Tarefa 4 |
| **Sai** | Teste único: matriz 3×3, F1 por classe, F1 macro | Entrega |
| **Sai** | Checagem de fluxo não visto, com baseline próprio | Entrega |
| **Sai** | Ficha da árvore (abaixo) e dicionário v0.4 igual às colunas usadas | Entrega |

- [x] A profundidade não foi escolhida de novo olhando o teste (a árvore foi carregada de `arvore_ajustada.joblib`, sem retreinar)
- [x] O baseline do teste não usou medição do próprio teste (a ficha é só do Período A)

---

## 1. Árvore que será medida

- [x] Critério, profundidade, mínimo de amostras na folha, colunas
- [x] Três regras em português, as mesmas da Tarefa 4 (não foram revistas depois de abrir o teste)
- [x] Confirmação de que país, IP, rota e RTT absoluto não estão na árvore (o notebook tem um `assert` contra `classe`, `fluxo_id`, RTT, mediana, rota, IP e país)

**Parâmetros:** critério gini; `max_depth` = 8 (profundidade obtida 8); `min_samples_leaf` = 1; `ccp_alpha` = 0,0005 (poda); 20 folhas; `random_state` = 42. Escolhidos na validação (grade de 150 combinações) na Tarefa 4. Alvo: classe da rodada 3 posições depois (3 × 240 s = 12 min), no mesmo fluxo e no mesmo bloco.

**Colunas (11):** `z_robusto`, `aumento_pct`, `jitter_relativo`, `perda_pct`, `timeout_atual`, `n5_timeout`, `n5_aumento80`, `n5_risco`, `z_delta1`, `z_media3_ant`, `z_inclin5`.

**Regras** (as maiores folhas de cada classe, conferidas no notebook da Tarefa 5 com as da Tarefa 4):

1. **OK:** se `z_robusto` ≤ 3,06, não há timeout nem aumento acima de 80% nas últimas 5 rodadas, nenhuma das últimas 5 é suspeita (`n5_risco` = 0) e o `z_robusto` não caiu bruscamente (`z_delta1` > −2,4), o estado em 12 min é OK.
2. **RISCO:** se `z_robusto` ≤ 4,0 e as 5 últimas rodadas são todas suspeitas (`n5_risco` = 5), o estado em 12 min é RISCO.
3. **FALHA:** se `z_robusto` > 4,0, a média do `z_robusto` das 3 rodadas anteriores é > 2,49 (o fluxo já vinha alto) e a inclinação das últimas 5 é ≤ 0,99, o estado em 12 min é FALHA.

## 2. Teste temporal (uma vez)

Fluxos conhecidos, período mais recente do Período B (`particao` = teste, os 30% finais de cada fluxo). N = 47.890 medições, de 65 fluxos, de 13/09 a 20/09/2026. Classes reais: OK 37.438, RISCO 3.242, FALHA 7.210.

- [x] Matriz 3×3 com contagem, não só porcentagem
- [x] Precisão, recall e F1 de OK, RISCO e FALHA
- [x] F1 macro
- [x] Recall de FALHA e a troca RISCO ↔ FALHA comentados
- [x] Dois casos: um acerto em caminho longo estável (classe OK) e um erro relevante

**Matriz (contagem; linhas = real, colunas = previsto):**

| | prev OK | prev RISCO | prev FALHA |
|---|---|---|---|
| **real OK** | 36.535 | 240 | 663 |
| **real RISCO** | 2.179 | 744 | 319 |
| **real FALHA** | 2.169 | 88 | 4.953 |

| Classe | Precisão | Recall | F1 |
|---|---|---|---|
| OK | 0,8936 | 0,9759 | 0,9330 |
| RISCO | 0,6940 | 0,2295 | 0,3449 |
| FALHA | 0,8345 | 0,6870 | 0,7536 |

**F1 macro no teste:** 0,6772 (validação da Tarefa 4: 0,7143).

**Recall de FALHA e troca RISCO ↔ FALHA:** o recall de FALHA no teste foi 0,687, praticamente igual ao da validação (0,6825). O erro mais caro é FALHA prevista como OK: 2.169 casos, cerca de 30% das FALHAs reais. A troca entre RISCO e FALHA é pequena: 319 RISCO previstos como FALHA e 88 FALHA previstos como RISCO. O ponto fraco é o RISCO: só 744 de 3.242 foram acertados (recall 0,2295), e 2.179 (67%) foram previstos como OK. Isso já aparecia na validação (recall 0,3422) e não foi resolvido na Tarefa 4. A queda do F1 macro de 0,7143 para 0,6772 vem quase toda do RISCO.

**Casos:**

- **Acerto em caminho longo estável (OK):** fluxo `1004421|103.77.105.3`, com 753 rodadas no teste, 99,3% delas realmente OK. A árvore previu OK em 100% das rodadas e acertou 99,3%. Exemplo: 18/09/2026 02:08:44 UTC, `z_robusto` = 0,14, real OK e previsto OK.
- **Erro relevante (FALHA prevista como OK):** fluxo `50126|103.77.105.3`, 18/09/2026 19:00:43 UTC. O `z_robusto` era 281,9, a rodada atual já era FALHA e o estado a 12 min também, mas a árvore previu OK. A regra 3 exige média das 3 rodadas anteriores > 2,49, e aqui `z_media3_ant` = −2,26: a árvore não reconhece o salto brusco de um fluxo que vinha normal. É o padrão dos 2.169 casos de FALHA → OK. Outros exemplos: `7324|87.238.48.84` em 18/09 04:53:27 UTC (`z_robusto` = 203,7).

## 3. Fluxo que a árvore não viu

Como o corte da Tarefa 2 é por fluxo no tempo, todo fluxo do dataset já aparece no treino da árvore oficial. Para ter fluxo inédito, o notebook separou 6 `fluxo_id` inteiros (sorteio com semente 42, 3 longos e 3 curtos), retreinou uma **árvore auxiliar com os mesmos hiperparâmetros** só nos demais fluxos e mediu nos separados. Essa árvore auxiliar **não é a oficial**. A ficha (mediana e MAD) dos fluxos separados sai só do Período A, com piso de 1.500 RTT válidos, e dos 65 fluxos com ficha suficiente.

- [x] O fluxo novo não aparece no treino (o notebook tem `assert`)
- [x] A mediana e o MAD não usam o trecho avaliado (a ficha é do Período A)
- [x] Dizer se um caminho longo estável permaneceu OK e se uma degradação foi marcada RISCO ou FALHA
- [x] Havia fluxos sobrando com baseline suficiente, então a conta foi feita

**Fluxos separados:** `6380|87.238.48.84`, `1003574|143.255.248.149`, `6723|87.238.48.84` (longos); `1002841|63.222.187.5`, `6544|87.238.48.84`, `7020|2001:503:c27::2:30` (curtos).

**Resultado:** F1 macro agregado de 0,4998, bem abaixo do teste normal (0,6772).

| Fluxo | Caminho | N | OK real | OK previsto | Acerto |
|---|---|---|---|---|---|
| `1002841\|63.222.187.5` | curto | 2.511 | 98,8% | 100,0% | 0,988 |
| `1003574\|143.255.248.149` | longo | 2.511 | 21,7% | 58,8% | 0,542 |
| `6380\|87.238.48.84` | longo | 2.503 | 85,7% | 99,1% | 0,850 |
| `6544\|87.238.48.84` | curto | 2.503 | 88,7% | 99,6% | 0,884 |
| `6723\|87.238.48.84` | longo | 2.503 | 89,3% | 98,8% | 0,896 |
| `7020\|2001:503:c27::2:30` | curto | 2.485 | 97,0% | 99,9% | 0,969 |

Matriz agregada nos 6 fluxos (linhas = real, colunas = previsto):

| | prev OK | prev RISCO | prev FALHA |
|---|---|---|---|
| **real OK** | 11.929 | 20 | 87 |
| **real RISCO** | 794 | 6 | 81 |
| **real FALHA** | 1.195 | 7 | 897 |

- **Fluxos estáveis:** os fluxos curtos `1002841` e `7020` ficaram OK em quase 100% das rodadas. Entre os longos, nenhum é estável no sentido estrito (todos têm FALHAs reais). O mais próximo é `6723`, com 89,6% de acerto e 98,8% das rodadas previstas como OK.
- **Degradação:** o fluxo longo `1003574|143.255.248.149` tinha 1.690 FALHAs reais (67% das rodadas) e a árvore acertou 879 (52%), prevendo OK em 58,8% das rodadas contra 21,7% de OK real.
- **Agregado:** o recall de FALHA foi 0,427 (897 de 2.099) e o de RISCO foi praticamente nulo (6 de 881). A degradação foi marcada como FALHA em parte dos casos e quase nunca como RISCO. A árvore generaliza mal para fluxo inédito, principalmente em degradação sustentada.

## 4. O que declarar

- **Árvore e rótulo:** o rótulo da Tarefa 2 usa `z_robusto`, `n5_risco`, `n5_timeout` e `n5_aumento80`, e a árvore usa as mesmas grandezas. Ela aprende a política de rotulagem, não um ticket de roteador. A importância na Tarefa 4 confirma: `z_robusto` 0,611 e `n5_risco` 0,174.
- **Preditor ou detector:** o alvo é o estado 12 min à frente. Comparação com “repetir a classe atual” no teste:

  | | F1 macro | Recall de FALHA | Recall de RISCO |
  |---|---|---|---|
  | Árvore (Tarefa 4) | 0,6772 | 0,6870 | 0,2295 |
  | Repetir a classe atual | 0,6695 | 0,7143 | 0,3834 |

  O ganho da árvore é de apenas 0,0077 no F1 macro, e a regra de repetir a classe atual tem recall melhor de FALHA e de RISCO. Como não há ganho material, o entregável é um **detector** do estado atual, não um preditor do estado a 12 min.
- **Limitações:** o baseline fixo (Período A) não acompanha troca de rota; rajada curta estima mal o jitter; os Anchors do RIPE Atlas não são a rede do campus; o recall de RISCO é baixo desde a validação e não foi resolvido na Tarefa 4; a árvore perde o início de saltos bruscos (a regra de FALHA exige que o fluxo já viesse alto) e generaliza mal para fluxo não visto (F1 macro 0,4998).

## 5. Ficha da árvore

| Campo | Conteúdo |
|---|---|
| Problema | Classe OK, RISCO ou FALHA pelo desvio ao baseline do fluxo, 12 min à frente |
| Unidade | Uma medição de um `fluxo_id` no Período B |
| Baseline | Período A, mediana e MAD, piso de 1.500 RTT válidos |
| Colunas | `z_robusto`, `aumento_pct`, `jitter_relativo`, `perda_pct`, `timeout_atual`, `n5_timeout`, `n5_aumento80`, `n5_risco`, `z_delta1`, `z_media3_ant`, `z_inclin5` |
| Árvore | gini, `max_depth` 8, `min_samples_leaf` 1, `ccp_alpha` 0,0005, 20 folhas, semente 42 |
| Teste (uma vez) | F1 macro 0,6772 e recall de FALHA 0,6870 |
| O que ela não faz | Não classifica distância. Não opera em fluxo sem ficha. |
| Como reproduzir | `requirements.txt`, `documentos/notebooks/Tarefa5_Arvore_Final.ipynb`, `config/coleta_config.json` |

**Dicionário v0.4:** arquivo separado, com exatamente as 11 colunas acima. As 3 de tendência (da v0.3): `z_delta1` = `z_robusto` atual − o da rodada anterior; `z_media3_ant` = média do `z_robusto` das 3 rodadas anteriores (mínimo 2 válidas); `z_inclin5` = inclinação do `z_robusto` nas últimas 5 rodadas (exige as 5 válidas). Valor ausente vira sentinela −999.

## 6. Scrum e diário

- [ ] Board atualizado — **Link do board:** `[GRUPO]`

| Integrante | O que fiz nesta tarefa | Dificuldades | O que pretendo manter/ajustar |
|---|---|---|---|
| Eduardo Quintino Filho | `[GRUPO]` | `[GRUPO]` | `[GRUPO]` |
| Felipe Veiga da Silva | `[GRUPO]` | `[GRUPO]` | `[GRUPO]` |
| Henrique de Aguiar Fernandes | `[GRUPO]` | `[GRUPO]` | `[GRUPO]` |
| Niccolas Lupetti dos Santos | `[GRUPO]` | `[GRUPO]` | `[GRUPO]` |
| Tharik Lima da Silva | `[GRUPO]` | `[GRUPO]` | `[GRUPO]` |
