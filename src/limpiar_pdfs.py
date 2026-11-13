#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
limpiar_pdfs.py — Limpieza del texto de PDFs antes de segmentarlo.

Extrae el texto de cada PDF y elimina:
  * encabezados y pies de página repetidos (títulos corridos, nombres de
    capítulo, avisos legales, etc.),
  * números de página («12», «- 12 -», «Página 3 de 40», «xiv»...),
  * caracteres corruptos: mojibake («investigaciÃ³n» → «investigación»),
    ligaduras («ﬁ» → «fi»), «(cid:123)», caracteres de control, invisibles,
    de uso privado y de reemplazo (�), espacios raros, guiones blandos.

Además reconstruye los párrafos (une las líneas cortadas por el ancho de la
página y las palabras partidas con guion) para que la segmentación posterior
trabaje con párrafos completos.

Por cada PDF escribe en la carpeta de salida:
  * <nombre>.txt          texto limpio, un párrafo por bloque separado por
                          una línea en blanco;
  * <nombre>.paginas.json párrafos por página + metadatos de la limpieza
                          (qué encabezados/pies se quitaron, estadísticas,
                          páginas sin texto), pensado para la etapa de
                          segmentación, metadatos y exportación a JSON.

Uso:
    .venv/bin/python src/limpiar_pdfs.py datos/fuentes_pdf/ -f --fecha-consulta 2026-11-06
    .venv/bin/python src/limpiar_pdfs.py carpeta_con_pdfs/ -r -o salida/
    .venv/bin/python src/limpiar_pdfs.py --help

Por defecto escribe en datos/limpios/.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import re
import statistics
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# Raíz del proyecto (chatbot_IA/): las rutas por defecto no dependen de la
# carpeta desde la que se ejecute el script.
RAIZ = Path(__file__).resolve().parent.parent

try:  # PyMuPDF (recomendado: da la posición de cada bloque en la página)
    import pymupdf as fitz
except ImportError:  # pragma: no cover
    try:
        import fitz  # nombre antiguo del paquete
    except ImportError:
        fitz = None

try:  # alternativa más básica, sin posiciones
    import pypdf
except ImportError:  # pragma: no cover
    pypdf = None

try:  # opcional: reparación de mojibake más completa
    import ftfy
except ImportError:  # pragma: no cover
    ftfy = None

__version__ = "1.1.0"
log = logging.getLogger("limpiar_pdfs")


class ErrorPDF(Exception):
    """Error al abrir o leer un PDF."""


# --------------------------------------------------------------------------
# Estructuras
# --------------------------------------------------------------------------
@dataclass
class Bloque:
    lineas: list[str]
    y0: float | None = None  # posición relativa (0 = arriba, 1 = abajo)
    y1: float | None = None

    @property
    def texto(self) -> str:
        return " ".join(l.strip() for l in self.lineas if l.strip())


@dataclass
class Pagina:
    numero: int
    bloques: list[Bloque]
    # True si cada bloque es una sola línea (pypdf): los párrafos se
    # reconstruyen sobre toda la página y no bloque a bloque.
    bloques_son_lineas: bool = False


@dataclass
class Estadisticas:
    contador: Counter = field(default_factory=Counter)

    def sumar(self, clave: str, n: int = 1) -> None:
        if n:
            self.contador[clave] += n


# --------------------------------------------------------------------------
# 1. Extracción
# --------------------------------------------------------------------------
def extraer_con_pymupdf(ruta: Path) -> list[Pagina]:
    try:
        doc = fitz.open(str(ruta))
    except Exception as e:
        raise ErrorPDF(f"no se pudo abrir: {e}") from e
    with doc:
        if doc.needs_pass and not doc.authenticate(""):
            raise ErrorPDF("el PDF está protegido con contraseña")
        paginas = []
        for i, page in enumerate(doc, 1):
            rect = page.rect
            alto = rect.height or 1.0
            bloques = []
            # sort=False conserva el orden del flujo del PDF, que respeta
            # las columnas en la mayoría de documentos maquetados.
            for b in page.get_text("blocks", sort=False):
                x0, y0, x1, y1, texto, _num, tipo = b[:7]
                if tipo != 0:  # 1 = imagen
                    continue
                bloques.append(
                    Bloque(
                        lineas=texto.split("\n"),
                        y0=(y0 - rect.y0) / alto,
                        y1=(y1 - rect.y0) / alto,
                    )
                )
            paginas.append(Pagina(i, bloques))
    return paginas


