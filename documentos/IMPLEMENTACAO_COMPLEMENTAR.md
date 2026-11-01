# Complementação ICMPMASTER — requisitos e limites

## Contrato da professora
`timestamp`, `ip`, `latencia_ms`, `perda_pacotes_pct`, `jitter_ms`, `status_real`.
O adaptador `contrato_icmp.py` converte para o esquema interno (`fluxo_id`, `rtt_medio_ms`, `perda_pct`, `jitter_ms`).
`status_real` é conservado para **avaliação apenas**, não integra as 11 features de inferência.

## Monitoramento direto
`ping_local.py` usa o `ping` do sistema operacional e registra medições em `data/ping_local/`.
O baseline por IP é construído após 30 respostas válidas; até lá a previsão fica indisponível.
Este baseline curto é **experimental** e NÃO equivale ao baseline de 1.500 RTT do RIPE Atlas.
As medições locais não se misturam às medições do RIPE Atlas.

O ping mede a partir do computador que executa o processo. Firewalls e políticas de rede podem impedir respostas. A extração de tempo suporta saída usual em inglês e português, mas outros formatos de sistema operacional podem exigir adaptação.

## Simulação
`simulador_icmp.py` gera sequências artificiais e as envia ao mesmo adaptador/pipeline do ping local, com origem `simulacao` e arquivos próprios. A classe `status_real` é uma anotação do cenário, não é usada na inferência. Uma única medição extrema não garante a classe prevista para três rodadas no futuro.

## Experimento sintético
`experimento_sintetico.py` gera cenários determinísticos e treina **outro modelo**, separado da árvore V1, com separação temporal por fluxo e lacuna de três rodadas entre treino/teste. Os resultados são exclusivos do mundo sintético e não comprovam qualidade em redes reais.

## Pacote técnico
`pacote_modelo/modelo.joblib` inclui `modelo`, `features`, `familia`, `params`.
`metadados.json` documenta o modelo e `baseline.csv` é uma cópia da referência original de fluxos RIPE Atlas. A inferência deve calcular as 11 features com histórico válido antes de chamar o modelo; IP novo não recebe previsão sem baseline.

## Avaliação e limitações
O monitoramento RIPE Atlas já existente foi preservado. A árvore oficial prediz três **rodadas** à frente (~12 min apenas quando a cadência é ~4 min). O alerta auxiliar é experimental e foi selecionado em validação; ganho independente não está comprovado. O modelo sintético não substitui a árvore oficial. Os dados históricos e os artefatos de treinamento foram preservados.

## Limites da validação entregue
Os testes unitários não substituem testes reais em redes Windows/Linux, execução prolongada, verificação de limites de API ou validação independente das previsões.

## Compatibilidade de versões
Os modelos originais foram serializados com `scikit-learn 1.9.1`. O ambiente de construção deste pacote possui 1.8.0, portanto a execução do alerta auxiliar nesse ambiente foi bloqueada por proteção contra incompatibilidade. `requirements.txt` exige 1.9.1; valide instalação no Python local antes de usar o auxiliar. A árvore oficial foi carregada com aviso e conferida em uma amostra de 20 linhas, o que **não** substitui a validação em ambiente de versões compatíveis.

## Comparação de resultados (não equiparar amostras)
| Origem | Modelo | F1 macro | Observação |
|---|---|---:|---|
| RIPE Atlas, teste histórico da Tarefa 5 | Árvore oficial V1 | 0,6772 | Dado histórico preservado |
| RIPE Atlas, teste histórico da Tarefa 5 | Persistência | 0,6695 | Mesmo teste histórico |
| Dados sintéticos gerados (seed 42) | Árvore **treinada apenas nos sintéticos** | 0,4699 | 636 linhas de teste sintético |
| Dados sintéticos gerados (seed 42) | Persistência | 0,6762 | Mesmo teste sintético |

A comparação **não** demonstra que um conjunto é mais difícil ou mais fácil, pois os alvos, distribuições e contextos são diferentes. Não atribuir os resultados sintéticos ao modelo oficial.
