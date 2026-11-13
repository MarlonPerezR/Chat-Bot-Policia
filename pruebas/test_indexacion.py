"""Pruebas de indexacion.py: segmentaciones, métricas e índice FAISS.
No descargan modelos (los embeddings se simulan).

    .venv/bin/python -m unittest discover -s pruebas -v
"""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import indexacion as ix  # noqa: E402


def frag(ident, articulo, texto, epigrafe="Epígrafe", estado="vigente"):
    return {"identificador": ident, "norma": "Ley 1801 de 2016", "articulo": articulo,
            "ubicacion_jerarquica": {"libro": "LIBRO PRIMERO. X", "titulo": "TÍTULO I. Y", "capitulo": None},
            "epigrafe": epigrafe, "texto": texto, "estado_vigencia": estado, "tema": epigrafe,
            "notas": [], "fecha_consulta": "2026-11-06"}


CORPUS = [
    frag("art_1", "1", "uno " * 30, "Objeto"),
    frag("art_1_num_1", "1", "1. dos " * 10, "Objeto"),
    frag("art_2", "2", "tres " * 50, "Multas", "inexequible"),
    frag("art_2_par_1", "2", "PARÁGRAFO 1. cuatro " * 10, "Multas"),
]


class Segmentaciones(unittest.TestCase):
    def test_fragmento_con_encabezado(self):
        u = ix.construir_unidades(CORPUS, "fragmento")
        self.assertEqual(len(u), 4)
        self.assertTrue(u[1]["texto_embedding"].startswith("Ley 1801 de 2016, artículo 1. Objeto.\n1. dos"))
        self.assertEqual(u[1]["texto"], CORPUS[1]["texto"])  # el texto a mostrar no lleva encabezado

    def test_articulo_completo(self):
        u = ix.construir_unidades(CORPUS, "articulo")
        self.assertEqual([x["id"] for x in u], ["art_1", "art_2"])
        self.assertEqual(u[1]["identificadores"], ["art_2", "art_2_par_1"])
        self.assertEqual(u[1]["estado_vigencia"], "inexequible_parcial")  # fragmentos con estados distintos
        self.assertIn("cuatro", u[1]["texto"])

    def test_ventanas_fijas(self):
        u = ix.unidades_fijas(CORPUS, tam=40, solape=10)
        palabras = sum(len(f["texto"].split()) for f in CORPUS) + 2 * 3 + 1  # + «ARTÍCULO N. Epígrafe.»
        self.assertTrue(all(len(x["texto"].split()) <= 40 for x in u))
        # Cubren todo el texto y la última ventana llega al final.
        self.assertTrue(u[-1]["texto"].endswith("cuatro"))
        self.assertGreaterEqual((len(u) - 1) * 30 + 40, palabras)
        # Una ventana que cruza de un artículo al otro se asocia a ambos.
        self.assertTrue(any(x["articulos"] == ["1", "2"] for x in u))
        # Solape: el final de una ventana se repite al comienzo de la siguiente.
        self.assertEqual(u[0]["texto"].split()[-10:], u[1]["texto"].split()[:10])

    def test_solape_invalido(self):
        with self.assertRaises(ix.IndexacionError):
            ix.unidades_fijas(CORPUS, tam=10, solape=10)
        with self.assertRaises(ix.IndexacionError):
            ix.construir_unidades(CORPUS, "otra")


class Metricas(unittest.TestCase):
    def test_metricas(self):
        ranking = [["9"], ["5"], ["5", "6"], ["7"], ["8"]]
        m = ix.metricas(ranking, {"5", "7"}, ks=(1, 3, 5))
        self.assertEqual(m["P@1"], 0)
        self.assertAlmostEqual(m["P@3"], 2 / 3)
        self.assertEqual(m["R@3"], 0.5)
        self.assertEqual(m["R@5"], 1.0)
        self.assertEqual(m["RR"], 0.5)

    def test_sin_relevantes(self):
        self.assertEqual(ix.metricas([["1"], ["2"]], {"9"}, ks=(1,))["RR"], 0.0)


class ModeloFalso:
    """Embeddings deterministas: un vector por artículo esperado."""
    def __init__(self, vectores_consulta):
        self.v = vectores_consulta

    def consultas(self, textos):
        return np.array(self.v[:len(textos)], dtype="float32")


class IndiceYEvaluacion(unittest.TestCase):
    def test_faiss_y_evaluar(self):
        unidades = ix.construir_unidades(CORPUS, "articulo")
        base = np.eye(4, dtype="float32")[:2]  # art 1 → e0, art 2 → e1
        indice = ix.crear_indice(base)
        preguntas = [{"id": 1, "pregunta": "a", "articulos": ["2"]},
                     {"id": 2, "pregunta": "b", "articulos": ["1"]},
                     {"id": 3, "pregunta": "c", "articulos": []}]
        consultas = [[0, 1, 0, 0], [0.6, 0.8, 0, 0], [0, 0, 1, 0]]
        ev = ix.evaluar(ModeloFalso(consultas), indice, unidades, preguntas)
        r = ev["resumen"]
        self.assertEqual(r["P@1"], 0.5)
        self.assertEqual(r["MRR"], 0.75)  # (1 + 1/2) / 2
        self.assertAlmostEqual(r["similitud_max_fuera"]["max"], 0.0)
        self.assertEqual(ev["por_pregunta"][0]["recuperados"][0], "art_2")


if __name__ == "__main__":
    unittest.main()
