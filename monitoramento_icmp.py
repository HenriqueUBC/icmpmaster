"""Coleta incremental RIPE Atlas e previsões ICMPMASTER V1.

Execute na raiz: .\\.venv\\Scripts\\python.exe monitoramento_icmp.py
Parar: Ctrl+C. Uma consulta: --uma-vez.
Não altera datasets históricos, baseline nem modelo.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from config.coleta import normalize_records, request_json, DEFAULT_API
from preditor_icmp import prever_medicao

RAIZ = Path(__file__).resolve().parent
PASTA = RAIZ / 'data' / 'monitoramento'
MEDICOES = PASTA / 'medicoes_novas.csv'
PREVISOES = PASTA / 'previsoes.csv'
BASELINE = RAIZ / 'data' / 'processed' / 'baseline_por_fluxo.csv'
COLS_PREV = ['timestamp', 'fluxo_id', 'previsao_12min', 'measurement_id', 'coletado_em_utc']
COLS_CHAVE = ['fluxo_id', 'timestamp']


def carregar_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() and path.stat().st_size else pd.DataFrame()


def salvar_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    df.to_csv(temp, index=False)
    temp.replace(path)


def coletar(cfg: dict, inicio: datetime, fim: datetime) -> pd.DataFrame:
    api = cfg.get('api', {}).get('base', DEFAULT_API).rstrip('/')
    permitidos = {8937123, 19206759, 22680685, 23574809, 29539835, 32089417}
    bruto = []
    for medicao in cfg.get('medicoes', []):
        mid = int(medicao['msm_id'])
        if mid not in permitidos:
            continue
        probes = medicao.get('probes', [])
        if not probes:
            continue
        parametros = {
            'start': int(inicio.timestamp()),
            'stop': int(fim.timestamp()) - 1,
            'probe_ids': ','.join(str(int(p)) for p in probes),
            'format': 'json',
        }
        resultados = request_json(f'{api}/measurements/{mid}/results/', parametros, cfg)
        if not isinstance(resultados, list):
            raise RuntimeError(f'Resposta inesperada da medição {mid}')
        bruto.extend(resultados)
    return normalize_records(bruto)


def rodada(janela_minutos: int) -> None:
    cfg = json.loads((RAIZ / 'config' / 'coleta_config.json').read_text(encoding='utf-8'))
    baseline = pd.read_csv(BASELINE)
    validos = set(baseline.loc[baseline['status'].eq('ok'), 'fluxo_id'].astype(str))
    fim = datetime.now(timezone.utc)
    inicio = fim - timedelta(minutes=janela_minutos)
    novas = coletar(cfg, inicio, fim)
    if novas.empty:
        print(f'[{fim.isoformat()}] Nenhuma medição retornada na janela de {janela_minutos} min.')
        return
    novas = novas.loc[novas['fluxo_id'].astype(str).isin(validos)].copy()
    if novas.empty:
        print('Nenhuma medição corresponde a um fluxo com baseline válido.')
        return
    anteriores = carregar_csv(MEDICOES)
    todas = pd.concat([anteriores, novas], ignore_index=True)
    todas['timestamp'] = pd.to_datetime(todas['timestamp'], utc=True, errors='coerce')
    todas = todas.dropna(subset=COLS_CHAVE).sort_values(COLS_CHAVE)
    todas = todas.drop_duplicates(COLS_CHAVE, keep='first')
    # Evita misturar medições com mesmo fluxo e instante de fontes distintas.
    existentes = set()
    if not anteriores.empty:
        ant_ts = pd.to_datetime(anteriores['timestamp'], utc=True, errors='coerce')
        existentes = set(zip(anteriores['fluxo_id'].astype(str), ant_ts))
    adicionadas = todas.loc[
        ~pd.Series(list(zip(todas['fluxo_id'].astype(str), todas['timestamp'])), index=todas.index).isin(existentes)
    ].copy()
    salvar_csv(todas, MEDICOES)

    previsoes = carregar_csv(PREVISOES)
    previstos = set()
    if not previsoes.empty:
        previstos = set(zip(previsoes['fluxo_id'].astype(str), pd.to_datetime(previsoes['timestamp'], utc=True)))
    resultados = []
    aguardando = 0
    for fluxo, serie in todas.groupby('fluxo_id', sort=False):
        serie = serie.sort_values('timestamp').reset_index(drop=True)
        for idx, atual in serie.iterrows():
            chave = (str(fluxo), atual['timestamp'])
            if chave in previstos:
                continue
            # Exigir 5 medições recentes em até 30 min evita usar contexto obsoleto.
            if idx < 4 or (atual['timestamp'] - serie.loc[idx - 4, 'timestamp']) > pd.Timedelta(minutes=30):
                aguardando += 1
                continue
            historico = serie.iloc[:idx].copy()
            try:
                resultado = prever_medicao(atual.to_dict(), historico, baseline)
            except (ValueError, KeyError) as exc:
                print(f'Aviso: fluxo {fluxo} em {atual["timestamp"]}: {exc}')
                continue
            resultados.append({
                'timestamp': resultado['timestamp'],
                'fluxo_id': resultado['fluxo_id'],
                'previsao_12min': resultado['previsao_12min'],
                'measurement_id': atual.get('measurement_id'),
                'coletado_em_utc': fim.isoformat(),
            })
            previstos.add(chave)
    if resultados:
        previsoes = pd.concat([previsoes, pd.DataFrame(resultados)], ignore_index=True)
        previsoes = previsoes.drop_duplicates(COLS_CHAVE, keep='first').sort_values('timestamp')
        salvar_csv(previsoes[COLS_PREV], PREVISOES)
    print(f'[{fim.isoformat()}] Recebidas: {len(novas)} | Novas: {len(adicionadas)} | '
          f'Previsões geradas: {len(resultados)} | Aguardando histórico recente: {aguardando}')
    print(f'Dados salvos em: {PASTA}')


def main() -> None:
    parser = argparse.ArgumentParser(description='Monitoramento periódico do ICMPMASTER')
    parser.add_argument('--uma-vez', action='store_true', help='Consulta uma vez e encerra')
    parser.add_argument('--intervalo-segundos', type=int, default=60)
    parser.add_argument('--janela-minutos', type=int, default=20)
    args = parser.parse_args()
    if args.intervalo_segundos < 60 or args.janela_minutos < 5:
        parser.error('Intervalo mínimo: 60 segundos; janela mínima: 5 minutos.')
    print('Monitoramento RIPE Atlas iniciado. Ctrl+C para interromper.')
    while True:
        try:
            rodada(args.janela_minutos)
        except (OSError, ValueError, RuntimeError, KeyError) as exc:
            print(f'Falha na rodada: {exc}')
            if args.uma_vez:
                raise
        if args.uma_vez:
            return
        try:
            time.sleep(args.intervalo_segundos)
        except KeyboardInterrupt:
            print('\nMonitoramento encerrado.')
            return


if __name__ == '__main__':
    main()
