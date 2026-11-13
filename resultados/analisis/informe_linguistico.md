# Informe de análisis lingüístico del corpus

**Entregable 2.** Describe el preprocesamiento del corpus y sus estadísticas, frecuencias, n-gramas, colocaciones, concordancias, glosario y sinónimos. Estos resultados orientan el diseño del motor RAG: cómo segmentar y vectorizar, qué búsqueda léxica conviene y cómo expandir las consultas.

**Corpus:** Ley 1801 de 2016 (Código Nacional de Seguridad y Convivencia Ciudadana), texto compilado del Gestor Normativo de Función Pública consultado el 2026-11-06.  
**Herramientas:** spaCy 3.8.7 con el modelo `es_core_news_md` 3.8.0, más reglas propias para entidades del dominio.  
**Generado:** 2026-11-12 con `analisis_linguistico.py` 1.0.0. Todas las cifras se recalculan al volver a ejecutar el script.

## 1. Preprocesamiento

Cada fragmento de `corpus.json` pasa por estos pasos:

1. **Normalización:** Unicode NFC, comillas tipográficas («», “”) a comillas rectas, rayas a guion y espacios múltiples a uno. Se conservan mayúsculas y tildes porque el etiquetador y el reconocedor de entidades las usan; el campo `texto_normalizado` guarda además la versión en minúsculas.
2. **Tokenización** con el tokenizador de spaCy para español (separa signos, paréntesis y contracciones como «al» y «del»).
3. **Lematización** con el lematizador del modelo (por reglas y tablas guiado por la etiqueta POS): «multas» → «multa», «impondrá» → «imponer».
4. **Etiquetado gramatical (POS)** con el esquema Universal Dependencies.
5. **Reconocimiento de entidades:** las etiquetas LOC/ORG/PER del modelo se combinan con reglas propias para AUTORIDAD (lista de autoridades de policía), LUGAR (lugares que menciona el Código), MONTO (salarios mínimos, multas generales tipo 1–4, multas especiales) y PLAZO («cinco (5) días hábiles»). La etiqueta MISC del modelo se descarta porque en este texto marca sobre todo frases en mayúscula inicial.

Para las estadísticas, un **token** es una palabra o cifra (sin signos de puntuación) y un **tipo** es una forma distinta en minúsculas.

## 2. Estadísticas descriptivas

| Medida | Valor |
|---|---|
| Artículos | 249 |
| Fragmentos (artículo, numeral, parágrafo) | 1125 |
| Oraciones | 2640 |
| Tokens | 48680 |
| Tipos (formas distintas) | 4696 |
| Lemas distintos | 3418 |
| Relación tipo/token (TTR) | 0.0965 |
| TTR estandarizada (ventanas de 1.000 tokens) | 0.3637 |
| Hapax legomena (formas que aparecen una vez) | 2172 |
| Longitud media por fragmento (tokens) | 43.27 (mediana 30, máx. 644) |
| Longitud media por artículo completo (tokens) | 195.5 (mediana 115, máx. 1331) |

La TTR global (0.0965) es baja porque depende del tamaño del texto: con 48680 tokens las palabras se repiten mucho. La TTR estandarizada (0.3637) permite comparar con otros textos. El vocabulario jurídico es repetitivo (fórmulas como «medida correctiva a aplicar», «multa general tipo 2»), lo que favorece la búsqueda léxica y el uso de un glosario para expandir consultas.

El fragmento más largo es `art_73_par_unico` (644 tokens) y el artículo más largo es el 135 (1331 tokens). El 90 % de los fragmentos tiene 86 tokens o menos y el 90 % de los artículos 495 o menos; esto se tiene en cuenta en la fase 3 para elegir el tamaño de los fragmentos que se indexan.

**Distribución por libro**

| Libro | Artículos | Fragmentos | Tokens |
|---|---|---|---|
| Libro Primero | 23 | 50 | 2430 |
| Libro Segundo | 125 | 710 | 29251 |
| Libro Tercero | 101 | 365 | 16999 |

**Estado de vigencia de los fragmentos**

| Estado | Fragmentos |
|---|---|
| vigente | 972 |
| inexequible_parcial | 7 |
| inexequible | 146 |

## 3. Etiquetado gramatical (POS)

| Etiqueta | Categoría | Tokens | % |
|---|---|---|---|
| NOUN | sustantivo | 12333 | 25.33 |
| ADP | preposición | 8948 | 18.38 |
| DET | determinante | 6489 | 13.33 |
| ADJ | adjetivo | 5176 | 10.63 |
| VERB | verbo | 3542 | 7.28 |
| PROPN | nombre propio | 3262 | 6.7 |
| CCONJ | conj. coordinante | 2798 | 5.75 |
| NUM | numeral | 1946 | 4.0 |
| PRON | pronombre | 1917 | 3.94 |
| ADV | adverbio | 865 | 1.78 |
| AUX | auxiliar | 864 | 1.77 |
| SCONJ | conj. subordinante | 503 | 1.03 |
| SYM | símbolo | 34 | 0.07 |
| INTJ | interjección | 2 | 0.0 |
| PART | partícula | 1 | 0.0 |

Predominan sustantivos, preposiciones y determinantes: es un texto nominal, típico de la prosa normativa («la imposición del pago de una suma de dinero»). Los verbos aparecen sobre todo en futuro y en infinitivo («será», «impondrá», «portar»), propios de la enumeración de comportamientos prohibidos.

## 4. Entidades reconocidas

