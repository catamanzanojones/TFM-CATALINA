"""
Configuración central del sistema RAG.

Todo lo que depende del documento concreto (nombre para las citas, páginas que
forman el corpus, perfil tipográfico) vive aquí, en DOCUMENTOS. El resto del
código es genérico: para cambiar de dominio basta con cambiar este archivo.

Los modelos de Gemini se añadirán el día 2, tras verificar cuáles están
vigentes en el tier gratuito.
"""

from pathlib import Path

# --- Rutas (absolutas, para que funcionen igual desde scripts y notebooks) ---
RAIZ = Path(__file__).resolve().parent.parent
CARPETA_RAW = RAIZ / "data" / "raw"
CARPETA_PROCESADOS = RAIZ / "data" / "processed"              # salida de Docling
CARPETA_ESTRUCTURADOS = CARPETA_PROCESADOS / "estructurado"   # Markdown con jerarquía
CARPETA_STORAGE = RAIZ / "storage"

# --- Documentos ---
# Clave: nombre del archivo sin extensión. Un documento que no aparezca aquí se
# usa entero, con el nombre de archivo en las citas y sin jerarquía de títulos.
DOCUMENTOS = {
    "Vampiro _ la mascarada -- Mark Rein-Hagen -- Quinta edición, Madrid, 2018": {
        # Nombre legible que aparecerá en las citas.
        "nombre": "Vampiro: La Mascarada (5ª ed.)",
        # Páginas IMPRESAS que forman el corpus (ambos extremos incluidos).
        "rangos_paginas": [
            (115, 132),   # Reglas
            (135, 171),   # Personajes: creación de personajes y rasgos centrales
            (243, 288),   # Disciplinas
            (295, 305),   # Sistemas avanzados: conflicto avanzado (combate)
        ],
        # Perfil tipográfico: (fuente, tamaño en pt) -> nivel de título.
        # Obtenido analizando las fuentes del PDF en las páginas del corpus.
        "titulos": {
            ("BodoniSvtyTwoITCTT-Book-SC700", 56): 1,   # capítulo (Reglas, Disciplinas)
            ("BodoniSvtyTwoITCTT-Book", 36): 2,         # parte (Creación de personajes)
            ("BodoniSvtyTwoITCTT-Book", 22): 3,         # sección (Tiempo, Celeridad)
            ("Cormorant-Bold", 14): 4,                  # apartado (Rasgos, Nivel 4)
            ("GillSans-Bold-SC700", 7): 5,              # subapartado en versalitas
        },
    },
}

# --- Chunking (estructural híbrido) ---
CHUNK_TAMANO_MAX = 3000   # caracteres; las secciones más largas se subdividen
CHUNK_OVERLAP = 400       # caracteres de solape al subdividir una sección
CHUNK_TAMANO_MIN = 300    # secciones más cortas se unen a la siguiente

# --- Chunking de tamaño fijo (baseline para el experimento P1) ---
CHUNK_FIJO_TAMANO = 1000  # caracteres
CHUNK_FIJO_OVERLAP = 200  # caracteres
