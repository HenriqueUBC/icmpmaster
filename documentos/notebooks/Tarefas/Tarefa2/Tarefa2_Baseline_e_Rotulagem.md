# Diário da Tarefa 2 — Baseline do fluxo e rotulagem OK, RISCO, FALHA

**Período:** 18/09/2026 a 30/09/2026  
**Projeto:** Preditor de degradação de rede com RTT normalizado (independente da rota)

**Equipe:**   ICMPMASTER

**Integrantes:**  Eduardo Quintino Filho, Felipe Veiga da Silva, Henrique de Aguiar Fernandes, Niccolas Lupetti dos Santos, Tharik Lima da Silva



**Scrum Master da tarefa:**   HENRIQUE DE AGUIAR FERNANDES


**Repositório GitHub:**  https://github.com/sgntgifc0c/icmpmaster

> Esta tarefa lê o `data/raw/` da Tarefa 1. Não troca a coleta sem versionar.
>
> O trabalho é **obter o baseline de cada fluxo e rotular o Período B** com a tabela desta página. A árvore não entra aqui. País, IP e rota não entram na tabela que a árvore vai ler.
>
> Ordem obrigatória: inspeção do bruto → ficha de baseline no Período A → métricas relativas no Período B → rótulo na ordem da tabela → só então o recorte temporal dentro de B.



### Contrato desta tarefa


|           | Artefato                                                              | Origem / destino                            |
| --------- | --------------------------------------------------------------------- | ------------------------------------------- |
| **Entra** | `data/raw/` e dicionário v0.1                                         | Tarefa 1                                    |
| **Sai**   | `baseline_por_fluxo.csv` (uma ficha por `fluxo_id`)                   | Tarefas 3 a 5                               |
| **Sai**   | Dataset rotulado do Período B, com a classe e as métricas abaixo      | Tarefa 3 **usa este arquivo e este rótulo** |
| **Sai**   | Recorte temporal dentro de B (treino mais antigo, teste mais recente) | Tarefas 3 a 5 — **o mesmo corte**           |
| **Sai**   | Dicionário v0.2 (bruto, ficha, métricas, classe, colunas proibidas)   | Tarefa 3                                    |


**Não sai daqui:** árvore treinada, profundidade escolhida, acurácia, F1.

- [x] O notebook lê o bruto da Tarefa 1

---



## 1. Inspeção do bruto (ainda sem rótulo)

`data/raw/` permanece intocado. A auditoria vai para o diário; a tabela de trabalho, para `data/interim/`.

- [x] Contagem de linhas, fluxos, duplicatas e RTT vazio
- [x] Nenhum RTT ausente foi gravado como 0
- [x] Período A e Período B não compartilham timestamp do mesmo fluxo

**N bruto:** 346569  
**N de fluxos:** 100  
**Evidências:** notebook `documentos/notebooks/Baseline/Baseline_dos_dados.ipynb`, seções 1 e 2.

## 2. Como obter o baseline

Uma ficha por `fluxo_id`. Só o Período A. O Período B não entra na conta e não atualiza a ficha.


| Passo | O que fazer                                                                                                            |
| ----- | ---------------------------------------------------------------------------------------------------------------------- |
| 1     | Separar o fluxo e ordenar pelo timestamp.                                                                              |
| 2     | Período A = bloco inicial. Período B = bloco seguinte, sem amostra nos dois.                                           |
| 3     | RTT válido = medição com RTT presente. Timeout fica **fora** da mediana e do MAD, e **dentro** do dataset como evento. |
| 4     | Menos de **1.500** RTT válidos no A: `baseline_insuficiente`. Esse fluxo **não** recebe classe. Não inventar mediana.  |
| 5     | Gravar uma linha em `baseline_por_fluxo.csv` e congelar.                                                               |



| Campo da ficha  | Fórmula, somente Período A                                 |
| --------------- | ---------------------------------------------------------- |
| `mediana`       | mediana dos RTT válidos (ms)                               |
| `MAD`           | mediana(\|RTT − mediana\|), só com RTT válidos            |
| `jitter_tipico` | mediana do jitter nas medições em que o jitter existe (ms) |
| `perda_tipica`  | mediana de `perda_pct`, inclusive timeout (%)              |
| `prop_resposta` | medições com RTT válido / medições do período              |


