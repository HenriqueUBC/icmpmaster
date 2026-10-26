# Diário da Tarefa 1 — Problema e coleta bruta (sem rótulo)

**Período:** 17/08/2026 a 17/09/2026  
**Projeto:** Preditor de degradação de rede com RTT normalizado (independente da rota)  
**Modelo desta disciplina:** árvore de decisão. Nesta tarefa não se treina árvore.

**Equipe:** ICMPMASTER

**Integrantes:**  Eduardo Quintino Filho, Felipe Veiga da Silva, Henrique de Aguiar Fernandes, Niccolas Lupetti dos Santos, Tharik Lima da Silva

**Scrum Master da tarefa:**  Henrique de Aguiar Fernandes

**Repositório GitHub:**
 https://github.com/sgntgifc0c/icmpmaster
> Esta tarefa entrega o problema e o **dado cru**. Não há classe OK, RISCO ou FALHA. Não há baseline, não há mediana e não há árvore. Quem rotular aqui mistura a coleta com a decisão da Tarefa 2.
>
> A rota entra na coleta só para haver caminhos curtos e longos no mesmo arquivo. RTT alto **não** é falha. País, IP e nome da rota **não** serão coluna da árvore.

### Contrato desta tarefa

| | Artefato | Quem usa depois |
|---|---|---|
| **Entra** | RFC do projeto | — |
| **Sai** | RFC preenchido pelo grupo (problema, horizonte, custo de errar FALHA, fora de escopo) | Tarefas 2 e 5 |
| **Sai** | Dicionário v0.1 só com colunas **brutas** da medição | Tarefa 2 |
| **Sai** | `data/raw/` + `config/` + `requirements.txt` | Tarefa 2 **é obrigada a usar este bruto** |
| **Sai** | Este diário | Tarefas seguintes |

**Não sai daqui:** baseline, rótulo, `z_robusto`, split, árvore, métrica de modelo.

---

## 1. Definição do problema

Responder no diário. A resposta tem de bater com o RFC.

| Pergunta | Resposta do grupo |
|---|---|
| Qual evento a árvore vai classificar? | Degradação do fluxo em relação ao **próprio** normal: OK, RISCO ou FALHA. Não é “rota longa” nem “RTT acima de 100 ms”. |
| O que é um fluxo? | `fluxo_id = probe_id \| dst_addr` (origem, destino e, se existir, `measurement_id`). |
| O que é cada linha do bruto? | Uma medição ICMP desse fluxo, com timestamp. Ainda **sem** classe. |
| Qual horizonte fica para depois? | Detector: estado da medição atual. Preditor: estado 12 minutos à frente. A árvore só entra na Tarefa 3. |
| Quem usa o alerta? | Quem opera o enlace: investigar (FALHA), observar (RISCO) ou não agir (OK). |
| O que está proibido como definição de falha? | Limiar global de RTT, país, continente ou nome da rota. |

- [x] RFC do grupo preenchido a partir desta tabela
- [x] Dicionário v0.1 só com variáveis brutas

## 2. O que coletar (e o que não criar)

Fonte: medições públicas já existentes de ping IPv4 (mesh de Anchors do RIPE Atlas, somente `GET`). Não criar medição própria e não gastar crédito.

Cada registro bruto guarda, quando a API trouxer:

| Campo | Unidade | Papel agora |
|---|---|---|
| `timestamp` | UTC | Ordenar o fluxo |
| `measurement_id` | — | Identidade da medição |
| `probe_id` | — | Origem |
| `dst_addr` | — | Destino |
| `fluxo_id` | texto estável | `probe_id\|dst_addr` |
| RTT da rajada (médio; mín/máx se existirem) | ms | Medição. Vazio se não houver resposta. **Nunca 0** |
| enviados, recebidos | contagem | |
| `perda_pct` | % | `(enviados − recebidos) / enviados × 100` |
| `jitter_ms` | ms | Desvio-padrão dos RTT da rajada **somente** com 2 ou mais respostas. Senão, vazio. **Nunca 0 fingindo estabilidade** |
| `timeout_atual` | 0 ou 1 | 1 se não há RTT ou perda = 100% |
| país ou rota | texto | Só auditoria de diversidade. **Fora da futura árvore** |

Regras da coleta:

