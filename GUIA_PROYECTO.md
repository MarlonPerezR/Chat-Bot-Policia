# LexPolicía AI — Centro de Mando (frontend React + API Node)

Asistente ciudadano sobre el **Código Nacional de Seguridad y Convivencia
Ciudadana (Ley 1801 de 2016)**. El usuario pregunta en lenguaje natural; la app
busca los fragmentos relevantes de la ley y **Gemini** redacta la respuesta
citando únicamente esos fragmentos (patrón **RAG**), mostrando además las
fuentes (artículo, epígrafe y estado de vigencia).

## Arquitectura (todo Node.js)

```
Pregunta del usuario
  → [frontend React/Vite]  POST /api/consultar
  → [backend Express]
        1. embebe la pregunta con Gemini (embeddings)
        2. similitud coseno contra los 1.125 fragmentos del Código
        3. envía los mejores fragmentos + la pregunta a gemini-2.5-flash
        4. devuelve { respuesta, fuentes, fuera_de_dominio }
  → el front muestra la respuesta y las tarjetas de fuentes
```

- **Motor documental**: derivado del repo en Python `Chat-Bot-Policia` (UNIR, PLN).
  De ahí viene `backend/data/corpus.json` (los 1.125 fragmentos segmentados de la
  ley con sus metadatos: artículo, jerarquía, vigencia, notas). **No** se usa
  FAISS ni modelos locales: la búsqueda semántica se hace con los embeddings
  gratuitos de Gemini, por eso no hay descargas pesadas ni Python.
- **Diseño**: réplica fiel del mockup `Main.dc.html` (colores, Montserrat/Poppins,
  tarjetas, hero), extendido con una vista de chat en el mismo estilo.

```
Proyecto IA/
├── backend/            API Express + RAG con Gemini
│   ├── server.js         endpoints /api/consultar, /api/frecuentes, /api/health
│   ├── gemini.js         cliente REST de Gemini (embeddings + generación)
│   ├── retrieval.js      carga corpus + embeddings, búsqueda por coseno
│   ├── build-index.js    genera la caché de embeddings (una sola vez)
│   ├── .env              GEMINI_API_KEY y modelos (NO se sube al repo)
│   └── data/
│       ├── corpus.json       corpus de la Ley 1801 (del repo Python)
│       └── embeddings.json   caché de vectores (la genera build-index)
└── frontend/           Vite + React
    └── src/…              Home (hero + frecuentes) y Chat (respuesta + fuentes)
```

## Puesta en marcha

Requisitos: **Node.js 18+** (probado con Node 24). No necesitas Python.

### 1) Backend

```bash
cd backend
npm install
# pon tu clave en .env  (GEMINI_API_KEY=...)  — gratis en https://aistudio.google.com
npm run build-index      # genera data/embeddings.json (una sola vez, ~13 min por el límite gratuito)
npm start                # API en http://localhost:3001
```

> El límite gratuito de Gemini es ~100 embeddings/minuto, así que `build-index`
> va a ese ritmo y tarda unos minutos. Guarda el progreso y se puede **reanudar**
> (vuelve a ejecutarlo si se interrumpe). Solo hay que hacerlo una vez.

### 2) Frontend

```bash
cd frontend
npm install
npm run dev              # http://localhost:5173
```

Vite redirige `/api/*` al backend, así que levanta **los dos** a la vez (dos
terminales). Abre `http://localhost:5173`.

## Modelos (configurables en `backend/.env`)

| Variable | Valor | Uso |
|---|---|---|
| `GEMINI_CHAT_MODEL` | `gemini-2.5-flash` | redacta la respuesta |
| `GEMINI_EMBED_MODEL` | `gemini-embedding-001` | embeddings (dim 768) |

## Notas

- **Seguridad**: `.env` está en `.gitignore`. La API key no debe subirse al repo.
  Si se expuso, rótala en Google AI Studio.
- **Fuera de dominio**: si la mejor coincidencia queda por debajo del umbral, la
  app responde que la consulta no está cubierta por la Ley 1801 (no alucina).
- **Siguiente paso posible**: si el equipo termina la API Node/FAISS "oficial",
  basta cambiar el motor de búsqueda en `backend/retrieval.js`; el front no cambia.
```