| Etiqueta | Menciones | Más frecuentes |
|---|---|---|
| AUTORIDAD | 378 | autoridades de policía, autoridad de policía, policía nacional, gobierno nacional, personal uniformado de la policía nacional, alcaldes, alcalde, inspector de policía |
| LUGAR | 297 | inmuebles, espacio público, inmueble, transporte público, lugares abiertos al público, parques, domicilio, zonas comunes |
| PLAZO | 83 | un año, seis (6) meses, diez (10) días, un (1) año, cinco (5) días siguientes, cinco (5) días hábiles, tres (3) años, doce (12) meses |
| ORGANIZACION | 69 | instituto colombiano de antropología e historia, secretaría de salud, fuerza pública, ministerio de tecnologías de la información y las comunicaciones, contaduría general de la nación, asamblea departamental, ministerio de salud, cámara de comercio |
| MONTO | 58 | multa especial, multas especiales, dos (2) salarios mínimos diarios legales vigentes (smdlv), cuatro (4) salarios mínimos diarios legales vigentes (smdlv), ocho (8) salarios mínimos diarios legales vigentes (smdlv), dieciséis (16) salarios mínimos diarios legales vigentes (smdlv), ciento cincuenta (150) salarios mínimos legales mensuales vigentes, doscientos cincuenta (250) salarios mínimos legales mensuales vigentes |
| PERSONA | 6 | dogo argentino, fila brasileiro, bull terrier, staffordshire terrier, tosa japonés, entidades territoriales ccpet |

AUTORIDAD, LUGAR, MONTO y PLAZO salen de las reglas propias y son fiables. ORGANIZACION y PERSONA vienen del modelo genérico, entrenado con noticias: sin el filtro de nombres propios marcaba como organización o persona las celdas de las tablas («Destrucción de bien», «Suspensión temporal…»), y aun con él quedan errores como las razas de perros potencialmente peligrosos del art. 126 etiquetadas como PERSONA. Para el motor RAG se usan las etiquetas de reglas.

## 5. Frecuencias

Lemas de contenido (sustantivos, verbos, adjetivos, adverbios y nombres propios, sin palabras vacías) más frecuentes:

| Lema | Frecuencia | Por 10.000 tokens | Fragmentos |
|---|---|---|---|
| actividad | 453 | 93.06 | 216 |
| público | 403 | 82.79 | 236 |
| numeral | 367 | 75.39 | 62 |
| policía | 356 | 73.13 | 233 |
| multa | 350 | 71.9 | 81 |
| medida | 304 | 62.45 | 215 |
| autoridad | 295 | 60.6 | 213 |
| general | 280 | 57.52 | 79 |
| parágrafo | 269 | 55.26 | 265 |
| tipo | 261 | 53.62 | 67 |
| comportamiento | 232 | 47.66 | 178 |
| convivencia | 209 | 42.93 | 152 |
| persona | 204 | 41.91 | 164 |
| suspensión | 198 | 40.67 | 61 |
| nacional | 181 | 37.18 | 132 |
| ley | 178 | 36.57 | 133 |
| lugar | 177 | 36.36 | 141 |
| correctivo | 138 | 28.35 | 125 |
| bien | 136 | 27.94 | 96 |
| temporal | 136 | 27.94 | 58 |
| presente | 132 | 27.12 | 114 |
| siguiente | 128 | 26.29 | 123 |
| complejo | 123 | 25.27 | 45 |
| artículo | 120 | 24.65 | 103 |
| norma | 119 | 24.45 | 111 |
| aglomeración | 116 | 23.83 | 55 |
| establecido | 111 | 22.8 | 103 |
| caso | 105 | 21.57 | 91 |
| código | 97 | 19.93 | 85 |
| especial | 96 | 19.72 | 54 |

La lista completa (100 lemas) está en `frecuencias_lemas.csv`.

## 6. N-gramas

Secuencias de dos y tres palabras que no cruzan signos de puntuación y no empiezan ni terminan en palabra vacía.

**Bigramas**

| Bigrama | Frecuencia |
|---|---|
| multa general | 235 |
| general tipo | 226 |
| suspensión temporal | 114 |
| medidas correctivas | 111 |
| policía nacional | 73 |
| público complejas | 69 |
| medida correctiva | 67 |
| espacio público | 52 |
| presente artículo | 50 |
| programa comunitario | 46 |
| actividad pedagógica | 46 |
| multa especial | 44 |
| suspensión definitiva | 42 |
| siguientes medidas | 41 |
| involucren aglomeraciones | 39 |
| presente código | 38 |
| gobierno nacional | 38 |
| personal uniformado | 37 |
| siguientes comportamientos | 34 |
| comportamientos medida | 33 |

**Trigramas**

| Trigrama | Frecuencia |
|---|---|
| multa general tipo | 226 |
| temporal de actividad | 104 |
| aglomeraciones de público | 91 |
| autoridades de policía | 80 |
| autoridad de policía | 49 |
| pedagógica de convivencia | 46 |
| participación en programa | 45 |
| comunitario o actividad | 45 |
| actividades que involucren | 37 |
| correctiva a aplicar | 33 |
| organizadores de actividades | 33 |
| comportamientos medida correctiva | 32 |
| especial por comportamientos | 30 |
| distrital o municipal | 27 |
| comportamientos antes señalados | 27 |
| abiertos al público | 26 |
| niñas y adolescentes | 25 |
| siguientes medidas correctivas | 22 |
| actividad que involucra | 22 |
| definitiva de actividad | 22 |

## 7. Colocaciones

Bigramas de palabras léxicas (frecuencia ≥ 5) ordenados por log-likelihood (G², Dunning 1993). Se incluyen la información mutua puntual (PMI), que premia combinaciones exclusivas aunque sean raras, y el t-score, que premia las frecuentes. Un G² mayor que 10,83 es significativo con p < 0,001.

