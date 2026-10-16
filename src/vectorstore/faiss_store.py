"""
Vector store con FAISS: índice IndexFlatIP con vectores normalizados.

- IndexFlatIP calcula el producto escalar (inner product, "IP") entre la
  consulta y TODOS los vectores guardados: búsqueda exacta ("flat"), sin
  aproximaciones. Con unos cientos de chunks es instantánea.
- Si los vectores tienen norma 1, el producto escalar ES la similitud coseno:
      cos(a, b) = a·b / (|a|·|b|) = a·b     cuando |a| = |b| = 1
  Por eso se normaliza siempre antes de añadir y antes de buscar, aunque
  gemini-embedding-2 ya los devuelva normalizados: así no dependemos del modelo.
  (La comprobación a mano está en src/retrieval/cosine_manual.py.)

Uso (construir el índice y guardarlo en storage/):
    python -m src.vectorstore.faiss_store                      (chunks estructurales)
    python -m src.vectorstore.faiss_store --estrategia fijo    (baseline)
"""

import argparse
import json
from dataclasses import asdict

import faiss
import numpy as np

from src import config
from src.chunking.chunker import Chunk, chunks_estructurales, chunks_fijos
from src.embeddings.embedder import embeber_chunks
from src.ingest.loader import cargar_documentos


def normalizar_filas(vectores) -> np.ndarray:
    """Matriz float32 (lo que usa FAISS) con cada fila dividida por su norma."""
    matriz = np.array(vectores, dtype="float32")
    faiss.normalize_L2(matriz)   # modifica la matriz: cada fila pasa a tener norma 1
    return matriz


class IndiceVectorial:
    """Un índice FAISS junto con los chunks que representa cada posición."""

    def __init__(self, dimension: int = config.DIMENSION_EMBEDDINGS):
        self.indice = faiss.IndexFlatIP(dimension)
        self.chunks: list[Chunk] = []   # chunks[i] corresponde al vector i

    def anadir(self, chunks: list[Chunk], vectores) -> None:
        self.indice.add(normalizar_filas(vectores))
        self.chunks.extend(chunks)

    def buscar(self, vector_consulta, k: int = 5) -> list[tuple[Chunk, float]]:
        """Los k chunks más parecidos a la consulta, con su similitud coseno."""
        similitudes, posiciones = self.indice.search(normalizar_filas([vector_consulta]), k)
        return [(self.chunks[i], float(s))
                for i, s in zip(posiciones[0], similitudes[0]) if i != -1]

    # --- Persistencia: el índice en .faiss y los chunks en .json ---
    def guardar(self, nombre: str) -> None:
        config.CARPETA_STORAGE.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.indice, str(config.CARPETA_STORAGE / f"indice_{nombre}.faiss"))
        datos = [asdict(c) for c in self.chunks]
        (config.CARPETA_STORAGE / f"indice_{nombre}.json").write_text(
            json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")

    @classmethod
    def cargar(cls, nombre: str) -> "IndiceVectorial":
        nuevo = cls()
        nuevo.indice = faiss.read_index(str(config.CARPETA_STORAGE / f"indice_{nombre}.faiss"))
        datos = json.loads((config.CARPETA_STORAGE / f"indice_{nombre}.json").read_text(encoding="utf-8"))
        nuevo.chunks = [Chunk(**d) for d in datos]
        return nuevo


def guardar_secciones(almacen: dict, nombre: str) -> None:
    """Almacén de secciones (para la expansión al padre del día 3)."""
    datos = {}
    for s in almacen.values():
        paginas = [p for p, _ in s.lineas if p is not None]
        datos[s.id] = {
            "titulo": s.titulo, "nivel": s.nivel, "padre_id": s.padre_id,
            "hijos_ids": s.hijos_ids, "texto": "\n".join(l for _, l in s.lineas).strip(),
            "pagina_inicio": min(paginas) if paginas else None,
            "pagina_fin": max(paginas) if paginas else None,
        }
    (config.CARPETA_STORAGE / f"secciones_{nombre}.json").write_text(
        json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")


def construir(estrategia: str) -> IndiceVectorial:
    """Carga documentos -> chunks -> embeddings -> índice FAISS, y lo guarda."""
    paginas = cargar_documentos()
    if estrategia == "estructural":
        chunks, almacen = chunks_estructurales(paginas)
        guardar_secciones(almacen, estrategia)
    else:
        chunks = chunks_fijos(paginas)
    print(f"Estrategia '{estrategia}': {len(chunks)} chunks")

    vectores = embeber_chunks(chunks)
    indice = IndiceVectorial()
    indice.anadir(chunks, vectores)
    indice.guardar(estrategia)
    print(f"Índice guardado: {indice.indice.ntotal} vectores de dimensión {indice.indice.d}")
    return indice


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Construir el índice FAISS.")
    parser.add_argument("--estrategia", choices=["estructural", "fijo"], default="estructural")
    construir(parser.parse_args().estrategia)
