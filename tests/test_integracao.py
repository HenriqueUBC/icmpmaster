from pathlib import Path
import sys
import unittest
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from contrato_icmp import normalizar_medicao
from baseline_local import construir_baseline
import modelo_icmp as mi
from preditor_icmp import prever_medicao
from alerta_icmp import carregar_alerta_auxiliar

RAIZ = Path(__file__).resolve().parents[1]

class Integracao(unittest.TestCase):
    def test_contrato_nao_vaza_rotulo(self):
        base = {"timestamp": "2026-11-01T12:00:00Z", "ip": "192.0.2.5",
                "latencia_ms": 22, "perda_pacotes_pct": 0, "jitter_ms": 1}
        a = normalizar_medicao({**base, "status_real": "FALHA"})
        b = normalizar_medicao({**base, "status_real": "OK"})
        self.assertEqual({k: v for k,v in a.items() if k != 'status_real'},
                         {k: v for k,v in b.items() if k != 'status_real'})
    def test_timeout(self):
        a = normalizar_medicao({"timestamp":"2026-11-01T12:00Z", "ip":"192.0.2.1",
                "latencia_ms":None, "perda_pacotes_pct":100, "jitter_ms":None})
        self.assertEqual(a["timeout_atual"], 1)
        self.assertTrue(pd.isna(a["rtt_medio_ms"]))
    def test_ip_invalido(self):
        with self.assertRaises(ValueError):
            normalizar_medicao({"timestamp":"2026-11-01T12:00Z", "ip":"IP falso",
                "latencia_ms":10, "perda_pacotes_pct":0, "jitter_ms":1})
    def test_baseline_aquecimento(self):
        d = pd.DataFrame([{"fluxo_id":"ping_local|192.0.2.1", "timestamp":f"2026-11-01T12:{i:02d}:00Z",
                           "rtt_medio_ms":20+i*.1, "jitter_ms":1} for i in range(5)])
        self.assertEqual(construir_baseline(d).iloc[0]["status"], "aquecimento")
    def test_arvore_original(self):
        arvore, colunas = mi.carregar_modelo()
        self.assertEqual(len(colunas), 11)
        self.assertEqual(arvore.n_features_in_, 11)
    def test_auxiliar_independente_streamlit(self):
        caminho = RAIZ / "modelos" / "alerta_antecipado.joblib"
        import sklearn
        if sklearn.__version__ != "1.9.1":
            self.skipTest("Modelo auxiliar salvo em sklearn 1.9.1; ambiente atual incompatível")
        pacote = carregar_alerta_auxiliar(str(caminho), caminho.stat().st_mtime_ns)
        self.assertEqual(len(pacote["features"]), 11)

if __name__ == "__main__":
    unittest.main()
