"""
Embeddings de chunks y de preguntas, con caché en disco.

Formato de los textos: gemini-embedding-2 no tiene parámetro task_type, así que
la tarea se indica con un prefijo (config.PREFIJO_*):
  - pregunta: "task: search result | query: {pregunta}"
  - chunk:    "title: {documento > ruta de títulos} | text: {texto}"
El "title" de cada chunk es su ruta de títulos: justo el contexto jerárquico
que queríamos que tuviera el vector.

Caché: un diccionario {clave: vector} guardado en storage/cache_embeddings.json.
La clave es el hash SHA-256 de (modelo, dimensión, texto formateado): si cambia
cualquiera de los tres, la clave cambia y se recalcula; si no, nunca se repite
una llamada a la API. Se guarda tras cada lote, para no perder lo ya calculado
si la API falla a mitad.
"""

import hashlib
import json

from src import config
from src.chunking.chunker import Chunk
from src.llm_clients import embeber_textos


def texto_documento(chunk: Chunk) -> str:
    """Texto que se envía al modelo para un chunk: ruta como título + contenido."""
    titulo = " > ".join([chunk.documento] + chunk.ruta)
    return config.PREFIJO_DOCUMENTO.format(titulo=titulo, texto=chunk.texto)


def texto_consulta(pregunta: str) -> str:
    """Texto que se envía al modelo para una pregunta."""
    return config.PREFIJO_CONSULTA.format(texto=pregunta)


def clave_cache(texto: str) -> str:
    base = f"{config.MODELO_EMBEDDINGS}|{config.DIMENSION_EMBEDDINGS}|{texto}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def cargar_cache() -> dict:
    if config.CACHE_EMBEDDINGS.exists():
        return json.loads(config.CACHE_EMBEDDINGS.read_text(encoding="utf-8"))
    return {}


def guardar_cache(cache: dict) -> None:
    config.CARPETA_STORAGE.mkdir(parents=True, exist_ok=True)
    config.CACHE_EMBEDDINGS.write_text(json.dumps(cache), encoding="utf-8")


def embeber(textos: list[str]) -> list[list[float]]:
    """
    Embeddings de textos ya formateados. Solo se llama a la API para los que no
    están en la caché.
    """
    cache = cargar_cache()
    claves = [clave_cache(t) for t in textos]
    pendientes = {k: t for k, t in zip(claves, textos) if k not in cache}   # sin repetidos
    if pendientes:
        print(f"  Embeddings: {len(textos) - len(pendientes)} en caché, "
              f"{len(pendientes)} nuevos -> llamando a la API...")
        lista = list(pendientes.items())
        for inicio in range(0, len(lista), config.EMBEDDINGS_POR_LOTE):
            lote = lista[inicio: inicio + config.EMBEDDINGS_POR_LOTE]
            vectores = embeber_textos([t for _, t in lote])
            cache.update({k: v for (k, _), v in zip(lote, vectores)})
            guardar_cache(cache)   # se guarda tras cada lote
    return [cache[k] for k in claves]


def embeber_chunks(chunks: list[Chunk]) -> list[list[float]]:
    return embeber([texto_documento(c) for c in chunks])


def embeber_consulta(pregunta: str) -> list[float]:
    return embeber([texto_consulta(pregunta)])[0]
