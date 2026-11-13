# Corpus del Código Nacional de Seguridad y Convivencia Ciudadana

**Entregable 1.** Este documento describe el archivo `corpus.json`: de dónde sale, cuándo se consultó, cómo se segmentó, qué metadatos tiene y bajo qué condiciones se puede usar.

## 1. Origen

| | |
|---|---|
| Norma | Ley 1801 de 2016, «por la cual se expide el Código Nacional de Seguridad y Convivencia Ciudadana» |
| Fuente | Gestor Normativo (EVA) del Departamento Administrativo de la Función Pública, `funcionpublica.gov.co/eva/gestornormativo` |
| Versión | Texto compilado: Función Pública incorpora en el texto las modificaciones posteriores y las decisiones de la Corte Constitucional, con notas que indican el origen de cada cambio |
| Formato descargado | PDF generado por el Gestor Normativo (metadatos del archivo: autor «Departamento Administrativo de la Función Pública», título «Ley-1801-de-2016-Gestor-Normativo», 85 páginas) |
| Fecha de consulta | **6 de noviembre de 2026**. Coincide con la fecha de creación que registra el propio PDF y queda guardada en el campo `fecha_consulta` de cada fragmento |

Ese mismo día se descargaron, del mismo Gestor Normativo, las normas que modifican o reglamentan el Código. Se usan para verificar las notas de modificación, pero **no** se segmentan como corpus, porque el texto compilado de la Ley 1801 ya incluye sus cambios:

| Norma | Relación con el Código | Notas del corpus que la citan |
|---|---|---|
| Ley 2197 de 2022 | Seguridad ciudadana: modifica y adiciona artículos (p. ej. 27, 180, 223A) | 21 |
| Decreto 555 de 2017 | Corrige yerros de la Ley 1801 | 15 |
| Ley 2000 de 2019 | Consumo, porte y distribución de sustancias psicoactivas en lugares con presencia de menores de edad | 9 |
| Ley 2220 de 2022 | Estatuto de conciliación (conciliación y mediación en convivencia) | 6 |
| Ley 2030 de 2020 | Modifica los artículos 205 y 206 (atribuciones de alcaldes e inspectores) | 3 |
| Ley 2318 de 2023 | Prohíbe el uso de animales para disuadir manifestaciones, motines y asonadas | 3 (+1 que la nota fecha por error en 2013) |
| Ley 2054 de 2020 | Modifica el artículo 119 (lugares para animales domésticos abandonados o aprehendidos) | 2 |
| Ley 1955 de 2019 | Plan Nacional de Desarrollo | 1 |

Una nota cita además la Ley 2455 de 2025, que no se descargó. Su modificación ya está incorporada en el texto compilado.

## 2. Procesamiento

```text
PDF (Función Pública)
  │  limpiar_pdfs.py 1.1.0
  ▼
limpios/Ley_1801_de_2016.txt + .paginas.json
  │  segmentar_codigo.py 1.2.0
  ▼
corpus.json (1.125 fragmentos)
```

**Limpieza** (`limpiar_pdfs.py`):
- Extrae el texto con PyMuPDF.
- Quita el encabezado «Departamento Administrativo de la Función Pública» y el pie «Ley 1801 de 2016 N EVA - Gestor Normativo». Los reconoce porque se repiten con el mismo texto y a la misma altura en muchas páginas.
- Repara los caracteres corruptos y las ligaduras.
- Une las líneas y las palabras partidas por el ancho de la página.
- Corrige restos de maquetación usando el vocabulario del propio documento: «con-vivencia» → «convivencia», «COMPORTAMIENTOSMEDIDA» → «COMPORTAMIENTOS MEDIDA», «Numeral1» → «Numeral 1».
- Cada eliminación y cada corrección queda registrada en `limpios/Ley_1801_de_2016.paginas.json`, para poder auditarla.

**Segmentación** (`segmentar_codigo.py`): ver la sección 3.

Todo el proceso se puede repetir con los comandos del `README.md`, y lo cubren 49 pruebas automáticas.

## 3. Criterios de segmentación

