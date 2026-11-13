"""Pruebas de segmentar_codigo.py con un texto sintético que imita el formato
del Código (títulos sin rótulo, tablas, notas de Función Pública).

    .venv/bin/python -m unittest discover -s pruebas -v
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import segmentar_codigo as sc  # noqa: E402

TEXTO = """LEY 1801 DE 2016

EL CONGRESO DE COLOMBIA

DECRETA:

LIBRO PRIMERO

DISPOSICIONES GENERALES

OBJETO DEL CÓDIGO.

CAPÍTULO I

OBJETO DEL CÓDIGO

ARTÍCULO 1. Objeto. Las disposiciones son de carácter preventivo.

ARTÍCULO 2. Objetivos específicos. Los objetivos son:

1. Propiciar la convivencia.

2. Promover el respeto.

a) primer literal del numeral dos.

PARÁGRAFO . Quien incurra en los comportamientos tendrá medidas:

COMPORTAMIENTOS

MEDIDA CORRECTIVA A APLICAR

Numeral 1

Multa General tipo 2

LIBRO SEGUNDO

DE LOS DERECHOS Y DEBERES DE

LAS PERSONAS

DEL DERECHO DE REUNIÓN

ARTÍCULO 3.   Medios.   Son medios inmateriales:

1. Orden.

2. Permiso.

Son medios materiales:

1. Traslado.

PARÁGRAFO 2. Texto del parágrafo con lista:

1. Primero del parágrafo.

PARÁGRAFO TRANSITORIO. Texto transitorio.

ARTÍCULO 3A. Sin perjuicio de lo anterior, se aplicará el siguiente procedimiento:

1. Paso uno.

(Declarado INEXEQUIBLE mediante Sentencia de la Corte Constitucional C-223 de 2017)

ARTÍCULO 4. Vigencia. La presente ley rige desde su promulgación.

(Expresión subrayada, declarada INEXEQUIBLE mediante Sentencia C-1 de 2020)

EL PRESIDENTE DEL HONORABLE SENADO DE LA REPÚBLICA,