- [x] Vários fluxos, com pelo menos um caminho curto e um caminho longo no mesmo período
- [x] A diversidade geográfica está documentada e **não** virou classe
- [x] Dois blocos de tempo contíguos, sem amostra nos dois: Período A (só para o baseline da Tarefa 2) e Período B (medições que serão rotuladas). Referência do projeto: 7 dias + 7 dias a partir de 06/09/2026 04:32 UTC. Outro recorte só vale se os dois blocos continuarem sem sobreposição e o A tiver volume para o mínimo da Tarefa 2
- [x] Timeout permanece no arquivo
- [x] JSON bruto preservado; a tabela tratada não apaga o bruto
- [x] Parâmetros (período, probes, destinos) em `config/`, não espalhados no código
- [x] HTTP com timeout, releitura em erro transitório e coleta idempotente (rodar de novo não duplica)
- [x] `requirements.txt` da coleta

**Evidências (notebook, commit, trecho do config):**

- Notebook: `documentos/notebooks/Coletas/Coleta_de_dados_v2.0.ipynb` (seções 2 a 8: medições, probes, download dos Períodos A e B, tabela tratada e relatório de qualidade).
- Config: `config/coleta_config.json` (períodos A e B, medições, probes escolhidas, `chunk_horas`, `timeout_s` e `tentativas`).
- `requirements.txt` na raiz (requests, pandas, numpy, matplotlib, jupyter).
- Commits: https://github.com/sgntgifc0c/icmpmaster/commits/main

## 3. Relatório de qualidade — ainda sem classe

- [x] Registros por `fluxo_id`
- [x] Início e fim de cada fluxo
- [x] Campos ausentes (RTT vazio é ausência, não zero)
- [x] Duplicatas
- [x] Quantidade de timeouts
- [x] RTT e perda descritos (mínimo, mediana, máximo) **sem** dizer OK, RISCO ou FALHA

**N de registros brutos:** 346714  
**N de fluxos:** 100  
**Caminho curto e caminho longo presentes (quais):** Curtos:
| measurement_id | probe_id | pais_origem | pais_destino |
|---------------:|---------:|-------------|--------------|
| 8937123  | 7406        | NO           | NO           |
| 19206759 | 1016538     | EC           | EC           |
| 22680685 | 7113        | BR           | BR           |
| 23574809 | 1010583     | ID           | ID           |
| 29539835 | 1016347     | IE           | IE           |
| 32089417 | 7032        | PH           | PH           |



Um longo por medição:

| measurement_id | probe_id | pais_origem | pais_destino |
|---------------:|---------:|-------------|--------------|
| 8937123        | 6380     | GH          | NO           |
| 19206759       | 12849    | VE          | EC           |
| 22680685       | 6358     | UG          | BR           |
| 23574809       | 18087    | GR          | ID           |
| 29539835       | 13347    | NO          | IE           |
| 32089417       | 17846    | IL          | PH           |


## 4. Scrum

- [x] Product Owner = docente; Scrum Master da tarefa; time de desenvolvimento
- [x] Board com To do / Doing / Done
- [x] Pelo menos 3 histórias: coletar fluxos diversos; preservar o bruto com timeout; separar Período A e Período B sem rotular

**Histórias:**

1. **Coletar fluxos diversos.**
   Como equipe, quero coletar fluxos de várias sondas, com caminhos curtos e longos no mesmo período, para que a base represente situações diferentes de rede e não só um tipo de enlace.
   - *Critério de aceite:* pelo menos um caminho curto e um longo em cada período; diversidade geográfica documentada e sem virar classe.
   - *Resultado:* 40 fluxos em cada período. Período A: 20 curtos e 14 longos. Período B: 19 curtos e 15 longos. A tabela de países/ASN das sondas fica em arquivo separado, fora das tabelas de medição.
   - *Evidência:* notebook, seções 10-C a 10-E e 10-H.
   - *Status:* Done