| Colocación | Frec. | G² | PMI | t-score |
|---|---|---|---|---|
| general tipo | 226 | 2447.57 | 7.194 | 14.931 |
| multa general | 235 | 2347.55 | 6.878 | 15.199 |
| medidas correctivas | 111 | 1354.48 | 8.089 | 10.497 |
| suspensión temporal | 114 | 1198.18 | 7.526 | 10.619 |
| medida correctiva | 67 | 821.26 | 8.374 | 8.161 |
| programa comunitario | 46 | 682.55 | 9.699 | 6.774 |
| público complejas | 69 | 638.56 | 7.174 | 8.249 |
| policía nacional | 73 | 533.99 | 6.127 | 8.422 |
| personal uniformado | 37 | 523.61 | 9.635 | 6.075 |
| espacio público | 52 | 508.28 | 7.1 | 7.159 |
| actividad pedagógica | 46 | 499.01 | 7.758 | 6.751 |
| involucren aglomeraciones | 39 | 462.58 | 8.615 | 6.229 |
| presente artículo | 50 | 451.31 | 7.227 | 7.024 |
| suspensión definitiva | 42 | 439.44 | 7.66 | 6.449 |
| gobierno nacional | 38 | 409.9 | 7.841 | 6.138 |
| comportamiento contrario | 25 | 362.47 | 10.032 | 4.995 |
| interés cultural | 28 | 349.26 | 9.234 | 5.283 |
| multa especial | 44 | 344.58 | 6.394 | 6.554 |
| presente código | 38 | 319.31 | 6.945 | 6.114 |
| siguientes medidas | 41 | 309.02 | 6.402 | 6.327 |
| daños materiales | 23 | 306.34 | 9.723 | 4.79 |
| normatividad vigente | 24 | 288.97 | 9.107 | 4.89 |
| involucran aglomeraciones | 23 | 286.24 | 8.789 | 4.785 |
| autoridad competente | 31 | 285.51 | 7.397 | 5.535 |
| aplicar numeral | 29 | 271.85 | 7.468 | 5.355 |

## 8. Concordancias (KWIC)

### «multa» — 350 ocurrencias

```text
art_27_par_1       ORTAMIENTOS MEDIDA CORRECTIVA A APLICAR Numeral 1  [Multa]  General tipo 2 Numeral 2 Amonestación; Participac
art_27_par_1        o actividad pedagógica de convivencia. Numeral 3  [Multa]  General tipo 3. Numeral 4 Participación en progra
art_27_par_1       omunitario o actividad pedagógica de convivencia;  [Multa]  General tipo 2. Numeral 5 Construcción, cerramien
art_27_par_1       ebles o inmuebles; Destrucción de bien. Numeral 6  [Multa]  General tipo 2; Prohibición de ingreso a activida
art_27_par_1       as o no complejas; Destrucción de bien. Numeral 7  [Multa]  General tipo 2; Prohibición de ingreso a activida
art_28_par_unico   ORTAMIENTOS MEDIDA CORRECTIVA A APLICAR Numeral 1  [Multa]  General tipo 3; Remoción de bienes, Destrucción d
art_28_par_unico   emoción de bienes, Destrucción de bien. Numeral 2  [Multa]  General tipo 3; Reparación de daños materiales de
art_28_par_unico   años materiales de muebles o inmuebles. Numeral 3  [Multa]  General tipo 4 Numeral 4 Multa General Tipo 3; Re
art_28_par_unico   muebles. Numeral 3 Multa General tipo 4 Numeral 4  [Multa]  General Tipo 3; Reparación de daños materiales de
art_30_par_3       PORTAMIENTOS MEDIDA CORRECTIVAA APLICAR Numeral 1  [Multa]  General tipo 4. Destrucción de bien. Suspensión t
art_30_par_3       bien. Suspensión temporal de actividad. Numeral 2  [Multa]  General tipo 4. Destrucción de bien. Suspensión t
art_30_par_3        Suspensión definitiva de la actividad. Numeral 3  [Multa]  General tipo 4. Destrucción de bien. Numeral 4 Mu
```
Se muestran 12 de 350; todas están en `kwic.txt`.

### «comparendo» — 19 ocurrencias

```text
art_154_par_1      o de policía in situ quedará plasmado en orden de  [comparendo]  o en sala de mediación policial, se dejará consta
art_180_par_unico  a imposición de multa general, impondrán orden de  [comparendo]  al infractor, evidenciando el hecho. Es deber de 
art_180_par_unico  o (5) días hábiles siguientes a la expedición del  [comparendo] , se le disminuirá el valor de la multa en un cinc
art_180_par_unico  o (5) días hábiles siguientes a la expedición del  [comparendo] , solicitar a la autoridad de policía que se conmu
art_180_par_unico  la aplicación de la multa señalada en la orden de  [comparendo]  o con el cumplimiento de la medida de participaci
art_180_par_transitorio los cinco (5) días siguientes a la expedición del  [comparendo]  . *jurisprudencia*                               
art_181_num_2      integridad urbanística no se impondrá a través de  [comparendo] . El personal uniformado de la Policía Nacional po
art_185A           udo a nivel nacional de los pagos por concepto de  [comparendos]  y medidas correctivas impuestas por los Inspector
art_185A            diversas materias, entre ellas, la aplicación de  [comparendos] .                                                 
art_185A_par_2     udo a nivel nacional de los pagos por concepto de  [comparendos]  y medidas correctivas impuestas por los Inspector
art_219            ontrario a la convivencia, podrá expedir orden de  [comparendo]  a cualquier persona. Sin perjuicio de la aplicaci
art_219_par_1      eraciones de público, no se impondrán en orden de  [comparendo] . El personal uniformado de la Policía Nacional po
```
Se muestran 12 de 19; todas están en `kwic.txt`.

### «medida correctiva» — 171 ocurrencias

