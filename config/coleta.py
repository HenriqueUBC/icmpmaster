#!/usr/bin/env python3
"""
Coletor acelerado de resultados do RIPE Atlas para o ICMPMASTER.

- Consulta somente GET; não cria medições.
- Coleta em blocos de 24 horas, como o notebook Coleta_de_dados_v2.0.
- Executa blocos em paralelo com concorrência limitada.
- Salva cada bloco JSON localmente para permitir retomar a execução.
- Gera um JSON consolidado com os resultados brutos e um CSV com as 13
  colunas utilizadas por data/interim/medicoes.csv.

Requisitos:
    python -m pip install requests pandas numpy

Execute na pasta do projeto (onde existe config/coleta_config.json):
    python coleta.py

Opcional:
    python coleta.py --limite-registros 100000
    python coleta.py --linhas-por-arquivo 50000
    python coleta.py --workers 4
    python coleta.py --saida saida_coleta
    python coleta.py --inicio 2026-09-06T04:32:00Z --fim 2026-09-20T04:32:00Z

A data final é exclusiva. Por padrão, são usados os períodos A+B do arquivo
config/coleta_config.json. Se o arquivo não for encontrado, o script para
com uma mensagem explicativa, em vez de inventar IDs/probes.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

COLS = [
    "timestamp", "measurement_id", "probe_id", "dst_addr", "fluxo_id",
    "rtt_medio_ms", "rtt_min_ms", "rtt_max_ms", "enviados", "recebidos",
    "perda_pct", "jitter_ms", "timeout_atual",
]
CHAVE = ["measurement_id", "probe_id", "dst_addr", "timestamp"]
DEFAULT_API = "https://atlas.ripe.net/api/v2"


def epoch(value: str) -> int:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return int(ts.timestamp())


def iso_utc(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def load_config(project_root: Path) -> tuple[dict[str, Any], Path]:
    cfg_path = project_root / "config" / "coleta_config.json"
    if not cfg_path.exists():
        raise FileNotFoundError(
            f"Não encontrei {cfg_path}. Execute o script na pasta do ICMPMASTER "
            "ou coloque o script na raiz do projeto."
        )
    with cfg_path.open(encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg, cfg_path



def request_json(url: str, params: dict[str, Any], cfg: dict[str, Any]) -> Any:
    api_cfg = cfg.get("api", {})
    timeout = int(api_cfg.get("timeout_s", 60))
    attempts = int(api_cfg.get("tentativas", 4))
    wait = float(api_cfg.get("espera_s", 2))
    last_error = "erro desconhecido"

    # Sessão própria por requisição/tarefa: evita compartilhar Session entre threads.
    with requests.Session() as session:
        session.headers["User-Agent"] = (
            "icmpmaster-aula/2.0 (projeto academico; somente GET)"
        )
        for attempt in range(attempts):
            try:
                response = session.get(url, params=params, timeout=timeout)
                if response.status_code == 200:
                    return response.json()
                if response.status_code in (429, 500, 502, 503, 504):
                    last_error = f"HTTP {response.status_code}"
                    retry_after = response.headers.get("Retry-After", "")
                    delay = float(retry_after) if retry_after.isdigit() else wait * (2 ** attempt)
                    time.sleep(delay)
                    continue
                response.raise_for_status()
            except (requests.Timeout, requests.ConnectionError, requests.HTTPError,
                    ValueError) as exc:
                last_error = repr(exc)
                if attempt < attempts - 1:
                    time.sleep(wait * (2 ** attempt))
    raise RuntimeError(f"Falha ao consultar {url}: {last_error}")


def parse_record(record: dict[str, Any]) -> dict[str, Any]:
    results = record.get("result") or []
    rtts = [
        item["rtt"] for item in results
        if isinstance(item, dict)
        and item.get("rtt") is not None
        and not item.get("dup")
    ]
    sent = record.get("sent")
    received = record.get("rcvd")
    sent = sent if sent is not None else len(results)
    received = received if received is not None else len(rtts)
    return {
        "timestamp": record.get("timestamp"),
        "measurement_id": record.get("msm_id"),
        "probe_id": record.get("prb_id"),
        "dst_addr": record.get("dst_addr") or record.get("dst_name"),
        "rtt_medio_ms": float(np.mean(rtts)) if rtts else np.nan,
        "rtt_min_ms": float(min(rtts)) if rtts else np.nan,
        "rtt_max_ms": float(max(rtts)) if rtts else np.nan,
        "enviados": sent,
        "recebidos": received,
        "jitter_ms": float(np.std(rtts, ddof=1)) if len(rtts) >= 2 else np.nan,
    }


def normalize_records(records: list[dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=COLS)

    df = pd.DataFrame([parse_record(record) for record in records])
    if df.empty:
        return pd.DataFrame(columns=COLS)

    numeric_ts = pd.to_numeric(df["timestamp"], errors="coerce")
    if numeric_ts.notna().all():
        df["timestamp"] = pd.to_datetime(numeric_ts, unit="s", utc=True)
    else:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")

    for col in ("rtt_medio_ms", "rtt_min_ms", "rtt_max_ms"):
        df.loc[df[col] <= 0, col] = np.nan

    sent = pd.to_numeric(df["enviados"], errors="coerce")
    received = pd.to_numeric(df["recebidos"], errors="coerce")
    calculated_loss = (sent - received) / sent.where(sent > 0) * 100
    df["perda_pct"] = np.where(sent.notna(), calculated_loss, np.nan)
    df["timeout_atual"] = (
        df["rtt_medio_ms"].isna() | (df["perda_pct"] == 100)
    ).astype(int)
    df["fluxo_id"] = df["probe_id"].astype(str) + "|" + df["dst_addr"].astype(str)
    return df[COLS]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Coleta paralela de resultados do RIPE Atlas.")
    parser.add_argument("--workers", type=int, default=4,
                        help="Número máximo de requisições simultâneas (padrão: 4; máximo recomendado: 4).")
    parser.add_argument("--saida", default="saida_coleta_ripe",
                        help="Pasta local para JSONs brutos e arquivos finais.")
    parser.add_argument("--inicio", help="Início UTC ISO-8601; sobrescreve os períodos do config.")
    parser.add_argument("--fim", help="Fim UTC ISO-8601 exclusivo; sobrescreve os períodos do config.")
    parser.add_argument(
        "--limite-registros", type=int, default=300000,
        help="Máximo de registros brutos usados nos arquivos finais (padrão: 100000; 0 = sem limite)."
    )
    parser.add_argument(
        "--linhas-por-arquivo", type=int, default=50000,
        help="Máximo de linhas por arquivo CSV (padrão: 50000)."
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.workers < 1 or args.workers > 4:
        print("Use --workers entre 1 e 4 para limitar a carga sobre a API.", file=sys.stderr)
        return 2
    if args.limite_registros < 0:
        print("--limite-registros deve ser 0 (sem limite) ou um número positivo.", file=sys.stderr)
        return 2
    if args.linhas_por_arquivo < 1:
        print("--linhas-por-arquivo deve ser maior que zero.", file=sys.stderr)
        return 2

    script_dir = Path(__file__).resolve().parent
    cwd = Path.cwd()
    candidates = [cwd, *cwd.parents, script_dir, *script_dir.parents]
    project_root = next(
        (p for p in candidates if (p / "config" / "coleta_config.json").exists()),
        None,
    )
    if project_root is None:
        print(
            "ERRO: não encontrei config/coleta_config.json. "
            "Coloque o script na raiz do ICMPMASTER ou execute-o dentro dessa pasta.",
            file=sys.stderr,
        )
        return 2

    cfg, cfg_path = load_config(project_root)
    api_base = cfg.get("api", {}).get("base", DEFAULT_API).rstrip("/")

    IDS_PERMITIDOS = {
    8937123,
    19206759,
    22680685,
    23574809,
    29539835,
    32089417,
    }

    measurements = [
    m for m in cfg.get("medicoes", [])
    if int(m.get("msm_id", -1)) in IDS_PERMITIDOS
    ]
    if not measurements:
        print("ERRO: nenhuma medição encontrada em config/coleta_config.json.", file=sys.stderr)
        return 2

    if args.inicio and args.fim:
        start_ts, end_ts = epoch(args.inicio), epoch(args.fim)
    elif args.inicio or args.fim:
        print("Informe --inicio e --fim juntos, ou nenhum dos dois.", file=sys.stderr)
        return 2
    else:
        periods = cfg.get("periodos", {})
        if "A" not in periods or "B" not in periods:
            print("ERRO: períodos A e B não estão definidos no config.", file=sys.stderr)
            return 2
        start_ts = epoch(periods["A"]["inicio"])
        end_ts = epoch(periods["B"]["fim"])

    if end_ts <= start_ts:
        print("ERRO: --fim precisa ser posterior a --inicio.", file=sys.stderr)
        return 2

    out_dir = Path(args.saida).expanduser().resolve()
    raw_dir = out_dir / "raw_chunks"
    raw_dir.mkdir(parents=True, exist_ok=True)

    chunks: list[dict[str, Any]] = []
    cursor = start_ts
    day_seconds = 24 * 60 * 60
    while cursor < end_ts:
        chunk_end = min(cursor + day_seconds, end_ts)
        chunks.append({"start": cursor, "stop": chunk_end, "label": datetime.fromtimestamp(
            cursor, tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")})
        cursor = chunk_end

    jobs = []
    for measurement in measurements:
        msm_id = int(measurement["msm_id"])
        probes = sorted({int(pid) for pid in measurement.get("probes", [])})
        if not probes:
            print(f"AVISO: measurement {msm_id} não tem probes no config; será ignorada.")
            continue
        probe_tag = hashlib.md5(",".join(map(str, probes)).encode()).hexdigest()[:8]
        for chunk in chunks:
            path = raw_dir / f"msm{msm_id}_{chunk['label']}_p{probe_tag}.json"
            jobs.append((msm_id, probes, chunk, path))

    total = len(jobs)
    if total == 0:
        print("ERRO: não há combinações de medição/probe para coletar.", file=sys.stderr)
        return 2

    print(f"Projeto: {project_root}")
    print(f"Configuração: {cfg_path}")
    print(f"Período UTC: {iso_utc(start_ts)} até {iso_utc(end_ts)} (fim exclusivo)")
    print(f"Medições: {len(measurements)} | blocos diários por medição: {len(chunks)}")
    print(f"Requisições previstas: {total} | concorrência: {args.workers}")
    print(f"Saída local: {out_dir}")
    print("A coleta usa somente GET. Arquivos de blocos existentes serão reaproveitados.\n")

    completed = 0
    failures: list[str] = []

    def fetch_job(job: tuple[int, list[int], dict[str, Any], Path]) -> tuple[Path, int, bool]:
        msm_id, probes, chunk, path = job
        if path.exists():
            try:
                with path.open(encoding="utf-8") as f:
                    existing = json.load(f)
                if isinstance(existing, list):
                    return path, len(existing), True
            except (OSError, json.JSONDecodeError):
                pass

        params = {
            "start": chunk["start"],
            "stop": chunk["stop"] - 1,
            "probe_ids": ",".join(map(str, probes)),
            "format": "json",
        }
        url = f"{api_base}/measurements/{msm_id}/results/"
        data = request_json(url, params, cfg)
        if not isinstance(data, list):
            raise RuntimeError(f"Resposta inesperada para medição {msm_id}: esperava uma lista JSON.")
        atomic_write_text(path, json.dumps(data, ensure_ascii=False, separators=(",", ":")))
        return path, len(data), False

    start_clock = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_map = {executor.submit(fetch_job, job): job for job in jobs}
        for future in concurrent.futures.as_completed(future_map):
            job = future_map[future]
            completed += 1
            msm_id, _, chunk, _ = job
            try:
                path, count, reused = future.result()
                status = "reutilizado" if reused else "coletado"
                print(f"[{completed}/{total}] msm {msm_id} {chunk['label']}: {count} registros ({status})")
            except Exception as exc:
                failures.append(f"msm {msm_id} {chunk['label']}: {exc}")
                print(f"[{completed}/{total}] ERRO msm {msm_id} {chunk['label']}: {exc}", file=sys.stderr)

    if failures:
        failure_file = out_dir / "falhas_coleta.txt"
        atomic_write_text(failure_file, "\n".join(failures) + "\n")
        print(f"\nA coleta teve {len(failures)} falha(s). Veja: {failure_file}")
        print("Execute novamente com os mesmos parâmetros: blocos válidos serão reaproveitados.")
        # Ainda processa o que foi coletado, mas sinaliza saída diferente de zero ao final.

    all_records: list[dict[str, Any]] = []
    missing_chunks = []
    for msm_id, probes, chunk, path in jobs:
        if not path.exists():
            missing_chunks.append(path.name)
            continue
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                all_records.extend(data)
        except (OSError, json.JSONDecodeError) as exc:
            missing_chunks.append(f"{path.name}: {exc}")

    total_raw_records = len(all_records)
    limit_reached = args.limite_registros > 0 and total_raw_records > args.limite_registros
    if limit_reached:
        all_records = all_records[:args.limite_registros]
        print(
            f"\nAVISO: limite de {args.limite_registros:,} registros atingido. "
            "Os arquivos finais conterão apenas esse recorte."
        )

    # CSV normalizado. O CSV é dividido em partes para evitar um único arquivo enorme.
    df = normalize_records(all_records)
    if not df.empty:
        df = df.drop_duplicates(CHAVE, keep="first")
        df = df.sort_values(["fluxo_id", "timestamp"]).reset_index(drop=True)

    csv_paths = []
    if df.empty:
        csv_path = out_dir / "medicoes.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8")
        csv_paths.append(csv_path)
    else:
        for part_number, first in enumerate(range(0, len(df), args.linhas_por_arquivo), start=1):
            part_df = df.iloc[first:first + args.linhas_por_arquivo]
            if len(df) <= args.linhas_por_arquivo:
                csv_path = out_dir / "medicoes.csv"
            else:
                csv_path = out_dir / f"medicoes_parte_{part_number:03d}.csv"
            part_df.to_csv(csv_path, index=False, encoding="utf-8")
            csv_paths.append(csv_path)

    # JSON bruto também é dividido em partes; cada arquivo é JSON válido e autocontido.
    json_paths = []
    json_part_size = args.linhas_por_arquivo
    json_batches = [
        all_records[i:i + json_part_size]
        for i in range(0, len(all_records), json_part_size)
    ] or [[]]
    for part_number, batch in enumerate(json_batches, start=1):
        if len(json_batches) == 1:
            json_path = out_dir / "medicoes_brutas.json"
        else:
            json_path = out_dir / f"medicoes_brutas_parte_{part_number:03d}.json"
        atomic_write_text(
            json_path,
            json.dumps(
                {
                    "metadata": {
                        "source": "RIPE Atlas API",
                        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
                        "start_utc": iso_utc(start_ts),
                        "end_utc_exclusive": iso_utc(end_ts),
                        "measurement_ids": [int(m["msm_id"]) for m in measurements],
                        "chunk_size_hours": 24,
                        "workers": args.workers,
                        "raw_record_count_in_part": len(batch),
                        "raw_record_count_total_before_limit": total_raw_records,
                        "raw_record_limit": args.limite_registros,
                        "limit_reached": limit_reached,
                        "csv_record_count": len(df),
                        "failed_jobs": len(failures),
                        "missing_chunks": missing_chunks,
                        "part": part_number,
                        "parts_total": len(json_batches),
                    },
                    "results": batch,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )
        json_paths.append(json_path)

    elapsed = time.monotonic() - start_clock
    print("\n--- Resumo ---")
    print(f"Tempo decorrido: {elapsed / 60:.1f} minutos")
    print(f"Registros brutos encontrados nos blocos: {total_raw_records:,}")
    print(f"Registros brutos usados nos JSONs finais: {len(all_records):,}")
    print(f"Linhas no CSV após remover duplicatas: {len(df):,}")
    print("Arquivos CSV:")
    for path in csv_paths:
        print(f"  - {path}")
    print("Arquivos JSON bruto:")
    for path in json_paths:
        print(f"  - {path}")
    print(f"Blocos brutos individuais (retomada): {raw_dir}")
    if args.limite_registros == 0:
        print("Limite de registros: desativado.")
    else:
        print(f"Limite configurado: {args.limite_registros:,} registros.")
    if limit_reached:
        print(
            "ATENÇÃO: o limite foi aplicado aos arquivos finais consolidados. "
            "A pasta raw_chunks preserva os blocos completos baixados e pode ocupar mais espaço."
        )
    if failures or missing_chunks:
        print("ATENÇÃO: a coleta está incompleta; confira falhas_coleta.txt e execute novamente.")
        return 1
    print("Coleta e exportação concluídas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