La segmentación es jerárquica y usa expresiones regulares. Recorre el texto párrafo a párrafo y lleva la cuenta de la posición en la jerarquía: **Libro → Título → Capítulo → Artículo → Parágrafo → Numeral**.

1. **Libro**: «LIBRO PRIMERO/SEGUNDO/TERCERO», con su nombre aunque esté partido en varias líneas.
2. **Título**: el PDF de Función Pública no trae los rótulos «TÍTULO I», solo el nombre en mayúsculas.
   - Se reconoce como un bloque en mayúsculas seguido de un CAPÍTULO o de un ARTÍCULO.
   - Se numera dentro de cada libro, con lo que resultan 20 títulos.
   - Las cabeceras de tabla («COMPORTAMIENTOS / MEDIDA CORRECTIVA A APLICAR») no se confunden con títulos, porque las sigue «Numeral 1».
3. **Capítulo**: «CAPÍTULO I», más su nombre (47 capítulos). Algunos títulos tienen artículos antes de su primer capítulo; en esos artículos el capítulo queda vacío.
4. **Artículo**: «ARTÍCULO 27.» y los artículos con letra añadidos por leyes posteriores («ARTÍCULO 185A», «223A», «234A», «237B»).
   - El **epígrafe** es la frase corta que sigue al número, hasta el primer punto. Los artículos 119 y 223A no tienen epígrafe.
5. **Parágrafo**: «PARÁGRAFO 1.», «PARÁGRAFO.» (único) y «PARÁGRAFO TRANSITORIO».
6. **Numeral**: «1.», «2.»… dentro del artículo o de un parágrafo. Los literales «a)», «b)» quedan dentro de su numeral.

Cada artículo se divide en **fragmentos sin solapamiento**. Así el chatbot puede citar exactamente el numeral o parágrafo que responde (RF2), y además se puede reconstruir el artículo completo uniendo sus fragmentos.

| Identificador | Contenido |
|---|---|
| `art_27` | texto del artículo antes del primer numeral o parágrafo |
| `art_27_num_6` | numeral 6, con sus literales |
| `art_27_par_1` | parágrafo 1, incluida la tabla «Numeral N → medida correctiva» |
| `art_27_par_1_num_2` | numeral dentro de un parágrafo |
| `art_180_par_unico`, `art_180_par_transitorio` | parágrafo sin número / transitorio |
| `art_149_inc_2`, `art_149_inc_2_num_1` | segunda lista del artículo cuando la numeración vuelve a 1 (arts. 87 y 149) |

**Exclusiones:** el preámbulo («EL CONGRESO DE COLOMBIA DECRETA») y las firmas finales.

**Resultado:** 249 artículos (del 1 al 243, más 6 con letra) en 1.125 fragmentos:
- 249 de encabezado de artículo;
- 615 numerales;
- 259 parágrafos;
- 23 incisos que reinician una lista;
- más los numerales que hay dentro de parágrafos.

El segmentador avisa si falta un artículo, si hay uno repetido o si alguno aparece fuera de orden. En esta versión no hay ninguno de los tres casos.

## 4. Metadatos de cada fragmento

```json
{
  "identificador": "art_27_num_7",
  "norma": "Ley 1801 de 2016",
  "articulo": "27",
  "ubicacion_jerarquica": {
    "libro": "LIBRO SEGUNDO. DE LA LIBERTAD, LOS DERECHOS Y DEBERES DE LAS PERSONAS EN MATERIA DE CONVIVENCIA",
    "titulo": "TÍTULO III. DEL DERECHO DE LAS PERSONAS A LA SEGURIDAD Y A LA DE SUS BIENES",
    "capitulo": "CAPÍTULO I. VIDA E INTEGRIDAD DE LAS PERSONAS"
  },
  "epigrafe": "Comportamientos que ponen en riesgo la vida e integridad",
  "texto": "7. Portar armas neumáticas, de aire, de fogueo, de letalidad reducida o sprays, ...",
  "estado_vigencia": "vigente",
  "tema": "Comportamientos que ponen en riesgo la vida e integridad",
  "notas": ["(Expresion REVISADA, mediante Sentencia de la Corte Constitucional C-051 de 2020)"],
  "fecha_consulta": "2026-11-06"
}
```

