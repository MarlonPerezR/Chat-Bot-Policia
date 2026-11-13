# chatbot_IA: motor documental del chatbot del Código de Policía (Ley 1801 de 2016)

Parte en Python del proyecto final (UNIR, PLN): del PDF de Función Pública al índice FAISS que consultará la API. El backend (Node.js) y el frontend (React) los desarrolla el resto del equipo.

## Estructura

```text
chatbot_IA/
├── README.md                 este archivo
├── requirements.txt          dependencias de Python
├── src/                      código
│   ├── limpiar_pdfs.py         1. PDF → texto limpio
│   ├── segmentar_codigo.py     2. texto → corpus jerárquico (fase 1)
│   ├── analisis_linguistico.py 3. análisis con spaCy (fase 2)
│   ├── indexacion.py           4. embeddings + FAISS + evaluación (fase 3)
│   └── buscador.py             5. búsqueda semántica (la usará la API, fase 4)
├── datos/
│   ├── fuentes_pdf/            PDF originales de Función Pública (consulta 2026-11-06)
│   ├── limpios/                texto limpio (.txt) y registro de limpieza (.paginas.json)
│   └── corpus.json             corpus segmentado: 1.125 fragmentos con metadatos
├── recursos/                 listas curadas por el equipo
│   ├── terminos.json           glosario, sinónimos, autoridades, lugares, términos KWIC
│   └── preguntas_evaluacion.json  banco de preguntas con artículos esperados
├── resultados/               todo lo que generan los scripts (se puede regenerar)
│   ├── analisis/               fase 2: estadísticas, frecuencias, KWIC, glosario, informe
│   └── indice/                 fase 3: índices FAISS, evaluación, gráfico PCA, informe
├── entregables/              documentos para el profesor
│   ├── 01_documento_corpus.md
│   └── 02_informe_analisis_linguistico.md  (copia de resultados/analisis/informe_linguistico.md)
└── pruebas/                  55 pruebas automáticas (unittest)
```

Las rutas por defecto se calculan desde la raíz del proyecto, así que los scripts funcionan desde cualquier carpeta.

## Pipeline completo

```bash
cd chatbot_IA
.venv/bin/python src/limpiar_pdfs.py datos/fuentes_pdf/ -f --fecha-consulta 2026-11-06
.venv/bin/python src/segmentar_codigo.py
.venv/bin/python src/analisis_linguistico.py
.venv/bin/python src/indexacion.py
.venv/bin/python src/buscador.py "¿Puede la policía entrar a mi casa sin orden?"
```

## Instalación (ya hecha en esta carpeta)

```bash
cd ~/Documents/chatbot_IA
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m spacy download es_core_news_md
```

La primera ejecución de `src/indexacion.py` descarga los modelos de embeddings de Hugging Face (unos 1,6 GB en total; quedan en `~/.cache/huggingface`).

## Limpieza de PDFs: `src/limpiar_pdfs.py`

`limpiar_pdfs.py` extrae el texto de los PDFs que le indiques, le quita los encabezados, los pies de página, los números de página y los caracteres corruptos, y guarda el resultado en la carpeta que elijas. Es la primera etapa de un flujo que luego segmenta el texto, le asigna metadatos y lo exporta a JSON.

### Uso

```bash
# Uno o varios archivos
.venv/bin/python src/limpiar_pdfs.py datos/fuentes_pdf/Ley_1801_de_2016.pdf          # → datos/limpios/

# Todos los PDF de una carpeta (con -r también las subcarpetas)
.venv/bin/python src/limpiar_pdfs.py ~/Downloads/normas/ -r -o otra_carpeta/

# Ver qué encabezados y pies se quitaron
.venv/bin/python src/limpiar_pdfs.py datos/fuentes_pdf/ -v

# Lo que se usó para el corpus (PDF de Función Pública descargados el 6-nov-2026)
.venv/bin/python src/limpiar_pdfs.py datos/fuentes_pdf/ -f --fecha-consulta 2026-11-06
```