FULANO DE TAL.
"""


class Segmentacion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        entrada = Path(cls.tmp.name) / "ley.txt"
        entrada.write_text(TEXTO, encoding="utf-8")
        cls.salida = Path(cls.tmp.name) / "corpus.json"
        cls.corpus = sc.segmentar(entrada, cls.salida)
        cls.por_id = {f["identificador"]: f for f in cls.corpus}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_claves_exactas(self):
        claves = {"identificador", "ubicacion_jerarquica", "epigrafe", "texto", "estado_vigencia", "tema", "notas",
                  "norma", "articulo", "fecha_consulta"}
        for f in self.corpus:
            self.assertEqual(set(f), claves)
            self.assertEqual(set(f["ubicacion_jerarquica"]), {"libro", "titulo", "capitulo"})

    def test_json_escrito(self):
        self.assertEqual(json.loads(self.salida.read_text(encoding="utf-8")), self.corpus)

    def test_identificadores(self):
        self.assertEqual(list(self.por_id), [
            "art_1", "art_2", "art_2_num_1", "art_2_num_2", "art_2_par_unico",
            "art_3", "art_3_num_1", "art_3_num_2", "art_3_inc_2", "art_3_inc_2_num_1",
            "art_3_par_2", "art_3_par_2_num_1", "art_3_par_transitorio",
            "art_3A", "art_3A_num_1", "art_4",
        ])

    def test_jerarquia_y_titulos_sin_rotulo(self):
        u = self.por_id["art_1"]["ubicacion_jerarquica"]
        self.assertEqual(u["libro"], "LIBRO PRIMERO. DISPOSICIONES GENERALES")
        self.assertEqual(u["titulo"], "TÍTULO I. OBJETO DEL CÓDIGO")
        self.assertEqual(u["capitulo"], "CAPÍTULO I. OBJETO DEL CÓDIGO")
        u = self.por_id["art_3"]["ubicacion_jerarquica"]
        # Nombre de libro partido en dos párrafos; el título se reinicia en I.
        self.assertEqual(u["libro"], "LIBRO SEGUNDO. DE LOS DERECHOS Y DEBERES DE LAS PERSONAS")
        self.assertEqual(u["titulo"], "TÍTULO I. DEL DERECHO DE REUNIÓN")
        self.assertIsNone(u["capitulo"])

    def test_epigrafe_y_texto(self):
        art = self.por_id["art_3"]
        self.assertEqual(art["epigrafe"], "Medios")
        self.assertEqual(art["texto"], "Son medios inmateriales:")
        self.assertEqual(self.por_id["art_3A"]["epigrafe"], "")
        self.assertEqual(self.por_id["art_3A"]["tema"], "Del derecho de reunión")

    def test_literal_y_tabla_en_su_lugar(self):
        self.assertIn("a) primer literal", self.por_id["art_2_num_2"]["texto"])
        self.assertIn("Numeral 1\nMulta General tipo 2", self.por_id["art_2_par_unico"]["texto"])
        # La tabla no se confunde con un título.
        self.assertEqual(self.por_id["art_2_par_unico"]["ubicacion_jerarquica"]["titulo"], "TÍTULO I. OBJETO DEL CÓDIGO")

    def test_vigencia(self):
        self.assertEqual(self.por_id["art_1"]["estado_vigencia"], "vigente")
        self.assertEqual(self.por_id["art_3A"]["estado_vigencia"], "inexequible")
        self.assertEqual(self.por_id["art_3A_num_1"]["estado_vigencia"], "inexequible")
        self.assertEqual(self.por_id["art_4"]["estado_vigencia"], "inexequible_parcial")

    def test_notas_fuera_del_texto(self):
        f = self.por_id["art_3A_num_1"]
        self.assertEqual(f["texto"], "1. Paso uno.")
        self.assertEqual(f["notas"], ["(Declarado INEXEQUIBLE mediante Sentencia de la Corte Constitucional C-223 de 2017)"])
        self.assertEqual(self.por_id["art_4"]["texto"], "La presente ley rige desde su promulgación.")
        self.assertEqual(len(self.por_id["art_4"]["notas"]), 1)
        self.assertEqual(self.por_id["art_1"]["notas"], [])

    def test_metadatos_de_origen(self):
        self.assertEqual(self.por_id["art_3A_num_1"]["articulo"], "3A")
        self.assertEqual(self.por_id["art_2_par_unico"]["articulo"], "2")
        for f in self.corpus:
            self.assertEqual(f["norma"], "Ley 1801 de 2016")
            self.assertIsNone(f["fecha_consulta"])  # no hay .paginas.json

    def test_fecha_desde_paginas_json_y_explicita(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "Ley_1801_de_2016.txt"
            p.write_text("ARTÍCULO 1. Objeto. Texto.", encoding="utf-8")
            (Path(d) / "Ley_1801_de_2016.paginas.json").write_text(
                '{"fecha_consulta": "2026-11-06"}', encoding="utf-8")
            f = sc.segmentar(p, None)[0]
            self.assertEqual((f["norma"], f["fecha_consulta"]), ("Ley 1801 de 2016", "2026-11-06"))
            f = sc.segmentar(p, None, norma="Ley X", fecha_consulta="2026-01-01")[0]
            self.assertEqual((f["norma"], f["fecha_consulta"]), ("Ley X", "2026-01-01"))

    def test_firmas_excluidas(self):
        self.assertNotIn("PRESIDENTE", self.por_id["art_4"]["texto"])


class Errores(unittest.TestCase):
    def test_archivo_inexistente(self):
        with self.assertRaises(sc.SegmentacionError):
            sc.segmentar("/no/existe.txt", None)

    def test_sin_articulos(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.txt"
            p.write_text("Texto sin artículos.\n\nOtro párrafo.", encoding="utf-8")
            with self.assertRaises(sc.SegmentacionError):
                sc.segmentar(p, None)

    def test_saltos_y_espacios_irregulares(self):
        texto = "ARTÍCULO 7.\tObjeto.  Texto\r\npartido en dos líneas.\r\nPARÁGRAFO 1. Otro."
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.txt"
            p.write_bytes(texto.encode("utf-8"))
            corpus = sc.segmentar(p, None)
        self.assertEqual([f["identificador"] for f in corpus], ["art_7", "art_7_par_1"])
        self.assertEqual(corpus[0]["texto"], "Texto partido en dos líneas.")


if __name__ == "__main__":
    unittest.main()
