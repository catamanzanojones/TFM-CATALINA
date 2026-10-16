"""
Chunking: trocea las páginas del corpus en fragmentos (chunks) para indexar.

Dos estrategias:
  - chunks_fijos():          tamaño fijo con overlap sobre el texto seguido de
                             cada documento, sin mirar los títulos. Es el
                             baseline (experimento P1).
  - chunks_estructurales():  un chunk por sección lógica según los títulos del
                             Markdown. Las secciones largas se subdividen con el
                             mismo troceado de tamaño fijo y las muy cortas se
                             unen a la siguiente. Cada chunk lleva su ruta de
                             títulos y los ids de sus secciones ancestro.

Ambas devuelven objetos Chunk con documento y páginas (para las citas).
chunks_estructurales() devuelve además el almacén de secciones, que el día 3
permitirá pasar al LLM la sección padre completa de un chunk recuperado.

Uso (estadísticas y volcado a storage/ para inspeccionarlos):
    python -m src.chunking.chunker
"""

import bisect
import json
import re
import statistics
from dataclasses import asdict, dataclass, field

from src import config
from src.ingest.loader import Pagina, cargar_documentos

TITULO = re.compile(r"^(#{1,6}) (.*)$")


@dataclass
class Chunk:
    id: str
    doc_id: str
    documento: str                 # nombre legible, para las citas
    texto: str
    pagina_inicio: int | None
    pagina_fin: int | None
    ruta: list[str] = field(default_factory=list)            # títulos, del capítulo hacia abajo
    seccion_id: str | None = None                            # sección más profunda que lo contiene
    ancestros_ids: list[str] = field(default_factory=list)   # secciones por encima de seccion_id

    @property
    def texto_con_ruta(self) -> str:
        """Texto que se convertirá en embedding: la ruta de títulos + el texto.
        Así el vector "sabe" de qué capítulo y sección habla el fragmento."""
        if not self.ruta:
            return self.texto
        return " > ".join(self.ruta) + "\n\n" + self.texto


@dataclass
class Seccion:
    id: str
    doc_id: str
    titulo: str
    nivel: int                     # 0 = raíz del documento
    padre_id: str | None
    hijos_ids: list[str] = field(default_factory=list)
    lineas: list[tuple] = field(default_factory=list)        # (página, línea) de su texto propio


# ---------------------------------------------------------------------------
# Utilidades: texto seguido con seguimiento de páginas
# ---------------------------------------------------------------------------

def unir_lineas(lineas: list[tuple]):
    """
    Une una lista de (página, línea) en un solo texto y apunta en qué posición
    empieza cada página, para poder saber después la página de cualquier carácter.
    Devuelve (texto, posiciones de inicio, páginas).
    """
    partes, inicios, paginas = [], [], []
    posicion = 0
    for pagina, linea in lineas:
        if not paginas or paginas[-1] != pagina:
            inicios.append(posicion)
            paginas.append(pagina)
        partes.append(linea)
        posicion += len(linea) + 1   # +1 por el salto de línea que las une
    return "\n".join(partes), inicios, paginas


def pagina_en(posicion: int, inicios: list[int], paginas: list) -> int | None:
    """Página en la que cae el carácter `posicion` (búsqueda binaria)."""
    return paginas[bisect.bisect_right(inicios, posicion) - 1]


def agrupar_por_documento(paginas: list[Pagina]) -> list[tuple[str, list[Pagina]]]:
    """[(doc_id, páginas de ese documento)], manteniendo el orden."""
    grupos = {}
    for p in paginas:
        grupos.setdefault(p.doc_id, []).append(p)
    return list(grupos.items())


# ---------------------------------------------------------------------------
# Estrategia 1: tamaño fijo con overlap (baseline)
# ---------------------------------------------------------------------------

def trocear_fijo(texto: str, tamano: int, overlap: int) -> list[tuple[int, int]]:
    """
    Trocea `texto` en ventanas de unos `tamano` caracteres que se solapan
    `overlap` caracteres. Devuelve las posiciones (inicio, fin) de cada trozo.

    Para no partir palabras: si un corte cae a mitad de palabra, se retrocede
    hasta el último espacio o salto de línea, y el trozo siguiente empieza al
    principio de una palabra.
    """
    assert 0 <= overlap < tamano, "El overlap debe ser menor que el tamaño"
    trozos, inicio = [], 0
    while inicio < len(texto):
        fin = min(inicio + tamano, len(texto))
        if fin < len(texto):
            hueco = max(texto.rfind(" ", inicio, fin), texto.rfind("\n", inicio, fin))
            if hueco > inicio + overlap:   # retroceder solo si el trozo no queda demasiado corto
                fin = hueco
        trozos.append((inicio, fin))
        if fin == len(texto):
            break
        # El siguiente trozo empieza `overlap` caracteres antes del final de
        # este, avanzando hasta el principio de una palabra.
        siguiente = fin - overlap
        while siguiente < fin and not texto[siguiente - 1].isspace():
            siguiente += 1
        inicio = siguiente
    return trozos