Si un resultado ya existe, se omite. Con `-f` se sobrescribe. Un PDF dañado no detiene el lote: se informa del error y se sigue con los demás. Si hubo algún error, el código de salida es 1.

### Qué produce

Por cada `nombre.pdf`, en la carpeta de salida:

| Archivo | Contenido |
|---|---|
| `nombre.txt` | Texto limpio, un párrafo por bloque separado por una línea en blanco. Los párrafos partidos entre páginas se unen. |
| `nombre.paginas.json` | Párrafos por página y metadatos de la limpieza. Es la entrada pensada para la segmentación. |

Estructura del JSON:

```json
{
  "archivo_origen": "Ley_1801_de_2016.pdf",
  "ruta_origen": "datos/fuentes_pdf/Ley_1801_de_2016.pdf",
  "fecha_consulta": "2026-11-06",
  "fecha_procesamiento": "2026-11-12T18:20:11+00:00",
  "extractor": "pymupdf 1.26.5",
  "version_limpiador": "1.1.0",
  "total_paginas": 85,
  "paginas_sin_texto": [],
  "encabezados_pies_eliminados": [
    {"texto": "Departamento Administrativo de la Función Pública",
     "motivo": "repetido", "paginas": [1, 2, 3]}
  ],
  "reparaciones_lexicas": {"con-vivencia": "convivencia", "AAPLICAR": "A APLICAR", "Iey": "ley"},
  "estadisticas": {"ligaduras": 517, "bloques_encabezado_pie_eliminados": 170, "parrafos": 2455},
  "paginas": [
    {"numero": 1, "parrafos": ["LEY 1801 DE 2016", "..."], "ultimo_parrafo_continua": false}
  ]
}
```

`ultimo_parrafo_continua: true` significa que el último párrafo de esa página sigue en la siguiente. La segmentación puede usarlo para unirlos sin perder el número de página.

### Qué limpia y cómo

**Encabezados y pies.** Se revisa la franja superior e inferior de cada página (por defecto el 12 % del alto, `--margen`). Un bloque se elimina si aparece **con el mismo texto y a la misma altura** en al menos el 30 % de las páginas (`--umbral`). Para comparar se ignoran los números, de modo que «Ley 1801 de 2016 **1** EVA» y «… **2** EVA» cuentan como el mismo pie. La condición de la altura protege el contenido: una nota como «(Ver Sentencia C-088 de 2019)» puede repetirse cerca del borde en varias páginas, pero cada vez a una altura distinta, y se conserva.

**Números de página.** En la franja del borde se quitan «12», «- 12 -», «Página 3 de 40», «Pág. 7», «xiv», etc.

**Caracteres corruptos.**
- Mojibake: «investigaciÃ³n» → «investigación», «Â¿» → «¿», «â€œ» → «“».
- Ligaduras: «modiﬁcado» → «modificado».
- Restos de fuentes sin mapa (`(cid:123)`), el carácter de reemplazo `�`, caracteres de control, invisibles (espacio de ancho cero, BOM), de uso privado y sin asignar.
- Viñetas de fuentes Symbol/Wingdings → «•».
- Espacios no separables y raros → espacio normal. Los puntos guía de índices se eliminan.
- Líneas sin letras ni números («_____», «* * *»).
- No se usa NFKC, así que «½», «2º» o los superíndices de las notas no se alteran.

**Párrafos.** Se unen las líneas cortadas por el ancho de la página y las palabras partidas con guion («despla-/zarse» → «desplazarse»; para desactivarlo, `--conservar-guiones`). Abren párrafo propio las líneas que empiezan por viñeta o literal («a)», «1.») y los encabezados de unidad (ARTÍCULO, PARÁGRAFO, CAPÍTULO, TÍTULO, LIBRO, SECCIÓN, ANEXO). Así la segmentación los encuentra al inicio de un párrafo. Una cifra entre paréntesis que repite un número escrito en letras («…más de dos» + «(2) meses») no se toma como viñeta.