```text
art_8              razonabilidad. La adopción de medios de Policía y  [medidas correctivas]  debe ser proporcional y razonable atendiendo las 
art_10             establecido en este Código, para la imposición de  [medidas correctivas] . Colaborar con las autoridades judiciales para la
art_11             para la convivencia y establecer los medios y las  [medidas correctivas]  en caso de su incumplimiento.                    
art_12_num_2                                  2. Establecer medios o  [medidas correctivas]  diferentes a las previstas por el legislador.    
art_13             Policía, ciñéndose a los medios, procedimientos y  [medidas correctivas]  establecidas en la presente ley. Estas Corporacio
art_13_num_2                  2. Establecer medios, procedimientos o  [medidas correctivas]  diferentes a las previstas por el legislador.    
art_17             mentos no podrán regular comportamientos, imponer  [medidas correctivas]  o crear procedimientos distintos a los establecid
art_20             s el ejercicio de materialización de los medios y  [medidas correctivas] , de acuerdo con las atribuciones constitucionales
art_25             entos contrarios a la convivencia serán objeto de  [medidas correctivas]  de conformidad con esta ley, sin perjuicio de las
art_25_par_2       ya una conducta tipificada en el Código Penal, la  [medida correctiva]  a imponer no podrá tener la misma naturaleza que 
art_27_par_1       s, será objeto de la aplicación de las siguientes  [medidas correctivas] : COMPORTAMIENTOS MEDIDA CORRECTIVA A APLICAR Nume
art_27_par_1       s siguientes medidas correctivas: COMPORTAMIENTOS  [MEDIDA CORRECTIVA]  A APLICAR Numeral 1 Multa General tipo 2 Numeral 
```
Se muestran 12 de 171; todas están en `kwic.txt`.

### «espacio público» — 56 ocurrencias

```text
art_2_num_1        mportamientos que favorezcan la convivencia en el  [espacio público] , áreas comunes, lugares abiertos al público o que
art_30_num_2        actos circenses, prender o manipular fuego en el  [espacio público] , lugar abierto al público, sin contar con la auto
art_32_num_1       ienes muebles o inmuebles que se encuentran en el  [espacio público] , en lugar privado abierto al público o utilizados
art_33_num_2                                                   2. En  [espacio público] , lugares abiertos al público, o que siendo privad
art_34_num_3       s psicoactivas - incluso la dosis personal- en el  [espacio público]  o lugares abiertos al público ubicados dentro del
art_34_num_4        bebidas alcohólicas, sustancias prohibidas en el  [espacio público]  o lugares abiertos al público dentro del perímetr
art_36             podrá restringir su movilidad o permanencia en el  [espacio público]  o en lugares abiertos al público, de manera tempo
art_40_num_5       manifestaciones y reuniones de las personas en el  [espacio público]  o en lugares privados, en razón a su etnia, raza,
art_47_num_1       ones o manifestaciones públicas y pacíficas en el  [espacio público] .                                                 
art_49_par_1       expendio y/o consumo de bebidas alcohólicas en el  [espacio público]  que esté alrededor del recinto donde se lleva a c
art_50                                        Al terminar el uso del  [espacio público]  para el desarrollo de actividades que generen agl
art_51                                           En caso de daños al  [espacio público]  que ocurran con ocasión de actividades de aglomer
```
Se muestran 12 de 56; todas están en `kwic.txt`.

## 9. Glosario de términos jurídicos

Términos elegidos a partir de las frecuencias, las colocaciones y los artículos de definiciones del Código (arts. 5, 32, 139, 218, entre otros). La definición se toma literalmente del Código cuando éste la da («se entiende por…», epígrafe «Definición de…» o artículo dedicado al término).

- **convivencia** — 209 ocurrencias en 104 artículos (arts. 1, 2, 4, 5, 6, 7, 10, 11, 12, 16…).
  - *Definición (art_5):* Para los efectos de este Código, se entiende por convivencia, la interacción pacífica, respetuosa y armónica entre las personas, con los bienes, y con el ambiente, en el marco del ordenamiento jurídico.
- **privacidad** — 3 ocurrencias en 3 artículos (arts. 31, 32, 206).
  - *Definición (art_32):* Para efectos de este Código, se entiende por privacidad de las personas el derecho de ellas a satisfacer sus necesidades y desarrollar sus actividades en un ámbito que le sea exclusivo y por lo tanto considerado como privado.
- **espacio público** — 56 ocurrencias en 34 artículos (arts. 2, 30, 32, 33, 34, 36, 40, 47, 49, 50…).
  - *Definición (art_139):* Es el conjunto de muebles e inmuebles públicos, bienes de uso público, bienes fiscales, áreas protegidas y de especial importancia ecológica y los elementos arquitectónicos y naturales de los inmuebles privados, destinados por su naturaleza, usos o afectación, a la satisfacción de necesidades colectivas que trascienden los límites de los intereses individuales de todas las personas en el territorio nacional.
- **bienes fiscales** — 7 ocurrencias en 6 artículos (arts. 77, 135, 139, 140, 225, 226).
  - *Definición (art_139_par_1):* Para efectos de este Código se entiende por bienes fiscales, además de los enunciados por el artículo 674 del Código Civil, los de propiedad de entidades de derecho público, cuyo uso generalmente no pertenece a todos los habitantes y sirven como medios necesarios para la prestación de las funciones y los servicios públicos, tales como los edificios, granjas experimentales, lotes de terreno destinados a obras de infraestructura dirigidas a la instalación o dotación de servicios públicos y los…
- **bienes de uso público** — 7 ocurrencias en 5 artículos (arts. 77, 135, 139, 181, 226).
  - *Definición (art_139_par_2):* Para efectos de este Código se entiende por bienes de uso público los que permanentemente están al uso, goce, disfrute de todos los habitantes de un territorio, como por ejemplo los parques, caminos o vías públicas y las aguas que corren.
