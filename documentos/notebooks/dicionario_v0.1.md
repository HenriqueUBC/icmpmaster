# Dicionário de Dados v0.1

## Projeto

*Projeto:* Preditor de degradação de rede com RTT normalizado  
*Tarefa:* Tarefa 1 — Problema e coleta bruta (sem rótulo)

---

## Dicionário de dados brutos

| Campo | Tipo | Descrição |
|---|---|---|
| fw | inteiro | Versão do firmware da probe utilizada na medição. |
| mver | texto | Versão do formato/modelo de dados da medição. |
| lts | inteiro | Segundos desde a última sincronização do relógio da probe (*last time synchronized*). |
| dst_name | texto | Nome associado ao destino da medição. |
| af | inteiro | Família do endereço IP utilizada na medição. |
| dst_addr | texto | Endereço IP de destino da medição. |
| src_addr | texto | Endereço IP de origem observado na medição. |
| proto | texto | Protocolo utilizado na medição. |
| size | inteiro | Tamanho do pacote utilizado na medição. |
| result | lista/objeto | Resultado bruto das tentativas de medição, incluindo respostas ou ausência de resposta. |
| dup | inteiro | Quantidade de respostas duplicadas observadas. |
| rcvd | inteiro | Quantidade de pacotes recebidos. |
| sent | inteiro | Quantidade de pacotes enviados. |
| min | decimal | Menor RTT registrado na medição (ms). `-1` quando não houve resposta. |
| max | decimal | Maior RTT registrado na medição (ms). `-1` quando não houve resposta. |
| avg | decimal | RTT médio registrado na medição (ms). `-1` quando não houve resposta. |
| msm_id | inteiro | Identificador da medição do RIPE Atlas. |
| prb_id | inteiro | Identificador da probe responsável pela medição. |
| timestamp | inteiro | Instante da medição, em segundos desde 1970-01-01 (UTC). |
| msm_name | texto | Nome da medição. |
| from | texto | Identificação da origem associada ao resultado da medição. |
| type | texto | Tipo da medição. |
| step | inteiro | Intervalo/passo configurado entre medições. |
| stored_timestamp | inteiro | Timestamp relacionado ao armazenamento do resultado da medição. |
| ttl | inteiro | Valor de TTL observado no resultado da medição. |

---

## Observações

- Este dicionário contém somente as variáveis presentes no dado bruto coletado.
- Não há classe OK, RISCO ou FALHA nesta etapa.
- Não há baseline, z_robusto ou outras variáveis derivadas.
- O campo result mantém o resultado bruto das tentativas de medição, incluindo situações sem resposta.
- Quando não houver resposta, o RTT não deve ser interpretado como 0.
- A definição de fluxo_id utilizada pelo projeto é:

fluxo_id = probe_id | dst_addr

- País, IP e nome da rota não são utilizados como classe ou critério de classificação.

---

## Fonte

*Fonte dos dados:* RIPE Atlas  
*Tipo de coleta:* medições públicas de ping ICMP  
*Formato original:* JSON