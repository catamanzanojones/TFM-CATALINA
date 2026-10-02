# Sistema RAG — Trabajo Fin de Máster

Sistema RAG (Retrieval-Augmented Generation) **básico, construido desde cero**,
sin frameworks de agentes, con fines didácticos: entender y poder defender cada
pieza. No es un sistema de producción.

**Dominio**: reglas de un juego de rol poco conocido (para que el LLM no las
sepa de memoria). El PDF, con copyright, no se incluye en el repositorio.

## Arranque rápido

```bash
# 1. Entorno virtual
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate # Linux/Mac

# 2. Dependencias (se amplían por días; ver requirements.txt)
pip install -r requirements.txt

# 3. Claves
copy .env.example .env      # y rellenar las claves
```

## Estructura

| Carpeta | Contenido |
|---|---|
| `data/raw/` | PDFs fuente (no versionados) |
| `data/processed/` | Markdown generado por Docling |
| `storage/` | Índice FAISS y caché de embeddings (no versionado) |
| `src/` | Código del sistema, un módulo por pieza |
| `eval/` | Dataset de preguntas y resultados de evaluación |
| `notebooks/` | Walkthrough que crece cada día |
| `docs/memoria/` | Borradores técnicos de la memoria |
| `scripts/` | Utilidades sueltas (p. ej. comparación de extracción) |

## Estado

En desarrollo. Ver el plan semanal y las decisiones técnicas en `CLAUDE.md`.