- **aglomeraciones de público** — 111 ocurrencias en 32 artículos (arts. 27, 33, 47, 48, 50, 51, 52, 58, 59, 60…).
  - *Definición (art_47):* Para efectos de las obligaciones relacionadas con el derecho de reunión, entiéndase como aglomeración de público toda reunión de un número plural de personas producto de una convocatoria individual o colectiva.
- **plan de emergencia y contingencia** — 7 ocurrencias en 5 artículos (arts. 63, 64, 65, 68, 73).
  - *Definición (art_64):* Se entiende por plan de emergencia y contingencia el documento básico que prepara el organizador de espectáculos, actividades culturales en el espacio público, mediante el cual se señalan los lineamientos generales para proyectar, presentar y cumplir su realización.
- **estacionamiento** — 7 ocurrencias en 3 artículos (arts. 32, 89, 90).
  - *Definición (art_89):* Son los bienes públicos o privados, destinados y autorizados de acuerdo con lo dispuesto en las normas de uso del suelo y en las normas que lo desarrollen o complementen por los concejos distritales o municipales, para el estacionamiento y depósito temporal de vehículos automotores, motos o bicicletas, a título oneroso o gratuito.
- **medio de transporte** — 19 ocurrencias en 10 artículos (arts. 30, 123, 124, 134, 146, 147, 149, 158, 160, 202).
  - *Definición (art_160_par_1):* Se entiende por medio de transporte todo medio que permita la movilización o el desplazamiento de una persona o grupo de personas, de un lugar a otro, independientemente de sus características o tipo de tracción utilizada.
- **equipo terminal móvil** — 16 ocurrencias en 3 artículos (arts. 87, 95, 164).
  - *Definición (art_95_par_1):* Se entiende por equipo terminal móvil, todo dispositivo que posea un IMEI (Identificador Internacional de Equipo Móvil), por sus siglas en inglés, o aquel identificador que cumpla una función equivalente a este, y por medio del cual el usuario accede a las redes de telecomunicaciones móviles para la prestación de servicios de comunicaciones de voz y/o datos.
- **orden de policía** — 16 ocurrencias en 10 artículos (arts. 35, 38, 149, 150, 156, 176, 186, 188, 222, 223).
  - *Definición (art_150):* La orden de Policía es un mandato claro, preciso y conciso dirigido en forma individual o de carácter general, escrito o verbal, emanado de la autoridad de Policía, para prevenir o superar comportamientos o hechos contrarios a la convivencia, o para restablecerla.
- **orden de comparendo** — 12 ocurrencias en 4 artículos (arts. 154, 180, 219, 223A).
  - *Definición (art_218):* Entiéndase por esta, la acción del personal uniformado de la Policía Nacional que consiste en entregar un documento oficial que contiene orden escrita o virtual para presentarse ante autoridad de Policía o cumplir medida correctiva.
- **medida correctiva** — 171 ocurrencias en 87 artículos (arts. 8, 10, 11, 12, 13, 17, 20, 25, 27, 28…).
  - *Definición (art_172):* Las medidas correctivas, son acciones impuestas por las autoridades de Policía a toda persona que incurra en comportamientos contrarios a la convivencia o el incumplimiento de los deberes específicos de convivencia.
- **medio de policía** — 8 ocurrencias en 4 artículos (arts. 8, 35, 149, 155).
  - *Definición (art_149):* Los medios de Policía son los instrumentos jurídicos con que cuentan las autoridades competentes para el cumplimiento efectivo de la función y actividad de Policía, así como para la imposición de las medidas correctivas contempladas en este Código.
- **poder de policía** — 2 ocurrencias en 2 artículos (arts. 11, 16).
  - *Definición (art_11):* El poder de Policía es la facultad de expedir las normas en materia de Policía, que son de carácter general, impersonal y abstracto, ejercido por el Congreso de la República para regular el ejercicio de la libertad, los derechos y los deberes constitucionales, para la convivencia y establecer los medios y las medidas correctivas en caso de su incumplimiento.
- **función de policía** — 5 ocurrencias en 5 artículos (arts. 20, 199, 201, 205, 206).
  - *Definición (art_16):* Consiste en la facultad de hacer cumplir las disposiciones dictadas en ejercicio del poder de Policía, mediante la expedición de reglamentos generales y de acciones apropiadas para garantizar la convivencia.
- **actividad de policía** — 18 ocurrencias en 15 artículos (arts. 1, 19, 20, 92, 93, 94, 95, 101, 110, 149…).
  - *Definición (art_20):* Es el ejercicio de materialización de los medios y medidas correctivas, de acuerdo con las atribuciones constitucionales, legales y reglamentarias conferidas a los uniformados de la Policía Nacional, para concretar y hacer cumplir las decisiones dictadas en ejercicio del poder y la función de Policía, a las cuales está subordinada.
- **amonestación** — 30 ocurrencias en 15 artículos (arts. 27, 33, 39, 40, 44, 59, 74, 94, 100, 101…).
  - *Definición (art_174):* Es un llamado de atención en privado o en público con el objetivo de concientizar a la persona de la conducta realizada y de su efecto negativo para la convivencia, en procura de un reconocimiento de la conducta equivocada, el compromiso a futuro de no repetición y el respeto a las normas de convivencia.
- **participación en programa comunitario o actividad pedagógica de convivencia** — 43 ocurrencias en 19 artículos (arts. 27, 35, 39, 45, 59, 74, 92, 101, 111, 115…).
  - *Definición (art_175):* Es la obligación de participar en una actividad de interés público o programa pedagógico en materia de convivencia, organizado por la administración distrital o municipal, en todo caso tendrá una duración de hasta seis (6) horas.