def extraer_con_pypdf(ruta: Path) -> list[Pagina]:
    try:
        lector = pypdf.PdfReader(str(ruta))
        if lector.is_encrypted:
            try:
                ok = lector.decrypt("")
            except Exception:
                ok = 0
            if not ok:
                raise ErrorPDF("el PDF está protegido con contraseña")
        paginas_pdf = list(lector.pages)
    except ErrorPDF:
        raise
    except Exception as e:
        raise ErrorPDF(f"no se pudo abrir: {e}") from e

    paginas = []
    for i, page in enumerate(paginas_pdf, 1):
        try:
            texto = page.extract_text() or ""
        except Exception as e:
            log.warning("  página %d: no se pudo extraer texto (%s)", i, e)
            texto = ""
        bloques = [Bloque([l]) for l in texto.split("\n")]
        paginas.append(Pagina(i, bloques, bloques_son_lineas=True))
    return paginas


def extraer(ruta: Path, extractor: str) -> tuple[list[Pagina], str]:
    if extractor in ("auto", "pymupdf") and fitz is not None:
        return extraer_con_pymupdf(ruta), f"pymupdf {fitz.VersionBind}"
    if extractor == "pymupdf":
        raise ErrorPDF("PyMuPDF no está instalado (pip install pymupdf)")
    if pypdf is not None:
        return extraer_con_pypdf(ruta), f"pypdf {pypdf.__version__}"
    raise ErrorPDF("no hay extractor disponible: instale pymupdf o pypdf")


# --------------------------------------------------------------------------
# 2. Limpieza de caracteres
# --------------------------------------------------------------------------
LIGADURAS = {
    "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi",
    "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st", "Ĳ": "IJ",
    "ĳ": "ij", "Œ": "OE", "œ": "oe",
}
# Viñetas de fuentes Symbol/Wingdings que llegan como caracteres privados.
VINETAS_PRIVADAS = {"\uf0b7": "•", "\uf0a7": "•", "\uf076": "•", "\uf0d8": "•",
                    "\uf0fc": "•", "\uf0a8": "•", "\uf02d": "-"}
RE_CID = re.compile(r"\(cid:\d+\)")
RE_ESPACIOS_RAROS = re.compile(r"[\t   -   　]")
RE_VARIOS_ESPACIOS = re.compile(r" {2,}")
RE_PUNTOS_GUIA = re.compile(r"(?:\s*[.·_]){4,}\s*")  # «Capítulo 1 ........ 23»

# Mojibake: texto UTF-8 leído como Windows-1252/Latin-1.
#   á → Ã¡   ñ → Ã±   ¿ → Â¿   “ → â€œ   — → â€”
_CONTINUACION = (
    "\u0080-¿ŒœŠšŸŽžƒˆ"
    "˜–—‘-„†-•…‰‹›"
    "€™"
)
RE_MOJIBAKE = re.compile(
    f"[ÂÃ][{_CONTINUACION}]|â[{_CONTINUACION}]{{2}}"
)


def _a_bytes_cp1252(s: str) -> bytes:
    salida = bytearray()
    for ch in s:
        try:
            salida += ch.encode("cp1252")
        except UnicodeEncodeError:
            if ord(ch) < 256:  # bytes que cp1252 no define (0x81, 0x8d...)
                salida.append(ord(ch))
            else:
                raise
    return bytes(salida)


def _reparar_secuencia(m: re.Match) -> str:
    s = m.group(0)
    try:
        return _a_bytes_cp1252(s).decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def reparar_mojibake(texto: str, est: Estadisticas) -> str:
    # Se cuentan antes, porque ftfy también las reemplaza.
    est.sumar("ligaduras", sum(texto.count(lig) for lig in LIGADURAS))
    if ftfy is not None:
        reparado = ftfy.fix_text(
            texto,
            normalization="NFC",
            uncurl_quotes=False,
            fix_latin_ligatures=True,
            fix_character_width=True,
        )
        if reparado != texto:
            est.sumar("textos_reparados_ftfy")
        texto = reparado
    nuevo, n = RE_MOJIBAKE.subn(_reparar_secuencia, texto)
    if nuevo != texto:
        est.sumar("mojibake_reparado", n)
    return nuevo


