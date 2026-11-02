"""Monitoramento ao vivo do ICMPMASTER (ping real + simulação de eventos).

Reproduz, medição a medição, as MESMAS fórmulas usadas nos notebooks das
Tarefas 2 e 4 (z robusto, aumento %, jitter relativo, janelas n5_*, tendência
do z) e passa o resultado pela árvore da Tarefa 4 (`arvore_ajustada.joblib`).

Não depende de Streamlit nem de `modelo_icmp.py`, para poder ser testado em
linha de comando (ver tests/test_ao_vivo.py).
"""
from __future__ import annotations

import json
import math
import platform
import re
import subprocess
import warnings
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np

RAIZ = Path(__file__).resolve().parent
ARQ_ARVORE = RAIZ / "documentos" / "notebooks" / "Arvore" / "saida_tarefa4" / "arvore_ajustada.joblib"
ARQ_BASELINES = RAIZ / "data" / "processed" / "baseline_ao_vivo.json"

# Mesmas 11 colunas e mesma ordem da árvore (config_modelo.json da Tarefa 4).
FEATURES = [
    "z_robusto", "aumento_pct", "jitter_relativo", "perda_pct", "timeout_atual",
    "n5_timeout", "n5_aumento80", "n5_risco", "z_delta1", "z_media3_ant", "z_inclin5",
]
SENTINELA = -999          # valor vazio entra como -999 na árvore (igual ao treino)
MIN_RTT_AO_VIVO = 30      # medições válidas para montar o baseline ao vivo
CLASSES = ["OK", "RISCO", "FALHA"]
CENARIOS = {
    "RISCO (desvio moderado sustentado)": "RISCO",
    "FALHA (pico de latência)": "FALHA_LATENCIA",
    "FALHA (perda total de pacotes)": "FALHA_PERDA",
}


def _nan(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def _f(x) -> float:
    return math.nan if x is None else float(x)


# ----------------------------------------------------------------- baseline
@dataclass
class Baseline:
    mediana: float
    mad: float
    iqr: float
    jitter_tipico: float
    n_rtt_validos: int = 0

    def denominador(self) -> float:
        """Escala do z robusto: 1,4826*MAD; se MAD=0, max(IQR/1,349; 1 ms)."""
        d = 1.4826 * self.mad
        if d > 0:
            return d
        alt = self.iqr / 1.349 if not _nan(self.iqr) else 1.0
        return max(alt, 1.0)


def calcular_baseline(rtts, jitters=()) -> Baseline:
    """Ficha de baseline (mesma definição da Tarefa 2) a partir de RTTs válidos."""
    r = np.array([x for x in rtts if not _nan(x)], dtype=float)
    if r.size == 0:
        raise ValueError("Sem RTT válido para montar o baseline.")
    med = float(np.median(r))
    mad = float(np.median(np.abs(r - med)))
    iqr = float(np.quantile(r, 0.75) - np.quantile(r, 0.25))
    j = np.array([x for x in jitters if not _nan(x)], dtype=float)
    jt = float(np.median(j)) if j.size else math.nan
    return Baseline(med, mad, iqr, jt, int(r.size))


def salvar_baseline(host: str, b: Baseline, caminho: Path = ARQ_BASELINES) -> None:
    dados = json.loads(caminho.read_text()) if caminho.exists() else {}
    dados[host] = asdict(b)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, indent=2))


def carregar_baseline(host: str, caminho: Path = ARQ_BASELINES) -> Baseline | None:
    if not caminho.exists():
        return None
    d = json.loads(caminho.read_text()).get(host)
    return Baseline(**d) if d else None


# --------------------------------------------------------------------- ping
_RE_HOST = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-:]*$")
_RE_RTT = re.compile(r"(?:time|tempo)\s*([=<])\s*(\d+(?:[.,]\d+)?)\s*ms", re.I)


def parsear_ping(saida: str, enviados: int) -> dict:
    """Extrai RTTs da saída do `ping` (Linux/macOS/Windows, inglês ou pt-BR)."""
    rtts = []
    for sinal, valor in _RE_RTT.findall(saida):
        v = float(valor.replace(",", "."))
        rtts.append(v * 0.5 if sinal == "<" else v)   # Windows: "tempo<1ms"
    rtts = rtts[:enviados]
    recebidos = len(rtts)
    return {
        "rtt_medio_ms": float(np.mean(rtts)) if rtts else math.nan,
        "jitter_ms": float(np.std(rtts, ddof=1)) if len(rtts) >= 2 else math.nan,
        "enviados": enviados,
        "recebidos": recebidos,
        "perda_pct": (enviados - recebidos) / enviados * 100 if enviados else math.nan,
    }


def medir_ping(host: str, n: int = 3, timeout_s: int = 2) -> dict:
    """Executa `ping` real (3 pacotes, como na coleta do RIPE) e devolve uma medição."""
    if not _RE_HOST.match(host):
        raise ValueError(f"Host inválido: {host!r}")
    so = platform.system()
    if so == "Windows":
        cmd = ["ping", "-n", str(n), "-w", str(timeout_s * 1000), host]
    elif so == "Darwin":
        cmd = ["ping", "-c", str(n), "-W", str(timeout_s * 1000), host]
    else:
        cmd = ["ping", "-c", str(n), "-i", "0.2", "-W", str(timeout_s), host]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=n * timeout_s + 5)
        saida = p.stdout + p.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError):
        saida = ""
    m = parsear_ping(saida, n)
    m.update({"timestamp": datetime.now(timezone.utc), "host": host,
              "origem": "real", "cenario": ""})
    return m


