"""Pruebas de analisis_linguistico.py (requieren spaCy y es_core_news_md).

    .venv/bin/python -m unittest discover -s pruebas -v
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import analisis_linguistico as al  # noqa: E402

try:
    import spacy
    spacy.load(al.MODELO_POR_DEFECTO)
    HAY_MODELO = True
except Exception:  # noqa: BLE001
    HAY_MODELO = False


def frag(ident, articulo, texto, epigrafe=""):
    return {"identificador": ident, "norma": "Ley 1801 de 2016", "articulo": articulo,
            "ubicacion_jerarquica": {"libro": "LIBRO PRIMERO. X", "titulo": None, "capitulo": None},
            "epigrafe": epigrafe, "texto": texto, "estado_vigencia": "vigente", "tema": epigrafe,
            "notas": [], "fecha_consulta": "2026-11-06"}


CORPUS = [
    frag("art_5", "5", "Para los efectos de este Código, se entiende por convivencia, la interacción "
         "pacífica entre las personas.", "Definición"),
    frag("art_174", "174", "Es un llamado de atención en privado o en público.", "Amonestación"),
    frag("art_180", "180", "Multa Tipo 1: Dos (2) salarios mínimos diarios legales vigentes (smdlv). "
         "El inspector de Policía impondrá las multas dentro de los cinco (5) días hábiles siguientes.",
         "Multas"),
    frag("art_181", "181", "La multa general tipo 2 se paga en el espacio público. La multa se reduce.", "Multa especial"),
    frag("art_219", "219", "El personal uniformado de la Policía Nacional podrá expedir orden de comparendo.",
         "Procedimiento"),
]


class Funciones(unittest.TestCase):
    def test_normalizar(self):
        self.assertEqual(al.normalizar("«Hola»  —  “mundo”\n"), '"Hola" - "mundo"')

    def test_sttr(self):
        self.assertIsNone(al.sttr(["a"] * 10, 1000))
        self.assertEqual(al.sttr(["a", "b"] * 1000, 1000), 0.002)

    def test_expandir_consulta(self):
        indice = {"parte": ["orden de comparendo"], "requisa": ["registro"], "la calle": ["espacio público"]}
        self.assertEqual(al.expandir_consulta("¿Qué hago si me pusieron un parte en la calle?", indice),
                         ["espacio público", "orden de comparendo"])
        self.assertEqual(al.expandir_consulta("departamento", indice), [])

    def test_regex_monto_y_plazo(self):
        self.assertEqual(al.RE_MONTO.search("multa de ciento cincuenta (150) salarios mínimos legales "
                                            "mensuales vigentes").group(0),
                         "ciento cincuenta (150) salarios mínimos legales mensuales vigentes")
        self.assertEqual(al.RE_PLAZO.search("dentro de los cuarenta y ocho (48) horas").group(0),
                         "cuarenta y ocho (48) horas")
        self.assertIsNone(al.RE_PLAZO.search("de día y hora"))

    def test_definicion(self):
        d = al.buscar_definicion("convivencia", CORPUS)
        self.assertEqual(d["identificador"], "art_5")
        self.assertTrue(d["texto"].startswith("Para los efectos"))
        self.assertEqual(al.buscar_definicion("amonestación", CORPUS)["identificador"], "art_174")
        self.assertEqual(al.buscar_definicion("multa", CORPUS)["identificador"], "art_180")  # «Multas»
        self.assertIsNone(al.buscar_definicion("comparendo", CORPUS))


@unittest.skipUnless(HAY_MODELO, "requiere spaCy y es_core_news_md")
class Analisis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        (d / "corpus.json").write_text(json.dumps(CORPUS, ensure_ascii=False), encoding="utf-8")
        terminos = {"kwic": ["multa", "espacio público"], "glosario": ["convivencia", "multa", "orden de comparendo"],
                    "sinonimos": {"orden de comparendo": ["parte"], "inexistente xyz": ["nada"]},
                    "autoridades": ["inspector de policía", "personal uniformado de la policía nacional"],
                    "lugares": ["espacio público"]}
        (d / "terminos.json").write_text(json.dumps(terminos, ensure_ascii=False), encoding="utf-8")
        cls.salida = d / "analisis"
        al.log.disabled = True  # avisos esperados («inexistente xyz»)
        try:
            cls.r = al.analizar(d / "corpus.json", cls.salida, d / "terminos.json")
        finally:
            al.log.disabled = False

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_archivos(self):
        for nombre in ["corpus_procesado.jsonl", "estadisticas.json", "frecuencias_lemas.csv", "ngramas.csv",
                       "colocaciones.csv", "kwic.txt", "kwic.json", "glosario.json", "sinonimos.json",
                       "informe_linguistico.md"]:
            self.assertTrue((self.salida / nombre).is_file(), nombre)
        lineas = (self.salida / "corpus_procesado.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lineas), len(CORPUS))

    def test_registro(self):
        r = self.r["registros"][2]
        self.assertEqual(r["identificador"], "art_180")
        self.assertEqual(len(r["tokens"]), len(r["lemas"]))
        self.assertEqual(len(r["tokens"]), len(r["pos"]))
        self.assertIn("multa", r["lemas"])  # «multas» lematizado
        etiquetas = {(e["etiqueta"], e["texto"]) for e in r["entidades"]}
        self.assertIn(("MONTO", "Dos (2) salarios mínimos diarios legales vigentes (smdlv)"), etiquetas)
        self.assertIn(("PLAZO", "cinco (5) días hábiles"), etiquetas)
        self.assertIn(("AUTORIDAD", "inspector de Policía"), etiquetas)

    def test_estadisticas(self):
        e = self.r["estadisticas"]
        self.assertEqual(e["n_articulos"], 5)
        self.assertEqual(e["n_fragmentos"], 5)
        self.assertEqual(e["n_tokens"], sum(r["n_tokens"] for r in self.r["registros"]))
        self.assertAlmostEqual(e["relacion_tipo_token"], round(e["n_tipos"] / e["n_tokens"], 4))
        self.assertNotIn("PUNCT", e["pos"])

    def test_kwic_por_lema(self):
        nodos = [l["nodo"].lower() for l in self.r["kwic"]["multa"]]
        self.assertIn("multas", nodos)
        self.assertEqual(len(self.r["kwic"]["espacio público"]), 1)

    def test_glosario_y_sinonimos(self):
        g = {e["termino"]: e for e in self.r["glosario"]["terminos"]}
        self.assertEqual(g["convivencia"]["definicion"]["identificador"], "art_5")
        self.assertEqual(g["orden de comparendo"]["articulos"], ["219"])
        s = self.r["sinonimos"]
        self.assertEqual(s["indice_inverso"]["parte"], ["orden de comparendo"])
        self.assertEqual(s["terminos"]["inexistente xyz"]["frecuencia_en_corpus"], 0)

    def test_ngramas_no_cruzan_puntuacion(self):
        for g in self.r["ngramas"]:
            self.assertNotIn(".", g["ngrama"])


class Errores(unittest.TestCase):
    def test_corpus_inexistente(self):
        with self.assertRaises(al.AnalisisError):
            al.analizar("/no/existe.json", "/tmp/x")


if __name__ == "__main__":
    unittest.main()
