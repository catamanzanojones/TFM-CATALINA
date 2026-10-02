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

- Páginas comparadas: _(pendiente)_
- Resultado: _(pendiente de ejecutar con el PDF)_
- Decisión: _(pendiente)_

### Ingesta (pendiente, tras superar el punto de control)
- `convert_docling.py`: PDF → Markdown, una sola vez, salida en
  `data/processed/`, conservando el número de página para las citas.
- `loader.py`: loader propio que lee los `.md` (y TXT/MD sueltos).

### Chunking (pendiente)
- Función propia de tamaño fijo con overlap. Parámetros reales: _(pendiente)_.
