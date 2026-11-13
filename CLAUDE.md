# CLAUDE.md — LexPolicía AI

Guía para trabajar en este proyecto (y para agentes como Claude Code). El
repositorio contiene **dos partes**:

1. **Motor documental (Python)** — el original del equipo (UNIR, PLN): limpia el
   PDF de la Ley 1801 de 2016, lo segmenta y genera el índice FAISS. Carpetas
   `src/`, `datos/`, `recursos/`, `resultados/`, `pruebas/`. Ver `README.md`.
2. **Aplicación (Node.js)** — añadida en la rama `feat/frontend-react-backend-node`:
   - `backend/` — API Express con patrón **RAG**: recupera fragmentos del Código
     y **Gemini** redacta la respuesta citándolos.
   - `frontend/` — **Vite + React**, réplica del mockup "Centro de Mando".

> La **app no necesita Python**: usa el corpus ya exportado (`backend/data/corpus.json`,
> derivado del motor) y las APIs de Gemini. Python solo hace falta si quieres
> regenerar el corpus/índice con el motor original.

---

## Puesta en marcha en otro PC (clonar y ejecutar)

### Requisitos
- **Node.js 18 o superior** (probado con Node 24) y **npm**. Nada más para la app.
- Una **API key gratuita de Google Gemini** → https://aistudio.google.com (botón
  "Get API key").

### 1. Clonar el repositorio y cambiar a la rama de la app
```bash
git clone https://github.com/MarlonPerezR/Chat-Bot-Policia.git
cd Chat-Bot-Policia
git checkout feat/frontend-react-backend-node
```

### 2. Backend (API)
```bash
cd backend
npm install
cp .env.example .env        # en Windows (PowerShell):  Copy-Item .env.example .env
#  Edita .env y pon tu clave:  GEMINI_API_KEY=tu_api_key
npm start                   # API en http://localhost:3001
```
Comprueba que responde: abre http://localhost:3001/api/health → debe decir `"ok":true`.

### 3. Frontend (interfaz)
En **otra terminal**:
```bash
cd frontend
npm install
npm run dev                 # interfaz en http://localhost:5173
```
Abre **http://localhost:5173**. Vite redirige `/api/*` al backend (puerto 3001),
así que ambos deben estar corriendo a la vez.

### 4. (Opcional) Activar búsqueda semántica
Por defecto la búsqueda es **léxica (BM25)** y funciona sin más. Para usar
**búsqueda semántica** con embeddings de Gemini (mejor calidad):
```bash
cd backend
npm run build-index         # genera data/embeddings.json (una sola vez)
# reinicia el backend (npm start) para que lo cargue
```
`build-index` tarda unos minutos por el límite gratuito de Gemini (~100
embeddings/minuto y **1000/día**). Guarda el progreso y **se reanuda** si se corta
(vuelve a ejecutarlo). Si el índice no está completo, el backend usa BM25 solo.

---

## Modelos de Gemini (configurables en `backend/.env`)

| Variable | Valor usado | Notas |
|---|---|---|
| `GEMINI_CHAT_MODEL` | `gemini-flash-lite-latest` | Redacta la respuesta. Ver aviso abajo. |
| `GEMINI_EMBED_MODEL` | `gemini-embedding-001` | Embeddings (dim 768). |

**Aviso sobre disponibilidad (verificado 2026-11-13 con una key gratuita nueva):**
- `text-embedding-004` **no** está disponible → se usa `gemini-embedding-001`.
- `gemini-2.5-flash` y los flash "completos" (`gemini-3.8-flash`,
  `gemini-flash-latest`) devolvían **404/503** para la key de prueba. El único
  estable fue **`gemini-flash-lite-latest`**. Si tu key sí tiene acceso a un
  modelo mejor, cámbialo en `.env` (no hay que tocar código).

---

## Estructura de la app

```
backend/
  server.js        Express: /api/consultar, /api/frecuentes, /api/health + prompt RAG
  gemini.js        cliente REST de Gemini (embeddings + generación)
  retrieval.js     crearBuscador(): motor semántico (coseno) o BM25 según el índice
  build-index.js   genera data/embeddings.json (una vez, reanudable)
  data/corpus.json 1.125 fragmentos de la Ley 1801 (del motor Python)
  .env             GEMINI_API_KEY y modelos — NO se sube al repo
frontend/
  vite.config.js   proxy /api → http://localhost:3001
  src/App.jsx      estado: Home ↔ Chat; llama a /api/consultar
  src/components/   Header, Home, SearchBar, Chat, Message, Sources, Icons
  src/theme.js     tokens de color/tipografía tomados del mockup
```

## Convenciones y notas para agentes
- **Nunca** subas `backend/.env` (contiene la API key). Ya está en `.gitignore`.
- Tampoco `node_modules/`, `frontend/dist/` ni `backend/data/embeddings*.json`.
- El diseño (colores, Montserrat/Poppins, tarjetas) sale del mockup
  `Main.dc.html`; respétalo al tocar el front. Tokens centralizados en `theme.js`.
- El prompt del sistema (en `server.js`) obliga a responder **solo** con los
  fragmentos recuperados y a avisar si la consulta no está en el Código: no
  inventar artículos. Mantén esa restricción.
- Para cambiar el motor de búsqueda (p. ej. conectar el FAISS "oficial" del
  equipo), basta con modificar `backend/retrieval.js`; el front no cambia.