# ---------------------------------------------------------------- simulação
def risco_simulavel(b: Baseline) -> bool:
    """RISCO exige 2 <= z e aumento <= 80 %: só cabe se 2*escala <= 0,75*mediana.
    Falha em baselines de resolução grossa (ex.: ping do Windows, que arredonda p/ 1 ms)."""
    return 2 * b.denominador() <= 0.75 * b.mediana


def simular_medicao(base: dict, cenario: str, b: Baseline) -> dict:
    """Substitui uma medição por uma sintética, marcada como 'simulada'.

    RISCO          : z ~ 2,8 (limite da regra: 2 <= z < 3,5) e aumento <= 75 %,
                     sem perda. Precisa durar 5 rodadas para a árvore dizer RISCO.
    FALHA_LATENCIA : RTT = 4x a mediana (aumento de 300 %, z muito alto).
    FALHA_PERDA    : 3 enviados, 0 recebidos (timeout).
    """
    m = dict(base)
    m["origem"], m["cenario"] = "simulada", cenario
    m["enviados"] = 3
    jt = 0.0 if _nan(b.jitter_tipico) else b.jitter_tipico
    if cenario == "RISCO":
        delta = min(2.8 * b.denominador(), 0.75 * b.mediana)
        m.update(rtt_medio_ms=b.mediana + delta, jitter_ms=jt, recebidos=3, perda_pct=0.0)
    elif cenario == "FALHA_LATENCIA":
        m.update(rtt_medio_ms=max(4 * b.mediana, b.mediana + 12 * b.denominador()),
                 jitter_ms=jt, recebidos=3, perda_pct=0.0)
    elif cenario == "FALHA_PERDA":
        m.update(rtt_medio_ms=math.nan, jitter_ms=math.nan, recebidos=0, perda_pct=100.0)
    else:
        raise ValueError(f"Cenário desconhecido: {cenario}")
    return m


# -------------------------------------------------------------------- árvore
_cache_arvore = {}


def carregar_arvore(caminho: Path = ARQ_ARVORE):
    if caminho not in _cache_arvore:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _cache_arvore[caminho] = joblib.load(caminho)
    return _cache_arvore[caminho]


def prever(vetor: dict, arvore=None) -> str:
    arvore = arvore or carregar_arvore()
    x = np.array([[SENTINELA if _nan(vetor[c]) else vetor[c] for c in FEATURES]], dtype=float)
    return str(arvore.predict(x)[0])


# ------------------------------------------------------------- fluxo ao vivo
class FluxoAoVivo:
    """Estado de um dispositivo monitorado: baseline + histórico das rodadas."""

    def __init__(self, host: str, baseline: Baseline, arvore=None):
        self.host, self.baseline, self.arvore = host, baseline, arvore
        self._linhas: list[dict] = []

    def processar(self, med: dict) -> dict:
        b = self.baseline
        rtt, jit, perda = _f(med.get("rtt_medio_ms")), _f(med.get("jitter_ms")), _f(med.get("perda_pct"))
        timeout = int(_nan(rtt) or perda >= 100)

        # z robusto
        if _nan(rtt):
            z = math.nan
        elif b.mad == 0 and rtt == b.mediana:
            z = 0.0
        else:
            z = (rtt - b.mediana) / b.denominador()
        # aumento %
        aum = (rtt - b.mediana) / b.mediana * 100 if (not _nan(rtt) and b.mediana > 0) else math.nan
        # jitter relativo
        if _nan(jit) or _nan(b.jitter_tipico):
            jrel = math.nan
        elif b.jitter_tipico == 0:
            jrel = 1.0 if jit == 0 else 3.0
        else:
            jrel = jit / b.jitter_tipico

        crit = bool((2 <= z < 3.5) or (30 <= aum <= 80) or (jrel >= 3))   # NaN -> False
        self._linhas.append({"z": z, "timeout": timeout, "aum80": bool(aum > 80), "crit": crit})
        u5 = self._linhas[-5:]
        n5_timeout = sum(l["timeout"] for l in u5)
        n5_aum80 = sum(l["aum80"] for l in u5)
        n5_risco = sum(l["crit"] for l in u5)

        # tendência do z (mesmas definições da Tarefa 4)
        zs = [l["z"] for l in self._linhas]
        z_delta1 = zs[-1] - zs[-2] if len(zs) >= 2 else math.nan
        ant = [v for v in zs[-4:-1] if not _nan(v)]
        z_media3 = float(np.mean(ant)) if len(ant) >= 2 else math.nan
        z_inc = math.nan
        if len(zs) >= 5 and not any(_nan(v) for v in zs[-5:]):
            z_inc = (-2 * zs[-5] - zs[-4] + zs[-2] + 2 * zs[-1]) / 10

        vetor = {
            "z_robusto": z, "aumento_pct": aum, "jitter_relativo": jrel, "perda_pct": perda,
            "timeout_atual": timeout, "n5_timeout": n5_timeout, "n5_aumento80": n5_aum80,
            "n5_risco": n5_risco, "z_delta1": z_delta1, "z_media3_ant": z_media3, "z_inclin5": z_inc,
        }
        # Regra da Tarefa 2 (estado ATUAL). A árvore (Tarefa 4) estima o estado a 3 rodadas.
        falha = perda >= 10 or n5_timeout >= 3 or z >= 3.5 or n5_aum80 >= 2
        classe_regra = "FALHA" if falha else ("RISCO" if (n5_risco >= 2 and crit) else "OK")

        # arvore=False desliga a previsão (usado para só rotular/extrair atributos em lote)
        arvore = None if self.arvore is False else prever(vetor, self.arvore)
        return {**med, **vetor, "classe_regra": classe_regra, "classe_arvore": arvore}