def limpiar_caracteres(linea: str, est: Estadisticas) -> str:
    """Limpia una línea de texto extraída de un PDF."""
    # El mojibake va primero: «í» corrupta es «Ã» + guion blando, y «Á» es
    # «Ã» + un carácter de control; si se borran antes, ya no se recuperan.
    linea = reparar_mojibake(linea, est)

    # Guion blando al final de línea = palabra partida: se convierte en
    # guion normal para que la reconstrucción de párrafos la una.
    linea = re.sub("\u00ad\\s*$", "-", linea)

    linea, n = RE_CID.subn("", linea)
    est.sumar("cid_eliminados", n)

    for priv, reemplazo in VINETAS_PRIVADAS.items():
        if priv in linea:
            linea = linea.replace(priv, reemplazo)

    for lig, reemplazo in LIGADURAS.items():
        linea = linea.replace(lig, reemplazo)

    linea = unicodedata.normalize("NFC", linea)
    linea = RE_ESPACIOS_RAROS.sub(" ", linea)

    salida = []
    for ch in linea:
        if ch == "�":
            est.sumar("caracter_reemplazo_eliminado")
            continue
        cat = unicodedata.category(ch)
        # Cc control, Cf formato (invisibles, BOM, guion blando),
        # Co uso privado, Cs sustitutos, Cn sin asignar.
        if cat in ("Cc", "Cf", "Co", "Cs", "Cn"):
            est.sumar("caracteres_invisibles_o_control")
            continue
        salida.append(ch)
    linea = "".join(salida)

    linea = RE_PUNTOS_GUIA.sub(" ", linea)
    linea = RE_VARIOS_ESPACIOS.sub(" ", linea).strip()

    # Líneas sin ninguna letra ni número («_____», «• • •», «* * *»).
    if linea and not any(c.isalnum() for c in linea):
        est.sumar("lineas_basura_eliminadas")
        return ""
    return linea


def limpiar_paginas(paginas: list[Pagina], est: Estadisticas) -> None:
    for pag in paginas:
        for b in pag.bloques:
            b.lineas = [limpiar_caracteres(l, est) for l in b.lineas]
        pag.bloques = [b for b in pag.bloques if b.texto]


# --------------------------------------------------------------------------
# 3. Encabezados, pies y números de página
# --------------------------------------------------------------------------
RE_NUM_PAGINA = re.compile(
    r"^[\s\-–—|·•.\[\]()]*"
    r"(?:p[áa]g(?:ina)?s?\.?\s*|p\.\s*)?"
    r"(?:\d{1,4}|[ivxlcdm]{1,7})"
    r"(?:\s*(?:de|/|of)\s*\d{1,4})?"
    r"[\s\-–—|·•.\[\]()]*$",
    re.IGNORECASE,
)


