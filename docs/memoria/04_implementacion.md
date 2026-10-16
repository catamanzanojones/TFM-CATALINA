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

### Ingesta (pendiente, tras superar el punto de control)
- `convert_docling.py`: PDF → Markdown, una sola vez, salida en
  `data/processed/`, conservando el número de página para las citas.
- `loader.py`: loader propio que lee los `.md` (y TXT/MD sueltos).

### Chunking (pendiente)
- Función propia de tamaño fijo con overlap. Parámetros reales: _(pendiente)_.
