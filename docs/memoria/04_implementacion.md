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
  Markdown con otro formato sin repetir la conversión.

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
2. Texto incrustado dentro de una ilustración se descarta: se pierden el poema
   de la pág. 161 (sin reglas) y la cronología de la pág. 57 (fuera del corpus).

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
4. **Respaldo para capítulos**: si en una página empieza un capítulo de los
   marcadores del PDF y no se ha colocado ningún título de nivel 1, se añade
   (la portadilla decorativa de "Reglas" no la extrae Docling).

Salida: `data/processed/estructurado/<documento>.md`. Los documentos sin perfil
tipográfico se copian sin cambios (el sistema funciona igual, sin jerarquía).

**Resultado final**: 868 de 895 títulos del PDF colocados (97 %); en el corpus
queda **1 sin colocar** ("establece tus creencias", pág. 146). Títulos en el
corpus por nivel: 1→2, 2→3, 3→38, 4→151, 5→186. El árbol resultante reproduce
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

### Loader (pendiente)
- `loader.py`: loader propio que lee los `.md` estructurados (y TXT/MD
  sueltos), parte por marcadores de página, limpia y filtra por rangos.
- Limpieza prevista: `<!-- image -->`, viñetas `- ■ ■`, líneas en blanco
  repetidas y palabras partidas por un salto de columna ("se resuel-" / "ve").

### Chunking (pendiente de implementar)
**Decisión: chunking estructural híbrido** (sustituye al tamaño fijo puro que
se había previsto inicialmente):
- Se corta por títulos; cada chunk lleva su **ruta de títulos**
  (p. ej. `Disciplinas > Celeridad > Nivel 4 > Puntería certera`), que se
  antepone al texto y sirve también para las citas.
- Secciones de más de **3000** caracteres se subdividen con la función propia de
  tamaño fijo con **overlap de 400** caracteres.
- Secciones de menos de **300** caracteres se unen a la siguiente.
- La función de tamaño fijo pura se conserva como **baseline** (experimento P1).
- No se usa el chunker de Docling.

**Justificación del tamaño máximo** (ver experimento E4): con 1500 caracteres
habría que partir el 31 % de las secciones (62 % del texto), perdiendo la
ventaja de cortar por títulos; con 3000 solo el 7 % (y menos aún tras añadir el
nivel 5). Como cada sección trata un único tema, se pueden permitir chunks más
grandes sin diluir el embedding. 3000 caracteres son unos 800 tokens, por debajo
del límite del modelo de embeddings (a confirmar el día 2) y sin problema para
el contexto del LLM (5 chunks ≈ 4000 tokens).

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

Causas de fallo en v1: dos puntos tras el título, títulos partidos por pypdf o
por Docling en varias líneas, portadilla decorativa no extraída y guiones de
corte de línea.

### Pendientes (día 6, si da tiempo)
- **P1 — Chunking de tamaño fijo vs. estructural**: misma evaluación con ambos
  chunkers.
- **P2 — Tamaño máximo de chunk**: 2000 / 3000 / 4000 caracteres.
- **P3 — Corpus reducido vs. libro completo**: efecto de indexar las 404 páginas
  en la calidad del retrieval.