**Reparaciones léxicas.** Corrigen restos de maquetación usando el vocabulario del propio documento: solo se cambia algo si el resultado son palabras que el documento usa en otros lugares. Cada cambio queda en `reparaciones_lexicas` del JSON. Para desactivarlas, `--sin-reparacion-lexica`.
- Guion de partición que quedó en mitad de línea: «con-vivencia» → «convivencia». Los compuestos legítimos («minero-ambiental», «PÚBLICO-PRIVADAS») no se tocan.
- Palabras en mayúsculas pegadas (celdas de tabla): «COMPORTAMIENTOSMEDIDA» → «COMPORTAMIENTOS MEDIDA», «AAPLICAR» → «A APLICAR».
- Número pegado a una palabra con mayúscula inicial: «Numeral1» → «Numeral 1». En minúscula («anuales1») se deja, porque suele ser una llamada a nota al pie.
- «I» mayúscula en lugar de «l» a mitad de frase: «la Iey» → «la ley».

En la Ley 1801 hubo 12 formas corregidas (más 24 «NumeralN»); en la Ley 2220, «Iey» (en 28 párrafos); en la Ley 2197, una cabecera pegada.

### Opciones

| Opción | Por defecto | Para qué |
|---|---|---|
| `-o, --salida` | `datos/limpios` | carpeta de resultados (se crea si no existe) |
| `-r, --recursivo` | no | buscar también en subcarpetas (se replica la estructura en la salida) |
| `--formato` | `ambos` | `txt`, `json` o `ambos` |
| `-f, --sobrescribir` | no | reemplazar resultados existentes |
| `--extractor` | `auto` | `pymupdf` (mejor) o `pypdf` (sin posiciones; usa `--lineas-borde`) |
| `--margen` | `0.12` | alto de la franja de búsqueda de encabezados y pies |
| `--umbral` | `0.3` | fracción de páginas en que debe repetirse |
| `--max-repeticiones` | `0` (off) | p. ej. `4`: en libros con un título corrido distinto por capítulo, bastan 4 páginas |
| `--lineas-borde` | `3` | solo con pypdf: líneas revisadas arriba y abajo |
| `--sin-reparacion-lexica` | no | no aplicar las reparaciones léxicas |
| `--fecha-consulta` | — | fecha de descarga de los PDF (AAAA-MM-DD); se guarda en el JSON |
| `-v, --detalle` | no | listar qué se eliminó |

### Limitaciones

- **PDF escaneados**: no tienen capa de texto. El script avisa (`paginas_sin_texto`) y, si ninguna página tiene texto, marca error. Hay que pasarles OCR antes (por ejemplo, `ocrmypdf`).
- **Tablas**: las celdas salen como párrafos sueltos o unidos, sin estructura de tabla.
- **Columnas**: se respeta el orden interno del PDF, que es correcto en casi todos los documentos maquetados. En PDFs con orden interno caótico, los bloques pueden salir desordenados.
- **Notas al pie** de cada página: no se quitan, porque cambian de una página a otra. Se conservan como párrafos al final de su página.
- Con documentos de 1 página solo se pueden quitar los números de página: hacen falta al menos 2 páginas para detectar repeticiones.

## Segmentación: `src/segmentar_codigo.py`

Segunda etapa. Toma el `.txt` limpio de la Ley 1801 de 2016 y genera `corpus.json`, una lista de fragmentos con su ubicación en la jerarquía Libro → Título → Capítulo → Artículo → Parágrafo → Numeral.

```bash
.venv/bin/python src/segmentar_codigo.py   # datos/limpios/Ley_1801_de_2016.txt → datos/corpus.json
```

Desde Python:

```python
import sys; sys.path.insert(0, "src")
from segmentar_codigo import segmentar
corpus = segmentar("datos/limpios/Ley_1801_de_2016.txt", "datos/corpus.json")  # None = no escribir
```

Cada fragmento:

