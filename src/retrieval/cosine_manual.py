"""
Similitud coseno calculada A MANO, en Python puro (sin numpy), y comprobación
de que da el mismo resultado que FAISS.

    cos(a, b) = (a · b) / (|a| · |b|)

    a · b  (producto escalar) = a[0]*b[0] + a[1]*b[1] + ... + a[n-1]*b[n-1]
    |a|    (norma, longitud)  = raíz cuadrada de (a[0]² + a[1]² + ... + a[n-1]²)

El coseno mide el ÁNGULO entre dos vectores, no su longitud: vale 1 si apuntan
en la misma dirección, 0 si son perpendiculares y -1 si son opuestos. En los
embeddings, "misma dirección" significa "significado parecido".

Uso:
    python -m src.retrieval.cosine_manual
"""

import math

from src.embeddings.embedder import embeber, texto_consulta
from src.vectorstore.faiss_store import IndiceVectorial


# ---------------------------------------------------------------------------
# Las tres operaciones, sin ninguna librería
# ---------------------------------------------------------------------------

def producto_escalar(a: list[float], b: list[float]) -> float:
    assert len(a) == len(b), "Los vectores deben tener la misma dimensión"
    total = 0.0
    for x, y in zip(a, b):
        total += x * y
    return total


def norma(a: list[float]) -> float:
    return math.sqrt(producto_escalar(a, a))   # a·a = suma de los cuadrados


def similitud_coseno(a: list[float], b: list[float]) -> float:
    return producto_escalar(a, b) / (norma(a) * norma(b))


# ---------------------------------------------------------------------------
# Parte 1: ejemplo de juguete con vectores de 3 dimensiones
# ---------------------------------------------------------------------------

def ejemplo_juguete() -> None:
    print("=" * 70)
    print("PARTE 1: ejemplo de juguete (vectores de 3 dimensiones)")
    print("=" * 70)
    a = [1.0, 2.0, 3.0]
    casos = {
        "b = 2·a   (misma dirección)": [2.0, 4.0, 6.0],
        "c         (perpendicular)  ": [-2.0, 1.0, 0.0],
        "d = -a    (opuesto)        ": [-1.0, -2.0, -3.0],
    }
    print(f"a = {a}")
    for nombre, v in casos.items():
        pe = producto_escalar(a, v)
        print(f"\n{nombre}: {v}")
        print(f"  a·v = " + " + ".join(f"({x:g})({y:g})" for x, y in zip(a, v)) + f" = {pe:g}")
        print(f"  |a| = {norma(a):.4f}   |v| = {norma(v):.4f}")
        print(f"  cos = {pe:g} / ({norma(a):.4f} · {norma(v):.4f}) = {similitud_coseno(a, v):.4f}")

    # Por qué hay que normalizar antes de usar el producto escalar (IndexFlatIP):
    b = casos["b = 2·a   (misma dirección)"]
    print("\nPor qué normalizar: b tiene el mismo significado (dirección) que a, pero")
    print(f"es el doble de largo. Producto escalar a·a = {producto_escalar(a, a):g}, "
          f"a·b = {producto_escalar(a, b):g}: ¡b 'ganaría' a la propia a!")
    print(f"El coseno no se deja engañar: cos(a, a) = {similitud_coseno(a, a):.4f}, "
          f"cos(a, b) = {similitud_coseno(a, b):.4f}.")
    print("Con vectores de norma 1, producto escalar y coseno coinciden: por eso")
    print("FAISS IndexFlatIP + vectores normalizados = búsqueda por coseno.")


# ---------------------------------------------------------------------------
# Parte 2: casos reales, a mano frente a FAISS
# ---------------------------------------------------------------------------

PREGUNTAS = [
    "¿Cuántos puntos de Experiencia cuesta aumentar un Atributo?",   # Personajes
    "¿Qué hace el poder Puntería certera de Celeridad?",             # Disciplinas
    "¿Qué ocurre si saco un crítico en una tirada?",                 # Reglas
]


def comparar_con_faiss(k: int = 3) -> None:
    print("\n" + "=" * 70)
    print("PARTE 2: casos reales (768 dimensiones, 324 chunks)")
    print("=" * 70)
    indice = IndiceVectorial.cargar("estructural")
    # Los vectores de los chunks, sacados del propio índice FAISS (normalizados).
    vectores_chunks = [list(map(float, indice.indice.reconstruct(i)))
                       for i in range(indice.indice.ntotal)]
    vectores_preguntas = embeber([texto_consulta(p) for p in PREGUNTAS])

    diferencia_maxima = 0.0
    for pregunta, vector in zip(PREGUNTAS, vectores_preguntas):
        # A mano: coseno con TODOS los chunks y ordenar de mayor a menor.
        a_mano = sorted(((similitud_coseno(vector, v), i) for i, v in enumerate(vectores_chunks)),
                        reverse=True)[:k]
        # FAISS
        con_faiss = indice.buscar(vector, k)

        print(f"\nPregunta: {pregunta}")
        print(f"  {'#':<3}{'a mano':>9}{'FAISS':>9}   chunk (ruta)")
        for puesto, ((s_mano, i), (chunk, s_faiss)) in enumerate(zip(a_mano, con_faiss), 1):
            mismo = "✓" if indice.chunks[i].id == chunk.id else "✗ DISTINTO"
            diferencia_maxima = max(diferencia_maxima, abs(s_mano - s_faiss))
            print(f"  {puesto:<3}{s_mano:>9.5f}{s_faiss:>9.5f}   {mismo} {chunk.id} "
                  f"{' > '.join(chunk.ruta[-2:])} (pág. {chunk.pagina_inicio})")

    print(f"\nDiferencia máxima entre coseno a mano y FAISS: {diferencia_maxima:.2e}")
    print("(FAISS trabaja en float32 y Python en float64: diferencias del orden de 1e-7)")


if __name__ == "__main__":
    ejemplo_juguete()
    comparar_con_faiss()
