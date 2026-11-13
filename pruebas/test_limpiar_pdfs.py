"""Pruebas de limpiar_pdfs.py con textos y PDFs sintéticos.

    .venv/bin/python -m unittest discover -s pruebas -v
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import limpiar_pdfs as lp  # noqa: E402


def limpiar(texto):
    return lp.limpiar_caracteres(texto, lp.Estadisticas())


class Caracteres(unittest.TestCase):
    def test_mojibake(self):
        self.assertEqual(limpiar("investigaciÃ³n sobre el niÃ±o"),
                         "investigación sobre el niño")
        self.assertEqual(limpiar("Â¿QuÃ© pasÃ³?"), "¿Qué pasó?")
        self.assertEqual(limpiar("â€œcomillasâ€\x9d y guion â€” largo"),
                         "“comillas” y guion — largo")
        # «í» y «Á» corruptas contienen guion blando / control: no se pierden.
        self.assertEqual(limpiar("polÃ­tica Ã\x81rea"), "política Área")

    def test_no_toca_texto_correcto(self):
        t = "Él cumplió 30 años en Bogotá; ¿qué más? «Sí», dijo — ½ y 2º."
        self.assertEqual(limpiar(t), t)

    def test_ligaduras_cid_invisibles(self):
        self.assertEqual(limpiar("modiﬁcado eﬃcaz"), "modificado efficaz")
        self.assertEqual(limpiar("pa(cid:12)labra"), "palabra")
        self.assertEqual(limpiar("pa​lab﻿ra\x07 x"), "palabra x")
        self.assertEqual(limpiar("texto� roto"), "texto roto")
        self.assertEqual(limpiar("a b c\t d"), "a b c d")

    def test_vinetas_y_basura(self):
        self.assertEqual(limpiar(" punto"), "• punto")
        self.assertEqual(limpiar("__________"), "")
        self.assertEqual(limpiar("* * *"), "")
        self.assertEqual(limpiar("Introducción ........ 5"), "Introducción 5")

    def test_guion_blando_final(self):
        self.assertEqual(limpiar("pala­"), "pala-")


class NumerosDePagina(unittest.TestCase):
    def test_patrones(self):
        for t in ["12", "- 12 -", "— 3 —", "Página 3 de 40", "Pág. 7",
                  "p. 9", "xiv", "3/10", "[5]"]:
            self.assertTrue(lp.RE_NUM_PAGINA.match(t), t)
        for t in ["Artículo 12", "12 de octubre", "Capítulo I. Inicio"]:
            self.assertFalse(lp.RE_NUM_PAGINA.match(t), t)


class Parrafos(unittest.TestCase):
    def test_une_lineas_y_palabras_partidas(self):
        lineas = ["El conflicto armado dejó una huella profunda en la",
                  "región y sus habitantes, que debieron despla-",
                  "zarse durante años hacia otras ciudades del país.",
                  "Corto.",
                  "Nuevo párrafo que empieza aquí con mayúscula y sigue."]
        p = lp.reconstruir_parrafos(lineas, 50, False)
        self.assertEqual(p[0], "El conflicto armado dejó una huella profunda en la "
                               "región y sus habitantes, que debieron desplazarse "
                               "durante años hacia otras ciudades del país. Corto.")
        self.assertEqual(p[1], lineas[-1])

    def test_conservar_guiones(self):
        p = lp.reconstruir_parrafos(["una línea larga que termina con despla-",
                                     "zarse"], 40, True)
        self.assertEqual(p, ["una línea larga que termina con despla- zarse"])

    def test_vinetas_y_articulos_abren_parrafo(self):
        lineas = ["Texto de una tabla que ocupa toda la línea completa",
                  "ARTÍCULO 101. Comportamientos que afectan la fauna.",
                  "a) primer literal que es bastante largo para la línea",
                  "b) segundo literal"]
        p = lp.reconstruir_parrafos(lineas, 50, False)
        self.assertEqual(len(p), 4, p)

    def test_no_corta_referencia_en_minuscula(self):
        lineas = ["según lo dispuesto en el texto de la norma y en el",
                  "artículo 5 de la Ley 100 de 1993, se procede así."]
        self.assertEqual(len(lp.reconstruir_parrafos(lineas, 50, False)), 1)

    def test_fusiona_bloques_cortados(self):
        p = lp.fusionar_cortados(["Una frase que se corta sin", "terminar aquí."],
                                 False)
        self.assertEqual(p, ["Una frase que se corta sin terminar aquí."])

    def test_cifra_entre_parentesis_no_es_vineta(self):
        lineas = ["cuando la obra se suspenda por más de dos",
                  "(2) meses, o cuando sea necesario."]
        self.assertEqual(lp.reconstruir_parrafos(lineas, 40, False),
                         ["cuando la obra se suspenda por más de dos (2) meses, "
                          "o cuando sea necesario."])
        self.assertEqual(lp.fusionar_cortados(lineas, False),
                         ["cuando la obra se suspenda por más de dos (2) meses, "
                          "o cuando sea necesario."])
        # Tras una frase terminada sí es una lista.
        self.assertEqual(len(lp.fusionar_cortados(
            ["Son requisitos:", "(1) contar con permiso."], False)), 1 + 1)


class ReparacionLexica(unittest.TestCase):
    BASE = ["La convivencia y la ley.", "Promover la convivencia según la ley.",
            "La ley protege la convivencia.", "COMPORTAMIENTOS", "COMPORTAMIENTOS",
            "COMPORTAMIENTOS", "MEDIDA CORRECTIVA", "MEDIDA", "MEDIDA",
            "Numeral 1", "Numeral 2", "Numeral 3", "APLICAR", "APLICAR", "APLICAR",
            "A quien incurra. A la persona. A todos."]

    def reparar(self, *parrafos):
        salida, cambios = lp.reparar_lexico(self.BASE + list(parrafos), lp.Estadisticas())
        return salida[len(self.BASE):], cambios

    def test_guion_interno(self):
        salida, cambios = self.reparar("Fomentar la con-vivencia.")
        self.assertEqual(salida, ["Fomentar la convivencia."])
        self.assertEqual(cambios, {"con-vivencia": "convivencia"})

    def test_compuesto_legitimo_no_se_toca(self):
        salida, _ = self.reparar("Control minero-ambiental y alianzas PÚBLICO-PRIVADAS.")
        self.assertEqual(salida, ["Control minero-ambiental y alianzas PÚBLICO-PRIVADAS."])

    def test_palabras_pegadas(self):
        salida, _ = self.reparar("COMPORTAMIENTOSMEDIDA CORRECTIVA AAPLICAR", "Numeral7")
        self.assertEqual(salida, ["COMPORTAMIENTOS MEDIDA CORRECTIVA A APLICAR", "Numeral 7"])

    def test_nota_al_pie_en_minuscula_no_se_separa(self):
        salida, _ = self.reparar("Los aportes anuales1 se calculan así.")
        self.assertEqual(salida, ["Los aportes anuales1 se calculan así."])

    def test_i_mayuscula_por_l(self):
        salida, _ = self.reparar("Conforme a la Iey vigente.", "Iniciar el trámite.")
        self.assertEqual(salida, ["Conforme a la ley vigente.", "Iniciar el trámite."])


class Bordes(unittest.TestCase):
    def _paginas(self, n, nota_pags=(), nota_y=None):
        pags = []
        for i in range(1, n + 1):
            bloques = [
                lp.Bloque(["Informe anual de prueba"], 0.03, 0.05),
                # Párrafo que empieza dentro de la franja superior y solo
                # cambia en un número: no es encabezado.
                lp.Bloque([f"Resumen del capítulo {i} con el mismo texto."],
                          0.10, 0.30),
                lp.Bloque([f"Cuerpo de la página {i}, distinto en cada una."],
                          0.2, 0.5),
            ]
            if i in nota_pags:
                y = nota_y[i] if nota_y else 0.90
                bloques.append(lp.Bloque(["(Ver nota aclaratoria)"], y, y + 0.01))
            bloques.append(lp.Bloque([f"Documento X {i} - Pie"], 0.95, 0.97))
            pags.append(lp.Pagina(i, bloques))
        return pags

    def test_quita_encabezado_y_pie_repetidos(self):
        pags = self._paginas(10)
        quitar, resumen = lp.detectar_bordes(pags, 3, 0.12, 0.3, 0)
        self.assertEqual(len(quitar), 20)
        self.assertEqual({r["texto"] for r in resumen},
                         {"Informe anual de prueba", "Documento X 1 - Pie"})

    def test_conserva_nota_repetida_a_distinta_altura(self):
        alturas = {2: 0.89, 4: 0.06, 6: 0.92, 8: 0.10}
        pags = self._paginas(10, nota_pags=alturas, nota_y=alturas)
        quitar, resumen = lp.detectar_bordes(pags, 3, 0.12, 0.3, 4)
        self.assertNotIn("(Ver nota aclaratoria)", {r["texto"] for r in resumen})


@unittest.skipIf(lp.fitz is None, "requiere PyMuPDF")
class DocumentoCompleto(unittest.TestCase):
    def _crear_pdf(self, ruta: Path, paginas=4):
        doc = lp.fitz.open()
        for i in range(1, paginas + 1):
            page = doc.new_page()
            page.insert_text((72, 30), "Revista de Prueba - Volumen 3", fontsize=9)
            temas = ["sus causas", "el territorio", "las víctimas",
                     "la reparación", "los testimonios", "la memoria"]
            cuerpo = (f"Este es el texto de la página {i}. La investigaciÃ³n "
                      f"continúa con más detalles sobre {temas[i % 6]}.")
            page.insert_textbox(lp.fitz.Rect(72, 100, 520, 400), cuerpo,
                                fontsize=11)
            page.insert_text((290, 815), str(i), fontsize=9)
        doc.save(str(ruta))

    def test_cli_extremo_a_extremo(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "entrada").mkdir()
            self._crear_pdf(tmp / "entrada" / "doc.pdf")
            salida = tmp / "salida"
            codigo = lp.main([str(tmp / "entrada"), "-o", str(salida)])
            self.assertEqual(codigo, 0)
            texto = (salida / "doc.txt").read_text(encoding="utf-8")
            self.assertNotIn("Revista de Prueba", texto)
            self.assertNotIn("Ã", texto)
            self.assertIn("La investigación continúa", texto)
            self.assertFalse(any(l.strip().isdigit() for l in texto.splitlines()))
            datos = json.loads((salida / "doc.paginas.json")
                               .read_text(encoding="utf-8"))
            self.assertEqual(datos["total_paginas"], 4)
            self.assertEqual(len(datos["paginas"]), 4)
            # Sin -f no sobrescribe.
            antes = (salida / "doc.txt").stat().st_mtime_ns
            lp.main([str(tmp / "entrada"), "-o", str(salida)])
            self.assertEqual(antes, (salida / "doc.txt").stat().st_mtime_ns)

    @unittest.skipIf(lp.pypdf is None, "requiere pypdf")
    def test_extractor_pypdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self._crear_pdf(tmp / "doc.pdf")
            res = lp.limpiar_pdf(tmp / "doc.pdf", lp.Opciones(extractor="pypdf"))
            self.assertNotIn("Revista de Prueba", res["_texto"])
            self.assertIn("investigación", res["_texto"])

    def test_pdf_danado(self):
        with tempfile.TemporaryDirectory() as tmp:
            malo = Path(tmp) / "malo.pdf"
            malo.write_bytes(b"esto no es un pdf")
            self.assertEqual(lp.main([str(malo), "-o", str(Path(tmp) / "s")]), 1)


if __name__ == "__main__":
    unittest.main()