- **multa** — 350 ocurrencias en 56 artículos (arts. 27, 28, 30, 33, 34, 35, 38, 40, 44, 45…).
  - *Definición (art_180):* Es la imposición del pago de una suma de dinero en moneda colombiana, cuya graduación depende del comportamiento realizado, según la cual varia el monto de la multa.
- **multa general** — 236 ocurrencias en 39 artículos (arts. 27, 28, 30, 33, 34, 35, 38, 40, 44, 45…).
  - *El Código no lo define; uso (art_33_par_1):* Multa General tipo 3; Disolución de reunión o actividad que involucra aglomeraciones de público no complejas.
- **multa especial** — 46 ocurrencias en 6 artículos (arts. 51, 73, 135, 140, 180, 181).
  - *Definición (art_181):* Las multas especiales se clasifican en tres tipos:
- **decomiso** — 15 ocurrencias en 8 artículos (arts. 93, 101, 105, 115, 134, 140, 173, 206).
  - *Definición (art_179):* Es la privación de manera definitiva de la tenencia o la propiedad de bienes muebles no sujetos a registro, utilizados por una persona en comportamientos contrarios a las normas de convivencia, mediante acto motivado.
- **destrucción de bien** — 58 ocurrencias en 19 artículos (arts. 27, 28, 30, 34, 38, 59, 74, 92, 93, 95…).
  - *Definición (art_192):* Consiste en destruir por motivos de interés general un bien mueble cuando implique un riesgo o amenaza a la convivencia o al ambiente, o sea utilizado de manera ilegal con perjuicio a terceros.
- **demolición de obra** — 8 ocurrencias en 4 artículos (arts. 135, 173, 193, 206).
  - *Definición (art_194):* Consiste en la destrucción de edificación desarrollada con violación de las normas urbanísticas, ambientales o de ordenamiento territorial, o cuando la edificación amenaza ruina, para facilitar la evacuación de personas, para superar o evitar incendios, o para prevenir una emergencia o calamidad pública.
- **suspensión temporal de actividad** — 105 ocurrencias en 18 artículos (arts. 30, 34, 38, 44, 88, 92, 93, 94, 95, 100…).
  - *Definición (art_196):* Es el cese por un término de entre tres (3) a diez (10) días proporcional a la gravedad de la infracción, de una actividad económica o sin ánimo de lucro, o que siendo privada ofrezca servicios al público a la que está dedicada una persona natural o jurídica.
- **suspensión definitiva de actividad** — 22 ocurrencias en 8 artículos (arts. 38, 46, 92, 95, 105, 110, 173, 206).
  - *Definición (art_197):* Es el cese definitivo de una actividad económica, formal o informal, con o sin ánimo de lucro, o que siendo privada ofrezca servicios al público a la que está dedicada una persona natural o jurídica; comprende la suspensión definitiva de la autorización o permiso dado a la persona o al establecimiento respectivo, para el desarrollo de la actividad.
- **remoción de bienes** — 15 ocurrencias en 9 artículos (arts. 27, 28, 135, 140, 144, 173, 206, 209, 210).
  - *Definición (art_187):* Es la orden dada a una persona para que remueva de manera definitiva bienes muebles de su propiedad, bajo su posesión, tenencia o bajo su responsabilidad cuando contraríen las normas de convivencia.
- **inutilización de bienes** — 12 ocurrencias en 6 artículos (arts. 103, 105, 173, 209, 210, 222).
  - *Definición (art_191):* Consiste en la inhabilitación total de los bienes empleados para actividades ilícitas que atenten contra los recursos naturales, o ingresen, permanezcan, operen, en áreas protegidas y de especial importancia ecológica.
- **restitución y protección de bienes inmuebles** — 8 ocurrencias en 5 artículos (arts. 77, 103, 105, 173, 206).
  - *Definición (art_190):* Consiste en devolver la posesión o tenencia a quien tiene el legítimo derecho sobre los bienes inmuebles de particulares, baldíos, fiscales, de uso público, área protegida y de especial importancia ecológica¸ bienes de empresas destinados a servicios públicos cuando hayan sido ocupadas o perturbadas por vías de hecho.
- **reparación de daños materiales** — 21 ocurrencias en 10 artículos (arts. 27, 28, 51, 77, 78, 135, 140, 146, 173, 206).
  - *El Código no lo define; uso (art_27_par_1):* Construcción, cerramiento, reparación o mantenimiento de inmuebles; Remoción de bienes; Reparación de daños materiales de muebles o inmuebles; Destrucción de bien.
- **traslado por protección** — 12 ocurrencias en 2 artículos (arts. 149, 155).
  - *Definición (art_155):* Cuando la vida e integridad de una persona natural se encuentre en riesgo o peligro y no acepte la mediación policial corno mecanismo para la solución del desacuerdo, el personal uniformado de la Policía Nacional, podrá trasladarla para su protección en los siguientes casos:
- **centro de traslado por protección** — 7 ocurrencias en 1 artículos (arts. 155).
  - *El Código no lo define; uso (art_155_par_2):* El personal uniformado de la Policía Nacional, entregara la persona a un familiar que asuma su protección, o en su defecto al coordinador del Centro de Traslado por Protección, para que garantice sus derechos, lo anterior con estricta observancia de lo dispuesto en el Parágrafo 4 del presente Artículo.
- **retiro del sitio** — 1 ocurrencias en 1 artículos (arts. 149).
  - *El Código no lo define; uso (art_149_inc_2_num_2):* Retiro del sitio.
- **registro** — 58 ocurrencias en 28 artículos (arts. 68, 79, 82, 87, 92, 95, 101, 105, 112, 124…).
  - *Definición (art_158):* Acción que busca identificar o encontrar elementos, para prevenir o poner fin a un comportamiento contrario a norma de convivencia o en desarrollo de actividad de Policía, la cual se realiza sobre las personas y medios de transporte, sus pertenencias y bienes muebles e inmuebles, de conformidad con lo establecido en la ley.
