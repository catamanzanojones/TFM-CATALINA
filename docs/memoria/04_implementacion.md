# 04 — Implementación

Borrador técnico del sistema. Se amplía con cada módulo: qué hace, parámetros
reales usados y decisiones tomadas. La redacción académica final se hace aparte.

---

## Día 1 — Setup e ingesta

### Estructura del proyecto
Se crea el esqueleto de carpetas (`data/`, `src/` con un módulo por pieza,
`eval/`, `notebooks/`, `docs/memoria/`, `scripts/`) y los archivos base:
`requirements.txt` (se amplía por días, no se instala todo de golpe),
`.gitignore` (excluye `data/raw/`, `storage/` y `.env`), `.env.example` y
`README.md`.

**Decisión**: las dependencias se añaden módulo a módulo para que quede claro
qué pieza necesita qué, y para evitar instalar lo que aún no se usa.

### Entorno
Python 3.11 en entorno virtual (`.venv/`). Se descartó el Python 3.14 del
sistema por posible falta de compatibilidad de PyTorch (dependencia de Docling).
Versiones instaladas: pypdf 6.21.0, Docling 2.140.0, torch 2.14.1 (CPU).

### Punto de control: extracción pypdf vs. Docling
Antes de comprometerse con el PDF elegido, se comparan dos extractores sobre
páginas difíciles (tablas y maquetación a dos columnas):

- **pypdf**: extracción de texto plano, rápida, sin estructura.
- **Docling**: conversión a Markdown preservando estructura (tablas, títulos).

Script: `scripts/compare_extraction.py`. Aísla cada página en un PDF temporal y
la convierte, volcando ambas salidas a `data/processed/comparacion/`.

**Criterio de decisión**: si el texto sale ilegible incluso con Docling
(tablas rotas, columnas entremezcladas) → se pivota al Plan B (3 reglamentos de
juegos de mesa).

**Documento**: *Vampiro: La Mascarada*, 5ª edición (Madrid, 2018), 404 páginas.

**Selección de páginas**: se localizaron automáticamente con un análisis previo
(pypdf en modo *layout*), puntuando cada página por proporción de líneas con un
hueco central (indicio de dos columnas) y de líneas con varios huecos y dígitos
(indicio de tabla). Se eligió una página difícil por cada tema del TFM:

| Pág. PDF | Pág. impresa | Capítulo | Dificultad |
|---|---|---|---|
| 130 | 128 | Reglas – Ejemplos de tiradas | 2 columnas + recuadro lateral |
| 153 | 151 | Personajes – Creación | 2 columnas + tabla de costes |
| 222 | 220 | Vampiros – Frenesí | 3 tablas de detonantes |
| 256 | 254 | Disciplinas (Celeridad) | bloques de poderes con fichas |
| 300 | 298 | Conflicto avanzado | 2 columnas, reglas de combate |

**Resultado**:

| Aspecto | pypdf | Docling |
|---|---|---|
| Orden de lectura a 2 columnas | Correcto en este PDF | Correcto en las 5 páginas |
| Tablas | Destrozadas (cada fila partida en 3-4 líneas) | Tablas Markdown legibles (4 de 4) |
| Palabras partidas con guion | No las une | Las une en el texto (no en tablas) |
| Cabeceras y número de página | Mezclados con el texto | Eliminados |
| Títulos | Texto plano | `##` en los títulos principales |

**Defectos de Docling detectados** (a tratar en el loader o asumidos):
1. Viñetas decorativas duplicadas (`- ■ ■`) y marcadores `<!-- image -->`.
2. Los subtítulos en versalitas (p. ej. nombres de poderes) no se detectan como
   títulos y quedan como texto normal.
3. En tablas: alguna fila final se escapa como texto suelto, la fila de
   cabecera queda fuera de la tabla y no se unen guiones dentro de las celdas.
4. Algún párrafo queda partido donde el texto salta de columna (mitigado por el
   overlap del chunking).
5. Docling aplica OCR por defecto; como el PDF tiene capa de texto, se
   desactivará en la conversión completa (más rápida y sin errores de OCR).

**Observación**: la numeración del PDF va 2 páginas por delante de la impresa.
Para las citas se usará la página impresa.

**Decisión**: Docling supera el punto de control → **no se pivota**, se sigue
con *Vampiro: La Mascarada*.