def clave_borde(texto: str) -> str:
    """Forma normalizada para comparar encabezados entre páginas: ignora
    números (que cambian de página a página), mayúsculas y espacios."""
    t = unicodedata.normalize("NFKC", texto).lower()
    t = re.sub(r"\d+", "#", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip(" .-–—|·•")


def detectar_bordes(
    paginas: list[Pagina],
    lineas_borde: int,
    margen: float,
    umbral: float,
    max_repeticiones: int,
) -> tuple[set[tuple[int, int]], list[dict]]:
    """Devuelve los bloques a eliminar (índice de página, índice de bloque)
    y un resumen legible de lo eliminado."""
    n = len(paginas)
    # Ancho de una línea llena ≈ percentil 90 de los largos de línea.
    largos = sorted(len(b.texto) for p in paginas for b in p.bloques)
    linea_llena = 0.8 * largos[int(0.9 * (len(largos) - 1))] if largos else 60
    # (página, bloque) -> (clave de texto, posición en la página)
    candidatos: dict[tuple[int, int], tuple[str, tuple]] = {}

    for pi, pag in enumerate(paginas):
        indices = list(range(len(pag.bloques)))
        if pag.bloques_son_lineas or not indices or pag.bloques[0].y0 is None:
            # Sin posiciones: las primeras y últimas líneas de la página, hasta
            # la primera de ancho completo (ahí empieza el cuerpo); la
            # «posición» es el número de línea contado desde su borde.
            def hasta_cuerpo(orden):
                sel = []
                for bi in orden[:lineas_borde]:
                    if len(pag.bloques[bi].texto) >= linea_llena:
                        break
                    sel.append(bi)
                return sel
            arriba = hasta_cuerpo(indices)
            abajo = list(reversed(hasta_cuerpo(indices[::-1])))
            for orden, bi in enumerate(arriba):
                candidatos[(pi, bi)] = (clave_borde(pag.bloques[bi].texto),
                                        ("arriba", orden))
            for orden, bi in enumerate(reversed(abajo)):
                candidatos.setdefault(
                    (pi, bi),
                    (clave_borde(pag.bloques[bi].texto), ("abajo", orden)))
        else:
            # Con posiciones: los bloques cuyo centro vertical cae en la franja
            # superior o inferior (un párrafo del cuerpo que solo roza la
            # franja no cuenta). La posición se guarda en % del alto.
            for bi in indices:
                b = pag.bloques[bi]
                centro = (b.y0 + b.y1) / 2
                if centro <= margen or centro >= 1 - margen:
                    candidatos[(pi, bi)] = (clave_borde(b.texto),
                                            ("y", round(centro * 100)))

    # Un encabezado o pie real se repite con el mismo texto Y en el mismo
    # sitio de la página. Una nota del cuerpo («(Ver Sentencia C-088…)»)
    # puede repetirse cerca del borde, pero cada vez a una altura distinta.
    paginas_por_sitio: dict[tuple, set[int]] = defaultdict(set)
    for (pi, _bi), (clave, sitio) in candidatos.items():
        if clave and len(clave) <= 200:
            paginas_por_sitio[(clave, sitio)].add(pi)

    def paginas_en_sitio(clave: str, sitio: tuple) -> int:
        if sitio[0] != "y":
            return len(paginas_por_sitio.get((clave, sitio), ()))
        # Tolerancia de ±1 % del alto por pequeñas diferencias de maquetación.
        cerca: set[int] = set()
        for d in (-1, 0, 1):
            cerca |= paginas_por_sitio.get((clave, ("y", sitio[1] + d)), set())
        return len(cerca)

    # Se considera encabezado/pie lo que aparece en el mismo sitio en al menos
    # el `umbral` de las páginas. `max_repeticiones` (si es > 0) rebaja esa
    # exigencia en documentos largos, para títulos corridos por capítulo.
    minimo = max(2, math.ceil(umbral * n))
    if max_repeticiones > 0:
        minimo = max(2, min(minimo, max_repeticiones))

    eliminar: set[tuple[int, int]] = set()
    resumen: dict[str, dict] = {}
    for (pi, bi), (clave, sitio) in sorted(candidatos.items()):
        texto = paginas[pi].bloques[bi].texto
        if n >= 2 and clave and paginas_en_sitio(clave, sitio) >= minimo:
            motivo = "repetido"
        elif RE_NUM_PAGINA.match(texto):
            motivo = "numero_de_pagina"
            clave = "<número de página>"
        else:
            continue
        eliminar.add((pi, bi))
        r = resumen.setdefault(
            clave, {"texto": texto, "motivo": motivo, "paginas": []}
        )
        r["paginas"].append(paginas[pi].numero)
    return eliminar, list(resumen.values())


# --------------------------------------------------------------------------
# 4. Reconstrucción de párrafos
# --------------------------------------------------------------------------
RE_VINETA = re.compile(
    r"^\s*(?:[•●▪■◦○·*\-–—]|\(?\d{1,3}[.)]|\(?[a-zA-Z][.)])\s+"
)
# Encabezados de unidades de documentos normativos y académicos: siempre
# abren párrafo, para que la segmentación posterior los encuentre al inicio.
RE_INICIO_UNIDAD = re.compile(
    r"^(?:ART[ÍI]CULO|PAR[ÁA]GRAFO|CAP[ÍI]TULO|T[ÍI]TULO|LIBRO|SECCI[ÓO]N|ANEXO)\b"
    r"|^(?:Art[íi]culo|Par[áa]grafo|Cap[íi]tulo)\s+(?:\d+|[úu]nico|transitorio)"
    r"[°ºo]?(?:\s*[A-Za-z])?\s*[.:\-–—]"
)
FIN_DE_FRASE = tuple(".!?:;…»”\"’)]")
RE_PALABRA_PARTIDA = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]-$")
# «…por más de dos» + «(2) meses…»: cifra entre paréntesis que repite el
# número escrito en letras, no una viñeta.
RE_CIFRA_EN_FRASE = re.compile(r"^\(\d+\)\s+[a-záéíóúüñ]")


def es_cifra_que_continua(anterior: str, linea: str) -> bool:
    return bool(RE_CIFRA_EN_FRASE.match(linea)) and not anterior.endswith(FIN_DE_FRASE)


def unir(a: str, b: str, conservar_guiones: bool) -> str:
    if (not conservar_guiones and RE_PALABRA_PARTIDA.search(a)
            and b[:1].islower()):
        return a[:-1] + b
    return f"{a} {b}"