- **uso de la fuerza** — 9 ocurrencias en 6 artículos (arts. 10, 56, 140, 149, 162, 166).
  - *Definición (art_166):* Es el medio material, necesario, proporcional y racional, empleado por el personal uniformado de la Policía Nacional, como último recurso físico para proteger la vida e integridad física de las personas incluida la de ellos mismos, sin mandamiento previo y escrito, para prevenir, impedir o superar la amenaza o perturbación de la convivencia y la seguridad pública, de conformidad con la ley.
- **aprehensión con fin judicial** — 1 ocurrencias en 1 artículos (arts. 149).
  - *Definición (art_168):* El personal uniformado de la Policía Nacional, podrá aprehender a una persona en sitio público o abierto al público, o privado, cuando sea señalada de haber cometido infracción penal o sorprendida en flagrante delito o cuando un particular haya pedido auxilio o la haya aprehendido, siempre que el solicitante concurra conjuntamente al despacho del funcionario que deba recibir formalmente la denuncia.
- **incautación** — 5 ocurrencias en 4 artículos (arts. 140, 149, 164, 165).
  - *Definición (art_164):* Es la aprehensión material transitoria de bienes muebles, semovientes, flora y fauna silvestre que efectúa el personal uniformado de la Policía Nacional, cuya tenencia, venta, oferta, suministro, distribución, transporte, almacenamiento, importación, exportación, porte, conservación, elaboración o utilización, constituya comportamiento contrario a la convivencia y a la ley.
- **proceso verbal inmediato** — 3 ocurrencias en 3 artículos (arts. 157, 210, 222).
  - *Definición (art_222):* Se tramitarán por el proceso verbal inmediato los comportamientos contrarios a la convivencia, de competencia del personal uniformado de la Policía Nacional, los comandantes de estación o subestación de Policía, y los comandantes del Centro de Atención Inmediata de Policía, en las etapas siguientes:
- **proceso verbal abreviado** — 6 ocurrencias en 6 artículos (arts. 222, 223, 223A, 224, 234A, 242).
  - *Definición (art_223):* Se tramitarán por el proceso verbal abreviado los comportamientos contrarios a la convivencia, de competencia de los Inspectores de Policía, los Alcaldes y las autoridades especiales de Policía, en las etapas siguientes:
- **registro nacional de medidas correctivas** — 7 ocurrencias en 5 artículos (arts. 182, 184, 185A, 185B, 223A).
  - *Definición (art_184):* La Policía Nacional llevará un registro nacional de medidas correctivas que incluirá la identificación de la persona, el tipo de comportamiento contrario a la convivencia, el tipo de medida correctiva y el estado de pago de la multa o cumplimiento de la medida correctiva.
- **salarios mínimos diarios legales vigentes** — 4 ocurrencias en 1 artículos (arts. 180).
  - *El Código no lo define; uso (art_180):* Multa Tipo 1: Dos (2) salarios mínimos diarios legales vigentes (smdlv).
- **personal uniformado de la policía nacional** — 33 ocurrencias en 20 artículos (arts. 72, 155, 156, 159, 160, 162, 163, 164, 165, 166…).
  - *El Código no lo define; uso (art_72):* El personal uniformado de la Policía Nacional, podrá ingresar a los lugares en que se desarrollen actividades que involucren aglomeraciones de públicos complejas o no complejas, en cualquier momento y solamente para cumplir con su función.
- **inspector de policía** — 16 ocurrencias en 13 artículos (arts. 79, 82, 179, 181, 185B, 198, 205, 206, 210, 222…).
  - *El Código no lo define; uso (art_79):* Para el ejercicio de la acción de Policía en el caso de la perturbación de los derechos de que trata este título, las siguientes personas, podrán instaurar querella ante el inspector de Policía, mediante el procedimiento único estipulado en este Código:
- **corregidor** — 4 ocurrencias en 3 artículos (arts. 198, 205, 207).
  - *El Código no lo define; uso (art_205_num_8):* Resolver el recurso de apelación en el procedimiento verbal abreviado, cuando no exista autoridad especial de Policía en el municipio o distrito a quien se le haya atribuido, en relación con las medidas correctivas que aplican los inspectores de Policía rurales y urbanos o corregidores, en primera instancia.
- **comandante de estación** — 7 ocurrencias en 7 artículos (arts. 19, 87, 92, 198, 209, 222, 232).
  - *El Código no lo define; uso (art_19):* Este Comité estará conformado por el Alcalde, el Personero Municipal y el Comandante de Estación del respectivo distrito, municipio o localidad.
- **alcalde** — 50 ocurrencias en 36 artículos (arts. 14, 15, 17, 19, 29, 30, 34, 36, 37, 49…).
  - *Definición (art_204):* El alcalde es la primera autoridad de Policía del Distrito o Municipio.
- **sustancias psicoactivas** — 18 ocurrencias en 10 artículos (arts. 27, 34, 38, 39, 41, 59, 74, 134, 140, 155).
  - *El Código no lo define; uso (art_27_num_11):* (sic) Portar armas, elementos y dispositivos menos letales bajo el influjo de sustancias psicoactivas ilícitas o prohibidas, o en estado de embriaguez.
- **bebidas alcohólicas** — 16 ocurrencias en 8 artículos (arts. 34, 38, 49, 74, 85, 140, 155, 202).
  - *El Código no lo define; uso (art_49):* En los lugares habilitados para aglomeraciones, se autoriza el consumo de bebidas alcohólicas de acuerdo con las siguientes disposiciones:
