"""Testes do monitoramento ao vivo (unittest/pytest): python -m unittest discover -s tests"""
import math
import sys
import unittest
import warnings
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
warnings.filterwarnings("ignore")
import ao_vivo as av  # noqa: E402

LAN = av.Baseline(mediana=1.2, mad=0.0185, iqr=0.0385, jitter_tipico=0.04, n_rtt_validos=30)


def _real(rng):
    r = rng.normal(1.2, 0.06, 3).clip(0.2)
    return dict(rtt_medio_ms=float(r.mean()), jitter_ms=float(r.std(ddof=1)), enviados=3,
                recebidos=3, perda_pct=0.0, origem="real", cenario="")


class AoVivo(unittest.TestCase):
    def test_parser_linux_e_windows_ptbr(self):
        a = av.parsear_ping("64 bytes: icmp_seq=1 ttl=64 time=1.20 ms\n64 bytes: time=1.00 ms\n", 3)
        self.assertEqual(a["recebidos"], 2)
        self.assertAlmostEqual(a["perda_pct"], 100 / 3)
        self.assertAlmostEqual(a["rtt_medio_ms"], 1.1)
        w = av.parsear_ping("Resposta de x: bytes=32 tempo=2ms TTL=64\nResposta de x: tempo<1ms TTL=64\n"
                            "Esgotado o tempo limite do pedido.", 3)
        self.assertEqual(w["recebidos"], 2)
        self.assertAlmostEqual(w["rtt_medio_ms"], 1.25)
        self.assertEqual(av.parsear_ping("", 3)["perda_pct"], 100.0)

    def test_host_invalido_e_rejeitado(self):
        for ruim in ("-f 8.8.8.8", "a b", "x;rm -rf /", ""):
            with self.assertRaises(ValueError):
                av.medir_ping(ruim)

    def test_demo_ok_risco_falha_com_arvore_real(self):
        rng = np.random.default_rng(1)
        fl = av.FluxoAoVivo("lan", LAN)
        vistos = []
        for cen, n in [(None, 10), ("RISCO", 6), (None, 4), ("FALHA_LATENCIA", 3)]:
            for _ in range(n):
                m = _real(rng)
                m = av.simular_medicao(m, cen, LAN) if cen else m
                o = fl.processar(m)
                self.assertEqual(o["origem"], "simulada" if cen else "real")
                vistos.append(o["classe_arvore"])
        self.assertEqual(vistos[:10], ["OK"] * 10)
        self.assertIn("RISCO", vistos[10:16])
        self.assertEqual(vistos[-3:], ["FALHA"] * 3)

    def test_sem_falso_alarme_em_rede_estavel(self):
        rng = np.random.default_rng(2)
        fl = av.FluxoAoVivo("lan", LAN)
        self.assertEqual({fl.processar(_real(rng))["classe_arvore"] for _ in range(200)}, {"OK"})

    def test_perda_total_regra_diz_falha(self):
        fl = av.FluxoAoVivo("lan", LAN)
        o = fl.processar(av.simular_medicao(_real(np.random.default_rng(0)), "FALHA_PERDA", LAN))
        self.assertEqual(o["classe_regra"], "FALHA")
        self.assertEqual(o["timeout_atual"], 1)

    def test_risco_simulavel(self):
        self.assertTrue(av.risco_simulavel(LAN))
        self.assertFalse(av.risco_simulavel(av.Baseline(1.0, 0.0, 0.0, 0.0)))   # ping do Windows (1 ms)

    def test_atributos_e_classe_iguais_ao_dataset(self):
        import pandas as pd
        arqs = [RAIZ / "data/interim/medicoes.csv", RAIZ / "data/processed/dataset_rotulado_B.csv",
                RAIZ / "data/processed/baseline_por_fluxo.csv"]
        if not all(a.exists() for a in arqs):
            self.skipTest("dados do projeto ausentes")
        m = pd.read_csv(arqs[0], parse_dates=["timestamp"])
        b = pd.read_csv(arqs[1], parse_dates=["timestamp"]).sort_values(["fluxo_id", "timestamp"])
        fic = pd.read_csv(arqs[2]).set_index("fluxo_id")
        cols = ["z_robusto", "aumento_pct", "jitter_relativo", "perda_pct", "timeout_atual",
                "n5_timeout", "n5_aumento80", "n5_risco"]
        for f in ["1000755|63.222.187.5", "1003574|143.255.248.149"]:
            r = fic.loc[f]
            base = av.Baseline(r["mediana"], r["MAD"], r["iqr"], r["jitter_tipico"], int(r["n_rtt_validos_A"]))
            mb = m[(m.fluxo_id == f) & (m.timestamp >= "2026-09-13T04:32:00Z")
                   & (m.timestamp < "2026-09-20T04:32:00Z")].sort_values("timestamp")
            ref = b[b.fluxo_id == f].reset_index(drop=True)
            fl = av.FluxoAoVivo(f, base)
            o = pd.DataFrame([fl.processar(x._asdict()) for x in mb.itertuples(index=False)])
            self.assertEqual(len(o), len(ref))
            for c in cols:
                self.assertTrue(np.allclose(o[c].astype(float), ref[c].astype(float), equal_nan=True, rtol=1e-6), c)
            self.assertTrue((o["classe_regra"].to_numpy() == ref["classe"].to_numpy()).all())


if __name__ == "__main__":
    unittest.main()