### Conversión PDF → Markdown (`src/ingest/convert_docling.py`)
Convierte todos los PDF de `data/raw/` con Docling y guarda, en
`data/processed/`, un `.md` y un `.json` por documento. Se ejecuta una sola vez
(si el `.md` ya existe no se repite, salvo con `--forzar`).

**Parámetros reales**:
- `do_ocr = False`: el PDF tiene capa de texto; el OCR solo añade tiempo y
  errores.
- `do_table_structure = True`: reconstrucción de tablas.
- `--desfase 2`: diferencia entre la página del PDF y la impresa en este libro
  (comprobada en las 5 páginas del punto de control).

**Decisiones**:
- **Se convierte el PDF completo**, no solo los capítulos del corpus. Convertir
  es caro pero se hace una vez; la selección del corpus se hace después con
  rangos de páginas en `config.py`. Así se puede reducir o ampliar el corpus
  sin reconvertir (p. ej. experimento "corpus reducido vs. libro completo").
- **Marcador de página**: se exporta página a página
  (`export_to_markdown(page_no=n)`) y cada página va precedida de
  `<!-- pagina: N -->`, con N = **página impresa** (la que buscaría un lector en
  el libro). Las páginas sin número impreso (portada) quedan como 0.
- **El conversor no limpia el texto**: guarda la salida de Docling tal cual. La
  limpieza va en el loader (una responsabilidad por pieza).
- **Se guarda también el JSON** de Docling (`save_as_json`): permite regenerar el
  Markdown con otro formato sin repetir la conversión (`--desde-json`, ~2 min
  frente a 6,5 min). Se aprovechó tras la revisión manual (E8).
- **`traverse_pictures=True`** al exportar: incluye el texto que Docling sitúa
  dentro de una ilustración, que de otro modo se pierde (p. ej. los niveles 4-5
  de la Habilidad Ciencias). Añadido tras la revisión manual (E8).

**Resultado**: 404 páginas, 32 tablas, ~1,1 millones de caracteres de Markdown,
**6,5 minutos** en CPU (sin GPU). Docling avisó de una celda descartada en una
tabla.

**Validación**:
- Los marcadores cuadran con las páginas del punto de control (128, 220, 254,
  298).
- 63 páginas salen vacías: son ilustraciones a página completa (pypdf tampoco
  encuentra texto en ellas), incluido el relato ilustrado inicial (págs. 4-31).
- En las 112 páginas del corpus propuesto, Docling recupera al menos el 85 % de
  las letras que ve pypdf en 110; las otras 2 (245 y 299) no pierden texto: su
  final aparece en la página anterior (ver limitación 1).

**Limitaciones conocidas**:
1. Un párrafo que cruza de página se reconstruye entero y se asigna a la página
   donde **empieza** (p. ej. el párrafo de Klaus, págs. 150-151, queda en la
   150). La cita de la parte final puede indicar la página anterior.
2. Texto incrustado dentro de una ilustración: con la exportación por defecto
   se descartaba; con `traverse_pictures=True` se recupera, aunque a veces
   desordenado ("equi- •••• Eres un experto... / pos científicos."), y arrastra
   texto decorativo que se limpia en el loader (ver E8).

### Configuración (`src/config.py`)
Centraliza rutas y todo lo que depende del documento, de modo que el resto del
código sea independiente del dominio. Por documento (clave = nombre del
archivo): nombre legible para las citas (`"Vampiro: La Mascarada (5ª ed.)"`),
rangos de páginas impresas del corpus y perfil tipográfico. Las rutas son
absolutas (calculadas desde la ubicación de `config.py`) para que funcionen
igual desde scripts y desde el notebook.

**Corpus** (páginas impresas): Reglas 115-132, Personajes (creación y rasgos
centrales) 135-171, Disciplinas 243-288, Conflicto avanzado 295-305. Total:
112 páginas.

### Jerarquía de títulos (`src/ingest/estructura.py`)
**Problema**: Docling marca todos los títulos con el mismo nivel (`##`): una
disciplina entera ("Celeridad"), una parte de ella ("Nivel 4") y un recuadro
("EJEMPLO:") salen igual. Además no detecta los subtítulos en versalitas que van
pegados al párrafo ("frenesí de furia Las provocaciones..."). Sin jerarquía, un
chunk "Nivel 4: ..." no sabe a qué disciplina pertenece.

**Idea**: el libro marca la jerarquía con la tipografía. Un análisis de fuentes
con pypdf (ver experimento E3) muestra 5 niveles consistentes en todo el corpus.
Ese **perfil tipográfico** se declara en `config.py`; el código es genérico.