- **infracción urbanística** — 22 ocurrencias en 7 artículos (arts. 135, 136, 137, 180, 181, 206, 223).
  - *El Código no lo define; uso (art_135_par_7):* Multa especial por infracción urbanística; Demolición de obra; Construcción, cerramiento, reparación o mantenimiento de inmueble; Remoción de bienes.
- **contaminación visual** — 4 ocurrencias en 4 artículos (arts. 51, 140, 180, 181).
  - *El Código no lo define; uso (art_51):* En caso de daños al espacio público que ocurran con ocasión de actividades de aglomeraciones de público complejas y no complejas se impondrá multa especial por contaminación visual y las medidas correctivas de destrucción del bien y reparación de daños materiales de muebles e inmuebles de que trata el presente Código, a los empresarios del espectáculo público y coordinadores logísticos del evento.
- **mascota** — 11 ocurrencias en 8 artículos (arts. 101, 117, 120, 122, 123, 124, 134, 146).
  - *El Código no lo define; uso (art_117):* Solo podrán tenerse como mascotas los animales así autorizados por la normatividad vigente.

**Otros candidatos** (grupos nominales frecuentes que aún no están en el glosario): medidas correctivas (104), público complejas (69), aglomeraciones de público complejas (69), programa comunitario (45), actividad pedagógica (45), personal uniformado (37), organizadores de actividades (33), autoridad competente (31), comportamientos de los organizadores (30), objeto de la aplicación (29), normas vigentes (25), comportamiento contrario (25), normatividad vigente (24), actividad económica (24), comportamientos contrarios (23), daños materiales (23), suspensión temporal (23), interés cultural (22), comportamientos señalados (21), aglomeración de público (19), territorio nacional (18), servicios públicos (18), transporte público (18), medida de suspensión (18), autoridades competentes (17).

## 10. Sinónimos coloquiales para expandir consultas

Lista curada a mano en `recursos/terminos.json`: relaciona la forma en que un ciudadano pregunta con el término que usa el Código. La función `expandir_consulta()` la aplica en la fase 4, por ejemplo «me pusieron un parte» → «orden de comparendo».

| Término del Código | Formas coloquiales | Frecuencia en el corpus |
|---|---|---|
| orden de comparendo | comparendo, parte, me hicieron un comparendo, me pusieron un comparendo, papeleta | 12 |
| multa general | multa, multa de policía, sanción económica, cuánto me toca pagar | 236 |
| multa general tipo 1 | multa tipo 1, multa de 2 salarios mínimos diarios | 30 |
| multa general tipo 2 | multa tipo 2, multa de 4 salarios mínimos diarios | 35 |
| multa general tipo 3 | multa tipo 3, multa de 8 salarios mínimos diarios | 39 |
| multa general tipo 4 | multa tipo 4, multa de 16 salarios mínimos diarios | 121 |
| medida correctiva | sanción, castigo, penalidad, correctivo | 171 |
| personal uniformado de la policía nacional | policía, policías, agente, patrullero, uniformado, tombo | 33 |
| traslado por protección | me llevaron a la estación, me subieron a la patrulla, llevarlo a la UPJ, retención | 12 |
| centro de traslado por protección | UPJ, CTP, unidad permanente de justicia | 7 |
| registro | requisa, requisar, me requisaron, pedir papeles | 58 |
| registro nacional de medidas correctivas | RNMC, antecedentes de policía, estar reportado en la policía | 7 |
| inspector de policía | inspección de policía, inspector, inspección | 16 |
| espacio público | la calle, el andén, la vía pública, el parque, la plaza | 56 |
| riña | pelea, agarrón, bronca, pelear en la calle, reñir | 2 |
| sustancias psicoactivas | droga, drogas, marihuana, bareta, porro, fumar marihuana | 18 |
| bebidas alcohólicas | trago, licor, alcohol, cerveza, tomar en la calle | 16 |
| armas | cuchillo, navaja, arma blanca, machete | 19 |
| mascota | perro, gato, animal de compañía, perro de raza peligrosa, bozal | 11 |
| niños, niñas y adolescentes | menor de edad, menores, niño, adolescente | 25 |
| infracción urbanística | construir sin licencia, obra ilegal, ampliar la casa sin permiso | 22 |
| suspensión temporal de actividad | cierre del negocio, sellamiento, cerrar el establecimiento | 105 |
| establecimiento | negocio, local, bar, discoteca, tienda | 49 |
| transporte público | bus, TransMilenio, MIO, metro, colarse | 21 |
| amonestación | llamado de atención, regaño | 30 |
| participación en programa comunitario o actividad pedagógica de convivencia | curso pedagógico, curso de convivencia, taller de convivencia | 43 |
| salarios mínimos diarios legales vigentes | SMDLV, salario mínimo diario | 4 |
| aprehensión con fin judicial | captura, me detuvieron, arresto | 1 |
| uso de la fuerza | me golpearon, agresión policial, abuso de la fuerza | 9 |
| pólvora | fuegos artificiales, voladores, tote, juegos pirotécnicos | 3 |
| ruido | ruido, bulla, música a todo volumen, fiesta ruidosa, vecino ruidoso | 7 |

## 11. Conclusiones para el motor RAG

- El texto es nominal y repetitivo; la búsqueda léxica (BM25 sobre `lemas_contenido`) complementa bien a la semántica en la fase 4.
- Los fragmentos son cortos (mediana de 30 tokens): por eso al vectorizar se les antepone el epígrafe y la ubicación jerárquica para darles contexto.
- Montos y plazos aparecen siempre con la fórmula «palabra (cifra)», fácil de detectar por reglas; el modelo genérico de spaCy no los reconoce.
- Las preguntas ciudadanas usan otro registro («parte», «requisa», «bulla»); el diccionario de sinónimos cubre esa brecha.