- [x] Ficha conferida em pelo menos um fluxo curto e um fluxo longo (as medianas podem ser muito diferentes; as duas são “normal”)
- [x] Lista dos fluxos excluídos e o motivo (contagem abaixo de 1.500)

**Fluxos com ficha:** 65  
**Fluxos excluídos:** 5  
**Exemplo auditável (fluxo curto: mediana; fluxo longo: mediana):** curto: 1010583|103.77.105.3 | mediana 7.21 ms | MAD 4.27 | n válidos 2520
longo: 1000755|63.222.187.5 | mediana 254.83 ms | MAD 0.24 | n válidos 2517

## 3. Métricas de cada medição do Período B

Calcular só com a ficha congelada daquele `fluxo_id`.


| Métrica           | Fórmula                                                                 |
| ----------------- | ----------------------------------------------------------------------- |
| `z_robusto`       | (RTT atual − mediana) / (1,4826 × MAD)                                  |
| `aumento_pct`     | (RTT atual − mediana) / mediana × 100                                   |
| `jitter_relativo` | jitter atual / `jitter_tipico`                                          |
| `perda_pct`       | (enviados − recebidos) / enviados × 100                                 |
| `timeout_atual`   | 1 se não há RTT ou `perda_pct` = 100; senão 0                           |
| `n5_timeout`      | timeouts nas últimas 5 medições deste fluxo, incluindo a atual (0 a 5)  |
| `n5_aumento80`    | quantas das últimas 5 têm `aumento_pct` > 80                            |
| `n5_risco`        | quantas das últimas 5 cumprem o critério da linha 5 da tabela de rótulo |



| Situação                               | Conta                                                                           |
| -------------------------------------- | ------------------------------------------------------------------------------- |
| RTT ausente                            | Não calcular `z_robusto` nem `aumento_pct`. `timeout_atual` = 1. Não usar 0 ms. |
| MAD = 0 e RTT atual = mediana          | `z_robusto` = 0                                                                 |
| MAD = 0 e RTT atual ≠ mediana          | Denominador = max(IQR / 1,349, 1 ms)                                            |
| Jitter atual vazio                     | O critério de jitter não dispara                                                |
| `jitter_tipico` = 0 e jitter atual = 0 | `jitter_relativo` = 1                                                           |
| `jitter_tipico` = 0 e jitter atual > 0 | Tratar como `jitter_relativo` ≥ 3                                               |




## 4. Tabela de rotulagem — parar na primeira linha verdadeira

Cada linha do Período B, de um fluxo que tenha ficha. FALHA ganha de RISCO; RISCO ganha de OK.


| Ordem | Classe    | Métrica                                                                                                   | Limiar exato                                        |
| ----- | --------- | --------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| 1     | **FALHA** | `perda_pct`                                                                                               | ≥ 10 nesta medição (em 3 pacotes, 1 perda já é 33%) |
| 2     | **FALHA** | `n5_timeout`                                                                                              | ≥ 3                                                 |
| 3     | **FALHA** | `z_robusto`                                                                                               | ≥ 3,5 nesta medição, com RTT presente               |
| 4     | **FALHA** | `n5_aumento80`                                                                                            | ≥ 2                                                 |
| 5     | **RISCO** | nesta medição, pelo menos um: `2 ≤ z_robusto < 3,5`, ou `30 ≤ aumento_pct ≤ 80`, ou `jitter_relativo ≥ 3` | e `n5_risco` ≥ 2                                    |
| 6     | **OK**    | nenhuma linha anterior                                                                                    | pico isolado também é OK                            |


- [x] Três exemplos auditáveis no diário: um OK de caminho longo (RTT alto e `z_robusto` baixo), um RISCO, um FALHA de caminho curto ou de timeout
- [x] Contagem OK / RISCO / FALHA no Período B
- [x] A classe **não** foi definida por “RTT > 100 ms” nem pelo nome da rota
- [x] O Período A não foi rotulado
- [x] Dicionário v0.2 lista as colunas proibidas na árvore: país, IP, `rota_id`, `fluxo_id`, RTT absoluto como substituto das métricas relativas

**Contagem OK / RISCO / FALHA:**  125258 / 10621 / 25006

**Evidências (três linhas reais, com as métricas e a ordem que disparou a classe):**
Linhas 84 até 87 em dataset_rotulado.csv

