#!/usr/bin/env python3
"""Segmentación jerárquica del Código Nacional de Seguridad y Convivencia
Ciudadana (Ley 1801 de 2016) a partir del texto limpio que produce
``limpiar_pdfs.py``.

Recorre el documento párrafo a párrafo y guarda el estado de la jerarquía
(Libro → Título → Capítulo) para ubicar cada Artículo. Cada artículo se
divide en fragmentos sin solapamiento:

    art_27              encabezado del artículo (texto anterior al primer
                        numeral o parágrafo)
    art_27_num_3        numeral 3 del artículo, con sus literales e incisos
    art_27_par_1        parágrafo 1 (incluye tablas «Numeral N / medida»)
    art_27_par_1_num_2  numeral 2 dentro del parágrafo 1

Los parágrafos sin número se identifican como ``par_unico`` y los
transitorios como ``par_transitorio``.

Las notas editoriales de Función Pública («(Modificado por el Art. 3 de la
Ley 2318…)», «(Declarado INEXEQUIBLE…)», «(Ver Sentencia…)») salen del campo
``texto`` y quedan en ``notas`` del fragmento al que acompañan. Con ellas se
calcula ``estado_vigencia``.

Cada fragmento lleva además la norma de origen (``norma``, leída del
encabezado «LEY 1801 DE 2016» o del nombre del archivo), el número de artículo
(``articulo``) y la fecha en que se descargó el PDF (``fecha_consulta``, leída
del ``.paginas.json`` que deja limpiar_pdfs.py junto al .txt).

Nota sobre los títulos: en el PDF de Función Pública los encabezados
«TÍTULO I», «TÍTULO II»… no aparecen; solo queda el nombre del título como
una línea en mayúsculas. El analizador los reconoce por su posición (un bloque
en mayúsculas seguido de un CAPÍTULO o de un ARTÍCULO) y los numera dentro de
cada libro.

Uso:
    .venv/bin/python src/segmentar_codigo.py          # datos/limpios/Ley_1801… → datos/corpus.json
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

# Raíz del proyecto (chatbot_IA/): las rutas por defecto no dependen de la
# carpeta desde la que se ejecute el script.
RAIZ = Path(__file__).resolve().parent.parent

__version__ = "1.2.0"

log = logging.getLogger("segmentar_codigo")


class SegmentacionError(Exception):
    """Error que impide segmentar el documento."""


# ---------------------------------------------------------------------------
# Expresiones regulares
# ---------------------------------------------------------------------------
# Todas toleran tildes ausentes, mayúsculas/minúsculas y espacios variables.

ORDINALES = (
    r"PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|S[ÉE]PTIMO|OCTAVO|NOVENO|"
    r"D[ÉE]CIMO|[ÚU]NICO|[IVXLC]+|\d+"
)

RE_LIBRO = re.compile(rf"^LIBRO\s+({ORDINALES})\b\s*[.:\-–—]?\s*(.*)$", re.I)
RE_TITULO = re.compile(rf"^T[ÍI]TULO\s+({ORDINALES})\b\s*[.:\-–—]?\s*(.*)$", re.I)
RE_CAPITULO = re.compile(rf"^CAP[ÍI]TULO\s+({ORDINALES})\b\s*[.:\-–—]?\s*(.*)$", re.I)
# «ARTÍCULO 185A.», «Artículo 12 -», «ARTÍCULO 237 B.». Exige número para no
# confundirse con «ARTÍCULOS PIROTÉCNICOS…» ni con «Artículo 5 de la ley…».
RE_ARTICULO = re.compile(
    r"^ART[ÍI]CULO\s+(\d+)\s*([A-Z])?\s*(?:[.:\-–—]|o\.)\s*(.*)$", re.I | re.S
)
# «PARÁGRAFO 1.», «PARÁGRAFO .», «PARÁGRAFO.», «PARÁGRAFO 2 Contra…»,
# «PARÁGRAFO TRANSITORIO.», «PARÁGRAFO TRANSITORIO 2.», «PARÁGRAFO PRIMERO.»
RE_PARAGRAFO = re.compile(
    rf"^PAR[ÁA]GRAFO(?:\s+(TRANSITORIO))?(?:\s+({ORDINALES}))?(?:\s+(TRANSITORIO))?"
    r"\s*[.:\-–—]?\s*(.*)$",
    re.I | re.S,
)
# «1. Texto», «12) Texto», «3A. Texto». No confunde «1.000 pesos» porque
# exige espacio tras el signo.
RE_NUMERAL = re.compile(r"^(\d{1,3}[A-Z]?)\s*[.)]\s+(\S.*)$", re.S)
# Literales: «a) …», «b. …»
RE_LITERAL = re.compile(r"^[a-zñ]\s*[).]\s+\S", re.S)
# Párrafo que empieza con paréntesis: notas y, a veces, restos como «(2) meses…».
RE_NOTA = re.compile(r"^\(\s*\S")
# Notas editoriales de Función Pública que se sacan del texto al campo «notas»:
# «(Modificado por…)», «(Declarado INEXEQUIBLE…)», «(Ver Sentencia…)»,
# «NOTA: Ordena reemplazar…».
RE_NOTA_EDITORIAL = re.compile(
    r"^(?:\(+\s*(?:NOTA\b|Ver\b|Declarad|Modificad|Adicionad|Corregid|Derogad|"
    r"Reglamentad|Sustituid|Subrogad|Numeral|Par[áa]grafo|Art[íi]culo|Inciso|"
    r"Literal|Expresi|Ep[íi]grafe)|NOTA\s*:)",
    re.I,
)
# Inicio de las firmas: fin del articulado.
RE_FIN_ARTICULADO = re.compile(
    r"^(EL\s+PRESIDENTE\s+(DEL|DE\s+LA)\s+HONORABLE|PUBL[ÍI]QUESE\s+Y\s+C[ÚU]MPLASE)", re.I
)
# Palabras con que termina un nombre partido en dos párrafos.
RE_CONECTOR_FINAL = re.compile(r"\b(DE|DEL|LA|LAS|LOS|EL|Y|E|O|U|EN|A|AL|CON|POR|PARA|SUS?)$", re.I)

ORDINAL_A_NUMERO = {
    "PRIMERO": 1, "SEGUNDO": 2, "TERCERO": 3, "CUARTO": 4, "QUINTO": 5,
    "SEXTO": 6, "SEPTIMO": 7, "OCTAVO": 8, "NOVENO": 9, "DECIMO": 10, "UNICO": 1,
}

ROMANOS = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
           "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX"]


# ---------------------------------------------------------------------------
# Lectura y normalización
# ---------------------------------------------------------------------------

def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def normalizar_espacios(texto: str) -> str:
    """Une un párrafo en una sola línea con espacios simples."""
    texto = re.sub(r"[  -   　\t]", " ", texto)
    texto = re.sub(r"[​‌‍﻿]", "", texto)
    return re.sub(r"\s+", " ", texto).strip()


def leer_parrafos(ruta: Path) -> list[str]:
    """Lee el .txt y lo devuelve como lista de párrafos normalizados.

    Los párrafos se separan por líneas en blanco (formato de limpiar_pdfs.py).
    Si el archivo no tiene líneas en blanco, se toma cada línea como párrafo.
    Las líneas que empiezan con un encabezado de unidad abren párrafo nuevo
    aunque no haya línea en blanco antes.
    """
    if not ruta.is_file():
        raise SegmentacionError(f"No existe el archivo: {ruta}")
    datos = ruta.read_bytes()
    if not datos.strip():
        raise SegmentacionError(f"El archivo está vacío: {ruta}")
    try:
        texto = datos.decode("utf-8-sig")
    except UnicodeDecodeError:
        log.warning("%s no es UTF-8; se lee como latin-1", ruta.name)
        texto = datos.decode("latin-1")

    texto = unicodedata.normalize("NFC", texto).replace("\r\n", "\n").replace("\r", "\n")

    inicio_unidad = re.compile(
        r"^\s*(LIBRO|T[ÍI]TULO|CAP[ÍI]TULO|ART[ÍI]CULO\s+\d|PAR[ÁA]GRAFO)\b", re.I
    )

    if re.search(r"\n[ \t]*\n", texto):
        bloques = re.split(r"\n[ \t]*\n+", texto)
    else:
        # Sin líneas en blanco: una línea continúa la anterior salvo que la
        # anterior cierre frase o la nueva abra unidad, numeral, literal o nota.
        log.info("%s no separa párrafos con líneas en blanco; se reconstruyen por línea", ruta.name)
        abre = re.compile(r"^\s*(\d{1,3}[A-Z]?\s*[.)]\s|[a-zñ]\s*\)\s|\(|Numeral\b)")
        bloques = []
        for linea in texto.split("\n"):
            if not linea.strip():
                continue
            previa = bloques[-1].rstrip() if bloques else ""
            if (bloques and not re.search(r"[.:;)]$", previa)
                    and not inicio_unidad.match(linea) and not abre.match(linea)
                    and not es_mayusculas(linea) and not es_mayusculas(previa)):
                bloques[-1] += " " + linea
            else:
                bloques.append(linea)
    parrafos: list[str] = []
    for bloque in bloques:
        # Dentro de un bloque, separar las líneas que abren una unidad.
        actual: list[str] = []
        for linea in bloque.split("\n"):
            if actual and inicio_unidad.match(linea):
                parrafos.append(normalizar_espacios(" ".join(actual)))
                actual = []
            actual.append(linea)
        if actual:
            parrafos.append(normalizar_espacios(" ".join(actual)))
    return [p for p in parrafos if p]


def es_mayusculas(parrafo: str) -> bool:
    """True si el párrafo es un encabezado en mayúsculas (nombre de libro,
    título o capítulo, o cabecera de tabla)."""
    letras = [c for c in parrafo if c.isalpha()]
    if len(letras) < 3:
        return False
    return sum(c.isupper() for c in letras) / len(letras) >= 0.9


def a_numero(ordinal: str) -> str:
    """'PRIMERO' → '1', 'IV' → '4', '12' → '12', 'ÚNICO' → 'unico'."""
    o = _sin_tildes(ordinal).upper()
    if o == "UNICO":
        return "unico"
    if o in ORDINAL_A_NUMERO:
        return str(ORDINAL_A_NUMERO[o])
    if o.isdigit():
        return str(int(o))
    if re.fullmatch(r"[IVXLC]+", o) and o in ROMANOS:
        return str(ROMANOS.index(o))
    return o.lower()


# ---------------------------------------------------------------------------
# Modelo intermedio
# ---------------------------------------------------------------------------

@dataclass
class EstadoJerarquia:
    """Unidades superiores vigentes mientras se recorre el documento."""
    libro: str | None = None
    titulo: str | None = None
    capitulo: str | None = None
    titulos_en_libro: int = 0

    def nuevo_libro(self, nombre: str) -> None:
        self.libro, self.titulo, self.capitulo = nombre, None, None
        self.titulos_en_libro = 0

    def nuevo_titulo(self, nombre: str, numero: str | None = None) -> None:
        self.titulos_en_libro += 1
        if numero:
            etiqueta = numero
        elif self.titulos_en_libro < len(ROMANOS):
            etiqueta = ROMANOS[self.titulos_en_libro]
        else:
            etiqueta = str(self.titulos_en_libro)
        self.titulo = f"TÍTULO {etiqueta}. {nombre}" if nombre else f"TÍTULO {etiqueta}"
        self.capitulo = None

    def nuevo_capitulo(self, nombre: str) -> None:
        self.capitulo = nombre

    def ubicacion(self) -> dict:
        return {"libro": self.libro, "titulo": self.titulo, "capitulo": self.capitulo}


@dataclass
class Grupo:
    """Inciso introductorio y la lista de numerales que lo sigue."""
    parrafos: list[str] = field(default_factory=list)
    numerales: list[tuple[str, list[str]]] = field(default_factory=list)


def _es_prosa(parrafo: str) -> bool:
    return not (RE_NOTA.match(parrafo) or RE_LITERAL.match(parrafo) or RE_NUMERAL.match(parrafo))


@dataclass
class Bloque:
    """Unidad con texto propio y numerales hijos (artículo o parágrafo).

    Casi siempre tiene un solo grupo. Si la numeración vuelve a empezar en 1
    (p. ej. art. 149: «Son medios inmateriales: 1…5» y luego «Son medios
    materiales: 1…8»), se abre un grupo nuevo cuyo inciso introductorio son
    los párrafos de prosa que precedían al nuevo «1.».
    """
    clave: str
    grupos: list[Grupo] = field(default_factory=lambda: [Grupo()])

    @property
    def parrafos(self) -> list[str]:
        return self.grupos[0].parrafos

    def agregar(self, parrafo: str) -> None:
        """Añade un párrafo de continuación al numeral abierto, o al inciso."""
        grupo = self.grupos[-1]
        if grupo.numerales:
            grupo.numerales[-1][1].append(parrafo)
        else:
            grupo.parrafos.append(parrafo)

    def agregar_numeral(self, numero: str, parrafo: str) -> None:
        grupo = self.grupos[-1]
        if grupo.numerales and re.fullmatch(r"0*1", numero):
            # La lista se reinicia: la prosa final del último numeral es el
            # inciso que introduce la nueva lista.
            previo = grupo.numerales[-1][1]
            k = len(previo)
            while k > 1 and _es_prosa(previo[k - 1]):
                k -= 1
            nuevo = Grupo(parrafos=previo[k:])
            del previo[k:]
            self.grupos.append(nuevo)
            grupo = nuevo
        grupo.numerales.append((numero, [parrafo]))


@dataclass
class Articulo:
    numero: str
    epigrafe: str
    ubicacion: dict
    cuerpo: Bloque
    paragrafos: list[Bloque] = field(default_factory=list)

    @property
    def bloque_actual(self) -> Bloque:
        return self.paragrafos[-1] if self.paragrafos else self.cuerpo


# ---------------------------------------------------------------------------
# Analizador
# ---------------------------------------------------------------------------

def separar_epigrafe(resto: str) -> tuple[str, str]:
    """Separa «Objeto. Las disposiciones…» en ('Objeto', 'Las disposiciones…').

    El epígrafe es la primera frase si es corta. Si el artículo no tiene
    epígrafe (p. ej. «ARTÍCULO 223A. Sin perjuicio de…»), devuelve ('', resto).
    """
    resto = resto.strip()
    # Primer punto seguido de espacio y mayúscula/comilla/fin, sin cortar en
    # abreviaturas como «Art.», «No.», «Núm.».
    for m in re.finditer(r"\.(?=\s+[«\"“(¿¡A-ZÁÉÍÓÚÑ0-9]|\s*$)", resto):
        candidato = resto[: m.start()].strip()
        if re.search(r"\b(Art|No|N[úu]m|Inc|Lit|Par|Dto|Ltda|S\.A)$", candidato, re.I):
            continue
        # Un epígrafe es una frase nominal corta: sin «;» ni «:» y de pocas palabras.
        palabras = candidato.split()
        if 0 < len(palabras) <= 40 and len(candidato) <= 300 and not re.search(r"[;:]", candidato):
            return candidato, resto[m.end():].strip()
        break
    return "", resto


def clave_paragrafo(m: re.Match) -> str:
    transitorio = m.group(1) or m.group(3)
    numero = m.group(2)
    if transitorio:
        return f"par_transitorio_{a_numero(numero)}" if numero else "par_transitorio"
    return f"par_{a_numero(numero)}" if numero else "par_unico"


class AnalizadorCodigo:
    """Recorre los párrafos y arma la lista de artículos con su ubicación."""

    def __init__(self, parrafos: list[str]):
        self.p = parrafos
        self.estado = EstadoJerarquia()
        self.articulos: list[Articulo] = []
        self.actual: Articulo | None = None

    # -- utilidades de lectura anticipada ----------------------------------

    def _bloque_mayusculas(self, i: int) -> int:
        """Índice del primer párrafo que no es encabezado en mayúsculas desde i."""
        j = i
        while j < len(self.p) and self._es_nombre(self.p[j]):
            j += 1
        return j

    def _es_nombre(self, parrafo: str) -> bool:
        return (
            es_mayusculas(parrafo)
            and not RE_LIBRO.match(parrafo)
            and not RE_TITULO.match(parrafo)
            and not RE_CAPITULO.match(parrafo)
            and not RE_ARTICULO.match(parrafo)
            and not RE_PARAGRAFO.match(parrafo)
            and not RE_FIN_ARTICULADO.match(parrafo)
            and not RE_NOTA.match(parrafo)
        )

    def _abre_unidad(self, i: int) -> bool:
        return i < len(self.p) and bool(
            RE_LIBRO.match(self.p[i]) or RE_TITULO.match(self.p[i])
            or RE_CAPITULO.match(self.p[i]) or RE_ARTICULO.match(self.p[i])
        )

    @staticmethod
    def _unir_nombre(partes: list[str]) -> str:
        return normalizar_espacios(" ".join(partes)).rstrip(" .")

    # -- recorrido principal -----------------------------------------------

    def analizar(self) -> list[Articulo]:
        i = 0
        n = len(self.p)
        while i < n:
            parrafo = self.p[i]

            if RE_FIN_ARTICULADO.match(parrafo) and self.articulos:
                log.debug("Fin del articulado en el párrafo %d", i)
                break

            if m := RE_LIBRO.match(parrafo):
                i = self._leer_libro(i, m)
                continue
            if m := RE_TITULO.match(parrafo):
                i = self._leer_titulo_explicito(i, m)
                continue
            if m := RE_CAPITULO.match(parrafo):
                i = self._leer_capitulo(i, m)
                continue
            if m := RE_ARTICULO.match(parrafo):
                self._abrir_articulo(m)
                i += 1
                continue

            # Bloque en mayúsculas seguido de capítulo o artículo: título sin rótulo.
            if self._es_nombre(parrafo):
                j = self._bloque_mayusculas(i)
                if self._abre_unidad(j) and not RE_LIBRO.match(self.p[j]):
                    self.estado.nuevo_titulo(self._unir_nombre(self.p[i:j]))
                    i = j
                    continue

            if self.actual is not None:
                self._agregar_contenido(parrafo)
            # Lo anterior al primer artículo (preámbulo) se descarta.
            i += 1

        self._cerrar_articulo()
        if not self.articulos:
            raise SegmentacionError("No se encontró ningún «ARTÍCULO N.» en el texto.")
        return self.articulos

    def _leer_libro(self, i: int, m: re.Match) -> int:
        self._cerrar_articulo()
        etiqueta = f"LIBRO {m.group(1).upper()}"
        partes = [m.group(2)] if m.group(2) else []
        i += 1
        # Nombre del libro: el primer bloque en mayúsculas, más los párrafos
        # que continúan un nombre partido («…ALTERNATIVOS DE» + «SOLUCIÓN…»).
        if not partes and i < len(self.p) and self._es_nombre(self.p[i]):
            partes.append(self.p[i])
            i += 1
        while partes and RE_CONECTOR_FINAL.search(partes[-1]) and i < len(self.p) and self._es_nombre(self.p[i]):
            partes.append(self.p[i])
            i += 1
        nombre = self._unir_nombre(partes)
        self.estado.nuevo_libro(f"{etiqueta}. {nombre}" if nombre else etiqueta)
        # Lo que quede en mayúsculas antes del capítulo o artículo es el título.
        j = self._bloque_mayusculas(i)
        if j > i and self._abre_unidad(j):
            self.estado.nuevo_titulo(self._unir_nombre(self.p[i:j]))
            i = j
        return i

    def _leer_titulo_explicito(self, i: int, m: re.Match) -> int:
        self._cerrar_articulo()
        partes = [m.group(2)] if m.group(2) else []
        j = self._bloque_mayusculas(i + 1)
        partes += self.p[i + 1:j]
        self.estado.nuevo_titulo(self._unir_nombre(partes), numero=m.group(1).upper())
        return j

    def _leer_capitulo(self, i: int, m: re.Match) -> int:
        self._cerrar_articulo()
        etiqueta = f"CAPÍTULO {m.group(1).upper()}"
        partes = [m.group(2)] if m.group(2) else []
        j = self._bloque_mayusculas(i + 1)
        partes += self.p[i + 1:j]
        nombre = self._unir_nombre(partes)
        self.estado.nuevo_capitulo(f"{etiqueta}. {nombre}" if nombre else etiqueta)
        return j

    def _abrir_articulo(self, m: re.Match) -> None:
        self._cerrar_articulo()
        numero = m.group(1) + (m.group(2) or "").upper()
        epigrafe, resto = separar_epigrafe(m.group(3))
        cuerpo = Bloque(clave=f"art_{numero}")
        self.actual = Articulo(numero, epigrafe, self.estado.ubicacion(), cuerpo)
        if resto:
            self._agregar_contenido(resto, primero=True)

    def _agregar_contenido(self, parrafo: str, primero: bool = False) -> None:
        art = self.actual
        assert art is not None

        if m := RE_PARAGRAFO.match(parrafo):
            par = Bloque(clave=f"{art.cuerpo.clave}_{clave_paragrafo(m)}")
            par.parrafos.append(parrafo)
            art.paragrafos.append(par)
            return

        bloque = art.bloque_actual
        if not primero and (m := RE_NUMERAL.match(parrafo)):
            bloque.agregar_numeral(m.group(1).upper(), parrafo)
            return
        # Literales, notas editoriales e incisos siguen al numeral abierto.
        bloque.agregar(parrafo)

    def _cerrar_articulo(self) -> None:
        if self.actual is not None:
            self.articulos.append(self.actual)
            self.actual = None


# ---------------------------------------------------------------------------
# Construcción del corpus
# ---------------------------------------------------------------------------

RE_INEXEQUIBLE = re.compile(r"\bINEXEQUIBLES?\b|\bEXEQUIBLE\b[^)]*\bcon excepci[óo]n\b", re.I)
RE_DEROGADO = re.compile(r"\bderogad[oa]s?\b", re.I)
RE_PARCIAL = re.compile(r"expresi[óo]n|expresiones|subrayad|con excepci[óo]n|\binciso\b", re.I)
# Nota genérica («(Declarado INEXEQUIBLE mediante…)», «(Derogado por…)»), sin
# nombrar un parágrafo o numeral: al final de un artículo, alcanza a todo él.
RE_NOTA_GENERICA = re.compile(r"^\(\s*(Declarad[oa]s?|Derogad[oa]s?|Art[íi]culo)\b", re.I)


def _vigencia_nota(nota: str) -> str | None:
    """'derogado', 'inexequible', 'inexequible_parcial' o None para una nota."""
    if not RE_NOTA.match(nota):
        return None
    for regex, estado in ((RE_DEROGADO, "derogado"), (RE_INEXEQUIBLE, "inexequible")):
        if regex.search(nota):
            return "inexequible_parcial" if RE_PARCIAL.search(nota) else estado
    return None


def estado_vigencia(parrafos: list[str]) -> str:
    """Deduce la vigencia de un fragmento a partir de sus notas.

    Por defecto 'vigente'. 'inexequible' o 'derogado' si una nota declara así
    todo el fragmento; 'inexequible_parcial' si solo alcanza expresiones o
    incisos.
    """
    parcial = False
    for p in parrafos:
        estado = _vigencia_nota(p)
        if estado in ("derogado", "inexequible"):
            return estado
        parcial = parcial or estado == "inexequible_parcial"
    return "inexequible_parcial" if parcial else "vigente"


def _ultimos_parrafos(art: Articulo) -> list[str]:
    bloque = art.bloque_actual
    grupo = bloque.grupos[-1]
    return grupo.numerales[-1][1] if grupo.numerales else grupo.parrafos


def vigencia_articulo(art: Articulo) -> str | None:
    """Vigencia de todo el artículo si sus notas finales son genéricas.

    Función Pública pone «(Declarado INEXEQUIBLE mediante Sentencia…)» al final
    del artículo cuando la decisión lo alcanza entero (arts. 47 a 75), y
    «(Parágrafo 3, declarado INEXEQUIBLE…)» cuando solo alcanza una parte.
    """
    for p in reversed(_ultimos_parrafos(art)):
        if not RE_NOTA.match(p):
            break
        if RE_NOTA_GENERICA.match(p):
            estado = _vigencia_nota(p)
            if estado in ("derogado", "inexequible"):
                return estado
    return None


def _tema(epigrafe: str, ubicacion: dict) -> str:
    """Tema del fragmento: el epígrafe; si no hay, el nombre del capítulo o título."""
    if epigrafe:
        return epigrafe
    for nivel in ("capitulo", "titulo", "libro"):
        valor = ubicacion.get(nivel)
        if valor:
            # Quitar el rótulo «CAPÍTULO II. » y pasar a tipo oración.
            nombre = re.sub(r"^(CAP[ÍI]TULO|T[ÍI]TULO|LIBRO)\s+\S+\.?\s*", "", valor)
            if nombre:
                return nombre[:1].upper() + nombre[1:].lower()
    return ""


def es_nota_editorial(parrafo: str) -> bool:
    return bool(RE_NOTA_EDITORIAL.match(parrafo))


def _texto(parrafos: list[str]) -> str:
    return "\n".join(p for p in parrafos if p).strip()


def _ids_unicos(base: str, usados: set[str]) -> str:
    ident, k = base, 2
    while ident in usados:
        ident = f"{base}_{k}"
        k += 1
    if ident != base:
        log.warning("Identificador repetido %s; se usa %s", base, ident)
    usados.add(ident)
    return ident


RE_NORMA = re.compile(r"^(LEY|DECRETO(?:\s+LEY)?|ACTO\s+LEGISLATIVO|RESOLUCI[ÓO]N)\s+(\d+)\s+DE\s+(\d{4})$", re.I)


def _formatear_norma(tipo: str, numero: str, anio: str) -> str:
    return f"{normalizar_espacios(tipo).capitalize()} {numero} de {anio}"


def detectar_norma(parrafos: list[str], ruta: Path) -> str | None:
    """Nombre de la norma («Ley 1801 de 2016»): primer párrafo que lo sea,
    o el nombre del archivo («Ley_1801_de_2016.txt»)."""
    for p in parrafos[:20]:
        m = RE_NORMA.match(p)
        if m:
            return _formatear_norma(*m.groups())
    m = RE_NORMA.match(ruta.stem.replace("_", " "))
    return _formatear_norma(*m.groups()) if m else None


def leer_fecha_consulta(ruta: Path) -> str | None:
    """Lee ``fecha_consulta`` del .paginas.json hermano del .txt, si existe."""
    meta = ruta.with_name(ruta.stem + ".paginas.json")
    if not meta.is_file():
        return None
    try:
        return json.loads(meta.read_text(encoding="utf-8")).get("fecha_consulta")
    except (OSError, ValueError) as e:
        log.warning("No se pudo leer %s: %s", meta.name, e)
        return None


def construir_corpus(articulos: list[Articulo], norma: str | None = None,
                     fecha_consulta: str | None = None) -> list[dict]:
    """Convierte los artículos en la lista plana de fragmentos."""
    corpus: list[dict] = []
    usados: set[str] = set()

    def emitir(ident: str, art: Articulo, parrafos: list[str], vigencia_art: str | None) -> None:
        notas = [p for p in parrafos if es_nota_editorial(p)]
        texto = _texto([p for p in parrafos if not es_nota_editorial(p)])
        if not texto:
            # Un fragmento que solo tiene notas: van al fragmento anterior.
            if notas and corpus:
                corpus[-1]["notas"].extend(notas)
            return
        corpus.append({
            "identificador": _ids_unicos(ident, usados),
            "norma": norma,
            "articulo": art.numero,
            "ubicacion_jerarquica": dict(art.ubicacion),
            "epigrafe": art.epigrafe,
            "texto": texto,
            "estado_vigencia": vigencia_art or estado_vigencia(parrafos),
            "tema": _tema(art.epigrafe, art.ubicacion),
            "notas": notas,
            "fecha_consulta": fecha_consulta,
        })

    def emitir_bloque(bloque: Bloque, art: Articulo, vigencia_art: str | None) -> None:
        for k, grupo in enumerate(bloque.grupos, start=1):
            base = bloque.clave if k == 1 else f"{bloque.clave}_inc_{k}"
            emitir(base, art, grupo.parrafos, vigencia_art)
            for numero, parrafos in grupo.numerales:
                emitir(f"{base}_num_{numero}", art, parrafos, vigencia_art)

    for art in articulos:
        cuerpo = art.cuerpo
        # Un artículo cuyo texto propio está vacío (solo epígrafe + numerales)
        # se emite con el epígrafe para que «art_N» siempre exista.
        if not _texto([p for p in cuerpo.parrafos if not es_nota_editorial(p)]):
            cuerpo.grupos[0].parrafos.insert(0, art.epigrafe or f"Artículo {art.numero}")
        vigencia_art = vigencia_articulo(art)
        emitir_bloque(cuerpo, art, vigencia_art)
        for par in art.paragrafos:
            emitir_bloque(par, art, vigencia_art)
    return corpus


def _orden_articulo(numero: str) -> tuple[int, str]:
    m = re.match(r"(\d+)(.*)", numero)
    return (int(m.group(1)), m.group(2)) if m else (0, numero)


def revisar_continuidad(articulos: list[Articulo]) -> list[str]:
    """Devuelve avisos sobre artículos faltantes, repetidos o fuera de orden."""
    avisos = []
    numeros = [_orden_articulo(a.numero) for a in articulos]
    vistos: set[tuple[int, str]] = set()
    for previo, actual in zip(numeros, numeros[1:]):
        if actual <= previo:
            avisos.append(f"Artículo {actual[0]}{actual[1]} fuera de orden (después de {previo[0]}{previo[1]})")
        elif actual[0] > previo[0] + 1:
            faltan = ", ".join(str(k) for k in range(previo[0] + 1, actual[0]))
            avisos.append(f"Faltan artículos entre {previo[0]} y {actual[0]}: {faltan}")
    for num in numeros:
        if num in vistos:
            avisos.append(f"Artículo {num[0]}{num[1]} repetido")
        vistos.add(num)
    return avisos


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def segmentar(ruta_entrada: str | Path, ruta_salida: str | Path | None = RAIZ / "datos" / "corpus.json",
              norma: str | None = None, fecha_consulta: str | None = None) -> list[dict]:
    """Segmenta el .txt limpio y, si ``ruta_salida`` no es None, escribe el JSON.

    ``norma`` y ``fecha_consulta`` se detectan solos (encabezado/nombre del
    archivo y .paginas.json); pasarlos explícitamente los reemplaza.

    Devuelve la lista de fragmentos. Lanza ``SegmentacionError`` si el archivo
    no existe, está vacío o no contiene artículos.
    """
    ruta_entrada = Path(ruta_entrada).expanduser()
    parrafos = leer_parrafos(ruta_entrada)
    log.info("%s: %d párrafos leídos", ruta_entrada.name, len(parrafos))

    articulos = AnalizadorCodigo(parrafos).analizar()
    for aviso in revisar_continuidad(articulos):
        log.warning(aviso)

    norma = norma or detectar_norma(parrafos, ruta_entrada)
    fecha_consulta = fecha_consulta or leer_fecha_consulta(ruta_entrada)
    if norma is None:
        log.warning("No se reconoció el nombre de la norma; use --norma")
    if fecha_consulta is None:
        log.warning("Sin fecha de consulta (no hay .paginas.json); use --fecha-consulta")
    corpus = construir_corpus(articulos, norma, fecha_consulta)
    log.info("%d artículos → %d fragmentos", len(articulos), len(corpus))

    if ruta_salida is not None:
        ruta_salida = Path(ruta_salida).expanduser()
        ruta_salida.parent.mkdir(parents=True, exist_ok=True)
        try:
            ruta_salida.write_text(json.dumps(corpus, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as e:
            raise SegmentacionError(f"No se pudo escribir {ruta_salida}: {e}") from e
        log.info("Corpus guardado en %s", ruta_salida)
    return corpus


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Segmenta jerárquicamente el Código Nacional de Seguridad y Convivencia (Ley 1801 de 2016).",
    )
    parser.add_argument("entrada", nargs="?", default=str(RAIZ / "datos" / "limpios" / "Ley_1801_de_2016.txt"), help="archivo .txt limpio (por defecto: datos/limpios/Ley_1801_de_2016.txt)")
    parser.add_argument("-o", "--salida", default=str(RAIZ / "datos" / "corpus.json"), help="archivo JSON de salida (por defecto: datos/corpus.json)")
    parser.add_argument("--norma", help="nombre de la norma (por defecto se detecta, p. ej. «Ley 1801 de 2016»)")
    parser.add_argument("--fecha-consulta", help="AAAA-MM-DD (por defecto se lee del .paginas.json)")
    parser.add_argument("-v", "--detalle", action="store_true", help="mostrar mensajes de depuración")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.detalle else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    if args.fecha_consulta:
        from datetime import date
        try:
            date.fromisoformat(args.fecha_consulta)
        except ValueError:
            parser.error("--fecha-consulta debe tener formato AAAA-MM-DD")
    try:
        segmentar(args.entrada, args.salida, args.norma, args.fecha_consulta)
    except SegmentacionError as e:
        log.error("%s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