def reconstruir_parrafos(
    lineas: list[str], largo_tipico: float, conservar_guiones: bool
) -> list[str]:
    """Une las líneas que pertenecen al mismo párrafo.

    Una línea abre párrafo nuevo si la anterior quedó corta (no llegó al
    margen derecho: fin de párrafo o título) y esta no empieza en
    minúscula, o si empieza con una viñeta, numeración o encabezado de
    unidad (ARTÍCULO, PARÁGRAFO, CAPÍTULO...)."""
    parrafos: list[str] = []
    actual = ""
    anterior = ""
    for linea in lineas:
        linea = linea.strip()
        if not linea:
            if actual:
                parrafos.append(actual)
            actual = anterior = ""
            continue
        if not actual:
            actual = anterior = linea
            continue
        corta = len(anterior) < 0.75 * largo_tipico
        if es_cifra_que_continua(actual, linea):
            actual = unir(actual, linea, conservar_guiones)
        elif (RE_VINETA.match(linea) or RE_INICIO_UNIDAD.match(linea)
                or (corta and not linea[:1].islower())):
            parrafos.append(actual)
            actual = linea
        else:
            actual = unir(actual, linea, conservar_guiones)
        anterior = linea
    if actual:
        parrafos.append(actual)
    return parrafos


def fusionar_cortados(parrafos: list[str], conservar_guiones: bool) -> list[str]:
    """Une párrafos que se cortaron a mitad de frase (bloques partidos)."""
    salida: list[str] = []
    for p in parrafos:
        if salida and ((not salida[-1].endswith(FIN_DE_FRASE) and p[:1].islower())
                       or es_cifra_que_continua(salida[-1], p)):
            salida[-1] = unir(salida[-1], p, conservar_guiones)
        else:
            salida.append(p)
    return salida


# --------------------------------------------------------------------------
# 4b. Reparaciones léxicas con el vocabulario del propio documento
# --------------------------------------------------------------------------
# Restos de la maquetación que sobreviven a la reconstrucción de párrafos:
#   «con-vivencia»            guion de partición que quedó en mitad de línea
#   «COMPORTAMIENTOSMEDIDA»   celdas de tabla pegadas
#   «AAPLICAR», «Numeral1»    espacio perdido
#   «la Iey»                  «I» mayúscula en lugar de «l»
# Solo se corrige cuando el resultado son palabras que el mismo documento usa
# en otros lugares, de modo que un término legítimo con guion
# («minero-ambiental») o una sigla no se tocan.
LETRA = "A-Za-zÁÉÍÓÚÜÑáéíóúüñ"
RE_PALABRA = re.compile(rf"[{LETRA}]+")
RE_GUION_INTERNO = re.compile(rf"\b([{LETRA}]{{2,}})-([{LETRA}]{{2,}})\b")
RE_MAYUSCULAS_LARGA = re.compile(r"\b[A-ZÁÉÍÓÚÜÑ]{6,}\b")
# Solo palabras con inicial mayúscula («Numeral1», «Artículo5»): en minúscula
# («anuales1») el número suele ser una llamada a nota al pie.
RE_PALABRA_NUMERO = re.compile(r"\b([A-ZÁÉÍÓÚÑ][a-záéíóúüñ]{3,})(\d+)\b")
RE_I_POR_L = re.compile(r"(?<=[a-záéíóúñ,] )I([a-záéíóúñ]{2,})\b")
LETRAS_SUELTAS = {"a", "y", "o", "e", "u"}


class Vocabulario:
    """Frecuencias de las palabras del documento, en minúsculas."""

    def __init__(self, parrafos: list[str]):
        self.total = Counter()
        self.minusculas = Counter()  # apariciones escritas en minúscula
        for p in parrafos:
            for w in RE_PALABRA.findall(p):
                self.total[w.lower()] += 1
                if w.islower():
                    self.minusculas[w] += 1

    def conocida(self, palabra: str, minimo: int = 2) -> bool:
        return self.total[palabra.lower()] >= minimo

    def partir(self, token: str) -> str | None:
        """'COMPORTAMIENTOSMEDIDA' → 'COMPORTAMIENTOS MEDIDA' si ambas partes
        son palabras del documento más frecuentes que el bloque pegado."""
        bajo = token.lower()
        if self.minusculas[bajo]:  # se usa como palabra normal: es legítima
            return None
        propia = self.total[bajo]
        mejor = None
        for i in range(1, len(token)):
            a, b = bajo[:i], bajo[i:]
            if len(a) == 1 and a not in LETRAS_SUELTAS:
                continue
            if len(a) == 2 or len(b) < 3:  # «DE»+«…» daría cortes espurios
                continue
            fa, fb = self.total[a], self.total[b]
            if fa > propia and fb > propia and fa >= 3 and fb >= 3:
                # Preferir el corte con las partes más frecuentes.
                puntaje = min(fa, fb)
                if mejor is None or puntaje > mejor[0]:
                    mejor = (puntaje, i)
        if mejor is None:
            return None
        return f"{token[:mejor[1]]} {token[mejor[1]:]}"