| Nivel | Fuente y tamaño | Ejemplos |
|---|---|---|
| 1 Capítulo | Bodoni versalitas 56 pt | Reglas, Disciplinas |
| 2 Parte | Bodoni 36 pt | Creación de personajes, Conflicto avanzado |
| 3 Sección | Bodoni 22 pt | Tiempo, Pruebas simples, Celeridad |
| 4 Apartado | Cormorant Bold 14 pt | Rasgos, Reservas, Nivel 4 |
| 5 Subapartado | GillSans Bold versalitas 7 pt | puntería certera, frenesí de furia |

**Funcionamiento**:
1. Con pypdf (`extract_text(visitor_text=...)`) se obtienen, página a página,
   los textos con estilo de título. Los fragmentos seguidos del mismo nivel se
   unen (un título puede llegar partido: "disciplin" + "as").
2. Se recorre el Markdown de Docling página a página y cada título del PDF se
   empareja con el texto mediante una **comparación normalizada** (minúsculas,
   sin tildes, solo letras y dígitos), robusta a espacios, guiones y mayúsculas.
3. Reglas de emparejamiento:
   - Título pegado a un párrafo: solo se separa si lo que sigue empieza por
     mayúscula (frase nueva), saltando la puntuación ("armas arrojadizas: Un
     personaje..."). Evita partir "Rasgos centrales son..." por el título
     "Rasgos".
   - Títulos partidos por Docling en varias líneas ("círculo de protección" /
     "contra ghouls"): se unen hasta 3 líneas.
   - `##` de Docling seguido de texto en minúscula: se toma la línea entera
     (pypdf vio el título partido: "Experiencia y" + "perfeccionamiento").
   - `##` de Docling que no es título según el perfil ("EJEMPLO:", títulos de
     recuadros): se rebaja a negrita para que no corte la sección (96 casos en
     el corpus).
   - Se unen los guiones de corte de línea dentro del título ("fuer- za").
   - Al comprobar la mayúscula se saltan los signos de apertura ("establece tus
     creencias ¿Cuáles..."), y la puntuación de cierre se queda en el título
     ("¿Cómo Cazas?").
4. **Capítulos según los marcadores del PDF**: si en una página empieza un
   capítulo de los marcadores, su nombre manda (la portadilla decorativa puede
   salir incompleta: "Sistemas" en vez de "Sistemas Avanzados"); si no se ha
   colocado ningún título de nivel 1, se añade.

Salida: `data/processed/estructurado/<documento>.md`. Los documentos sin perfil
tipográfico se copian sin cambios (el sistema funciona igual, sin jerarquía).

**Resultado final**: 875 de 895 títulos del PDF colocados (98 %); en el corpus
**no queda ninguno sin colocar** (ver E5). Capítulos en las rutas de los chunks:
Reglas, Personajes, Disciplinas y Sistemas Avanzados. El árbol resultante reproduce
la estructura lógica del libro, p. ej.:

```
Reglas
    Pruebas simples
        Reservas
            Especialidades
Disciplinas
    Celeridad
        Nivel 4
            Puntería certera
            Sorbo de elegancia
```

**Limitaciones**: el perfil tipográfico se obtiene a mano para cada documento
(análisis de fuentes + revisión); un título con un estilo no recogido en el
perfil no se detecta (su texto acaba en la sección anterior).

### Loader (`src/ingest/loader.py`)
Lee los Markdown estructurados (`data/processed/estructurado/`; si un documento
no tiene versión estructurada, usa la de `data/processed/`) y los documentos
sueltos `.md`/`.txt` de `data/raw/`. Parte cada documento por los marcadores
`<!-- pagina: N -->` y devuelve una lista de páginas (`Pagina`: `doc_id`,
`documento` —nombre legible para citas—, `pagina`, `texto`, `en_corpus`). Los
documentos sin marcadores entran como una única página con `pagina = None`.

**Limpieza** (con expresiones regulares; las reglas 4-6 se añadieron tras la
revisión manual, ver E8):
1. Elimina `<!-- image -->` y las viñetas decorativas `■`.
2. Une palabras partidas por un salto de columna ("se resuel-" / "ve").
3. Colapsa líneas en blanco repetidas.
4. **Nivel 1 de las listas de niveles**: Docling convierte el "•" del nivel 1
   en una viñeta y el punto se pierde; si a un elemento sin puntos le sigue
   uno con "··", se le añade "·".
5. **Etiquetas flotantes**: quita las líneas en negrita que interrumpen una
   frase a medias ("...secarás a un" / "**Investigador investigador**" /
   "Cainita..."), que son rótulos de ilustraciones. Mira la línea anterior
   aunque esté en la página anterior.
6. **Texto decorativo** (aparece con `traverse_pictures`): letras o cifras
   sueltas espaciadas ("2 4 8", "L I BRO BÁS I CO"), una palabra repetida
   ("ejecutivo Ejecutivo") y rótulos duplicados en dos líneas seguidas
   ("Veterano" / "veterano"). Listas, tablas y títulos no se tocan.

**Decisión**: las páginas fuera del corpus **no se descartan** en el loader,
solo se marcan (`en_corpus = False`). El chunker necesita sus títulos para
construir la jerarquía: p. ej. el título del capítulo "Personajes" está en la
pág. 133 (fuera del corpus) y sus secciones (pág. 135 en adelante) sí entran.

**Resultado**: 404 páginas cargadas, 112 en el corpus, 373.603 caracteres.

### Chunking (`src/chunking/chunker.py`)
Dos estrategias, ambas implementadas a mano:

**1. Tamaño fijo con overlap** (`chunks_fijos`, baseline del experimento P1):
ventanas de 1000 caracteres con 200 de solape sobre el texto seguido de cada
documento, sin mirar los títulos (`trocear_fijo`). Para que los trozos sean
legibles, el final se pone en el mejor separador del último 25 % de la ventana
(fin de párrafo > fin de línea > fin de frase > espacio) y el trozo siguiente
empieza en el primer principio de línea o de frase de la zona de solape. La
versión inicial solo evitaba partir palabras: 353 de 467 chunks empezaban a
mitad de frase (ver E8).

**2. Estructural híbrido** (`chunks_estructurales`, estrategia principal):
1. Construye el **árbol de secciones** de cada documento a partir de los
   títulos `#`...`#####`. Los títulos se leen en todas las páginas; el texto,
   solo en las del corpus.
2. Un chunk por sección. Secciones de más de **3000** caracteres se subdividen
   con `trocear_fijo` (overlap **400**). Secciones con menos de **300**
   caracteres de texto se unen a la siguiente si es su hija o su hermana.
3. Cada chunk lleva **metadatos jerárquicos**:
   - `documento`, `pagina_inicio`, `pagina_fin` (para las citas);
   - `ruta`: títulos de todos los niveles, p. ej.
     `["Disciplinas", "Celeridad", "Nivel 4", "Puntería certera"]`;
   - `seccion_id` y `ancestros_ids`: apuntan al **almacén de secciones**
     (`{id: título, nivel, padre, hijos, texto propio}`), que permitirá la
     expansión al padre en la generación (ver P4).
4. El texto que se convierte en embedding es `texto_con_ruta`: la ruta de
   títulos seguida del texto, para que el vector "sepa" de qué capítulo y
   sección habla el fragmento.

**Justificación del tamaño máximo** (ver E4; decisión del día 1 que sustituye
al tamaño fijo puro previsto inicialmente, que se conserva como baseline): con
1500 caracteres habría que partir el 31 % de las secciones (62 % del texto),
perdiendo la ventaja de cortar por títulos; con 3000, solo el 7 % (y menos aún
tras añadir el nivel 5). Como cada sección trata un único tema, se pueden
permitir chunks más grandes sin diluir el embedding. 3000 caracteres son unos
800 tokens, muy por debajo del límite de `gemini-embedding-2` (8.192 tokens), y
sin problema para el contexto del LLM (5 chunks ≈ 4000 tokens).

**Regla de la ruta**: la ruta de un chunk es la de la sección más profunda que
contiene todo su texto. Si se unen secciones hermanas, queda la del padre común
(no se atribuye el chunk a una sola de ellas). Las secciones que solo aportan
su título (p. ej. "Nivel 4" seguido directamente de "Puntería certera") no
cuentan, para no perder el nivel más específico.

**Seguimiento de páginas**: al unir las líneas de un bloque se guarda en qué
posición empieza cada página; la página de cualquier carácter se obtiene con
búsqueda binaria (`bisect`). Así un chunk que cruza de página se cita como
"págs. X-Y".

**Separación de páginas**: entre una página y la siguiente se inserta una línea
en blanco; sin ella, la última línea de una página quedaba pegada a la primera
de la siguiente (ver E8).

**Resultado** (ver E7): 324 chunks estructurales frente a 482 de tamaño fijo.
Los chunks se vuelcan a `storage/chunks_*.json` para inspeccionarlos.

**Ajustes tras revisar chunks concretos**:
- La primera versión calculaba la ruta con todas las secciones unidas, y un
  poder ("Puntería certera") quedaba con la ruta de su padre ("Nivel 4"), que
  solo aportaba su título → se excluyen de la ruta las secciones sin texto
  propio.
- `estructura.py` perdía la puntuación de cierre de los títulos ("¿Cómo
  Cazas" sin "?") → ahora se conserva.

**Limitación**: algunos párrafos que Docling parte en un salto de página o de
columna llegan partidos en dos párrafos dentro del chunk (p. ej. "...Tira Astucia
+ Intimidación (la" / "dificultad es..."). Se analizó unirlos automáticamente y
se descartó: solo hay 15 casos en el corpus y casi todos son maquetación de
tablas o listas, que una regla automática estropearía (ver E8).

### Expansión al padre (prevista para el día 3)
Se busca con chunks pequeños (precisos), pero al LLM se le entrega el
**ancestro más grande que quepa en un tope de 6000 caracteres** (p. ej. un
chunk de "Puntería certera" entregaría "Celeridad > Nivel 4" completo, 1.212
car.; Celeridad entera, 10.406 car., no cabe). Si varios chunks comparten
ancestro, se envía una sola vez. Se implementará con un interruptor
(`EXPANDIR_CONTEXTO`) para evaluarlo (experimento P4). Datos en E6.

## Día 2 — Embeddings, coseno e índice

### Elección de modelos (verificada el 16/10/2026)
Fuentes: documentación oficial de la Gemini API (páginas *Models*, *Pricing*,
*Embeddings* y *Rate limits*, actualizadas el 13-15/10/2026). Prueba de humo
con la clave del proyecto: los tres modelos aparecen disponibles.

| Uso | Modelo | Motivo |
|---|---|---|
| Generación | `gemini-3.8-flash` | Estable, el Flash más reciente, recomendado para proyectos nuevos, con tier gratuito |
| Generación (alternativa) | `gemini-3.5-flash-lite` | El más rápido y barato; reserva si aprieta la cuota (p. ej. RAGAS) |
| Embeddings | `gemini-embedding-2` | Actual y recomendado, gratuito, hasta 8.192 tokens por texto |

Descartados: Gemini 4 Argon y 3.1 Pro (sin tier gratuito); familia 2.5 (acceso
limitado a quien ya la usaba); `gemini-embedding-001` (anterior, 2.048 tokens).

**Dimensión: 768.** `gemini-embedding-2` produce 3072 números por defecto, pero
está entrenado con *Matryoshka Representation Learning*: los primeros números
concentran la información más importante, de modo que se puede pedir un vector
más corto (128-3072) que sigue funcionando. 768 es una de las tallas
recomendadas: calidad muy cercana a 3072, caché e índice 4 veces más pequeños y
el mismo coste por llamada (se paga por texto de entrada, no por dimensión). Con
este corpus la diferencia práctica es mínima (experimento opcional P5).

**Consideración**: en el tier gratuito Google puede usar el contenido enviado
para mejorar sus productos; se envía texto de un libro con copyright (a
mencionar en la memoria como limitación / consideración ética).

### Cliente de modelos (`src/llm_clients.py`)
Único punto de acceso a la API (el resto del código no conoce el proveedor; un
cambio a Groq + sentence-transformers solo tocaría este archivo). Lee la clave
de `.env`. Las llamadas pasan por `con_reintentos`: ante un error de cuota (429)
o del servidor (5xx) espera y reintenta con **espera exponencial** (10, 20, 40 s
...; hasta 5 intentos). Embeddings en lotes de 50 textos por llamada, cada texto
en su propio `Content` (si no, la API devuelve un único vector conjunto).

### Embeddings y caché (`src/embeddings/embedder.py`)
`gemini-embedding-2` no tiene parámetro `task_type`: la tarea se indica con un
prefijo en el texto, con el formato de la documentación oficial:
- pregunta: `task: search result | query: {pregunta}`
- chunk: `title: {documento > ruta de títulos} | text: {texto}`

**Decisión**: el `title` de cada chunk es su ruta de títulos precedida del
nombre del documento (este último no aporta nada con un solo libro, pero sí en
el Plan B con varios reglamentos). Así el vector incorpora el contexto
jerárquico decidido el día 1.

**Caché en disco** (`storage/cache_embeddings.json`): diccionario
`{clave: vector}` con clave = SHA-256 de (modelo, dimensión, texto formateado).
Si cambia cualquiera de los tres se recalcula; si no, nunca se repite una
llamada. Se guarda tras cada lote para no perder lo calculado si la API falla a
mitad. Tamaño con 327 vectores: 3,4 MB.

### Índice vectorial (`src/vectorstore/faiss_store.py`)
`faiss.IndexFlatIP`: producto escalar exacto contra todos los vectores (sin
aproximaciones; con unos cientos de chunks es instantáneo). Los vectores se
normalizan siempre (`faiss.normalize_L2`) antes de añadir y de buscar, aunque
`gemini-embedding-2` ya los devuelva con norma 1: con norma 1 el producto
escalar es la similitud coseno, y así no se depende del modelo. Se guardan en
`storage/`: el índice (`indice_estructural.faiss`), los chunks con sus
metadatos (`indice_estructural.json`) y el almacén de secciones para la
expansión al padre (`secciones_estructural.json`).

**Resultado**: 324 vectores de dimensión 768; construcción en ~3 min por los
límites de cuota (ver E11).

### Coseno a mano (`src/retrieval/cosine_manual.py`)
Producto escalar, norma y coseno en Python puro (bucles, sin numpy):
`cos(a, b) = a·b / (|a|·|b|)`. Dos partes:
1. **Ejemplo de juguete** (3 dimensiones), calculado paso a paso con
   a = (1, 2, 3): misma dirección b = 2a → 1; perpendicular c = (−2, 1, 0) → 0;
   opuesto d = −a → −1. Muestra además por qué hay que normalizar: el producto
   escalar a·b = 28 es mayor que a·a = 14 aunque b tenga el mismo significado
   (dirección) que a; el coseno da 1 en ambos casos.
2. **Casos reales**: 3 preguntas (una por capítulo), coseno a mano contra los
   324 chunks frente a `IndiceVectorial.buscar` (FAISS). Resultados en E10.

---

## Registro de experimentos

Todos los análisis y experimentos realizados, con sus datos, para la memoria.

### Realizados

**E1 — Extracción pypdf vs. Docling** (día 1). 5 páginas difíciles
seleccionadas automáticamente. Docling reconstruye las tablas y respeta las dos
columnas; pypdf destroza las tablas. Detalle en "Punto de control". Decisión: no
se pivota.

**E2 — Cobertura de texto de Docling** (día 1). Comparación por página del
número de letras extraídas por Docling frente a pypdf en las 112 páginas del
corpus: 110 con ≥ 85 %; las 2 restantes (245, 299) no pierden texto, su final
aparece en la página anterior (párrafos que cruzan de página). En todo el libro,
63 páginas salen vacías y son ilustraciones (pypdf tampoco encuentra texto),
salvo 2 con texto dentro de una ilustración (págs. 57 y 161, fuera del corpus o
sin reglas).

**E3 — Análisis tipográfico** (día 1). Recuento de (fuente, tamaño) de todos los
fragmentos de texto de las 112 páginas del corpus, por capítulo. Resultado: 5
estilos de título consistentes en los 4 capítulos (tabla en "Jerarquía de
títulos"), más estilos que no son títulos: cabecera de página (GillSans 7 pt),
cabeceras de tabla (GillSans versalitas 6 pt), recuadros (GillSans 9 pt) y la
etiqueta "EJEMPLO:" (Cormorant Bold 8 pt). Texto normal: Cormorant Light 10 pt.

**E4 — Simulación del tamaño máximo de chunk** (día 1). Cortando por los
títulos `##` de Docling (antes de reconstruir la jerarquía): 290 secciones,
375.020 caracteres, mediana de 903 caracteres por sección.

| Máximo (car.) | Secciones a dividir | % del texto afectado | Chunks aprox. |
|---|---|---|---|
| 1000 | 129 (44 %) | 75 % | 547 |
| 1500 | 90 (31 %) | 62 % | 423 |
| 2000 | 55 (19 %) | 46 % | 367 |
| 3000 | 20 (7 %) | 24 % | 315 |
| 4000 | 9 (3 %) | 14 % | 300 |
| 6000 | 2 (1 %) | 4 % | 292 |

Decisión: máximo 3000 caracteres.

**E5 — Iteraciones de la reconstrucción de títulos** (día 1).

| Versión | Títulos colocados | Sin colocar en el corpus | Falsos positivos detectados |
|---|---|---|---|
| v1: comparación normalizada + regla de mayúscula | 776 / 912 | 24 | — |
| v2: + puntuación, títulos multilínea, `##` parciales, respaldo de capítulos | 868 / 895 | 1 | 4 títulos sospechosos (> 40 car.) |
| v3: + `##` seguido de mayúscula se separa, unión de guiones | 868 / 895 | 1 | 0 |
| v4 (tras E8): + signos de apertura/cierre, `traverse_pictures`, capítulos según marcadores | 875 / 895 | 0 | 0 |

Causas de fallo en v1: dos puntos tras el título, títulos partidos por pypdf o
por Docling en varias líneas, portadilla decorativa no extraída y guiones de
corte de línea.

**E6 — Tamaño de las secciones por nivel** (día 1). Sobre el Markdown
estructurado del corpus, tamaño de cada sección incluyendo sus subsecciones.
Sirve para decidir hasta qué nivel se puede entregar "el contexto completo" al
LLM (expansión al padre, P4).

| Nivel | Nº | Mediana (car.) | Máximo (car.) | Ejemplo |
|---|---|---|---|---|
| 1 Capítulo | 2 | 188.445 | 217.853 | Disciplinas |
| 2 Parte | 3 | 44.580 | 64.504 | Creación de personajes |
| 3 Sección | 38 | 9.363 | 28.554 | Celeridad: 10.406 |
| 4 Apartado | 151 | 1.439 | 18.366 | Nivel 4 (Celeridad): 1.212 |
| 5 Subapartado | 186 | 946 | 11.883 | — |

Conclusión: los niveles 1-2 son inviables como contexto; el nivel 3 a veces; el
4-5 casi siempre. De ahí el tope de 6000 caracteres para la expansión.

**E7 — Chunking de tamaño fijo vs. estructural: estadísticas** (día 1, cifras
tras los arreglos de E8). Mismo corpus (112 págs., 373.603 car.).

| Estrategia | Chunks | Mín. | Mediana | p90 | Máx. | Cruzan de página |
|---|---|---|---|---|---|---|
| Tamaño fijo 1000/200 | 482 | 643 | 910 | 982 | 999 | 137 |
| Estructural híbrido 3000/400/300 | 324 | 221 | 989 | 2409 | 2982 | 74 |

En el estructural: 16 secciones subdivididas por tamaño, 74 chunks que unen
secciones cortas y 0 chunks sin ruta. El
tamaño mínimo (221) corresponde a secciones cortas que no se pueden unir porque
la siguiente no es hija ni hermana. Pendiente: comparar su calidad de retrieval
(P1).

**E8 — Revisión manual de chunks y arreglos** (día 1). Muestra aleatoria
reproducible de 20 chunks estructurales (`random.seed(42)`), revisando ruta,
páginas, limpieza del texto, principio y final, tablas y títulos. 12 correctos y
8 con algún fallo;
se encontraron 6 tipos de fallo:

| # | Fallo | Causa | Arreglo |
|---|---|---|---|
| A | Rótulo en mitad de una frase ("secarás a un / **Investigador investigador** / Cainita") | Etiqueta de una ilustración colocada por Docling en el texto | Loader: quitar etiquetas que interrumpen una frase |
| B | Falta el punto del nivel 1 en las listas de niveles (40 casos) | Docling convierte "•" en viñeta | Loader: añadir "·" al elemento previo a "··" |
| C | Texto perdido (final de Ciencias) | Docling lo sitúa dentro de una ilustración | Exportar con `traverse_pictures=True` (sin reconvertir, desde el JSON) |
| D | Ruta incorrecta: la sección "Establece tus creencias" pegada a la anterior | Título seguido de "¿", que no se reconocía como mayúscula | `estructura.py`: saltar signos de apertura |
| E | Negrita pegada al párrafo anterior | Las páginas se unían con un solo salto de línea | Chunker: línea en blanco entre páginas |
| F | Trozos que empiezan a mitad de frase | `trocear_fijo` solo respetaba palabras | Cortes en fin de párrafo/línea/frase |

Recuento automático de síntomas en todos los chunks, antes → después:

| Síntoma | Fijo (467 → 482 chunks) | Estructural (324 chunks) |
|---|---|---|
| Empieza a mitad de frase | 353 → 14 | 14 → 1 |
| Acaba a mitad de frase | 291 → 11 | 17 → 8 |
| Etiqueta cortando una frase | 12 → 0 | 10 → 0 |
| Negrita pegada al párrafo | 16 → 0 | 17 → 0 |
| Nivel 1 sin punto | 40 → 0 | 36 → 0 |

Los arreglos introdujeron dos efectos secundarios, detectados al revisar y
corregidos: `traverse_pictures` añadió 16 líneas en el corpus, 7 de contenido
real y 9 decorativas ("2 4 8", "ejecutivo Ejecutivo"...), que se limpian en el
loader; y cambió el nombre de un capítulo ("Sistemas" en vez de "Sistemas
Avanzados"), resuelto usando siempre el nombre de los marcadores del PDF. Una
segunda muestra aleatoria (`random.seed(7)`, 10 chunks) tras los arreglos no
mostró fallos nuevos. Cobertura de líneas de pypdf en el Markdown: 98,9 % sin
`traverse_pictures`, 99,0 % con él; lo que falta son sobre todo cabeceras de
página (eliminadas a propósito).

Analizado y descartado: unir automáticamente párrafos partidos por un salto de
columna (15 casos, casi todos tablas o listas).

**E9 — Prueba de humo de embeddings y anisotropía** (día 2). Tres textos
embebidos con `gemini-embedding-2` a 768 dimensiones: dimensión 768 y norma
1,000000 en los tres (el modelo ya normaliza). Coseno de la pregunta "¿Cuántos
puntos de Experiencia cuesta subir un Atributo?" con un fragmento relevante
(costes de rasgos): **0,786**; con uno no relevante (Celeridad nivel 4):
**0,614**. Observación: incluso un texto sin relación tiene coseno alto. Es
habitual en modelos de embeddings (los vectores no se reparten por todas las
direcciones, "anisotropía"): lo que importa es el **orden** de las
puntuaciones, no su valor absoluto. Relevante para el router del día 4 (un
umbral fijo de similitud habrá que calibrarlo con datos).

**E10 — Coseno a mano vs. FAISS** (día 2). 3 preguntas, top-3 contra los 324
chunks estructurales:

| Pregunta | Top-1 (coseno) | ¿Mismo orden a mano y en FAISS? |
|---|---|---|
| ¿Cuántos puntos de Experiencia cuesta aumentar un Atributo? | Mar de tiempo, pág. 151 (0,76556), contiene la tabla "Costes de rasgos" | Sí (3/3) |
| ¿Qué hace el poder Puntería certera de Celeridad? | Nivel 4 > Puntería certera, pág. 254 (0,81430) | Sí (3/3) |
| ¿Qué ocurre si saco un crítico en una tirada? | Resultados de las tiradas, pág. 120 (0,76722), contiene "Críticos" | Sí (3/3) |

Mismos chunks y mismo orden en 9 de 9 posiciones; diferencia máxima entre
puntuaciones: **1,04·10⁻⁷** (FAISS usa float32 y Python float64). Conclusión:
IndexFlatIP con vectores normalizados calcula exactamente la similitud coseno.
Como anticipo del día 3, el top-1 es el chunk correcto en las 3 preguntas.

**E11 — Comportamiento de la cuota gratuita** (día 2). Al embeber los 324
chunks en lotes de 50, los dos primeros lotes pasan y los siguientes reciben
error 429 hasta que pasa el minuto; los reintentos con espera exponencial (10 +
20 + 40 s) lo resuelven sin perder nada. Patrón compatible con un límite de
~100 textos por minuto (Google ya no publica las cifras del tier gratuito; se
consultan en AI Studio). Tiempo total: ~3 min para 324 chunks. Gracias a la
caché, reconstruir el índice ya no hace ninguna llamada.

### Pendientes (día 6, si da tiempo)
- **P1 — Chunking de tamaño fijo vs. estructural**: misma evaluación con ambos
  chunkers (fijo 1000/200 frente a estructural 3000/400/300; ver E7).
- **P2 — Tamaño máximo de chunk**: 2000 / 3000 / 4000 caracteres.
- **P3 — Corpus reducido vs. libro completo**: efecto de indexar las 404 páginas
  en la calidad del retrieval.
- **P4 — Expansión al padre**: generación con y sin `EXPANDIR_CONTEXTO`
  (tope 6000 car.; ver E6). Especialmente relevante en preguntas multi-hop.
- **P5 — Dimensión de los embeddings**: 768 frente a 3072 (requiere volver a
  embeber el corpus una vez).
