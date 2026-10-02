# CLAUDE.md — Sistema RAG (TFM)

## Contexto
Trabajo Fin de Máster: sistema RAG **básico, construido desde cero** para
entenderlo y defenderlo pieza a pieza. **No es un sistema de producción.**
Plazo: 1 semana. Idioma de código, comentarios y borradores técnicos: **español**.

## Cómo trabajar (reglas para Claude)
- **Antes de crear, modificar o borrar cualquier archivo: explicar qué se va a
  hacer y esperar confirmación explícita del usuario.**
- Código simple, legible y comentado en español.
- **Prohibido** usar frameworks de agentes/RAG (LangChain, LlamaIndex) en el
  sistema. Todo a mano.
- Cada módulo implementado se documenta en `docs/memoria/04_implementacion.md`
  (qué hace, parámetros reales, decisiones). La redacción académica la hace el
  usuario aparte.
- **No iniciar ninguna ampliación** (guardrails, memoria conversacional,
  retrieval híbrido, observabilidad, FastAPI, LangGraph) salvo petición
  explícita.

## Decisiones técnicas fijadas
- **Dominio**: reglas de un juego de rol poco conocido (2-3 capítulos, ~60-100
  págs.: creación de personaje, combate, magia). PDF en `data/raw/`.
  - **Plan B**: 3 reglamentos de juegos de mesa. El código NO depende del dominio.
- **Ingesta**: Docling SOLO para PDF → Markdown (se ejecuta una vez, salida en
  `data/processed/`). Conservar el **número de página** de cada fragmento (citas).
  Después, loader propio y simple que lee esos `.md` (y TXT/MD sueltos).
- **Chunking**: función propia de tamaño fijo con overlap. NO usar el chunker de
  Docling.
- **LLM y embeddings**: Google Gemini API, tier gratuito, misma API key.
  Verificar modelos vigentes del tier gratuito antes de fijarlos en `config.py`.
  - Alternativa si hay problemas de cuota: Groq (Llama) + sentence-transformers
    en local.
- **Caché de embeddings** en disco (no repetir llamadas a la API).
- **Vector store**: FAISS local, `IndexFlatIP` con vectores normalizados
  (= similitud coseno).
- **Retrieval**: incluir ejemplo de similitud coseno **calculada a mano, sin
  numpy**, sobre 2-3 casos, y comprobar que coincide con FAISS. (Central
  pedagógicamente.)
- **Router**: clasificador mínimo "respondible con el corpus" vs. "fuera de
  dominio". Se decide el día 4.
- **Generación**: prompt con contexto recuperado + pregunta; la respuesta cita
  la fuente (documento y página).
- **Evaluación**: `eval/dataset.json` (15-20 preguntas con respuesta esperada),
  métricas con RAGAS, comparación contra baseline (mismo LLM sin RAG). Claude
  (API de pago) solo como comparación opcional, nunca como motor principal.
- **Claves** en `.env` (GEMINI_API_KEY, GROQ_API_KEY, ANTHROPIC_API_KEY), con
  `.env.example`.
- `data/raw/` y `storage/` en `.gitignore` (PDFs con copyright).

## Estructura del proyecto
```
data/{raw,processed}/, storage/
src/: config.py, llm_clients.py, pipeline.py
  ingest/ (convert_docling.py, loader.py), chunking/, embeddings/,
  vectorstore/, retrieval/ (cosine_manual.py, retriever.py), router/,
  generation/, eval/ (run_eval.py, baseline.py)
notebooks/01_walkthrough.ipynb  (crece cada día)
eval/dataset.json, eval/results/
docs/memoria/ (01_introduccion.md ... 07_conclusiones.md + figuras/)
requirements.txt, README.md
```

## Plan de la semana (con puntos de control)
- **Día 1**: setup, conversión Docling, loader, chunker.
  CONTROL: comparar extracción pypdf vs. Docling en 5 páginas difíciles (tablas,
  dos columnas). Si sale ilegible incluso con Docling → pivotar a Plan B.
- **Día 2**: embeddings + caché, coseno a mano, índice FAISS.
- **Día 3**: retriever top-k, generación con citas, pipeline end-to-end.
  CONTROL: 5 preguntas; si recupera el chunk correcto en <3 → reducir capítulos
  o pivotar. **A partir de aquí no se pivota más.**
- **Día 4**: router + dataset de evaluación (incluir preguntas fuera de dominio
  y 3-4 multi-hop a propósito).
- **Día 5**: evaluación RAGAS, baseline sin RAG, comparación opcional con Claude.
- **Día 6**: pulir notebook y variaciones de experimento si da tiempo.
- **Día 7**: margen para imprevistos y revisión.

## Git / GitHub
- Repositorio bajo la cuenta **catalinamanzano**.
- Commitear los cambios con frecuencia a medida que avanza el trabajo.
- `data/raw/`, `storage/` y `.env` NUNCA se suben (copyright y secretos).
