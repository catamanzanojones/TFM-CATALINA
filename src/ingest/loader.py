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
from src.ingest.estructura import normalizar

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
    # Listas de niveles (· a ·····): Docling convierte el "•" del nivel 1 en una
    # viñeta y el punto se pierde. Si a un elemento sin puntos le sigue uno con
    # dos, es el nivel 1: "- Conoces..." / "- ·· Pasas..." -> "- · Conoces...".
    texto = re.sub(r"^- (?![·•])(.*)\n(- [·•]{2}(?![·•]))", r"- · \1\n\2", texto, flags=re.M)
    texto = quitar_decoracion(texto)
    # Varias líneas en blanco seguidas -> una sola
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def es_decorativo(linea: str) -> bool:
    """
    Texto decorativo de las ilustraciones, sin contenido (aparece al exportar
    con traverse_pictures=True):
      - letras o cifras sueltas espaciadas: "2 4 8", "R E G L A S", "L I BRO BÁS I CO";
      - una palabra repetida (rótulos): "ejecutivo Ejecutivo", "ar tista Artista".
    """
    texto = linea.strip().strip("*").strip()
    if not texto or texto.startswith(("-", "|", "#")):
        return False   # listas, tablas y títulos no se tocan
    palabras = texto.split()
    if texto.upper() == texto and sum(1 for p in palabras if len(p) == 1) >= 3:
        return True
    letras = normalizar(texto)
    mitad = len(letras) // 2
    return len(palabras) <= 4 and len(letras) >= 6 and letras[:mitad] == letras[mitad:]


def quitar_decoracion(texto: str) -> str:
    """Quita las líneas decorativas y los rótulos duplicados en dos líneas seguidas
    ("Veterano" / "veterano")."""
    lineas = [l for l in texto.splitlines() if not es_decorativo(l)]
    resultado = []
    for linea in lineas:
        previa = next((l for l in reversed(resultado) if l.strip()), "")
        estructural = ("-", "|", "#")   # listas, tablas y títulos no se tocan
        corta = 0 < len(linea.split()) <= 2 and not linea.lstrip().startswith(estructural)
        if corta and not previa.lstrip().startswith(estructural) and normalizar(linea) == normalizar(previa):
            # Rótulo repetido: se quitan las dos apariciones.
            while resultado and not resultado[-1].strip():
                resultado.pop()
            resultado.pop()
            continue
        resultado.append(linea)
    return "\n".join(resultado)


ETIQUETA = re.compile(r"^\*\*.+\*\*$")   # línea entera en negrita ("##" de Docling rebajado)


def frase_a_medias(linea: str) -> bool:
    """¿Es una línea de párrafo que se corta sin terminar la frase?"""
    linea = linea.strip()
    if not linea or linea.startswith(("-", "|", "#", "*")):
        return False   # vacía, lista, tabla, título o negrita: no es un párrafo
    return linea[-1] not in '.:;!?»)"”…'


def quitar_etiquetas_flotantes(paginas: list["Pagina"]) -> int:
    """
    Quita las líneas en negrita que interrumpen una frase a medias, p. ej.:
        "...¿o secarás a un" / "**Investigador investigador**" / "Cainita para..."
    Son etiquetas de ilustraciones que Docling coloca en mitad del texto. Se mira
    la última línea con texto, aunque esté en la página anterior.
    Devuelve cuántas se han quitado.
    """
    anterior, quitadas = "", 0
    for p in paginas:
        nuevas = []
        for linea in p.texto.splitlines():
            if ETIQUETA.match(linea.strip()) and frase_a_medias(anterior):
                quitadas += 1
                continue
            nuevas.append(linea)
            if linea.strip():
                anterior = linea
        p.texto = "\n".join(nuevas)
    return quitadas


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
    quitar_etiquetas_flotantes(paginas)   # necesita ver varias páginas seguidas
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
