# Diário da Tarefa 3 — Primeira árvore de decisão

**Período:** 28/09/2026 a 04/10/2026  
**Projeto:** Preditor de degradação de rede com RTT normalizado (independente da rota)

**Equipe:** ICMPMASTER  
**Scrum Master da tarefa:** Henrique de Aguiar Fernandes  
**Repositório GitHub:** https://github.com/sgntgifc0c/icmpmaster

> Legenda: `[GRUPO]` = informação que só a equipe tem (board, diário individual). Todo o resto vem da execução real de `tarefa3_arvore.py` sobre `dataset_rotulado_B.csv` e `baseline_por_fluxo.csv` da Tarefa 2.

> Tarefa 1 coletou. Tarefa 2 fez o baseline e o rótulo. Esta tarefa **não refaz** a ficha nem a tabela de classes.

### Contrato desta tarefa

| | Artefato | Origem / destino |
|---|---|---|
| **Entra** | Ficha de baseline, dataset rotulado, corte temporal | Tarefa 2 — **os mesmos** |
| **Sai** | Árvore treinada só no treino, com profundidade e critério registrados | Tarefa 4 mexe nesta árvore, não no rótulo |
| **Sai** | Regras da árvore em texto e matriz 3×3 (OK, RISCO, FALHA) | Tarefa 4, para atacar o erro |
| **Sai** | Árvore de contraste (com rota ou RTT absoluto) e a frase do que ela aprendeu | Prova de que o modelo oficial não segue esse atalho |

- [x] Treino, validação e teste são os da Tarefa 2 (coluna `particao` do dataset rotulado, lida sem alteração)
- [x] A ficha de baseline não foi recalculada com o Período B (só lida; usada apenas para separar fluxo curto de longo nos erros e para a árvore de contraste)

**Dados de entrada:** 160.885 medições rotuladas do Período B, de 65 fluxos (os 5 fluxos `baseline_insuficiente` ficaram sem classe e fora). Corte: treino N=80.450, validação N=32.182, teste N=48.253.

| Bloco | OK | RISCO | FALHA |
|---|---|---|---|
| Treino | 62.788 | 4.852 | 12.810 |
| Validação | 24.738 | 2.498 | 4.946 |
| Teste | 37.732 | 3.271 | 7.250 |

Os três blocos têm as três classes, então não foi preciso ajustar a proporção.

---

## 1. Colunas que a árvore oficial pode usar

- [x] Lista de colunas do treino colada no diário
- [x] Conferido que a classe é o alvo, não uma feature (o script tem um `assert` que barra classe, `fluxo_id`, RTT em ms e rota na lista de features)

**Colunas usadas:** `z_robusto`, `aumento_pct`, `jitter_relativo`, `perda_pct`, `timeout_atual`, `n5_timeout`, `n5_aumento80`, `n5_risco`

Não entram: país, IP, `rota_id`, `fluxo_id`, nome do destino, RTT em ms.

**Tratamento de ausentes:** `z_robusto` e `aumento_pct` ficam vazios quando não há RTT (435 linhas no treino), e `jitter_relativo` fica vazio quando não há jitter. Para o scikit-learn o vazio vira o valor-sentinela −999, fora do domínio real. Nunca 0, que significaria "resposta instantânea". Nas regras, um corte como `z_robusto <= -499` significa "RTT ausente".

## 2. A árvore

- [x] Uma árvore de decisão (CART, scikit-learn 1.8, `DecisionTreeClassifier`)
- [x] `max_depth` e `min_samples_leaf` escolhidos olhando **só a validação**. Grade de 96 combinações: critério ∈ {gini, entropy}, `max_depth` ∈ {2, 3, 4, 5, 6, 8, 10, sem limite}, `min_samples_leaf` ∈ {1, 5, 10, 20, 50, 100}. Escolha pelo maior F1 macro na validação e, em empate, pela árvore com menos folhas. Grade completa em `saida_tarefa3/grade_validacao.csv`.
- [x] Semente registrada: `random_state = 42`
- [x] Ajuste (`fit`) só no treino
- [x] Profundidade real, número de folhas e primeiras divisões descritas
- [x] Três regras copiadas da árvore (`saida_tarefa3/arvore_oficial.txt`)

**Critério, profundidade máxima pedida, profundidade obtida, folhas:** critério = **gini**; `max_depth` = **8**; `min_samples_leaf` = **1**; profundidade obtida = **8**; folhas = **19**.