| fluxo_id | timestamp | z_robusto | aumento_pct | jitter_relativo | perda_pct | timeout_atual | n5_timeout | n5_aumento80 | n5_risco | classe | particao |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 1000755\|63.222.187.5 | 2026-09-13 10:02:59+00:00 | 1.3857982528053363 | 0.1955290328458625 | 0.28255795198970446 | 0.0 | 0 | 0 | 0 | 0 | OK | treino |
| 1000755\|63.222.187.5 | 2026-09-13 10:07:05+00:00 | 7.572608735896075 | 1.0684562917094964 | 42.200659407443254 | 0.0 | 0 | 0 | 0 | 1 | FALHA | treino |
| 1000755\|63.222.187.5 | 2026-09-13 10:11:04+00:00 | 0.9782406339026649 | 0.1380247410835637 | 3.7270169627173684 | 0.0 | 0 | 0 | 0 | 2 | RISCO | treino |

## 5. Recorte para a árvore (ainda sem treinar)

Dentro do Período B, por fluxo, em ordem de tempo:

- [x] Treino = trecho mais antigo; validação = trecho do meio; teste = trecho mais recente
- [x] Proporção de partida 50% / 20% / 30%, ajustada se um bloco ficar sem RISCO
- [x] Nenhum registro do Período A no treino
- [x] Corte com data e N de cada bloco

**Corte (datas e N treino / validação / teste): 

Treino: N = 80.450, de 13/09/2026 04:32 a 16/09/2026 18:34 (UTC)

Validação: N = 32.182, de 13/09/2026 15:14 a 18/09/2026 02:37 (UTC)

Teste: N = 48.253, de 13/09/2026 19:26 a 20/09/2026 04:31 (UTC)**

## 6. Scrum e diário

- [ ] Board atualizado

**Link do board:**

| Integrante | O que fiz nesta tarefa | Dificuldades | O que pretendo manter/ajustar |
|---|---|---|---|
| Eduardo Quintino Filho | Contribuí para compreender a definição das classes OK, RISCO e FALHA e sua relação com a qualidade da rede. | Definir critérios de classificação que representassem diferentes condições sem depender apenas do RTT absoluto. | Manter os critérios documentados e revisar sua coerência com o comportamento de cada fluxo. |
| Felipe Veiga da Silva | Contribuí para compreender o processamento dos dados e a utilização de baselines para comparar as medições. | Lidar com diferenças entre fluxos e evitar que informações futuras influenciassem o cálculo do baseline. | Preservar a separação temporal dos dados e revisar o tratamento de valores ausentes. |
| Henrique de Aguiar Fernandes | Contribuí para acompanhar a organização das atividades relacionadas à construção do baseline e à rotulagem. | Garantir que as regras e as responsabilidades da etapa estivessem alinhadas entre os integrantes. | Manter as etapas organizadas e registrar decisões que afetem as tarefas seguintes. |
| Niccolas Lupetti dos Santos | Contribuí para compreender as características relativas ao baseline, como variação de RTT, jitter e perda de pacotes. | Interpretar métricas relativas sem confundir variações normais com degradações reais. | Manter a análise baseada no comportamento de cada fluxo e revisar os critérios de rotulagem. |
| Tharik Lima da Silva | Contribuí para analisar a consistência das classes atribuídas e compreender os efeitos das regras de rotulagem. | Verificar casos limítrofes e situações em que diferentes regras poderiam produzir classificações distintas. | Manter a validação dos rótulos e documentar possíveis limitações das regras utilizadas. |
---



## Rubrica — Tarefa 2 (0 a 4,0)


| Critério                  | Peso    | Nota máxima                                                                                     | Nota          | Observações |
| ------------------------- | ------- | ----------------------------------------------------------------------------------------------- | ------------- | ----------- |
| Baseline por fluxo        | 1,5     | Ficha só com o Período A, fórmulas desta página, piso de 1.500, exclusões listadas, A congelado |               |             |
| Rotulagem                 | 1,5     | Tabela aplicada na ordem, exemplos curto/longo, timeout sem RTT = 0, contagem das três classes  |               |             |
| Independência da rota     | 0,5     | Rota e RTT absoluto fora do rótulo e fora das colunas da futura árvore                          |               |             |
| Recorte temporal + diário | 0,5     | Corte dentro de B, com N; diário de todos                                                       |               |             |
| **Total**                 | **4,0** |                                                                                                 | **___ / 4,0** |             |