```json
{
  "identificador": "art_27_num_7",
  "norma": "Ley 1801 de 2016",
  "articulo": "27",
  "ubicacion_jerarquica": {
    "libro": "LIBRO SEGUNDO. DE LA LIBERTAD, LOS DERECHOS Y DEBERES ...",
    "titulo": "TÍTULO III. DEL DERECHO DE LAS PERSONAS A LA SEGURIDAD Y A LA DE SUS BIENES",
    "capitulo": "CAPÍTULO I. VIDA E INTEGRIDAD DE LAS PERSONAS"
  },
  "epigrafe": "Comportamientos que ponen en riesgo la vida e integridad",
  "texto": "7. Portar armas neumáticas, ...",
  "estado_vigencia": "vigente",
  "tema": "Comportamientos que ponen en riesgo la vida e integridad",
  "notas": ["(Expresion REVISADA, mediante Sentencia de la Corte Constitucional C-051 de 2020)"],
  "fecha_consulta": "2026-11-06"
}
```

| Identificador | Contenido |
|---|---|
| `art_27` | texto del artículo antes del primer numeral o parágrafo (sin «ARTÍCULO 27.» ni el epígrafe) |
| `art_27_num_3` | numeral 3, con sus literales e incisos |
| `art_27_par_1` | parágrafo 1, incluida la tabla «Numeral N / medida correctiva» |
| `art_27_par_1_num_2` | numeral dentro de un parágrafo |
| `art_17_par_unico`, `art_x_par_transitorio` | parágrafo sin número / transitorio |
| `art_149_inc_2`, `art_149_inc_2_num_1` | segunda lista del artículo cuando la numeración vuelve a 1 |

Detalles:

- **Títulos.** El PDF no trae los rótulos «TÍTULO I», solo el nombre en mayúsculas. Se reconocen como un bloque en mayúsculas seguido de un CAPÍTULO o un ARTÍCULO, y se numeran dentro de cada libro. Las cabeceras de tabla («COMPORTAMIENTOS») no se confunden porque las sigue «Numeral 1».
- **`estado_vigencia`** sale de las notas de Función Pública: `vigente` (por defecto), `inexequible`, `derogado` o `inexequible_parcial` (cuando la nota habla de expresiones o incisos). Una nota genérica «(Declarado INEXEQUIBLE…)» al final del artículo alcanza a todo el artículo; «(Parágrafo 3, declarado INEXEQUIBLE…)» solo a ese fragmento.
- **`notas`** guarda las notas editoriales de Función Pública que acompañan al fragmento: modificaciones («(Modificado por el Art. 3 de la Ley 2318…)», «(Numeral adicionado por…)», «(Corregido por el Art. 9 del Decreto 555…)»), sentencias («(Declarado INEXEQUIBLE…)», «(Ver Sentencia…)») y avisos («NOTA: Ordena reemplazar…»). Salen de `texto`, así que `texto` es solo el contenido normativo. En la Ley 1801 son 193 notas en 164 fragmentos.
- **`norma`** se lee del encabezado «LEY 1801 DE 2016» (o del nombre del archivo); **`fecha_consulta`**, del `.paginas.json` que deja `limpiar_pdfs.py` junto al .txt. Ambos se pueden forzar con `--norma` y `--fecha-consulta`. **`articulo`** es el número del artículo («27», «223A»): sirve para filtrar o reagrupar fragmentos en artículos completos.
- **`tema`** es el epígrafe; si el artículo no tiene (119 y 223A), el nombre del capítulo.
- Avisa de artículos faltantes, repetidos o fuera de orden. Se descarta el preámbulo y todo lo que sigue a las firmas.
- Las leyes modificatorias (Ley 2197, 2000, etc.) **no** se segmentan bien con este script: sus artículos citan entre comillas el texto de la 1801. El texto compilado de Función Pública ya incluye esas modificaciones.

## Análisis lingüístico (fase 2): `src/analisis_linguistico.py`

```bash
.venv/bin/python src/analisis_linguistico.py   # → resultados/analisis/
```

Usa spaCy con `es_core_news_md` (unos 20 s). Normaliza, tokeniza, lematiza, etiqueta POS y reconoce entidades. Las etiquetas AUTORIDAD, LUGAR, MONTO y PLAZO salen de reglas propias; ORGANIZACION y PERSONA, del modelo con un filtro de nombres propios. Produce en `resultados/analisis/`:

