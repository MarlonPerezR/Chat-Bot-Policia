# Backend en Python — estado y pendientes

Este repo contiene el **motor documental en Python** (fases 1-3: limpieza del PDF,
segmentación, análisis lingüístico, embeddings + índice FAISS y búsqueda). La
**fase 4 (el servicio HTTP / API) nunca se construyó**. Este documento resume, con
base en el código actual, **qué falta para que el backend Python sea funcional**
de punta a punta (petición HTTP → respuesta redactada con fuentes).

> La app de la rama `feat/frontend-react-backend-node` ya cubre esta capa **en
> Node.js** (API + RAG + LLM con Gemini). Lo de abajo es lo que faltaría para
> hacerlo equivalente **en Python**, si el equipo prefiere esa vía.

## Lo que YA existe
- Pipeline completo: `src/limpiar_pdfs.py`, `segmentar_codigo.py`,
  `analisis_linguistico.py`, `indexacion.py`, `buscador.py`.
- Datos y resultados versionados: `datos/corpus.json`, `resultados/analisis/*`,
  y por estrategia `resultados/indice/<fragmento|articulo|fijo>/config.json` y
  `unidades.json`.
- `buscador.py` → clase `Buscador` con `.buscar(consulta, k)` y `.fuera_de_dominio()`.

## Lo que FALTA

### 1. Generar el índice FAISS (bloqueante)
`indice.faiss` y `embeddings.npy` están en `.gitignore` y **no están en el repo**.
Sin ellos, `Buscador()` lanza `FileNotFoundError`. Hay que:
- Instalar Python 3 + entorno: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
- Descargar el modelo de spaCy: `.venv/bin/python -m spacy download es_core_news_md`
- Ejecutar `.venv/bin/python src/indexacion.py` → **descarga ~1,6 GB** de modelos de
  Hugging Face la primera vez y genera el índice en `resultados/indice/<estrategia>/`.
- (El resto del pipeline ya está versionado, así que basta `indexacion.py`; opcional
  re-correr desde el PDF.)

### 2. Crear el servicio FastAPI — `POST /consultar` (NO existe)
No hay ningún `api.py` ni rutas; solo se menciona en el docstring de `buscador.py`.
Falta escribir el servicio:
- Añadir dependencias: `fastapi`, `uvicorn[standard]`, `pydantic` (no están en
  `requirements.txt`).
- App que instancie `Buscador` **una sola vez** al arrancar y exponga
  `POST /consultar` (body: consulta, k) devolviendo los resultados de `.buscar()`
  (RF2 citar artículo, RF5 fuentes) y marcando `fuera_de_dominio`.
- **CORS** habilitado para el frontend.
- Importante (de `buscador.py`/README): fijar `OMP_NUM_THREADS=1` y
  `KMP_DUPLICATE_LIB_OK=TRUE` **antes** de importar torch/faiss, o el proceso puede
  caerse al cargar FAISS y sentence-transformers juntos.

### 3. Capa de generación de respuesta (LLM / RAG) (NO existe)
El motor **solo recupera fragmentos**; no redacta respuestas (la única mención a
OpenAI es un comentario sobre embeddings alternativos). Para el "chatbot" falta:
- Un cliente LLM (OpenAI / Anthropic / Gemini) + su SDK en `requirements.txt`.
- Un prompt que redacte la respuesta **citando solo los fragmentos recuperados** y
  avise cuando la consulta no esté en el Código (apoyarse en
  `buscador.fuera_de_dominio()`).
- Clave de API en `.env` (RNF2). El `.gitignore` ya ignora `.env`, pero falta un
  `.env.example` documentando qué variables se necesitan.

### 4. Configuración y despliegue (NO existe)
- `.env.example` con las variables (clave LLM, modelo, puerto).
- Comando de arranque (`uvicorn api:app --port 8000`) documentado.
- Opcional: `Dockerfile` / `docker-compose` para fijar el entorno (Python + modelos).

## Resumen (checklist)

- [ ] Entorno Python + `requirements.txt` + modelo spaCy
- [ ] `src/indexacion.py` ejecutado → `indice.faiss` + `embeddings.npy` (~1,6 GB de descarga)
- [ ] Dependencias API: `fastapi`, `uvicorn`, `pydantic`
- [ ] Servicio `POST /consultar` que use `Buscador` (+ CORS + env vars OMP)
- [ ] Cliente LLM + prompt RAG + `.env` con la clave (generación de respuesta)
- [ ] `.env.example` + comando de arranque (+ Dockerfile opcional)

## Equivalencia con la app Node ya incluida
La rama `feat/frontend-react-backend-node` implementa los puntos **2, 3 y 4** en
Node (ver `backend/server.js`, `retrieval.js`, `gemini.js`) y evita el punto **1**
usando embeddings de Gemini (o BM25) en lugar de FAISS local. Si se quiere la vía
Python, el punto 1 sigue siendo necesario y los puntos 2-4 hay que portarlos.
