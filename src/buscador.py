#!/usr/bin/env python3
"""Búsqueda semántica sobre el índice FAISS de la fase 3.

Carga el índice elegido (``resultados/indice/<estrategia>/``) y el modelo de embeddings
indicado en su ``config.json``. Es la pieza que usará el servicio FastAPI de
la fase 4 (``/consultar``).

Desde Python:
    from buscador import Buscador
    b = Buscador()  # resultados/indice/fragmento
    for r in b.buscar("¿Qué pasa si no pago una multa?", k=5):
        print(r["puntaje"], r["id"], r["texto"][:80])

Desde la terminal:
    .venv/bin/python src/buscador.py "¿Puede la policía entrar a mi casa sin orden?"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
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


class Buscador:
    def __init__(self, carpeta: str | Path = RAIZ / "resultados" / "indice" / "fragmento",
                 sinonimos: str | Path | None = RAIZ / "resultados" / "analisis" / "sinonimos.json"):
        import torch  # antes que faiss: ver arriba
        torch.set_num_threads(max(1, (os.cpu_count() or 2) - 1))
        import faiss
        from sentence_transformers import SentenceTransformer

        carpeta = Path(carpeta)
        if not (carpeta / "indice.faiss").is_file():
            raise FileNotFoundError(f"No hay índice en {carpeta}; ejecute primero indexacion.py")
        self.config = json.loads((carpeta / "config.json").read_text(encoding="utf-8"))
        self.unidades = json.loads((carpeta / "unidades.json").read_text(encoding="utf-8"))
        self.indice = faiss.read_index(str(carpeta / "indice.faiss"))
        if self.indice.ntotal != len(self.unidades):
            raise ValueError("El índice y unidades.json no tienen el mismo número de elementos")
        self.modelo = SentenceTransformer(self.config["modelo"], device="cpu")
        self.umbral = self.config.get("umbral_fuera_de_dominio")
        self.indice_sinonimos = None
        if sinonimos and Path(sinonimos).is_file():
            self.indice_sinonimos = json.loads(Path(sinonimos).read_text(encoding="utf-8"))["indice_inverso"]

    def terminos_expandidos(self, consulta: str) -> list[str]:
        if not self.indice_sinonimos:
            return []
        from analisis_linguistico import expandir_consulta
        return expandir_consulta(consulta, self.indice_sinonimos)

    def buscar(self, consulta: str, k: int = 5, expandir: bool = False,
               excluir_inexequibles: bool = False) -> list[dict]:
        """Los ``k`` fragmentos más parecidos a la consulta, con su puntaje
        (similitud coseno, de -1 a 1) y sus metadatos."""
        texto = consulta
        if expandir:
            extra = self.terminos_expandidos(consulta)
            if extra:
                texto += " (" + "; ".join(extra) + ")"
        v = self.modelo.encode([self.config.get("prefijo_consulta", "") + texto],
                               normalize_embeddings=True, convert_to_numpy=True).astype("float32")
        n = min(len(self.unidades), k * 3 if excluir_inexequibles else k)
        puntajes, posiciones = self.indice.search(v, n)
        salida = []
        for p, i in zip(puntajes[0], posiciones[0]):
            u = self.unidades[i]
            if excluir_inexequibles and u.get("estado_vigencia") == "inexequible":
                continue
            salida.append({"puntaje": round(float(p), 4), **u})
            if len(salida) == k:
                break
        return salida

    def fuera_de_dominio(self, resultados: list[dict]) -> bool:
        """True si el mejor puntaje queda por debajo del umbral calibrado."""
        return bool(self.umbral is not None and (not resultados or resultados[0]["puntaje"] < self.umbral))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Consulta el índice FAISS del Código.")
    p.add_argument("consulta")
    p.add_argument("-k", type=int, default=5)
    p.add_argument("--indice", default=str(RAIZ / "resultados" / "indice" / "fragmento"))
    p.add_argument("--expandir", action="store_true", help="añadir términos del diccionario de sinónimos")
    a = p.parse_args(argv)
    b = Buscador(a.indice)
    res = b.buscar(a.consulta, a.k, expandir=a.expandir)
    if b.fuera_de_dominio(res):
        print(f"(Puntaje máximo por debajo del umbral {b.umbral}: probablemente no está en el Código)\n")
    for r in res:
        print(f"{r['puntaje']:.3f}  {r['id']:<22} [{r.get('estado_vigencia')}] {r.get('epigrafe', '')}")
        print("       " + r["texto"][:200].replace("\n", " ") + ("…" if len(r["texto"]) > 200 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