F1 macro na validação por profundidade (gini, `min_samples_leaf=1`): 2 → 0,859; 3 → 0,890; 4 → 0,974; 5 → 0,989; 6 → 0,998; 8, 10 e sem limite → 0,9999. A partir de 8 a árvore para de crescer (19 folhas), então 8 é o ponto mais simples.

**Primeiras divisões:** a raiz é `z_robusto ≤ 3,50`. O ramo `> 3,50` é uma folha FALHA. No ramo `≤ 3,50` a divisão seguinte é `n5_risco ≤ 1,50`. Depois aparecem `perda_pct ≤ 16,67`, `n5_aumento80 ≤ 1,50` e `n5_timeout ≤ 2,50`, que separam OK de FALHA, e `z_robusto ≤ 2,00` com `jitter_relativo ≤ 3,00` e `aumento_pct`, que separam RISCO.

**Importância das colunas:** `z_robusto` 0,647; `n5_risco` 0,166; `jitter_relativo` 0,068; `n5_aumento80` 0,056; `perda_pct` 0,048; `aumento_pct` 0,013; `n5_timeout` 0,003; `timeout_atual` 0.

**Regras lidas da árvore:**

1. se `z_robusto` ≤ 3,502 e `n5_risco` ≤ 1,5 e `perda_pct` ≤ 16,667 e `n5_aumento80` ≤ 1,5 e `n5_timeout` ≤ 2,5 então **OK** (n = 58.705 no treino, pureza 100%)
2. se `z_robusto` ≤ 3,502 e `n5_risco` > 1,5 e `z_robusto` > 1,999 e `n5_aumento80` ≤ 1,5 e `perda_pct` ≤ 16,667 e `n5_timeout` ≤ 2,5 então **RISCO** (n = 2.991, pureza 100%)
3. se `z_robusto` > 3,502 então **FALHA** (n = 11.148, pureza 100%)

Em português: sem pico forte, sem perdas, sem timeouts em sequência e com no máximo uma medição suspeita nas últimas cinco, é OK. Com um desvio entre 2 e 3,5 desvios robustos e pelo menos duas medições suspeitas nas últimas cinco, é RISCO. Acima de 3,5 desvios robustos é FALHA.

**Achado importante (vazamento de rótulo):** a árvore chega a F1 macro de 0,9999 porque as colunas de entrada são as mesmas grandezas que a tabela de rotulagem da Tarefa 2 usa (`perda_pct`, `n5_timeout`, `z_robusto`, `n5_aumento80`, `n5_risco`). Os limiares aprendidos, 3,50 / 2,00 / 16,67 (perda ≥ 10 com 3 pacotes) / 1,5 / 2,5, são os da tabela. A árvore redescobriu a regra do rótulo. Isso mostra que o modelo é coerente com o rótulo, não que generaliza para degradação real. É o principal ponto a atacar na Tarefa 4 (por exemplo, prever o estado 12 minutos à frente, que é o horizonte do preditor definido na Tarefa 1).

## 3. Leitura do erro

Medido no bloco de **validação** (N = 32.182). O teste permanece fechado até a Tarefa 5 e não foi medido.

**Matriz 3×3 (linhas = real, colunas = previsto):**

| | prev OK | prev RISCO | prev FALHA |
|---|---|---|---|
| **real OK** | 24.738 | 0 | 0 |
| **real RISCO** | 0 | 2.498 | 0 |
| **real FALHA** | 2 | 0 | 4.944 |

| Classe | Precisão | Recall | F1 | Suporte |
|---|---|---|---|---|
| OK | 0,9999 | 1,0000 | 1,0000 | 24.738 |
| RISCO | 1,0000 | 1,0000 | 1,0000 | 2.498 |
| FALHA | 1,0000 | 0,9996 | 0,9998 | 4.946 |

**F1 macro (validação): 0,9999.** Acurácia 0,9999, mas ela não decide: com maioria OK (77%), seria alta mesmo errando FALHA. O critério é o F1 macro e o recall de FALHA (0,9996).

**Erros concretos** (os dois únicos da validação, ambos FALHA classificada como OK):