2. **Preservar o bruto com timeout.**
   Como equipe, quero guardar o JSON original da API e manter os registros sem resposta, para não perder a informação de falha e poder refazer qualquer tratamento depois.
   - *Critério de aceite:* JSON bruto salvo sem alteração; nenhum registro de timeout removido; RTT ausente nunca gravado como 0.
   - *Resultado:* um JSON por sonda e por período. Os timeouts no JSON batem com os da tabela: 2.928 no Período A e 810 no Período B. A coleta é idempotente, então rodar de novo não duplica.
   - *Evidência:* notebook, seções 8, 9, 10-F e 10-G; `config/coleta_config.json`; `requirements.txt`.
   - *Status:* Done

3. **Separar Período A e Período B sem rotular.**
   Como equipe, quero dois blocos de tempo contíguos e sem sobreposição, para que o baseline (A) fique independente das medições que serão rotuladas na Tarefa 2 (B).
   - *Critério de aceite:* blocos de 7 dias a partir de 06/09/2026 04:32 UTC, sem medição em comum; relatório de qualidade sem classe.
   - *Resultado:* A vai de 06/09 04:32 a 13/09 04:31 (99.682 registros); B vai de 13/09 04:32 a 20/09 04:31 (100.470 registros). Nenhuma medição repetida entre os dois. Não existe coluna de classe em nenhuma tabela.
   - *Evidência:* notebook, seções 10-A, 10-G e 10-H.
   - *Status:* Done



## 5. Diário de bordo

- [x] Board atualizado — [Trello](https://trello.com/b/75gwQNwl/estrutura-de-dados-ii)

| Integrante | O que fiz nesta tarefa | Dificuldades | O que pretendo manter/ajustar |
|---|---|---|---|
| Eduardo Quintino Filho | Contribuí para compreender os requisitos iniciais do projeto e a finalidade da coleta de medições de rede. | Entender quais informações eram necessárias para representar adequadamente cada medição. | Manter os requisitos documentados e ajustar o contrato dos dados quando necessário. |
| Felipe Veiga da Silva | Contribuí para organizar os dados brutos e compreender as informações utilizadas pelo preditor de qualidade da rede. | Lidar com medições que apresentam valores ausentes, tempos limite e diferentes condições de conexão. | Preservar os dados originais e manter a rastreabilidade das medições. |
| Henrique de Aguiar Fernandes | Contribuí para organizar as atividades iniciais e alinhar o entendimento da equipe sobre os objetivos da tarefa. | Conciliar as atividades da equipe e garantir que todos compreendessem o escopo inicial. | Manter as tarefas organizadas e melhorar a comunicação entre os integrantes. |
| Niccolas Lupetti dos Santos | Contribuí para compreender a estrutura das medições ICMP e as informações relevantes para analisar a qualidade da rede. | Identificar quais atributos seriam úteis sem antecipar etapas de processamento posteriores. | Manter a estrutura dos dados documentada e revisar os atributos conforme os requisitos. |
| Tharik Lima da Silva | Contribuí para analisar a consistência das informações coletadas e a estrutura dos registros brutos. | Identificar possíveis inconsistências e compreender como representar medições sem resposta. | Manter verificações de consistência e melhorar a documentação dos dados. |

## 6. Evidências gerais

- Link do RFC:  https://github.com/sgntgifc0c/icmpmaster/blob/main/documentos/notebooks/RFC.md
- Link do dicionário v0.1: https://github.com/sgntgifc0c/icmpmaster/blob/main/documentos/notebooks/dicionario_v0.1.md
- Link dos commits: https://github.com/sgntgifc0c/icmpmaster/commits/main
- Link de `data/raw/` e do `config/`: [`raw/`](https://github.com/sgntgifc0c/icmpmaster/tree/main/raw) e [`config/`](https://github.com/sgntgifc0c/icmpmaster/tree/main/config)

---

## Rubrica — Tarefa 1 (0 a 4,0)

| Critério | Peso | Nota máxima | Nota | Observações |
|---|---|---|---|---|
| Problema | 0,5 | Fluxo, unidade de análise e proibição de RTT absoluto como falha estão explícitos | | |
| Coleta bruta | 1,5 | Vários fluxos (curto e longo), timeout preservado, RTT vazio ≠ 0, config externa, bruto intocável | | |
| Período A e Período B sem rótulo | 1,0 | Dois blocos sem sobreposição; relatório de qualidade **sem** classe | | |
| Scrum + diário | 1,0 | Papéis, board, histórias e diário de todos | | |
| **Total** | **4,0** | | **___ / 4,0** | |