def chunks_fijos(paginas: list[Pagina], tamano: int = config.CHUNK_FIJO_TAMANO,
                 overlap: int = config.CHUNK_FIJO_OVERLAP) -> list[Chunk]:
    """Baseline: tamaño fijo sobre el texto seguido de cada documento (solo corpus)."""
    chunks = []
    for doc_id, pags in agrupar_por_documento(paginas):
        lineas = [(p.pagina, linea) for p in pags if p.en_corpus
                  for linea in p.texto.splitlines()]
        texto, inicios, nums = unir_lineas(lineas)
        for a, b in trocear_fijo(texto, tamano, overlap):
            contenido = texto[a:b].strip()
            if contenido:
                chunks.append(Chunk(
                    id=f"f{len(chunks):04d}", doc_id=doc_id, documento=pags[0].documento,
                    texto=contenido,
                    pagina_inicio=pagina_en(a, inicios, nums),
                    pagina_fin=pagina_en(b - 1, inicios, nums),
                ))
    return chunks


# ---------------------------------------------------------------------------
# Estrategia 2: estructural híbrida (por títulos + tamaño fijo si hace falta)
# ---------------------------------------------------------------------------

def construir_secciones(pags: list[Pagina], prefijo: str) -> list[Seccion]:
    """
    Recorre las páginas de un documento y construye el árbol de secciones.

    Los títulos se leen en TODAS las páginas, para que la jerarquía sea
    correcta, pero el texto solo se guarda si la página está en el corpus.
    Devuelve las secciones en orden de lectura; la primera es la raíz (nivel 0).
    """
    raiz = Seccion(id=f"{prefijo}-s0000", doc_id=pags[0].doc_id,
                   titulo=pags[0].documento, nivel=0, padre_id=None)
    secciones = [raiz]
    pila = [raiz]   # secciones abiertas, de la raíz a la actual

    for p in pags:
        for linea in p.texto.splitlines():
            m = TITULO.match(linea)
            if m:
                nivel = len(m.group(1))
                # Un título de nivel N cierra las secciones abiertas de nivel >= N.
                while pila[-1].nivel >= nivel:
                    pila.pop()
                nueva = Seccion(id=f"{prefijo}-s{len(secciones):04d}", doc_id=p.doc_id,
                                titulo=m.group(2).strip(), nivel=nivel, padre_id=pila[-1].id)
                pila[-1].hijos_ids.append(nueva.id)
                secciones.append(nueva)
                pila.append(nueva)
                if p.en_corpus:
                    nueva.lineas.append((p.pagina, linea))   # el título va en el texto
            elif p.en_corpus:
                pila[-1].lineas.append((p.pagina, linea))
    return secciones


def cadena(seccion: Seccion, por_id: dict) -> list[Seccion]:
    """Secciones desde la raíz hasta `seccion` (ambas incluidas)."""
    resultado = [seccion]
    while resultado[-1].padre_id is not None:
        resultado.append(por_id[resultado[-1].padre_id])
    return resultado[::-1]


def ancestro_comun(secciones: list[Seccion], por_id: dict) -> Seccion:
    """Sección más profunda que contiene a todas las dadas."""
    cadenas = [cadena(s, por_id) for s in secciones]
    comun = cadenas[0][0]
    for nivel_secciones in zip(*cadenas):
        if all(s.id == nivel_secciones[0].id for s in nivel_secciones):
            comun = nivel_secciones[0]
        else:
            break
    return comun


def longitud_contenido(lineas: list[tuple]) -> int:
    """Caracteres de texto, sin contar las líneas de título."""
    return sum(len(linea.strip()) for _, linea in lineas if not TITULO.match(linea))


