# log_rede.csv — como os dados foram coletados

Arquivo: `data/processed/log_rede.csv` (gerado por `python exportar_log_rede.py`).

## Contrato de dados (Kickoff)

| Coluna | Origem no projeto | Observação |
|---|---|---|
| `timestamp` | `timestamp` da medição (UTC) | |
| `ip` | `dst_addr` (destino do ping) | Vários probes medem o mesmo destino; o fluxo `probe_id\|dst_addr` completo está em `dataset_rotulado_B.csv`. |
| `latencia_ms` | `rtt_medio_ms` (média dos 3 pings) | Vazio = timeout (sem resposta). |
| `perda_pacotes_pct` | `perda_pct` = (enviados − recebidos)/enviados × 100 | Em geral múltiplos de 33% (99% das medições têm 3 pacotes enviados). |
| `jitter_ms` | desvio padrão dos RTTs da medição | Vazio com menos de 2 respostas. |
| `status_real` | `classe` da Tarefa 2 (OK, RISCO, FALHA) | Ver regras abaixo. |

## Coleta

- Fonte: API pública do RIPE Atlas, só requisições `GET` (decisão do Memorando, 08/09/2026).
- Período A (06/09 a 13/09/2026): usado só para o baseline de cada fluxo (mediana, MAD, IQR, jitter típico).
- Período B (13/09 a 20/09/2026): medições rotuladas, 160.885 linhas em 65 fluxos (OK 77,9%, FALHA 15,5%, RISCO 6,6%).
- Cada medição = 3 pings em 99% das linhas (as demais têm 1 ou 2 pacotes enviados).

## Rótulo (primeira regra verdadeira vence)

1. FALHA se `perda_pct` ≥ 10; 2. FALHA se `n5_timeout` ≥ 3; 3. FALHA se `z_robusto` ≥ 3,5;
4. FALHA se `n5_aumento80` ≥ 2; 5. RISCO se (2 ≤ z < 3,5 ou 30 ≤ aumento ≤ 80 % ou jitter relativo ≥ 3) e `n5_risco` ≥ 2;
6. OK nos demais casos. (`n5_*` = contagem nas últimas 5 medições do próprio fluxo.)

## Amostragem do arquivo entregue

1.000 linhas por classe (3.000 no total), sorteio com semente 42, ordenadas por tempo. O conjunto completo
rotulado (160.885 linhas) sai com `python exportar_log_rede.py --completo`.

## Cenários e desvio do enunciado

Os cenários de RISCO e FALHA **não foram provocados** (sem Packet Tracer, sem saturar link ou desligar
interface): vêm do comportamento real de 65 rotas da internet medidas pelo RIPE Atlas. Os eventos controlados
para a demonstração ficam no modo "Simular evento" do dashboard (`pages/4_Monitoramento_ao_vivo.py`).
