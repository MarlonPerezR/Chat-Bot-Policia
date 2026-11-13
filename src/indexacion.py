#!/usr/bin/env python3
"""Fase 3: representación vectorial e indexación del corpus con FAISS.

Construye, para cada modelo de embeddings y cada estrategia de segmentación,
un índice FAISS y lo evalúa con el banco de preguntas
(``recursos/preguntas_evaluacion.json``):

    fragmento  los fragmentos jerárquicos de corpus.json (artículo, numeral,
               parágrafo), cada uno precedido de «artículo N. Epígrafe.»
    articulo   el artículo completo (todos sus fragmentos unidos)
    fijo       ventanas de tamaño fijo (por defecto 200 palabras, solape de
               50) sobre el texto corrido de la ley, sin mirar la estructura

Métricas por estrategia: Precisión@k, Recall@k (a nivel de artículo), MRR y
tamaño del contexto que se le pasaría al LLM. También mide la similitud
máxima de las preguntas fuera de dominio para fijar el umbral de RF3.

Guarda en ``resultados/indice/<estrategia>/`` (para el modelo elegido):
    indice.faiss      índice FAISS (producto interno sobre vectores normalizados = coseno)
    embeddings.npy    matriz de embeddings (float32)
    unidades.json     texto y metadatos de cada vector, en el mismo orden
    config.json       modelo, dimensión, estrategia, fecha
y en ``resultados/indice/``: resultados_evaluacion.json, embeddings_pca.png e
informe_fase3.md.

Uso:
    .venv/bin/python src/indexacion.py              # construir + evaluar
    .venv/bin/python src/indexacion.py --modelos intfloat/multilingual-e5-base
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import statistics
import sys
import time
from collections import OrderedDict
from datetime import date
from pathlib import Path

# Raíz del proyecto (chatbot_IA/): las rutas por defecto no dependen de la
# carpeta desde la que se ejecute el script.
RAIZ = Path(__file__).resolve().parent.parent

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
# macOS: PyTorch y FAISS traen cada uno su libomp. Cargadas juntas, el proceso
# se cae (violación de segmento o «OMP: Error #15»). Un solo hilo de OpenMP y
# permitir la copia duplicada lo evita; PyTorch recupera sus hilos con
# torch.set_num_threads (no usa el pool de OpenMP de FAISS).
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import numpy as np  # noqa: E402
import torch  # noqa: E402  (antes que faiss)

torch.set_num_threads(max(1, (os.cpu_count() or 2) - 1))

__version__ = "1.0.0"
log = logging.getLogger("indexacion")

MODELOS_POR_DEFECTO = ["intfloat/multilingual-e5-base",
                       "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"]
ESTRATEGIAS = ["fragmento", "articulo", "fijo"]
KS = (1, 3, 5, 10)


class IndexacionError(Exception):
    """Error que impide construir o evaluar el índice."""


# ---------------------------------------------------------------------------
# Estrategias de segmentación
# ---------------------------------------------------------------------------

def _encabezado(f: dict) -> str:
    norma = f.get("norma") or "Ley 1801 de 2016"
    epi = f" {f['epigrafe']}." if f.get("epigrafe") else ""
    return f"{norma}, artículo {f['articulo']}.{epi}"


def unidades_fragmento(corpus: list[dict]) -> list[dict]:
    """Un vector por fragmento. Se antepone artículo y epígrafe: un numeral
    suelto («7. Consumir bebidas…») no dice de qué trata el artículo."""
    return [{"id": f["identificador"], "articulos": [f["articulo"]],
             "texto_embedding": f"{_encabezado(f)}\n{f['texto']}", "texto": f["texto"],
             "identificadores": [f["identificador"]], "epigrafe": f["epigrafe"],
             "ubicacion_jerarquica": f["ubicacion_jerarquica"], "estado_vigencia": f["estado_vigencia"],
             "notas": f.get("notas", []), "norma": f.get("norma")} for f in corpus]


def _por_articulo(corpus: list[dict]) -> "OrderedDict[str, list[dict]]":
    grupos: OrderedDict[str, list[dict]] = OrderedDict()
    for f in corpus:
        grupos.setdefault(f["articulo"], []).append(f)
    return grupos


def unidades_articulo(corpus: list[dict]) -> list[dict]:
    """Un vector por artículo completo."""
    salida = []
    for art, frags in _por_articulo(corpus).items():
        texto = "\n".join(f["texto"] for f in frags)
        estados = {f["estado_vigencia"] for f in frags}
        estado = estados.pop() if len(estados) == 1 else "inexequible_parcial"
        salida.append({"id": f"art_{art}", "articulos": [art],
                       "texto_embedding": f"{_encabezado(frags[0])}\n{texto}", "texto": texto,
                       "identificadores": [f["identificador"] for f in frags], "epigrafe": frags[0]["epigrafe"],
                       "ubicacion_jerarquica": frags[0]["ubicacion_jerarquica"], "estado_vigencia": estado,
                       "notas": [n for f in frags for n in f.get("notas", [])], "norma": frags[0].get("norma")})
    return salida


def unidades_fijas(corpus: list[dict], tam: int = 200, solape: int = 50) -> list[dict]:
    """Ventanas de ``tam`` palabras con ``solape`` palabras repetidas sobre el
    texto corrido de la ley («ARTÍCULO N. Epígrafe. texto…»). Cada ventana
    sabe qué artículos cubre, para poder evaluarla y citarla."""
    if not 0 <= solape < tam:
        raise IndexacionError("El solape debe ser menor que el tamaño de la ventana")
    palabras, articulo_de = [], []
    for art, frags in _por_articulo(corpus).items():
        epi = f" {frags[0]['epigrafe']}." if frags[0]["epigrafe"] else ""
        texto = f"ARTÍCULO {art}.{epi} " + " ".join(f["texto"] for f in frags)
        for p in texto.split():
            palabras.append(p)
            articulo_de.append(art)
    salida, paso = [], tam - solape
    for n, inicio in enumerate(range(0, max(len(palabras) - solape, 1), paso)):
        trozo = palabras[inicio:inicio + tam]
        arts = list(OrderedDict.fromkeys(articulo_de[inicio:inicio + tam]))
        texto = " ".join(trozo)
        salida.append({"id": f"ventana_{n}", "articulos": arts, "texto_embedding": texto, "texto": texto,
                       "identificadores": [], "epigrafe": "", "ubicacion_jerarquica": None,
                       "estado_vigencia": None, "notas": [], "norma": corpus[0].get("norma"),
                       "palabra_inicial": inicio})
    return salida


def construir_unidades(corpus: list[dict], estrategia: str, tam: int = 200, solape: int = 50) -> list[dict]:
    if estrategia == "fragmento":
        return unidades_fragmento(corpus)
    if estrategia == "articulo":
        return unidades_articulo(corpus)
    if estrategia == "fijo":
        return unidades_fijas(corpus, tam, solape)
    raise IndexacionError(f"Estrategia desconocida: {estrategia}")


# ---------------------------------------------------------------------------
# Modelo de embeddings e índice
# ---------------------------------------------------------------------------

class ModeloEmbeddings:
    """Envoltorio de sentence-transformers. Los modelos E5 se entrenaron con
    los prefijos «query: » y «passage: »; sin ellos rinden peor."""

    def __init__(self, nombre: str):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:  # pragma: no cover
            raise IndexacionError("Falta sentence-transformers: .venv/bin/pip install -r requirements.txt") from e
        self.nombre = nombre
        self.modelo = SentenceTransformer(nombre, device="cpu")
        self.e5 = "e5" in nombre.lower()
        self.dimension = self.modelo.get_sentence_embedding_dimension()
        self.max_tokens = self.modelo.max_seq_length

    def _codificar(self, textos: list[str], prefijo: str) -> np.ndarray:
        if self.e5:
            textos = [prefijo + t for t in textos]
        v = self.modelo.encode(textos, batch_size=32, normalize_embeddings=True,
                               show_progress_bar=False, convert_to_numpy=True)
        return v.astype("float32")

    def pasajes(self, textos: list[str]) -> np.ndarray:
        return self._codificar(textos, "passage: ")

    def consultas(self, textos: list[str]) -> np.ndarray:
        return self._codificar(textos, "query: ")

    def truncados(self, textos: list[str]) -> int:
        """Cuántos textos superan la longitud máxima del modelo (se cortan)."""
        tok = self.modelo.tokenizer
        return sum(1 for t in textos if len(tok(t, add_special_tokens=True)["input_ids"]) > self.max_tokens)


def crear_indice(vectores: np.ndarray):
    import faiss
    indice = faiss.IndexFlatIP(vectores.shape[1])  # coseno: vectores ya normalizados
    indice.add(vectores)
    return indice


def guardar(carpeta: Path, indice, vectores: np.ndarray, unidades: list[dict], config: dict) -> None:
    import faiss
    carpeta.mkdir(parents=True, exist_ok=True)
    faiss.write_index(indice, str(carpeta / "indice.faiss"))
    np.save(carpeta / "embeddings.npy", vectores)
    sin_embedding = [{k: v for k, v in u.items() if k != "texto_embedding"} for u in unidades]
    (carpeta / "unidades.json").write_text(json.dumps(sin_embedding, ensure_ascii=False, indent=1), encoding="utf-8")
    (carpeta / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Evaluación
# ---------------------------------------------------------------------------

def metricas(ranking: list[list[str]], esperados: set[str], ks=KS) -> dict:
    """``ranking``: artículos de cada unidad recuperada, en orden.

    - P@k: fracción de las k unidades que contienen algún artículo esperado.
    - R@k: fracción de artículos esperados que aparecen en las k unidades.
    - RR: 1 / posición de la primera unidad relevante (0 si no hay).
    """
    salida = {}
    relevantes = [bool(esperados & set(arts)) for arts in ranking]
    for k in ks:
        cubiertos = {a for arts in ranking[:k] for a in arts} & esperados
        salida[f"P@{k}"] = sum(relevantes[:k]) / k
        salida[f"R@{k}"] = len(cubiertos) / len(esperados)
    salida["RR"] = next((1 / (i + 1) for i, r in enumerate(relevantes) if r), 0.0)
    return salida


def evaluar(modelo: ModeloEmbeddings, indice, unidades: list[dict], preguntas: list[dict],
            consulta_fn=None) -> dict:
    dentro = [p for p in preguntas if p["articulos"]]
    fuera = [p for p in preguntas if not p["articulos"]]
    textos = [consulta_fn(p["pregunta"]) if consulta_fn else p["pregunta"] for p in dentro + fuera]
    t0 = time.perf_counter()
    q = modelo.consultas(textos)
    puntajes, posiciones = indice.search(q, max(KS))
    ms = 1000 * (time.perf_counter() - t0) / len(textos)

    por_pregunta, acumulado = [], {}
    for p, fila, pts in zip(dentro, posiciones[:len(dentro)], puntajes[:len(dentro)]):
        ranking = [unidades[i]["articulos"] for i in fila]
        m = metricas(ranking, set(p["articulos"]))
        for k, v in m.items():
            acumulado.setdefault(k, []).append(v)
        por_pregunta.append({"id": p["id"], "pregunta": p["pregunta"], "esperados": p["articulos"],
                             "recuperados": [unidades[i]["id"] for i in fila[:5]],
                             "articulos_top5": list(OrderedDict.fromkeys(a for i in fila[:5] for a in unidades[i]["articulos"])),
                             "puntaje_max": round(float(pts[0]), 4), **{k: round(v, 3) for k, v in m.items()}})
    resumen = {("MRR" if k == "RR" else k): round(statistics.mean(v), 4) for k, v in acumulado.items()}
    palabras_top5 = [sum(len(unidades[i]["texto"].split()) for i in fila[:5]) for fila in posiciones[:len(dentro)]]
    resumen["palabras_contexto_top5"] = round(statistics.mean(palabras_top5), 1)
    resumen["ms_por_consulta"] = round(ms, 1)
    max_dentro = [float(x) for x in puntajes[:len(dentro), 0]]
    max_fuera = [float(x) for x in puntajes[len(dentro):, 0]]
    resumen["similitud_max_dentro"] = {"media": round(statistics.mean(max_dentro), 4), "min": round(min(max_dentro), 4)}
    if max_fuera:
        resumen["similitud_max_fuera"] = {"media": round(statistics.mean(max_fuera), 4), "max": round(max(max_fuera), 4)}
    return {"resumen": resumen, "por_pregunta": por_pregunta}


# ---------------------------------------------------------------------------
# Visualización
# ---------------------------------------------------------------------------

def grafico_pca(vectores: np.ndarray, unidades: list[dict], ruta: Path, titulo: str) -> bool:
    """Proyección PCA a 2D de los embeddings, coloreada por libro."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        log.warning("Sin matplotlib: no se genera %s", ruta.name)
        return False
    centrados = vectores - vectores.mean(axis=0)
    _, s, vt = np.linalg.svd(centrados, full_matrices=False)
    with np.errstate(all="ignore"):  # avisos espurios de Accelerate (macOS) en matmul
        xy = centrados @ vt[:2].T
    varianza = (s[:2] ** 2) / (s ** 2).sum()
    libros = [(u["ubicacion_jerarquica"] or {}).get("libro") or "—" for u in unidades]
    nombres = list(OrderedDict.fromkeys(libros))
    colores = ["#2a6fdb", "#e0782f", "#2e9e5b", "#8a5cc2"]
    fig, ax = plt.subplots(figsize=(8, 6), dpi=130)
    for n, libro in enumerate(nombres):
        idx = [i for i, l in enumerate(libros) if l == libro]
        nombre = libro.split(". ", 1)[1].capitalize() if ". " in libro else ""
        if len(nombre) > 45:
            nombre = nombre[:45].rsplit(" ", 1)[0] + "…"
        etiqueta = libro.split(".")[0].title() + (f": {nombre}" if nombre else "")
        ax.scatter(xy[idx, 0], xy[idx, 1], s=9, alpha=0.7, color=colores[n % len(colores)], label=etiqueta)
    ax.set_xlabel(f"Componente 1 ({100 * varianza[0]:.1f} % de la varianza)")
    ax.set_ylabel(f"Componente 2 ({100 * varianza[1]:.1f} %)")
    ax.set_title(titulo, fontsize=10)
    ax.legend(fontsize=7, loc="best", frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(ruta)
    plt.close(fig)
    return True


# ---------------------------------------------------------------------------
# Informe
# ---------------------------------------------------------------------------

def _f(x: float) -> str:
    return f"{x:.3f}"


def informe(resultados: dict, elegido: dict, meta: dict) -> str:
    L = []
    a = L.append
    a("# Fase 3: representación vectorial e indexación\n")
    a(f"**Corpus:** {meta['norma']}, {meta['n_fragmentos']} fragmentos de {meta['n_articulos']} artículos "
      f"(consulta {meta['fecha_consulta']}).  ")
    a(f"**Banco de preguntas:** {meta['n_dentro']} preguntas con artículos esperados (las 10 del enunciado y "
      f"{meta['n_dentro'] - 10} más) y {meta['n_fuera']} fuera de dominio, en `recursos/preguntas_evaluacion.json`.  ")
    a(f"**Generado:** {meta['generado']} con `indexacion.py` {__version__} (FAISS {meta['faiss']}, "
      f"sentence-transformers {meta['st']}).\n")

    a("## 1. Modelo de embeddings\n")
    a("Se compararon dos modelos multilingües de sentence-transformers que corren en local (sin claves de API, sin "
      "costo por consulta y sin enviar el texto a terceros):\n")
    for nombre, r in resultados.items():
        info = r["modelo"]
        a(f"- **`{nombre}`**: {info['dimension']} dimensiones, máximo {info['max_tokens']} tokens por texto.")
    a("")
    a("`multilingual-e5-base` (Wang et al., 2024) se entrenó específicamente para recuperación con pares "
      "pregunta–pasaje (prefijos «query:» y «passage:»), admite textos de hasta 512 tokens y está entre los mejores "
      "modelos abiertos de su tamaño en las tareas de recuperación del benchmark MTEB. `paraphrase-multilingual-MiniLM-L12-v2` es más "
      "liviano y rápido, pero se entrenó para parafraseo (frases de longitud similar) y corta los textos en 128 "
      "tokens. Una alternativa de pago es el modelo de embeddings de la API de OpenAI; el diseño permite cambiarlo "
      "con el parámetro `--modelos`.\n")

    a("## 2. Estrategias de segmentación comparadas\n")
    a("| Estrategia | Unidad que se vectoriza | Vectores |")
    a("|---|---|---|")
    primero = next(iter(resultados.values()))
    desc = {"fragmento": "fragmento jerárquico de `corpus.json` (encabezado, numeral o parágrafo) precedido de «artículo N. Epígrafe.»",
            "articulo": "artículo completo: epígrafe y todos sus fragmentos",
            "fijo": f"ventana fija de {meta['tam']} palabras con {meta['solape']} de solape sobre el texto corrido, sin respetar artículos"}
    for e, r in primero["estrategias"].items():
        a(f"| `{e}` | {desc[e]} | {r['n_unidades']} |")
    a("")

    a("## 3. Resultados de recuperación\n")
    a("P@k: proporción de las k unidades recuperadas que contienen un artículo esperado. R@k: proporción de los "
      "artículos esperados que aparecen en las k primeras unidades. MRR: media del inverso de la posición de la "
      "primera unidad relevante. «Palabras top-5»: tamaño del contexto que recibiría el LLM con k = 5.\n")
    a("| Modelo | Estrategia | P@1 | P@5 | R@1 | R@5 | R@10 | MRR | Palabras top-5 | Textos truncados | ms/consulta |")
    a("|---|---|---|---|---|---|---|---|---|---|---|")
    for nombre, r in resultados.items():
        corto = nombre.split("/")[-1]
        for e, re_ in r["estrategias"].items():
            s = re_["evaluacion"]["resumen"]
            marca = " **(elegido)**" if (nombre, e) == (elegido["modelo"], elegido["estrategia"]) else ""
            a(f"| {corto} | `{e}`{marca} | {_f(s['P@1'])} | {_f(s['P@5'])} | {_f(s['R@1'])} | {_f(s['R@5'])} | "
              f"{_f(s['R@10'])} | {_f(s['MRR'])} | {s['palabras_contexto_top5']:.0f} | "
              f"{re_['truncados']} de {re_['n_unidades']} | {s['ms_por_consulta']:.0f} |")
    a("")
    if "expansion" in elegido:
        s0, s1 = elegido["evaluacion"]["resumen"], elegido["expansion"]["resumen"]
        a(f"**Expansión de consultas con el diccionario de sinónimos de la fase 2** (configuración elegida): "
          f"MRR {_f(s0['MRR'])} → {_f(s1['MRR'])}, R@5 {_f(s0['R@5'])} → {_f(s1['R@5'])}.\n")

    a("## 4. Análisis\n")
    for linea in elegido["analisis"]:
        a(f"- {linea}")
    a("")

    a("## 5. Umbral para preguntas fuera del Código (RF3)\n")
    s = elegido["evaluacion"]["resumen"]
    a(f"Con la configuración elegida, la similitud coseno del mejor resultado es en promedio "
      f"{s['similitud_max_dentro']['media']:.3f} para preguntas del Código (mínimo {s['similitud_max_dentro']['min']:.3f}) "
      f"y {s['similitud_max_fuera']['media']:.3f} para preguntas fuera de dominio (máximo "
      f"{s['similitud_max_fuera']['max']:.3f}). {elegido['umbral_texto']}\n")

    a("## 6. Preguntas con peor recuperación (configuración elegida)\n")
    peores = sorted(elegido["evaluacion"]["por_pregunta"], key=lambda p: (p["RR"], p["R@5"]))[:6]
    a("| # | Pregunta | Esperados | Artículos en top-5 | RR |")
    a("|---|---|---|---|---|")
    for p in peores:
        a(f"| {p['id']} | {p['pregunta']} | {', '.join(p['esperados'])} | {', '.join(p['articulos_top5'])} | {p['RR']:.2f} |")
    a("")

    a("## 7. Índice FAISS construido\n")
    a(f"- Modelo: `{elegido['modelo']}`; estrategia: `{elegido['estrategia']}`; {elegido['n_unidades']} vectores de "
      f"{elegido['dimension']} dimensiones.")
    a("- Tipo: `IndexFlatIP` (búsqueda exacta por producto interno sobre vectores normalizados, equivalente a la "
      "similitud coseno). Con unos miles de vectores la búsqueda exacta tarda milisegundos; un índice aproximado "
      "(IVF, HNSW) solo compensaría con cientos de miles.")
    a(f"- Archivos: `resultados/indice/{elegido['estrategia']}/indice.faiss`, `embeddings.npy`, `unidades.json` (texto y "
      "metadatos de cada vector, en el mismo orden) y `config.json`. Las otras estrategias quedan en sus carpetas "
      "para repetir la comparación.")
    if meta.get("pca"):
        a("\n![Proyección PCA de los embeddings](embeddings_pca.png)\n")
        a("Proyección de los embeddings en sus dos componentes principales, coloreada por libro del Código.")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------

def _analisis(resultados: dict, elegido: dict) -> list[str]:
    """Frases de análisis calculadas a partir de los números."""
    lineas = []
    modelo = resultados[elegido["modelo"]]["estrategias"]
    s = {e: r["evaluacion"]["resumen"] for e, r in modelo.items()}
    orden = sorted(s, key=lambda e: -s[e]["MRR"])
    lineas.append("Con el modelo elegido el orden por MRR es " + " > ".join(f"`{e}` ({_f(s[e]['MRR'])})" for e in orden) + ".")
    if "articulo" in s and "fragmento" in s:
        lineas.append(f"El artículo completo da un contexto de {s['articulo']['palabras_contexto_top5']:.0f} palabras "
                      f"con k = 5, frente a {s['fragmento']['palabras_contexto_top5']:.0f} con fragmentos: más contexto "
                      "por consulta (más tokens y costo en el LLM) y artículos largos que el modelo trunca "
                      f"({modelo['articulo']['truncados']} de {modelo['articulo']['n_unidades']} superan "
                      f"{resultados[elegido['modelo']]['modelo']['max_tokens']} tokens).")
    if "fijo" in s:
        lineas.append("Las ventanas fijas cortan artículos por la mitad y mezclan el final de uno con el comienzo del "
                      "siguiente: no se pueden citar con precisión (RF2) ni filtrar por vigencia, porque una ventana no "
                      f"corresponde a un artículo, parágrafo o numeral. MRR: {_f(s['fijo']['MRR'])}.")
        if s["fijo"]["R@5"] > s.get("fragmento", s["fijo"])["R@5"]:
            lineas.append(f"Las ventanas fijas logran el mayor R@5 ({_f(s['fijo']['R@5'])}), pero en parte porque cada "
                          "ventana abarca dos o tres artículos: cubren más artículos esperados a costa de un contexto "
                          f"{s['fijo']['palabras_contexto_top5'] / max(s['fragmento']['palabras_contexto_top5'], 1):.0f} "
                          "veces más largo que el de los fragmentos.")
    otros = [n for n in resultados if n != elegido["modelo"]]
    for n in otros:
        so = resultados[n]["estrategias"][elegido["estrategia"]]["evaluacion"]["resumen"]
        lineas.append(f"Con la misma estrategia, `{n.split('/')[-1]}` obtiene MRR {_f(so['MRR'])} y R@5 {_f(so['R@5'])}, "
                      f"frente a {_f(s[elegido['estrategia']]['MRR'])} y {_f(s[elegido['estrategia']]['R@5'])} del modelo elegido.")
    lineas.append(f"Se elige `{elegido['estrategia']}` con `{elegido['modelo'].split('/')[-1]}`. " + elegido["razon"])
    return lineas


def elegir(resultados: dict) -> tuple[str, str, str]:
    """Mejor MRR entre las estrategias citables (fragmento o artículo); si
    `fijo` le gana, se informa pero no se elige porque no permite citar."""
    mejores = []
    for n, r in resultados.items():
        for e, re_ in r["estrategias"].items():
            mejores.append((re_["evaluacion"]["resumen"]["MRR"], re_["evaluacion"]["resumen"]["R@5"], n, e))
    citables = sorted([m for m in mejores if m[3] != "fijo"], reverse=True)
    mrr, r5, n, e = citables[0]
    razon = (f"Es la configuración citable con mayor MRR ({_f(mrr)}) y R@5 ({_f(r5)}). ")
    if e == "fragmento":
        razon += ("Además devuelve exactamente el parágrafo o numeral que responde, con su estado de vigencia y sus "
                  "notas, lo que permite citar con precisión (RF2) y mostrar la fuente (RF5).")
    else:
        razon += ("Al citar se puede indicar el artículo; para señalar el parágrafo o numeral exacto el backend puede "
                  "consultar después los fragmentos de ese artículo.")
    mejor_global = sorted(mejores, reverse=True)[0]
    if mejor_global[3] == "fijo":
        razon += f" La estrategia `fijo` obtuvo MRR {_f(mejor_global[0])}, pero no permite citar artículos con precisión."
    return n, e, razon


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Embeddings + FAISS + comparación de segmentaciones (fase 3).")
    p.add_argument("--corpus", default=str(RAIZ / "datos" / "corpus.json"))
    p.add_argument("--preguntas", default=str(RAIZ / "recursos" / "preguntas_evaluacion.json"))
    p.add_argument("--sinonimos", default=str(RAIZ / "resultados" / "analisis" / "sinonimos.json"), help="para evaluar la expansión de consultas")
    p.add_argument("-o", "--salida", default=str(RAIZ / "resultados" / "indice"))
    p.add_argument("--modelos", nargs="+", default=MODELOS_POR_DEFECTO)
    p.add_argument("--estrategias", nargs="+", default=ESTRATEGIAS, choices=ESTRATEGIAS)
    p.add_argument("--tam", type=int, default=200, help="palabras por ventana (estrategia fijo)")
    p.add_argument("--solape", type=int, default=50, help="palabras de solape (estrategia fijo)")
    p.add_argument("-v", "--detalle", action="store_true")
    p.add_argument("--version", action="version", version=__version__)
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.detalle else logging.INFO, format="%(levelname)s: %(message)s")
    for ruido in ("sentence_transformers", "transformers", "urllib3", "httpx", "huggingface_hub"):
        logging.getLogger(ruido).setLevel(logging.WARNING)

    try:
        corpus = json.loads(Path(a.corpus).read_text(encoding="utf-8"))
        preguntas = json.loads(Path(a.preguntas).read_text(encoding="utf-8"))["preguntas"]
    except (OSError, ValueError, KeyError) as e:
        log.error("No se pudo leer la entrada: %s", e)
        return 1
    articulos_corpus = {f["articulo"] for f in corpus}
    for q in preguntas:
        faltan = set(q["articulos"]) - articulos_corpus
        if faltan:
            log.error("Pregunta %s espera artículos que no están en el corpus: %s", q["id"], faltan)
            return 1

    expandir = None
    if Path(a.sinonimos).is_file():
        from analisis_linguistico import expandir_consulta
        indice_inv = json.loads(Path(a.sinonimos).read_text(encoding="utf-8"))["indice_inverso"]

        def expandir(texto: str) -> str:
            extra = expandir_consulta(texto, indice_inv)
            return texto + (" (" + "; ".join(extra) + ")" if extra else "")

    import faiss
    import sentence_transformers
    salida = Path(a.salida)
    resultados: dict = {}
    unidades_por_e = {e: construir_unidades(corpus, e, a.tam, a.solape) for e in a.estrategias}
    vectores_guardados: dict = {}
    for nombre in a.modelos:
        log.info("Modelo %s", nombre)
        t0 = time.perf_counter()
        modelo = ModeloEmbeddings(nombre)
        r = {"modelo": {"dimension": modelo.dimension, "max_tokens": modelo.max_tokens}, "estrategias": {}}
        for e, unidades in unidades_por_e.items():
            textos = [u["texto_embedding"] for u in unidades]
            t1 = time.perf_counter()
            vectores = modelo.pasajes(textos)
            indice = crear_indice(vectores)
            ev = evaluar(modelo, indice, unidades, preguntas)
            r["estrategias"][e] = {"n_unidades": len(unidades), "truncados": modelo.truncados(textos),
                                   "segundos_embeddings": round(time.perf_counter() - t1, 1), "evaluacion": ev}
            vectores_guardados[(nombre, e)] = (vectores, indice)
            s = ev["resumen"]
            log.info("  %-10s %4d vectores  MRR %.3f  R@5 %.3f  P@1 %.3f", e, len(unidades), s["MRR"], s["R@5"], s["P@1"])
        r["segundos_total"] = round(time.perf_counter() - t0, 1)
        resultados[nombre] = r
        if nombre != a.modelos[-1]:
            del modelo

    n_elegido, e_elegido, razon = elegir(resultados)
    modelo = ModeloEmbeddings(n_elegido)
    datos_e = resultados[n_elegido]["estrategias"][e_elegido]
    elegido = {"modelo": n_elegido, "estrategia": e_elegido, "razon": razon, "n_unidades": datos_e["n_unidades"],
               "dimension": modelo.dimension, "evaluacion": datos_e["evaluacion"]}
    if expandir:
        _, indice = vectores_guardados[(n_elegido, e_elegido)]
        elegido["expansion"] = evaluar(modelo, indice, unidades_por_e[e_elegido], preguntas, expandir)

    s = elegido["evaluacion"]["resumen"]
    if "similitud_max_fuera" in s:
        corte = round((s["similitud_max_dentro"]["min"] + s["similitud_max_fuera"]["max"]) / 2, 3)
        if s["similitud_max_fuera"]["max"] < s["similitud_max_dentro"]["min"]:
            elegido["umbral"] = corte
            elegido["umbral_texto"] = (f"Las dos distribuciones no se solapan en este banco: un umbral de {corte} separa "
                                       "ambos grupos. Se deja como valor inicial en `config.json`; debe revisarse en la "
                                       "fase 6 con el banco completo, y el prompt del LLM sigue siendo la defensa principal.")
        else:
            elegido["umbral"] = None
            elegido["umbral_texto"] = ("Las distribuciones se solapan, así que la similitud sola no basta para "
                                       "rechazar preguntas: el prompt del LLM debe instruirlo a responder que la "
                                       "información no está en el Código cuando el contexto no la contiene.")
    elegido["analisis"] = _analisis(resultados, elegido)

    for (nombre, e), (vectores, indice) in vectores_guardados.items():
        if nombre != n_elegido:
            continue
        config = {"modelo": nombre, "estrategia": e, "dimension": int(vectores.shape[1]), "n_vectores": int(vectores.shape[0]),
                  "tipo_indice": "IndexFlatIP", "metrica": "coseno (vectores normalizados)",
                  "prefijo_consulta": "query: " if "e5" in nombre.lower() else "",
                  "prefijo_pasaje": "passage: " if "e5" in nombre.lower() else "",
                  "umbral_fuera_de_dominio": elegido.get("umbral") if e == e_elegido else None,
                  "elegido": e == e_elegido, "tam_ventana": a.tam if e == "fijo" else None,
                  "solape": a.solape if e == "fijo" else None, "generado": date.today().isoformat(),
                  "corpus": os.path.relpath(Path(a.corpus).resolve(), RAIZ), "norma": corpus[0].get("norma"), "fecha_consulta": corpus[0].get("fecha_consulta")}
        guardar(salida / e, indice, vectores, unidades_por_e[e], config)

    vect_e, _ = vectores_guardados[(n_elegido, e_elegido)]
    pca = grafico_pca(vect_e, unidades_por_e[e_elegido], salida / "embeddings_pca.png",
                      f"Embeddings de {e_elegido}s ({n_elegido.split('/')[-1]}), proyección PCA")
    (salida / "resultados_evaluacion.json").write_text(
        json.dumps({"resultados": resultados, "elegido": elegido}, ensure_ascii=False, indent=1), encoding="utf-8")
    meta = {"norma": corpus[0].get("norma"), "fecha_consulta": corpus[0].get("fecha_consulta"),
            "n_fragmentos": len(corpus), "n_articulos": len(articulos_corpus),
            "n_dentro": sum(1 for q in preguntas if q["articulos"]), "n_fuera": sum(1 for q in preguntas if not q["articulos"]),
            "generado": date.today().isoformat(), "faiss": faiss.__version__, "st": sentence_transformers.__version__,
            "tam": a.tam, "solape": a.solape, "pca": pca}
    (salida / "informe_fase3.md").write_text(informe(resultados, elegido, meta), encoding="utf-8")
    log.info("Elegido: %s + %s. Informe en %s", n_elegido, e_elegido, salida / "informe_fase3.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