def chunks_estructurales(paginas: list[Pagina], maximo: int = config.CHUNK_TAMANO_MAX,
                         overlap: int = config.CHUNK_OVERLAP,
                         minimo: int = config.CHUNK_TAMANO_MIN):
    """
    Un chunk por sección; las de más de `maximo` caracteres se subdividen con
    trocear_fijo() y las de menos de `minimo` se unen a la siguiente (si es su
    hija o su hermana). Devuelve (chunks, almacén de secciones {id: Seccion}).
    """
    chunks, almacen = [], {}

    def emitir(lineas, secciones_bloque, por_id, documento):
        # La ruta del chunk es la de la sección más profunda que contiene todo
        # su texto (si se han unido secciones hermanas, la de su padre común).
        # Las secciones que solo aportan su título (p. ej. "Nivel 4" seguido
        # directamente de "Puntería certera") no cuentan para la ruta.
        con_texto = [s for s in secciones_bloque if longitud_contenido(s.lineas) > 0]
        destino = ancestro_comun(con_texto or secciones_bloque, por_id)
        superiores = [s for s in cadena(destino, por_id) if s.nivel > 0]
        ruta = [s.titulo for s in superiores]
        ancestros = [s.id for s in superiores[:-1]]
        texto, inicios, nums = unir_lineas(lineas)
        tramos = [(0, len(texto))] if len(texto) <= maximo else trocear_fijo(texto, maximo, overlap)
        for a, b in tramos:
            contenido = texto[a:b].strip()
            if contenido:
                chunks.append(Chunk(
                    id=f"e{len(chunks):04d}", doc_id=destino.doc_id, documento=documento,
                    texto=contenido,
                    pagina_inicio=pagina_en(a, inicios, nums),
                    pagina_fin=pagina_en(b - 1, inicios, nums),
                    ruta=ruta,
                    seccion_id=destino.id if destino.nivel > 0 else None,
                    ancestros_ids=ancestros,
                ))

    for indice, (doc_id, pags) in enumerate(agrupar_por_documento(paginas)):
        documento = pags[0].documento
        secciones = construir_secciones(pags, prefijo=f"d{indice}")
        por_id = {s.id: s for s in secciones}
        almacen.update(por_id)

        arrastre, arrastre_secciones = [], []   # secciones cortas pendientes de unir
        for s in secciones:
            if not s.lineas:
                continue   # sección sin texto dentro del corpus
            if arrastre:
                ultima = arrastre_secciones[-1]
                if s.padre_id not in (ultima.id, ultima.padre_id):
                    # La siguiente no es hija ni hermana: la corta va sola.
                    emitir(arrastre, arrastre_secciones, por_id, documento)
                    arrastre, arrastre_secciones = [], []
            lineas = arrastre + s.lineas
            bloque = arrastre_secciones + [s]
            if longitud_contenido(lineas) < minimo:
                arrastre, arrastre_secciones = lineas, bloque   # se une a la siguiente
            else:
                emitir(lineas, bloque, por_id, documento)
                arrastre, arrastre_secciones = [], []
        if arrastre:
            emitir(arrastre, arrastre_secciones, por_id, documento)   # la última del documento

    return chunks, almacen


# ---------------------------------------------------------------------------
# Estadísticas y volcado para inspección
# ---------------------------------------------------------------------------

def resumen(nombre: str, chunks: list[Chunk]) -> None:
    tam = sorted(len(c.texto) for c in chunks)
    print(f"{nombre}: {len(chunks)} chunks | tamaño mín {tam[0]} | mediana "
          f"{int(statistics.median(tam))} | p90 {tam[int(len(tam) * 0.9)]} | máx {tam[-1]}")


def guardar(chunks: list[Chunk], nombre_archivo: str) -> None:
    config.CARPETA_STORAGE.mkdir(parents=True, exist_ok=True)
    ruta = config.CARPETA_STORAGE / nombre_archivo
    datos = [asdict(c) | {"texto_con_ruta": c.texto_con_ruta} for c in chunks]
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  -> {ruta}")


if __name__ == "__main__":
    paginas = cargar_documentos()

    fijos = chunks_fijos(paginas)
    resumen("Tamaño fijo (baseline)", fijos)
    guardar(fijos, "chunks_fijos.json")

    estructurales, almacen = chunks_estructurales(paginas)
    resumen("Estructural híbrido   ", estructurales)
    guardar(estructurales, "chunks_estructurales.json")

    por_seccion = {}
    for c in estructurales:
        por_seccion[c.seccion_id] = por_seccion.get(c.seccion_id, 0) + 1
    subdivididas = sum(1 for n in por_seccion.values() if n > 1)
    unidos = sum(1 for c in estructurales
                 if sum(1 for l in c.texto.splitlines() if TITULO.match(l)) > 1)
    print(f"  Secciones subdivididas por tamaño: {subdivididas} | "
          f"chunks que unen varias secciones cortas: {unidos}")