| Campo | Descripción |
|---|---|
| `identificador` | Clave única del fragmento (sección 3). |
| `norma` | Norma de origen. Se lee del encabezado del texto. |
| `articulo` | Número del artículo como texto («27», «223A»). Sirve para filtrar y para reagrupar artículos completos. |
| `ubicacion_jerarquica` | Libro, título y capítulo, con número y nombre. `capitulo` es `null` si el artículo no está dentro de un capítulo. |
| `epigrafe` | Título breve del artículo, o cadena vacía si no tiene. |
| `texto` | Contenido normativo del fragmento, **sin** las notas editoriales. |
| `estado_vigencia` | Se deduce de las notas de Función Pública (ver abajo). |
| `tema` | Epígrafe del artículo. Si no tiene, el nombre del capítulo o del título. |
| `notas` | Notas editoriales de Función Pública que acompañan al fragmento: modificaciones, correcciones, sentencias y avisos. |
| `fecha_consulta` | Fecha de descarga del PDF fuente. |

### Estado de vigencia

| Valor | Cuándo se asigna | Fragmentos |
|---|---|---|
| `vigente` | Por defecto | 972 |
| `inexequible` | La nota declara INEXEQUIBLE el fragmento o el artículo entero. Una nota genérica al final del artículo («(Declarado INEXEQUIBLE…)») se aplica a todos sus fragmentos. | 146 |
| `inexequible_parcial` | La nota se refiere solo a una expresión, un inciso o un literal («Expresión subrayada declarada INEXEQUIBLE»). | 7 |
| `derogado` | La nota dice que fue derogado. | 0 |

**Por artículos:** 212 están vigentes en su totalidad, 30 son inexequibles en su totalidad y 7 tienen fragmentos con estados distintos. Los 30 inexequibles en su totalidad son, sobre todo, los arts. 47 a 75 sobre aglomeraciones de público, que la Corte declaró inexequibles (Sentencia C-223 de 2017).

**Notas:** hay 193 notas en 164 fragmentos, que citan 32 sentencias de la Corte Constitucional.

**Limitación:** el estado se infiere del texto de las notas. Una expresión «declarada inexequible» va subrayada en el original, pero el subrayado no se conserva en el texto plano, así que no se sabe qué palabras exactas afecta. Por eso esos fragmentos se marcan como `inexequible_parcial` y se conservan completos, con la nota.

## 5. Licencia y condiciones de uso

- **Texto de la ley.** Es un texto oficial. Según el artículo 41 de la Ley 23 de 1982 (derechos de autor), las leyes y demás actos oficiales pueden reproducirse libremente, siempre que la reproducción se ajuste a la publicación oficial. El corpus no altera el contenido normativo: solo lo segmenta y separa las notas. Antes de la entrega final conviene confirmar la redacción vigente de ese artículo, porque la Ley 1835 de 2017 modificó parcialmente la Ley 23.
- **Notas editoriales y compilación de Función Pública.** Son información pública de una entidad del Estado. Se citan como fuente y se conservan sin cambios en el campo `notas`.
- **Trabajo propio del equipo.** La segmentación, los metadatos (`identificador`, `ubicacion_jerarquica`, `tema`, `estado_vigencia`) y los scripts se proponen bajo licencia **CC BY 4.0** para los datos y **MIT** para el código, con atribución al equipo y a la fuente.
- **Aviso.** El corpus tiene fines académicos e informativos. No reemplaza la consulta del Diario Oficial ni la asesoría jurídica. La vigencia refleja la compilación de Función Pública al 6 de noviembre de 2026.

## 6. Archivos

| Archivo | Contenido |
|---|---|
| `corpus.json` | 1.125 fragmentos con sus metadatos |
| `limpios/Ley_1801_de_2016.txt` | Texto limpio del que sale el corpus |
| `limpios/Ley_1801_de_2016.paginas.json` | Párrafos por página y registro de la limpieza (eliminaciones, reparaciones, fecha de consulta) |
| `limpios/*` (otras normas) | Textos limpios de las normas modificatorias, para consulta |
| `limpiar_pdfs.py`, `segmentar_codigo.py` | Scripts que generan todo lo anterior |
