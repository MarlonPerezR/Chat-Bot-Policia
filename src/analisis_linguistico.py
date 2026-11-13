#!/usr/bin/env python3
"""Fase 2: análisis lingüístico del corpus de la Ley 1801 de 2016 con spaCy.

Lee ``datos/corpus.json`` (salida de segmentar_codigo.py) y produce en
``resultados/analisis/``:

    corpus_procesado.jsonl  un fragmento por línea: texto normalizado, tokens,
                            lemas, etiquetas POS, lemas de contenido (para BM25)
                            y entidades (AUTORIDAD, LUGAR, MONTO, PLAZO, …)
    estadisticas.json       artículos, tokens, tipos, relación tipo/token,
                            longitudes, POS y entidades
    frecuencias_lemas.csv   lemas de contenido más frecuentes
    ngramas.csv             bigramas y trigramas más frecuentes
    colocaciones.csv        bigramas con PMI, t-score y log-likelihood (G²)
    kwic.txt / kwic.json    concordancias de «multa», «comparendo», …
    glosario.json           términos jurídicos con frecuencia, artículos y
                            definición encontrada en el propio Código
    sinonimos.json          términos del Código ↔ formas coloquiales, más un
                            índice inverso para expandir consultas
    informe_linguistico.md  informe (entregable 2) armado con todo lo anterior

Las listas curadas (términos del glosario, sinónimos, autoridades, lugares y
términos KWIC) están en ``recursos/terminos.json``.

Uso:
    .venv/bin/python src/analisis_linguistico.py      # rutas por defecto
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import re
import statistics
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

# Raíz del proyecto (chatbot_IA/): las rutas por defecto no dependen de la
# carpeta desde la que se ejecute el script.
RAIZ = Path(__file__).resolve().parent.parent

__version__ = "1.0.0"

log = logging.getLogger("analisis_linguistico")

MODELO_POR_DEFECTO = "es_core_news_md"
POS_CONTENIDO = {"NOUN", "VERB", "ADJ", "PROPN", "ADV"}


class AnalisisError(Exception):
    """Error que impide hacer el análisis."""


# ---------------------------------------------------------------------------
# Normalización
# ---------------------------------------------------------------------------

_COMILLAS = str.maketrans({"“": '"', "”": '"', "«": '"', "»": '"', "„": '"',
                           "‘": "'", "’": "'", "´": "'", "–": "-", "—": "-",
                           " ": " "})


def normalizar(texto: str) -> str:
    """Normaliza Unicode (NFC), comillas, guiones y espacios. Conserva
    mayúsculas y tildes, que necesitan el etiquetador y el NER."""
    texto = unicodedata.normalize("NFC", texto).translate(_COMILLAS)
    return re.sub(r"\s+", " ", texto).strip()


def sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower())
                   if unicodedata.category(c) != "Mn")


# ---------------------------------------------------------------------------
# Entidades propias del dominio
# ---------------------------------------------------------------------------

_NUM_PALABRAS = (
    r"un|uno|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|"
    r"trece|catorce|quince|diecis[eé]is|diecisiete|dieciocho|diecinueve|veinte|"
    r"veinti\w+|treinta|cuarenta|cincuenta|sesenta|setenta|ochenta|noventa|"
    r"cien|ciento|doscientos|trescientos|cuatrocientos|quinientos|mil"
)
# «cuarenta y ocho (48)», «5», «un»: la «y» solo puede ir en medio.
_CANTIDAD = (rf"(?:\b(?:{_NUM_PALABRAS})\s+(?:(?:{_NUM_PALABRAS}|y)\s+){{0,5}}\(\d[\d.,]*\)"
             rf"|\b\d[\d.,]*\b|\b(?:{_NUM_PALABRAS})\b)")

RE_PLAZO = re.compile(
    rf"{_CANTIDAD}\s+(?:d[ií]as?|horas?|meses|mes|a[ñn]os?|semanas?|minutos?)"
    r"(?:\s+(?:h[aá]biles|calendario|siguientes|continuos))?", re.I)
RE_MONTO = re.compile(
    rf"{_CANTIDAD}\s+salarios?\s+m[ií]nimos?(?:\s+(?:legales|diarios|mensuales|vigentes|o|\(?smdlv\)?|\(?smmlv\)?)){{0,7}}"
    r"|\bmultas?\s+generales?\s+(?:de\s+)?tipos?\s+\d(?:\s*(?:,|y|o|a)\s*\d)*"
    r"|\bmultas?\s+especial(?:es)?"
    r"|\$\s?\d[\d.,]*|\b\d[\d.,]*\s+UVT\b", re.I)


def construir_nlp(modelo: str, autoridades: list[str], lugares: list[str]):
    """Carga spaCy y añade un componente que marca AUTORIDAD, LUGAR, MONTO y
    PLAZO. De las entidades del modelo se conservan LOC, ORG y PER (como
    LUGAR, ORGANIZACION y PERSONA); MISC se descarta porque en el texto
    jurídico casi siempre es ruido (frases en mayúscula inicial)."""
    try:
        import spacy
        from spacy.matcher import PhraseMatcher
        from spacy.tokens import Span
        from spacy.util import filter_spans
    except ImportError as e:  # pragma: no cover
        raise AnalisisError("Falta spaCy: .venv/bin/pip install spacy") from e
    try:
        nlp = spacy.load(modelo)
    except OSError as e:
        raise AnalisisError(f"Falta el modelo {modelo}: .venv/bin/python -m spacy download {modelo}") from e

    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    matcher.add("AUTORIDAD", [nlp.make_doc(t) for t in autoridades])
    matcher.add("LUGAR", [nlp.make_doc(t) for t in lugares])
    renombre = {"LOC": "LUGAR", "ORG": "ORGANIZACION", "PER": "PERSONA"}

    def marcar(doc):
        propias = [Span(doc, s, e, label=doc.vocab.strings[k]) for k, s, e in matcher(doc)]
        for etiqueta, regex in (("MONTO", RE_MONTO), ("PLAZO", RE_PLAZO)):
            for m in regex.finditer(doc.text):
                sp = doc.char_span(m.start(), m.end(), label=etiqueta, alignment_mode="expand")
                if sp is not None:
                    propias.append(sp)
        propias = filter_spans(propias)
        ocupados = {i for sp in propias for i in range(sp.start, sp.end)}
        modelo_ents = []
        for ent in doc.ents:
            if ent.label_ not in renombre or any(i in ocupados for i in range(ent.start, ent.end)):
                continue
            if not ent.text[:1].isupper() or not re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{3}", ent.text):
                continue
            if ent.text.isupper() and len(ent.text) > 25:  # cabeceras en mayúsculas
                continue
            # En las tablas «Destrucción de bien», «Suspensión…» empiezan con
            # mayúscula y el modelo los toma por nombres. Se exige un nombre
            # propio de verdad: siglas, o dos o más palabras con alguna PROPN
            # y sin verbos.
            if ent[0].lower_ in ("numeral", "parágrafo", "artículo", "literal"):
                continue
            # Sigla: palabra en mayúsculas que no es una palabra común
            # («APLICAR» en las cabeceras de tabla sí lo es).
            sigla = (len(ent) == 1 and ent.text.isupper() and 3 <= len(ent.text) <= 8
                     and ent.vocab[ent.text.lower()].is_oov)
            propio = (len(ent) >= 2 and any(t.pos_ == "PROPN" for t in ent)
                      and not any(t.pos_ in ("VERB", "AUX") for t in ent)
                      and sum(t.text[:1].isupper() for t in ent if t.is_alpha and not t.is_stop) >= 2)
            if not (sigla or propio):
                continue
            modelo_ents.append(Span(doc, ent.start, ent.end, label=renombre[ent.label_]))
        doc.ents = sorted(propias + modelo_ents, key=lambda s: s.start)
        return doc

    nlp._marcar_entidades = marcar  # se aplica en procesar(), después del pipeline
    return nlp


# ---------------------------------------------------------------------------
# Procesamiento por fragmento
# ---------------------------------------------------------------------------

def es_palabra(tok) -> bool:
    return not (tok.is_punct or tok.is_space) and bool(re.search(r"\w", tok.text))


def procesar(corpus: list[dict], nlp) -> tuple[list[dict], list]:
    """Devuelve los registros procesados y los Doc de spaCy (en el mismo orden)."""
    textos = [normalizar(f["texto"]) for f in corpus]
    docs = []
    for doc in nlp.pipe(textos, batch_size=64):
        docs.append(nlp._marcar_entidades(doc))
    registros = []
    for f, doc in zip(corpus, docs):
        palabras = [t for t in doc if es_palabra(t)]
        registros.append({
            "identificador": f["identificador"],
            "articulo": f.get("articulo"),
            "texto_normalizado": doc.text.lower(),
            "tokens": [t.text for t in doc if not t.is_space],
            "lemas": [t.lemma_.lower() for t in doc if not t.is_space],
            "pos": [t.pos_ for t in doc if not t.is_space],
            "lemas_contenido": " ".join(t.lemma_.lower() for t in palabras
                                        if t.pos_ in POS_CONTENIDO and not t.is_stop),
            "entidades": [{"texto": e.text, "etiqueta": e.label_,
                           "inicio": e.start_char, "fin": e.end_char} for e in doc.ents],
            "n_tokens": len(palabras),
            "n_oraciones": sum(1 for _ in doc.sents),
        })
    return registros, docs


# ---------------------------------------------------------------------------
# Estadísticas
# ---------------------------------------------------------------------------

def sttr(formas: list[str], ventana: int = 1000) -> float | None:
    """Relación tipo/token estandarizada: media del TTR en ventanas de
    ``ventana`` tokens (la TTR simple baja con el tamaño del texto)."""
    if len(formas) < ventana:
        return None
    valores = [len(set(formas[i:i + ventana])) / ventana
               for i in range(0, len(formas) - ventana + 1, ventana)]
    return round(statistics.mean(valores), 4)


def _resumen(valores: list[int]) -> dict:
    v = sorted(valores)
    return {"media": round(statistics.mean(v), 2), "mediana": statistics.median(v),
            "desviacion": round(statistics.pstdev(v), 2), "minimo": v[0], "maximo": v[-1],
            "p90": v[min(len(v) - 1, int(0.9 * len(v)))]}


def estadisticas(corpus: list[dict], registros: list[dict], docs: list) -> dict:
    palabras = [t for d in docs for t in d if es_palabra(t)]
    formas = [t.text.lower() for t in palabras]
    lemas = [t.lemma_.lower() for t in palabras]
    frec = Counter(formas)
    longitudes = [r["n_tokens"] for r in registros]
    por_articulo: dict[str, int] = defaultdict(int)
    for f, r in zip(corpus, registros):
        por_articulo[f.get("articulo") or f["identificador"]] += r["n_tokens"]
    mas_largo = max(zip(longitudes, (r["identificador"] for r in registros)))
    art_mas_largo = max(por_articulo.items(), key=lambda kv: kv[1])

    por_libro: dict[str, dict] = defaultdict(lambda: {"articulos": set(), "fragmentos": 0, "tokens": 0})
    for f, r in zip(corpus, registros):
        libro = (f["ubicacion_jerarquica"].get("libro") or "—").split(".")[0].title()
        por_libro[libro]["articulos"].add(f.get("articulo"))
        por_libro[libro]["fragmentos"] += 1
        por_libro[libro]["tokens"] += r["n_tokens"]

    pos = Counter(t.pos_ for t in palabras)
    entidades = Counter(e["etiqueta"] for r in registros for e in r["entidades"])
    ejemplos_ent: dict[str, Counter] = defaultdict(Counter)
    for r in registros:
        for e in r["entidades"]:
            ejemplos_ent[e["etiqueta"]][e["texto"].lower()] += 1

    return {
        "n_articulos": len(por_articulo),
        "n_fragmentos": len(registros),
        "n_oraciones": sum(r["n_oraciones"] for r in registros),
        "n_tokens": len(formas),
        "n_tipos": len(frec),
        "n_lemas": len(set(lemas)),
        "relacion_tipo_token": round(len(frec) / len(formas), 4) if formas else 0,
        "relacion_lema_token": round(len(set(lemas)) / len(formas), 4) if formas else 0,
        "sttr_1000": sttr(formas),
        "hapax": sum(1 for c in frec.values() if c == 1),
        "longitud_fragmento_tokens": {**_resumen(longitudes),
                                      "mas_largo": {"identificador": mas_largo[1], "tokens": mas_largo[0]}},
        "longitud_articulo_tokens": {**_resumen(list(por_articulo.values())),
                                     "mas_largo": {"articulo": art_mas_largo[0], "tokens": art_mas_largo[1]}},
        "por_libro": {k: {"articulos": len(v["articulos"]), "fragmentos": v["fragmentos"], "tokens": v["tokens"]}
                      for k, v in por_libro.items()},
        "vigencia": dict(Counter(f["estado_vigencia"] for f in corpus)),
        "pos": {k: {"n": n, "pct": round(100 * n / len(palabras), 2)} for k, n in pos.most_common()},
        "entidades": {k: {"n": n, "ejemplos": [t for t, _ in ejemplos_ent[k].most_common(8)]}
                      for k, n in entidades.most_common()},
    }


# ---------------------------------------------------------------------------
# Frecuencias, n-gramas y colocaciones
# ---------------------------------------------------------------------------

def frecuencias_lemas(docs: list, n: int = 100) -> list[dict]:
    frec, df = Counter(), Counter()
    total = 0
    for d in docs:
        vistos = set()
        for t in d:
            if not es_palabra(t):
                continue
            total += 1
            if t.pos_ in POS_CONTENIDO and not t.is_stop and t.is_alpha:
                lema = t.lemma_.lower()
                frec[lema] += 1
                vistos.add(lema)
        df.update(vistos)
    return [{"lema": l, "frecuencia": c, "por_10000": round(10000 * c / total, 2),
             "fragmentos": df[l]} for l, c in frec.most_common(n)]


def tramos(doc) -> list[list]:
    """Secuencias de palabras sin puntuación de por medio (los n-gramas no
    cruzan comas, puntos ni paréntesis)."""
    salida, actual = [], []
    for t in doc:
        if es_palabra(t):
            actual.append(t)
        elif actual:
            salida.append(actual)
            actual = []
    if actual:
        salida.append(actual)
    return salida


def ngramas(docs: list, n: int, minimo: int = 3, tope: int = 50) -> list[dict]:
    """N-gramas de formas en minúscula que no empiezan ni terminan en palabra
    vacía y no contienen números sueltos."""
    c = Counter()
    for d in docs:
        for tramo in tramos(d):
            for i in range(len(tramo) - n + 1):
                g = tramo[i:i + n]
                if g[0].is_stop or g[-1].is_stop or any(t.like_num for t in g):
                    continue
                c[" ".join(t.text.lower() for t in g)] += 1
    return [{"n": n, "ngrama": g, "frecuencia": f} for g, f in c.most_common(tope) if f >= minimo]


def colocaciones(docs: list, minimo: int = 5, tope: int = 100) -> list[dict]:
    """Bigramas de palabras léxicas adyacentes con PMI, t-score y G²
    (log-likelihood de Dunning). Se ordenan por G²."""
    pares, primeros, segundos = Counter(), Counter(), Counter()
    for d in docs:
        for tramo in tramos(d):
            for a, b in zip(tramo, tramo[1:]):
                x, y = a.text.lower(), b.text.lower()
                primeros[x] += 1
                segundos[y] += 1
                if not (a.is_stop or b.is_stop or a.like_num or b.like_num):
                    pares[(x, y)] += 1
    N = sum(primeros.values())
    salida = []
    for (x, y), o11 in pares.items():
        if o11 < minimo:
            continue
        c1, c2 = primeros[x], segundos[y]
        e11 = c1 * c2 / N
        tabla = [(o11, e11), (c1 - o11, c1 * (N - c2) / N),
                 (c2 - o11, (N - c1) * c2 / N), (N - c1 - c2 + o11, (N - c1) * (N - c2) / N)]
        g2 = 2 * sum(o * math.log(o / e) for o, e in tabla if o > 0)
        salida.append({"colocacion": f"{x} {y}", "frecuencia": o11,
                       "pmi": round(math.log2(o11 / e11), 3),
                       "t_score": round((o11 - e11) / math.sqrt(o11), 3),
                       "log_likelihood": round(g2, 2)})
    salida.sort(key=lambda r: -r["log_likelihood"])
    return salida[:tope]


# ---------------------------------------------------------------------------
# Búsqueda de términos (KWIC, glosario, sinónimos)
# ---------------------------------------------------------------------------

def lemas_de(nlp, termino: str) -> list[str]:
    return [t.lemma_.lower() for t in nlp(termino) if not t.is_space]


def buscar(docs: list, nlp, termino: str) -> list[tuple[int, int, int]]:
    """Ocurrencias (doc, inicio, fin) de ``termino``: coincide por forma en
    minúscula o por lema, para que «multa» encuentre «multas»."""
    formas = [t.lower_ for t in nlp.make_doc(termino)]
    lemas = lemas_de(nlp, termino)
    n = len(formas)
    hallados = []
    for k, d in enumerate(docs):
        toks = [t for t in d if not t.is_space]
        for i in range(len(toks) - n + 1):
            v = toks[i:i + n]
            if [t.lower_ for t in v] == formas or [t.lemma_.lower() for t in v] == lemas:
                hallados.append((k, v[0].i, v[-1].i + 1))
    return hallados


def kwic(docs: list, registros: list[dict], nlp, termino: str, ancho: int = 60) -> list[dict]:
    lineas = []
    for k, i, j in buscar(docs, nlp, termino):
        d = docs[k]
        ini, fin = d[i].idx, d[j - 1].idx + len(d[j - 1].text)
        izq = d.text[max(0, ini - ancho):ini]
        der = d.text[fin:fin + ancho]
        lineas.append({"identificador": registros[k]["identificador"],
                       "izquierda": izq.rjust(ancho),
                       "nodo": d.text[ini:fin], "derecha": der.ljust(ancho)})
    return lineas


RE_DEFINE = r"(?:se entiende(?:n)? por|entiendase por|se entendera(?:n)? por|se denomina(?:n)?)\s+(?:el |la |los |las )?"


def _primera_oracion(texto: str, desde: int = 0, maximo: int = 500) -> str:
    """La oración (o línea) de ``texto`` que contiene la posición ``desde``."""
    previo = max(texto.rfind(". ", 0, desde), texto.rfind("\n", 0, desde))
    inicio = 0 if previo == -1 else previo + (1 if texto[previo] == "\n" else 2)
    finales = [k for k in (texto.find(". ", desde + 1), texto.find("\n", desde + 1)) if k != -1]
    fin = min(finales) if finales else len(texto)
    trozo = texto[inicio:fin].strip()
    if trozo and not trozo.endswith((".", ":")):
        trozo += "."
    return trozo if len(trozo) <= maximo else trozo[:maximo].rsplit(" ", 1)[0] + "…"


_PREFIJOS_EPIGRAFE = re.compile(
    r"^(?:(?:definicion|objeto|tramite|concepto|naturaleza|clases?)\s+(?:de|del)\s+)?(?:las|los|la|el)?\s*")


def _raiz(frase: str) -> str:
    """Quita plurales de cada palabra: «multas especiales» → «multa especial»."""
    return " ".join(re.sub(r"(?<=[aeiou])s$|(?<=[^aeiou])es$", "", w) for w in frase.split())


def buscar_definicion(termino: str, corpus: list[dict]) -> dict | None:
    """Fragmento del Código que define ``termino``:
    1) «se entiende por <término>» en el texto;
    2) epígrafe «Definición de <término>»;
    3) epígrafe igual al término (p. ej. el artículo «Amonestación»)."""
    t = sin_tildes(termino)
    patron = re.compile(RE_DEFINE + re.escape(t))
    for f in corpus:
        m = patron.search(sin_tildes(f["texto"]))
        if m:
            return {"identificador": f["identificador"], "texto": _primera_oracion(f["texto"], m.start())}
    base = [f for f in corpus if f["identificador"] == f"art_{f.get('articulo')}"]
    rt = _raiz(t)
    for regla in (lambda e: e.startswith("definicion") and t in e,
                  lambda e: _raiz(_PREFIJOS_EPIGRAFE.sub("", e)) == rt,
                  lambda e: e.startswith(t + " ") and len(e) <= len(t) + 25):
        for f in base:
            if regla(sin_tildes(f["epigrafe"])):
                return {"identificador": f["identificador"], "texto": _primera_oracion(f["texto"])}
    return None


def uso_en_el_codigo(termino: str, ocurrencias, corpus, docs) -> dict:
    """Cuando el Código no define el término: la oración donde aparece por
    primera vez en un artículo cuyo epígrafe lo menciona (o la primera
    ocurrencia), como ejemplo de uso."""
    t = sin_tildes(termino)

    def oracion(k, i):
        texto = corpus[k]["texto"]
        pos = sin_tildes(texto).find(sin_tildes(docs[k][i].text))
        return _primera_oracion(texto, max(pos, 0))

    # Preferencia: epígrafe que nombra el término y oración con contenido
    # (≥ 12 palabras; las celdas de tabla «Multa General tipo 2.» no sirven).
    candidatos = [(k, i) for k, i, _ in ocurrencias]
    for filtro in (lambda k, o: t in sin_tildes(corpus[k]["epigrafe"]) and len(o.split()) >= 12,
                   lambda k, o: len(o.split()) >= 12,
                   lambda k, o: True):
        for k, i in candidatos:
            o = oracion(k, i)
            if filtro(k, o):
                return {"identificador": corpus[k]["identificador"], "texto": o}
    return None


def _articulos(ocurrencias, registros) -> list[str]:
    vistos = []
    for k, _, _ in ocurrencias:
        a = registros[k]["articulo"]
        if a not in vistos:
            vistos.append(a)
    return vistos


def glosario(terminos: list[str], corpus, registros, docs, nlp, candidatos_ngramas) -> dict:
    entradas = []
    for termino in terminos:
        oc = buscar(docs, nlp, termino)
        arts = _articulos(oc, registros)
        definicion = buscar_definicion(termino, corpus)
        entradas.append({"termino": termino, "frecuencia": len(oc), "n_articulos": len(arts),
                         "articulos": arts[:15], "definicion": definicion,
                         "uso": None if definicion or not oc else uso_en_el_codigo(termino, oc, corpus, docs)})
        if not oc:
            log.warning("Término del glosario sin ocurrencias: %s", termino)
    cubiertos = {sin_tildes(t) for t in terminos}
    candidatos = [g for g in candidatos_ngramas
                  if sin_tildes(g["ngrama"]) not in cubiertos][:40]
    return {"terminos": entradas, "candidatos": candidatos}


def terminos_candidatos(docs: list, minimo: int = 8) -> list[dict]:
    """Grupos nominales frecuentes (NOUN ADJ, NOUN ADP NOUN, NOUN ADP NOUN ADJ…)
    como candidatos a entrar al glosario."""
    patrones = {("NOUN", "ADJ"), ("NOUN", "ADP", "NOUN"), ("NOUN", "ADJ", "ADJ"),
                ("NOUN", "ADP", "NOUN", "ADJ"), ("NOUN", "ADP", "DET", "NOUN")}
    c = Counter()
    for d in docs:
        for tramo in tramos(d):
            for n in (2, 3, 4):
                for i in range(len(tramo) - n + 1):
                    g = tramo[i:i + n]
                    if tuple(t.pos_ for t in g) in patrones:
                        c[" ".join(t.text.lower() for t in g)] += 1
    return [{"ngrama": g, "frecuencia": f} for g, f in c.most_common(200) if f >= minimo]


def sinonimos(mapa: dict[str, list[str]], registros, docs, nlp) -> dict:
    entradas, indice = {}, {}
    for canonico, variantes in mapa.items():
        oc = buscar(docs, nlp, canonico)
        entradas[canonico] = {"variantes": variantes, "frecuencia_en_corpus": len(oc),
                              "articulos": _articulos(oc, registros)[:10]}
        if not oc:
            log.warning("Término canónico de sinónimos sin ocurrencias: %s", canonico)
        for v in variantes:
            indice.setdefault(sin_tildes(v), []).append(canonico)
    return {"terminos": entradas, "indice_inverso": indice}


def expandir_consulta(consulta: str, indice_inverso: dict[str, list[str]]) -> list[str]:
    """Términos del Código que corresponden a expresiones coloquiales de la
    consulta. Ejemplo: «me pusieron un parte» → ["orden de comparendo"]."""
    c = " " + re.sub(r"[^\w ]", " ", sin_tildes(consulta)) + " "
    salida = []
    for variante, canonicos in sorted(indice_inverso.items(), key=lambda kv: -len(kv[0])):
        if f" {variante} " in c:
            for t in canonicos:
                if t not in salida:
                    salida.append(t)
    return salida


# ---------------------------------------------------------------------------
# Salidas
# ---------------------------------------------------------------------------

def _csv(ruta: Path, filas: list[dict]) -> None:
    if not filas:
        ruta.write_text("", encoding="utf-8")
        return
    with ruta.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)


def _json(ruta: Path, datos) -> None:
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _tabla(filas: list[dict], columnas: list[tuple[str, str]]) -> str:
    cab = "| " + " | ".join(t for _, t in columnas) + " |"
    sep = "|" + "|".join("---" for _ in columnas) + "|"
    cuerpo = ["| " + " | ".join(str(f.get(k, "")).replace("|", "\\|") for k, _ in columnas) + " |" for f in filas]
    return "\n".join([cab, sep, *cuerpo])


ETIQUETAS_POS = {"NOUN": "sustantivo", "ADP": "preposición", "DET": "determinante", "VERB": "verbo",
                 "ADJ": "adjetivo", "CCONJ": "conj. coordinante", "PRON": "pronombre", "SCONJ": "conj. subordinante",
                 "ADV": "adverbio", "AUX": "auxiliar", "PROPN": "nombre propio", "NUM": "numeral", "SYM": "símbolo",
                 "X": "otro", "PART": "partícula", "INTJ": "interjección", "PUNCT": "puntuación", "SPACE": "espacio"}


def informe(est, frec, ngr, col, conc, glos, sins, meta) -> str:
    L = []
    a = L.append
    a("# Informe de análisis lingüístico del corpus\n")
    a("**Entregable 2.** Describe el preprocesamiento del corpus y sus estadísticas, frecuencias, n-gramas, "
      "colocaciones, concordancias, glosario y sinónimos. Estos resultados orientan el diseño del motor RAG: cómo "
      "segmentar y vectorizar, qué búsqueda léxica conviene y cómo expandir las consultas.\n")
    a(f"**Corpus:** {meta['norma']} (Código Nacional de Seguridad y Convivencia Ciudadana), texto compilado "
      f"del Gestor Normativo de Función Pública consultado el {meta['fecha_consulta']}.  ")
    a(f"**Herramientas:** spaCy {meta['spacy']} con el modelo `{meta['modelo']}` {meta['modelo_version']}, "
      f"más reglas propias para entidades del dominio.  ")
    a(f"**Generado:** {meta['generado']} con `analisis_linguistico.py` {__version__}. "
      "Todas las cifras se recalculan al volver a ejecutar el script.\n")

    a("## 1. Preprocesamiento\n")
    a("Cada fragmento de `corpus.json` pasa por estos pasos:\n")
    a("1. **Normalización:** Unicode NFC, comillas tipográficas («», “”) a comillas rectas, rayas a guion y espacios "
      "múltiples a uno. Se conservan mayúsculas y tildes porque el etiquetador y el reconocedor de entidades las usan; "
      "el campo `texto_normalizado` guarda además la versión en minúsculas.")
    a("2. **Tokenización** con el tokenizador de spaCy para español (separa signos, paréntesis y contracciones como «al» y «del»).")
    a("3. **Lematización** con el lematizador del modelo (por reglas y tablas guiado por la etiqueta POS): «multas» → «multa», «impondrá» → «imponer».")
    a("4. **Etiquetado gramatical (POS)** con el esquema Universal Dependencies.")
    a("5. **Reconocimiento de entidades:** las etiquetas LOC/ORG/PER del modelo se combinan con reglas propias para "
      "AUTORIDAD (lista de autoridades de policía), LUGAR (lugares que menciona el Código), MONTO (salarios mínimos, "
      "multas generales tipo 1–4, multas especiales) y PLAZO («cinco (5) días hábiles»). La etiqueta MISC del modelo se "
      "descarta porque en este texto marca sobre todo frases en mayúscula inicial.\n")
    a("Para las estadísticas, un **token** es una palabra o cifra (sin signos de puntuación) y un **tipo** es una forma "
      "distinta en minúsculas.\n")

    a("## 2. Estadísticas descriptivas\n")
    lf, la = est["longitud_fragmento_tokens"], est["longitud_articulo_tokens"]
    a(_tabla([
        {"m": "Artículos", "v": est["n_articulos"]},
        {"m": "Fragmentos (artículo, numeral, parágrafo)", "v": est["n_fragmentos"]},
        {"m": "Oraciones", "v": est["n_oraciones"]},
        {"m": "Tokens", "v": est["n_tokens"]},
        {"m": "Tipos (formas distintas)", "v": est["n_tipos"]},
        {"m": "Lemas distintos", "v": est["n_lemas"]},
        {"m": "Relación tipo/token (TTR)", "v": est["relacion_tipo_token"]},
        {"m": "TTR estandarizada (ventanas de 1.000 tokens)", "v": est["sttr_1000"]},
        {"m": "Hapax legomena (formas que aparecen una vez)", "v": est["hapax"]},
        {"m": "Longitud media por fragmento (tokens)", "v": f"{lf['media']} (mediana {lf['mediana']}, máx. {lf['maximo']})"},
        {"m": "Longitud media por artículo completo (tokens)", "v": f"{la['media']} (mediana {la['mediana']}, máx. {la['maximo']})"},
    ], [("m", "Medida"), ("v", "Valor")]))
    a("")
    a(f"La TTR global ({est['relacion_tipo_token']}) es baja porque depende del tamaño del texto: con "
      f"{est['n_tokens']} tokens las palabras se repiten mucho. La TTR estandarizada ({est['sttr_1000']}) permite "
      "comparar con otros textos. El vocabulario jurídico es repetitivo (fórmulas como «medida correctiva a aplicar», "
      "«multa general tipo 2»), lo que favorece la búsqueda léxica y el uso de un glosario para expandir consultas.\n")
    a(f"El fragmento más largo es `{lf['mas_largo']['identificador']}` ({lf['mas_largo']['tokens']} tokens) y el artículo "
      f"más largo es el {la['mas_largo']['articulo']} ({la['mas_largo']['tokens']} tokens). El 90 % de los fragmentos tiene "
      f"{lf['p90']} tokens o menos y el 90 % de los artículos {la['p90']} o menos; esto se tiene en cuenta en la fase 3 "
      "para elegir el tamaño de los fragmentos que se indexan.\n")
    a("**Distribución por libro**\n")
    a(_tabla([{"l": k, **v} for k, v in est["por_libro"].items()],
             [("l", "Libro"), ("articulos", "Artículos"), ("fragmentos", "Fragmentos"), ("tokens", "Tokens")]))
    a("")
    a("**Estado de vigencia de los fragmentos**\n")
    a(_tabla([{"e": k, "n": v} for k, v in est["vigencia"].items()], [("e", "Estado"), ("n", "Fragmentos")]))
    a("")

    a("## 3. Etiquetado gramatical (POS)\n")
    a(_tabla([{"t": k, "d": ETIQUETAS_POS.get(k, k), **v} for k, v in est["pos"].items()],
             [("t", "Etiqueta"), ("d", "Categoría"), ("n", "Tokens"), ("pct", "%")]))
    a("")
    a("Predominan sustantivos, preposiciones y determinantes: es un texto nominal, típico de la prosa normativa "
      "(«la imposición del pago de una suma de dinero»). Los verbos aparecen sobre todo en futuro y en infinitivo "
      "(«será», «impondrá», «portar»), propios de la enumeración de comportamientos prohibidos.\n")

    a("## 4. Entidades reconocidas\n")
    a(_tabla([{"e": k, "n": v["n"], "x": ", ".join(v["ejemplos"])} for k, v in est["entidades"].items()],
             [("e", "Etiqueta"), ("n", "Menciones"), ("x", "Más frecuentes")]))
    a("")
    a("AUTORIDAD, LUGAR, MONTO y PLAZO salen de las reglas propias y son fiables. ORGANIZACION y PERSONA vienen del "
      "modelo genérico, entrenado con noticias: sin el filtro de nombres propios marcaba como organización o persona "
      "las celdas de las tablas («Destrucción de bien», «Suspensión temporal…»), y aun con él quedan errores como las "
      "razas de perros potencialmente peligrosos del art. 126 etiquetadas como PERSONA. Para el motor RAG se usan las "
      "etiquetas de reglas.\n")

    a("## 5. Frecuencias\n")
    a("Lemas de contenido (sustantivos, verbos, adjetivos, adverbios y nombres propios, sin palabras vacías) más frecuentes:\n")
    a(_tabla(frec[:30], [("lema", "Lema"), ("frecuencia", "Frecuencia"), ("por_10000", "Por 10.000 tokens"), ("fragmentos", "Fragmentos")]))
    a("\nLa lista completa (100 lemas) está en `frecuencias_lemas.csv`.\n")

    a("## 6. N-gramas\n")
    a("Secuencias de dos y tres palabras que no cruzan signos de puntuación y no empiezan ni terminan en palabra vacía.\n")
    big = [g for g in ngr if g["n"] == 2][:20]
    tri = [g for g in ngr if g["n"] == 3][:20]
    a("**Bigramas**\n")
    a(_tabla(big, [("ngrama", "Bigrama"), ("frecuencia", "Frecuencia")]))
    a("\n**Trigramas**\n")
    a(_tabla(tri, [("ngrama", "Trigrama"), ("frecuencia", "Frecuencia")]))
    a("")

    a("## 7. Colocaciones\n")
    a("Bigramas de palabras léxicas (frecuencia ≥ 5) ordenados por log-likelihood (G², Dunning 1993). Se incluyen la "
      "información mutua puntual (PMI), que premia combinaciones exclusivas aunque sean raras, y el t-score, que premia "
      "las frecuentes. Un G² mayor que 10,83 es significativo con p < 0,001.\n")
    a(_tabla(col[:25], [("colocacion", "Colocación"), ("frecuencia", "Frec."), ("log_likelihood", "G²"),
                        ("pmi", "PMI"), ("t_score", "t-score")]))
    a("")

    a("## 8. Concordancias (KWIC)\n")
    for termino, lineas in conc.items():
        a(f"### «{termino}» — {len(lineas)} ocurrencias\n")
        a("```text")
        for l in lineas[:12]:
            a(f"{l['identificador']:<18} {l['izquierda'][-50:]:>50} [{l['nodo']}] {l['derecha'][:50]}")
        a("```")
        if len(lineas) > 12:
            a(f"Se muestran 12 de {len(lineas)}; todas están en `kwic.txt`.\n")
        else:
            a("")

    a("## 9. Glosario de términos jurídicos\n")
    a("Términos elegidos a partir de las frecuencias, las colocaciones y los artículos de definiciones del Código "
      "(arts. 5, 32, 139, 218, entre otros). La definición se toma literalmente del Código cuando éste la da "
      "(«se entiende por…», epígrafe «Definición de…» o artículo dedicado al término).\n")
    for e in glos["terminos"]:
        arts = ", ".join(e["articulos"][:10]) + ("…" if len(e["articulos"]) > 10 else "")
        a(f"- **{e['termino']}** — {e['frecuencia']} ocurrencias en {e['n_articulos']} artículos"
          + (f" (arts. {arts})" if arts else "") + ".")
        if e["definicion"]:
            a(f"  - *Definición ({e['definicion']['identificador']}):* {e['definicion']['texto']}")
        elif e.get("uso"):
            a(f"  - *El Código no lo define; uso ({e['uso']['identificador']}):* {e['uso']['texto']}")
    a("")
    a("**Otros candidatos** (grupos nominales frecuentes que aún no están en el glosario): "
      + ", ".join(f"{c['ngrama']} ({c['frecuencia']})" for c in glos["candidatos"][:25]) + ".\n")

    a("## 10. Sinónimos coloquiales para expandir consultas\n")
    a("Lista curada a mano en `recursos/terminos.json`: relaciona la forma en que un ciudadano pregunta con el término "
      "que usa el Código. La función `expandir_consulta()` la aplica en la fase 4, por ejemplo «me pusieron un parte» → "
      "«orden de comparendo».\n")
    a(_tabla([{"c": k, "v": ", ".join(v["variantes"]), "f": v["frecuencia_en_corpus"]} for k, v in sins["terminos"].items()],
             [("c", "Término del Código"), ("v", "Formas coloquiales"), ("f", "Frecuencia en el corpus")]))
    a("")

    a("## 11. Conclusiones para el motor RAG\n")
    a("- El texto es nominal y repetitivo; la búsqueda léxica (BM25 sobre `lemas_contenido`) complementa bien a la semántica en la fase 4.")
    a("- Los fragmentos son cortos (mediana de "
      f"{lf['mediana']} tokens): por eso al vectorizar se les antepone el epígrafe y la ubicación jerárquica para darles contexto.")
    a("- Montos y plazos aparecen siempre con la fórmula «palabra (cifra)», fácil de detectar por reglas; el modelo genérico "
      "de spaCy no los reconoce.")
    a("- Las preguntas ciudadanas usan otro registro («parte», «requisa», «bulla»); el diccionario de sinónimos cubre esa brecha.")
    return "\n".join(L) + "\n"


def analizar(ruta_corpus: str | Path, carpeta: str | Path = RAIZ / "resultados" / "analisis",
             ruta_terminos: str | Path = RAIZ / "recursos" / "terminos.json", modelo: str = MODELO_POR_DEFECTO) -> dict:
    ruta_corpus, carpeta = Path(ruta_corpus), Path(carpeta)
    if not ruta_corpus.is_file():
        raise AnalisisError(f"No existe el corpus: {ruta_corpus}")
    try:
        corpus = json.loads(ruta_corpus.read_text(encoding="utf-8"))
        terminos = json.loads(Path(ruta_terminos).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise AnalisisError(f"No se pudo leer la entrada: {e}") from e
    if not corpus:
        raise AnalisisError("El corpus está vacío")

    import spacy
    nlp = construir_nlp(modelo, terminos.get("autoridades", []), terminos.get("lugares", []))
    log.info("Procesando %d fragmentos con %s…", len(corpus), modelo)
    registros, docs = procesar(corpus, nlp)

    est = estadisticas(corpus, registros, docs)
    frec = frecuencias_lemas(docs)
    ngr = ngramas(docs, 2) + ngramas(docs, 3)
    col = colocaciones(docs)
    conc = {t: kwic(docs, registros, nlp, t) for t in terminos.get("kwic", [])}
    glos = glosario(terminos.get("glosario", []), corpus, registros, docs, nlp, terminos_candidatos(docs))
    sins = sinonimos(terminos.get("sinonimos", {}), registros, docs, nlp)

    carpeta.mkdir(parents=True, exist_ok=True)
    with (carpeta / "corpus_procesado.jsonl").open("w", encoding="utf-8") as fh:
        for r in registros:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    _json(carpeta / "estadisticas.json", est)
    _csv(carpeta / "frecuencias_lemas.csv", frec)
    _csv(carpeta / "ngramas.csv", ngr)
    _csv(carpeta / "colocaciones.csv", col)
    _json(carpeta / "kwic.json", conc)
    with (carpeta / "kwic.txt").open("w", encoding="utf-8") as fh:
        for t, lineas in conc.items():
            fh.write(f"=== {t} ({len(lineas)} ocurrencias) ===\n")
            for l in lineas:
                fh.write(f"{l['identificador']:<22} {l['izquierda']} [{l['nodo']}] {l['derecha']}\n")
            fh.write("\n")
    _json(carpeta / "glosario.json", glos)
    _json(carpeta / "sinonimos.json", sins)

    meta = {"norma": corpus[0].get("norma") or "Ley 1801 de 2016",
            "fecha_consulta": corpus[0].get("fecha_consulta") or "(sin fecha)",
            "spacy": spacy.__version__, "modelo": modelo, "modelo_version": nlp.meta.get("version", ""),
            "generado": date.today().isoformat()}
    (carpeta / "informe_linguistico.md").write_text(
        informe(est, frec, ngr, col, conc, glos, sins, meta), encoding="utf-8")
    log.info("Resultados en %s/", carpeta)
    return {"estadisticas": est, "frecuencias": frec, "ngramas": ngr, "colocaciones": col,
            "kwic": conc, "glosario": glos, "sinonimos": sins, "registros": registros}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Análisis lingüístico del corpus (fase 2).")
    p.add_argument("corpus", nargs="?", default=str(RAIZ / "datos" / "corpus.json"), help="corpus de segmentar_codigo.py")
    p.add_argument("-o", "--salida", default=str(RAIZ / "resultados" / "analisis"), help="carpeta de resultados (por defecto: resultados/analisis)")
    p.add_argument("-t", "--terminos", default=str(RAIZ / "recursos" / "terminos.json"), help="listas curadas")
    p.add_argument("-m", "--modelo", default=MODELO_POR_DEFECTO, help="modelo de spaCy")
    p.add_argument("-v", "--detalle", action="store_true")
    p.add_argument("--version", action="version", version=__version__)
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.detalle else logging.INFO, format="%(levelname)s: %(message)s")
    try:
        analizar(a.corpus, a.salida, a.terminos, a.modelo)
    except AnalisisError as e:
        log.error("%s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