def reparar_lexico(parrafos: list[str], est: Estadisticas,
                   unir_guiones: bool = True) -> tuple[list[str], dict]:
    """Aplica las reparaciones a todos los párrafos y devuelve también el
    registro {forma original: forma corregida} para documentarlas."""
    voc = Vocabulario(parrafos)
    cambios: dict[str, str] = {}

    def anotar(antes: str, despues: str, clave: str) -> str:
        if antes not in cambios:
            est.sumar(clave)
        cambios[antes] = despues
        return despues

    def guion(m: re.Match) -> str:
        unida = m.group(1) + m.group(2)
        if m.group(2)[:1].isupper() and not m.group(1).isupper():
            return m.group(0)  # «Decreto-Ley», «Bogotá-Cundinamarca»
        # Solo si la forma unida aparece en el documento («PÚBLICO-PRIVADAS»
        # no se toca). Si quedó pegada a otra palabra, la separa el paso
        # siguiente.
        if voc.conocida(unida):
            return anotar(m.group(0), unida, "guiones_internos_unidos")
        return m.group(0)

    def pegadas(m: re.Match) -> str:
        partida = voc.partir(m.group(0))
        return anotar(m.group(0), partida, "palabras_pegadas_separadas") if partida else m.group(0)

    def numero(m: re.Match) -> str:
        if voc.conocida(m.group(1), minimo=3):
            return anotar(m.group(0), f"{m.group(1)} {m.group(2)}", "palabras_pegadas_separadas")
        return m.group(0)

    def i_por_l(m: re.Match) -> str:
        con_l = "l" + m.group(1)
        # «la Iey»: «ley» es frecuente y «iey» nunca se escribe en minúscula.
        if voc.minusculas[con_l] >= 3 and not voc.minusculas["i" + m.group(1)]:
            return anotar(m.group(0), con_l, "i_mayuscula_por_l")
        return m.group(0)

    salida = []
    for p in parrafos:
        if unir_guiones:
            p = RE_GUION_INTERNO.sub(guion, p)
        p = RE_MAYUSCULAS_LARGA.sub(pegadas, p)
        p = RE_PALABRA_NUMERO.sub(numero, p)
        p = RE_I_POR_L.sub(i_por_l, p)
        salida.append(p)
    return salida, cambios


# --------------------------------------------------------------------------
# 5. Proceso de un documento
# --------------------------------------------------------------------------
@dataclass
class Opciones:
    lineas_borde: int = 3
    margen: float = 0.12
    umbral: float = 0.3
    max_repeticiones: int = 0
    conservar_guiones: bool = False
    extractor: str = "auto"
    reparar_lexico: bool = True
    fecha_consulta: str | None = None


def _ruta_relativa(ruta: Path) -> str:
    """Ruta del PDF relativa al proyecto (no expone la carpeta personal al
    compartir el repositorio); fuera del proyecto, solo el nombre."""
    try:
        return ruta.resolve().relative_to(RAIZ).as_posix()
    except ValueError:
        return ruta.name