| Fluxo | Timestamp (UTC) | Caminho | `z_robusto` | `aumento_pct` | `jitter_relativo` | `perda_pct` | `n5_*` (timeout / aum80 / risco) | Real | Árvore |
|---|---|---|---|---|---|---|---|---|---|
| 1003574\|143.255.248.149 | 2026-09-17 03:38:48 | longo | 3,5002 | 3,03 | 0,72 | 0 | 0 / 0 / 0 | FALHA | OK |
| 7101\|87.238.48.84 | 2026-09-17 16:33:28 | curto | 3,5014 | 2,16 | 4,89 | 0 | 0 / 0 / 1 | FALHA | OK |

Os dois erros são de fronteira: `z_robusto` ficou 0,0002 e 0,0014 acima do limiar 3,5 da tabela, mas a árvore aprendeu o corte em 3,502 (ponto médio entre valores do treino). Não houve caso de caminho longo estável (OK) classificado como FALHA na validação. Observação: o aumento de RTT desses dois pontos é de apenas 3% e 2%. Eles são FALHA porque o MAD desses fluxos é muito pequeno, então `z_robusto` é alto mesmo com variação mínima em ms. Vale discutir isso na Tarefa 4.

Para separar curto de longo usei a mediana do baseline: ≥ 83,09 ms (mediana das fichas) = longo. É só uma descrição, não entra em nenhuma regra.

## 4. Árvore de contraste (não é o modelo)

Treinada no **mesmo treino**, com os mesmos hiperparâmetros, acrescentando às 8 métricas o RTT absoluto (`rtt_ms`, reconstruído como mediana × (1 + `aumento_pct`/100), já que o dataset não traz o RTT em ms) e a `mediana` do baseline do fluxo (indica a distância do caminho). O dataset não tem coluna de rota.

- [x] Divisão perto da raiz: **`z_robusto ≤ 3,502`**, igual à oficial. `rtt_ms` e `mediana` receberam importância ≈ 0.
- [x] Esta árvore **fica fora da entrega final**.

**O que a árvore de contraste usou na raiz:** `z_robusto ≤ 3,502`. Com as métricas relativas disponíveis, o atalho da distância não apareceu: o rótulo é função exata dessas métricas, então a árvore não precisa de ms nem de mediana.

**Contraste auxiliar (só absoluto):** para mostrar o atalho em estado puro, treinei outra árvore vendo **apenas** `rtt_ms` e `mediana`. A raiz é `rtt_ms ≤ −499`, que é o timeout (RTT ausente) e vira FALHA. Em seguida divide por `mediana ≤ 40,70 ms` e por cortes fixos de `rtt_ms` em milissegundos (arquivo `arvore_contraste_so_absoluto.txt`). F1 macro na validação = **0,716** e recall de FALHA = **0,767**.

**Frase do que ela aprendeu:** *sem as métricas relativas, a árvore só consegue separar os fluxos pela distância (mediana do caminho e cortes fixos de ms), e fica bem pior (F1 macro 0,72 contra 0,9999); por isso o modelo oficial usa só métricas relativas e as árvores de contraste são descartadas.*

## 5. Scrum e diário

- [ ] Board atualizado — **Link do board:** `[GRUPO]`

| Integrante | O que fiz nesta tarefa | Dificuldades | O que pretendo manter/ajustar |
|---|---|---|---|
| Eduardo Quintino Filho | [GRUPO] | [GRUPO] | [GRUPO] |
| Felipe Veiga da Silva | [GRUPO] | [GRUPO] | [GRUPO] |
| Henrique de Aguiar Fernandes (SM) | [GRUPO] | [GRUPO] | [GRUPO] |
| Niccolas Lupetti dos Santos | [GRUPO] | [GRUPO] | [GRUPO] |
| Tharik Lima da Silva | [GRUPO] | [GRUPO] | [GRUPO] |

---

## Rubrica — Tarefa 3 (0 a 4,0)

| Critério | Peso | Nota máxima | Nota | Observações |
|---|---|---|---|---|
| Árvore oficial | 1,5 | Uma árvore, critério e profundidade declarados, regras em português, fit só no treino | | |
| Métricas de três classes | 1,0 | Matriz 3×3, F1 por classe e F1 macro; acurácia não é o critério | | |
| Independência da rota | 1,0 | Colunas relativas apenas; árvore de contraste mostra o atalho da distância e é descartada | | |
| Scrum + diário | 0,5 | Board e diário de todos | | |
| **Total** | **4,0** | | **___ / 4,0** | |
