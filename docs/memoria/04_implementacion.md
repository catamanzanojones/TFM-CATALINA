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

### Loader (pendiente)
- `loader.py`: loader propio que lee los `.md` (y TXT/MD sueltos).

### Chunking (pendiente)
- Función propia de tamaño fijo con overlap. Parámetros reales: _(pendiente)_.