def limpiar_pdf(ruta: Path, op: Opciones) -> dict:
    paginas, extractor = extraer(ruta, op.extractor)
    if not paginas:
        raise ErrorPDF("el PDF no tiene páginas")
    est = Estadisticas()

    limpiar_paginas(paginas, est)

    sin_texto = [p.numero for p in paginas
                 if sum(len(b.texto) for b in p.bloques) < 10]
    if len(sin_texto) == len(paginas):
        raise ErrorPDF(
            "no tiene texto extraíble (¿PDF escaneado? necesita OCR antes)"
        )

    eliminar, bordes = detectar_bordes(
        paginas, op.lineas_borde, op.margen, op.umbral, op.max_repeticiones
    )
    est.sumar("bloques_encabezado_pie_eliminados", len(eliminar))
    for pi, pag in enumerate(paginas):
        pag.bloques = [b for bi, b in enumerate(pag.bloques)
                       if (pi, bi) not in eliminar]

    largos = [len(l) for p in paginas for b in p.bloques
              for l in b.lineas if l]
    largo_tipico = statistics.median(largos) if largos else 60

    paginas_salida = []
    for pag in paginas:
        if pag.bloques_son_lineas:
            grupos = [[l for b in pag.bloques for l in b.lineas]]
        else:
            grupos = [b.lineas for b in pag.bloques]
        parrafos: list[str] = []
        for grupo in grupos:
            parrafos.extend(
                reconstruir_parrafos(grupo, largo_tipico, op.conservar_guiones)
            )
        parrafos = fusionar_cortados(parrafos, op.conservar_guiones)
        paginas_salida.append({"numero": pag.numero, "parrafos": parrafos})

    # Reparaciones léxicas con el vocabulario de todo el documento.
    cambios: dict[str, str] = {}
    if op.reparar_lexico:
        todos = [p for pag in paginas_salida for p in pag["parrafos"]]
        reparados, cambios = reparar_lexico(todos, est, not op.conservar_guiones)
        it = iter(reparados)
        for pag in paginas_salida:
            pag["parrafos"] = [next(it) for _ in pag["parrafos"]]

    # Marca los párrafos que siguen en la página siguiente.
    for actual, siguiente in zip(paginas_salida, paginas_salida[1:]):
        actual["ultimo_parrafo_continua"] = bool(
            actual["parrafos"] and siguiente["parrafos"]
            and not actual["parrafos"][-1].endswith(FIN_DE_FRASE)
            and siguiente["parrafos"][0][:1].islower()
        )
    if paginas_salida:
        paginas_salida[-1]["ultimo_parrafo_continua"] = False

    # Texto corrido: une los párrafos partidos entre páginas.
    todos = [p for pag in paginas_salida for p in pag["parrafos"]]
    texto = "\n\n".join(fusionar_cortados(todos, op.conservar_guiones))

    est.sumar("parrafos", len(todos))
    return {
        "archivo_origen": ruta.name,
        "ruta_origen": _ruta_relativa(ruta),
        "fecha_consulta": op.fecha_consulta,
        "fecha_procesamiento": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "extractor": extractor,
        "version_limpiador": __version__,
        "total_paginas": len(paginas),
        "paginas_sin_texto": sin_texto,
        "encabezados_pies_eliminados": bordes,
        "reparaciones_lexicas": dict(sorted(cambios.items())),
        "estadisticas": dict(est.contador),
        "paginas": paginas_salida,
        "_texto": texto,
    }


# --------------------------------------------------------------------------
# 6. Línea de órdenes
# --------------------------------------------------------------------------
def reunir_pdfs(entradas: list[str], recursivo: bool) -> list[tuple[Path, Path]]:
    """Devuelve (pdf, subcarpeta relativa de salida) por cada PDF pedido."""
    encontrados: list[tuple[Path, Path]] = []
    for e in entradas:
        p = Path(e).expanduser()
        if p.is_dir():
            patron = p.rglob("*") if recursivo else p.glob("*")
            pdfs = sorted(f for f in patron
                          if f.is_file() and f.suffix.lower() == ".pdf")
            if not pdfs:
                log.warning("sin PDFs en la carpeta: %s", p)
            encontrados += [(f, f.parent.relative_to(p)) for f in pdfs]
        elif p.is_file():
            if p.suffix.lower() != ".pdf":
                log.warning("se omite (no es .pdf): %s", p)
                continue
            encontrados.append((p, Path(".")))
        else:
            log.error("no existe: %s", p)
    # Sin duplicados, conservando el orden.
    vistos, unicos = set(), []
    for f, rel in encontrados:
        clave = f.resolve()
        if clave not in vistos:
            vistos.add(clave)
            unicos.append((f, rel))
    return unicos


