"""
Loader: lee los documentos ya convertidos y los devuelve como una lista de
páginas limpias, cada una con su documento y su número de página.

Fuentes que lee:
  - data/processed/estructurado/*.md  Markdown con jerarquía de títulos. Si un
                                      documento no tiene versión estructurada,
                                      se usa la de data/processed/.
  - data/raw/*.md y data/raw/*.txt    Documentos sueltos, sin marcadores de página.

Cada página se marca como dentro o fuera del corpus según los rangos de
config.py. Las de fuera NO se descartan aquí: el chunker necesita sus títulos
para construir la jerarquía (p. ej. el título del capítulo "Personajes" está en
la pág. 133, fuera del corpus, pero sus secciones sí entran). El chunker solo
usa el texto de las páginas del corpus.

Uso (estadísticas):
    python -m src.ingest.loader
"""

import re
from dataclasses import dataclass
from pathlib import Path

from src import config

MARCADOR = re.compile(r"<!-- pagina: (\d+) -->")


@dataclass
class Pagina:
    doc_id: str          # nombre del archivo sin extensión
    documento: str       # nombre legible, para las citas
    pagina: int | None   # página impresa (None si el documento no tiene marcadores)
    texto: str
    en_corpus: bool      # si su texto forma parte del corpus


def limpiar(texto: str) -> str:
    """Limpieza mínima de los restos de maquetación que deja Docling."""
    texto = texto.replace("<!-- image -->", "")
    # Viñetas decorativas: "- ■ ■ Coste: ..." -> "- Coste: ..."
    texto = re.sub(r"(?:■\s*)+", "", texto)
    # Palabra partida por un salto de columna: "se resuel-\n\nve" -> "se resuelve"
    texto = re.sub(r"([a-záéíóúñü])-\n\s*\n([a-záéíóúñü])", r"\1\2", texto)
    # Varias líneas en blanco seguidas -> una sola
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def nombre_legible(doc_id: str) -> str:
    """Nombre para las citas (config.py); si no hay, el nombre del archivo."""
    return config.DOCUMENTOS.get(doc_id, {}).get("nombre", doc_id)


def en_corpus(doc_id: str, pagina: int | None) -> bool:
    """¿Entra esta página en el corpus según los rangos de config.py?"""
    rangos = config.DOCUMENTOS.get(doc_id, {}).get("rangos_paginas")
    if not rangos or pagina is None:
        return True   # sin rangos definidos, todo el documento es corpus
    return any(inicio <= pagina <= fin for inicio, fin in rangos)


def cargar_documento(ruta: Path) -> list[Pagina]:
    """Lee un .md/.txt y lo parte en páginas usando los marcadores <!-- pagina: N -->."""
    doc_id = ruta.stem
    nombre = nombre_legible(doc_id)
    texto = ruta.read_text(encoding="utf-8")

    trozos = MARCADOR.split(texto)   # [texto_previo, nº, texto, nº, texto, ...]
    if len(trozos) == 1:
        # Sin marcadores: documento suelto, entra entero como una sola "página".
        return [Pagina(doc_id, nombre, None, limpiar(texto), True)]

    paginas = []
    for numero, contenido in zip(trozos[1::2], trozos[2::2]):
        n = int(numero)
        paginas.append(Pagina(doc_id, nombre, n, limpiar(contenido), en_corpus(doc_id, n)))
    return paginas


def rutas_documentos() -> list[Path]:
    """Archivos a cargar: versión estructurada si existe, más los sueltos de data/raw/."""
    rutas = []
    for ruta in sorted(config.CARPETA_PROCESADOS.glob("*.md")):
        estructurado = config.CARPETA_ESTRUCTURADOS / ruta.name
        rutas.append(estructurado if estructurado.exists() else ruta)
    rutas += sorted(config.CARPETA_RAW.glob("*.md")) + sorted(config.CARPETA_RAW.glob("*.txt"))
    return rutas


def cargar_documentos() -> list[Pagina]:
    """Todas las páginas de todos los documentos, en orden de lectura."""
    paginas = []
    for ruta in rutas_documentos():
        paginas.extend(cargar_documento(ruta))
    return paginas


if __name__ == "__main__":
    paginas = cargar_documentos()
    corpus = [p for p in paginas if p.en_corpus]
    documentos = sorted({p.documento for p in paginas})
    print(f"Documentos: {len(documentos)} -> {documentos}")
    print(f"Páginas cargadas: {len(paginas)} | en el corpus: {len(corpus)}")
    print(f"Caracteres en el corpus: {sum(len(p.texto) for p in corpus):,}")