| Archivo | Contenido |
|---|---|
| `corpus_procesado.jsonl` | por fragmento: texto normalizado, tokens, lemas, POS, `lemas_contenido` (para BM25) y entidades |
| `estadisticas.json` | artículos, tokens, tipos, TTR y TTR estandarizada, longitudes, POS, entidades, vigencia |
| `frecuencias_lemas.csv`, `ngramas.csv`, `colocaciones.csv` | frecuencias, bigramas/trigramas, colocaciones con PMI, t-score y G² |
| `kwic.txt`, `kwic.json` | concordancias de «multa», «comparendo», «medida correctiva», «espacio público» |
| `glosario.json` | términos jurídicos con frecuencia, artículos y la definición que da el propio Código |
| `sinonimos.json` | término del Código ↔ formas coloquiales, e índice inverso para expandir consultas |
| `informe_linguistico.md` | informe con todo lo anterior (fuente del entregable 2) |

Las listas curadas (términos del glosario y de KWIC, sinónimos, autoridades, lugares) están en `recursos/terminos.json`; el equipo puede ampliarlas y volver a ejecutar. `expandir_consulta("me pusieron un parte", indice)` devuelve `["orden de comparendo"]`.

## Embeddings e índice FAISS (fase 3): `src/indexacion.py`

```bash
.venv/bin/python src/indexacion.py                       # dos modelos × tres segmentaciones
.venv/bin/python src/indexacion.py --modelos intfloat/multilingual-e5-base --estrategias fragmento
```

Compara `intfloat/multilingual-e5-base` y `paraphrase-multilingual-MiniLM-L12-v2` con tres segmentaciones: `fragmento` (los de `corpus.json`, precedidos de «artículo N. Epígrafe.»), `articulo` (artículo completo) y `fijo` (ventanas de 200 palabras con 50 de solape, `--tam`/`--solape`). Las evalúa con `recursos/preguntas_evaluacion.json` (40 preguntas con artículos esperados y 5 fuera de dominio): P@k, R@k, MRR, tamaño del contexto y similitud de las preguntas fuera de dominio. Elige la mejor configuración citable y guarda en `resultados/indice/<estrategia>/`:

| Archivo | Contenido |
|---|---|
| `indice.faiss` | `IndexFlatIP` sobre vectores normalizados (coseno) |
| `embeddings.npy` | matriz de embeddings |
| `unidades.json` | texto y metadatos de cada vector, en el mismo orden |
| `config.json` | modelo, prefijos E5, dimensión, umbral fuera de dominio |

Además, `resultados/indice/informe_fase3.md` (justificación del modelo, tabla comparativa, análisis), `resultados_evaluacion.json` y `embeddings_pca.png`.

**macOS:** PyTorch y FAISS traen cada uno su `libomp` y, cargados juntos, el proceso se cierra. Los scripts fijan `OMP_NUM_THREADS=1` y `KMP_DUPLICATE_LIB_OK=TRUE` antes de importarlos; quien use FAISS y sentence-transformers en otro programa (la API) debe hacer lo mismo.

## Búsqueda: `src/buscador.py`

```python
import sys; sys.path.insert(0, "src")
from buscador import Buscador
b = Buscador()   # resultados/indice/fragmento
resultados = b.buscar("¿Qué pasa si no pago una multa?", k=5, expandir=True)
b.fuera_de_dominio(resultados)   # True si el mejor puntaje está bajo el umbral calibrado
```

Cada resultado trae `puntaje`, `id`, `articulos`, `texto`, `epigrafe`, `ubicacion_jerarquica`, `estado_vigencia` y `notas`: lo que necesita la API para citar (RF2) y mostrar las fuentes (RF5).

## Pruebas

```bash
.venv/bin/python -m unittest discover -s pruebas -v
```

Usan textos y PDFs sintéticos generados en el momento. Las de análisis lingüístico necesitan el modelo de spaCy; las de indexación no descargan modelos.