def nombre_libre(carpeta: Path, base: str, usados: set[Path]) -> Path:
    candidato, n = carpeta / base, 2
    while candidato in usados:
        candidato = carpeta / f"{base}_{n}"
        n += 1
    usados.add(candidato)
    return candidato


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Elimina encabezados, pies de página, números de página "
                    "y caracteres corruptos del texto de PDFs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("entradas", nargs="+",
                    help="archivos PDF y/o carpetas que los contienen")
    ap.add_argument("-o", "--salida", default=str(RAIZ / "datos" / "limpios"),
                    help="carpeta donde se guardan los resultados")
    ap.add_argument("-r", "--recursivo", action="store_true",
                    help="buscar PDFs también en subcarpetas")
    ap.add_argument("--formato", choices=["txt", "json", "ambos"],
                    default="ambos", help="qué archivos escribir")
    ap.add_argument("-f", "--sobrescribir", action="store_true",
                    help="reemplazar resultados existentes")
    ap.add_argument("--extractor", choices=["auto", "pymupdf", "pypdf"],
                    default="auto", help="biblioteca para extraer el texto")
    ap.add_argument("--margen", type=float, default=0.12,
                    help="franja superior e inferior (fracción del alto) "
                         "donde se buscan encabezados y pies (solo pymupdf)")
    ap.add_argument("--lineas-borde", type=int, default=3,
                    help="líneas iniciales y finales revisadas por página "
                         "(solo pypdf)")
    ap.add_argument("--umbral", type=float, default=0.3,
                    help="fracción de páginas en que debe repetirse un texto "
                         "del borde para tratarlo como encabezado/pie")
    ap.add_argument("--max-repeticiones", type=int, default=0,
                    help="si es > 0, con este número de repeticiones en el "
                         "mismo sitio basta aunque no se llegue al umbral "
                         "(títulos corridos por capítulo); 0 = desactivado")
    ap.add_argument("--conservar-guiones", action="store_true",
                    help="no unir palabras partidas con guion a fin de línea")
    ap.add_argument("--sin-reparacion-lexica", action="store_true",
                    help="no corregir palabras con guion interno, pegadas "
                         "o con «I» por «l»")
    ap.add_argument("--fecha-consulta", metavar="AAAA-MM-DD",
                    help="fecha en que se descargaron los PDF de la fuente "
                         "oficial; se guarda en el JSON")
    ap.add_argument("-v", "--detalle", action="store_true",
                    help="mostrar qué encabezados y pies se eliminaron")
    ap.add_argument("--version", action="version", version=__version__)
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not 0 < args.margen < 0.5:
        ap.error("--margen debe estar entre 0 y 0.5")
    if not 0 < args.umbral <= 1:
        ap.error("--umbral debe estar entre 0 y 1")
    if args.fecha_consulta:
        try:
            datetime.strptime(args.fecha_consulta, "%Y-%m-%d")
        except ValueError:
            ap.error("--fecha-consulta debe tener el formato AAAA-MM-DD")

    op = Opciones(
        lineas_borde=args.lineas_borde, margen=args.margen,
        umbral=args.umbral, max_repeticiones=args.max_repeticiones,
        conservar_guiones=args.conservar_guiones, extractor=args.extractor,
        reparar_lexico=not args.sin_reparacion_lexica,
        fecha_consulta=args.fecha_consulta,
    )
    pdfs = reunir_pdfs(args.entradas, args.recursivo)
    if not pdfs:
        log.error("no hay PDFs que procesar")
        return 1

    salida = Path(args.salida).expanduser()
    usados: set[Path] = set()
    ok = fallos = omitidos = 0
    for pdf, rel in pdfs:
        carpeta = salida / rel
        base = nombre_libre(carpeta, pdf.stem, usados)
        destinos = []
        if args.formato in ("txt", "ambos"):
            destinos.append(base.with_name(base.name + ".txt"))
        if args.formato in ("json", "ambos"):
            destinos.append(base.with_name(base.name + ".paginas.json"))
        if not args.sobrescribir and any(d.exists() for d in destinos):
            log.info("· %s: ya existe el resultado, se omite (use -f)", pdf.name)
            omitidos += 1
            continue

        log.info("· %s", pdf)
        try:
            res = limpiar_pdf(pdf, op)
        except ErrorPDF as e:
            log.error("  ERROR: %s", e)
            fallos += 1
            continue
        except Exception as e:  # un PDF dañado no detiene el lote
            log.exception("  ERROR inesperado: %s", e)
            fallos += 1
            continue

        carpeta.mkdir(parents=True, exist_ok=True)
        texto = res.pop("_texto")
        for d in destinos:
            if d.suffix == ".txt":
                d.write_text(texto + "\n", encoding="utf-8")
            else:
                d.write_text(json.dumps(res, ensure_ascii=False, indent=2),
                             encoding="utf-8")

        e = res["estadisticas"]
        log.info(
            "  %d páginas, %d párrafos; %d bloques de encabezado/pie quitados; "
            "corregidos: %d mojibake, %d ligaduras, %d invisibles/control, "
            "%d (cid)",
            res["total_paginas"], e.get("parrafos", 0),
            e.get("bloques_encabezado_pie_eliminados", 0),
            e.get("mojibake_reparado", 0), e.get("ligaduras", 0),
            e.get("caracteres_invisibles_o_control", 0),
            e.get("cid_eliminados", 0),
        )
        if args.detalle:
            for b in res["encabezados_pies_eliminados"]:
                log.info("    – [%s] «%s» (%d págs.)", b["motivo"],
                         b["texto"][:70], len(b["paginas"]))
        if res["paginas_sin_texto"]:
            log.warning("  aviso: páginas sin texto (¿escaneadas?): %s",
                        res["paginas_sin_texto"])
        for d in destinos:
            log.info("  → %s", d)
        ok += 1

    log.info("\nListo: %d procesados, %d omitidos, %d con error. Salida: %s",
             ok, omitidos, fallos, salida.resolve())
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
