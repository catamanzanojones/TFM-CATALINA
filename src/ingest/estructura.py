"""
Reconstrucción de la jerarquía de títulos del Markdown de Docling.

Problema: Docling marca todos los títulos con el mismo nivel (##) y no detecta
los subtítulos en versalitas que van pegados al párrafo ("frenesí de furia Las
provocaciones..."). Para trocear por secciones lógicas necesitamos la jerarquía.

Idea: la jerarquía está en la tipografía del PDF (cada nivel de título usa una
fuente y un tamaño concretos). Este script:
  1. Lee con pypdf, página a página, los textos escritos con estilo de título.
     Qué estilo es qué nivel lo dice el "perfil tipográfico" del documento en
     config.py; el código no sabe nada del dominio.
  2. Recorre el Markdown de Docling página a página y:
       - pone a cada título su nivel real (#, ##, ###...) si su texto coincide
         con un título del PDF en esa misma página;
       - separa los títulos pegados al inicio de un párrafo;
       - rebaja a negrita los "##" de Docling que no son títulos según el
         perfil (p. ej. "EJEMPLO:"), para que no corten secciones;
       - usa los marcadores del PDF como respaldo para los títulos de capítulo.
  3. Guarda el resultado en data/processed/estructurado/ e imprime un informe.

Los documentos sin perfil tipográfico se copian sin cambios.

Uso:
    python -m src.ingest.estructura
"""

import logging
import re
import unicodedata

from pypdf import PdfReader

from src import config

logging.getLogger("pypdf").setLevel(logging.ERROR)   # silenciar avisos de fuentes

MARCADOR = re.compile(r"<!-- pagina: (\d+) -->")
MAX_LINEAS_TITULO = 3   # un título puede venir partido en hasta 3 líneas


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes y solo letras/dígitos: "Nivel 4" -> "nivel4".
    Permite comparar títulos aunque cambien espacios, guiones o mayúsculas."""
    texto = unicodedata.normalize("NFKD", texto.lower())   # "á" -> "a" + tilde suelta
    return "".join(c for c in texto if c.isalnum())        # la tilde suelta no es alnum


# ---------------------------------------------------------------------------
# 1) Títulos según la tipografía del PDF
# ---------------------------------------------------------------------------

def titulos_de_pagina(pagina_pdf, perfil: dict) -> list[tuple[str, int]]:
    """
    Devuelve los títulos (texto, nivel) de una página del PDF.

    pypdf llama a `visitor` con cada fragmento de texto, su fuente y su tamaño.
    Un título puede llegar partido en varios fragmentos ("disciplin" + "as") o
    en varias líneas, así que unimos los fragmentos seguidos del mismo nivel.
    """
    titulos = []
    estado = {"nivel_anterior": None}

    def visitor(texto, cm, tm, fuente, tamano):
        if not normalizar(texto):
            return   # espacios, saltos y guiones sueltos no cortan un título en curso
        nombre_fuente = (fuente or {}).get("/BaseFont", "").split("+")[-1]
        # El tamaño real es el nominal escalado por las matrices de texto (tm) y
        # de transformación (cm) del PDF.
        tamano_real = round(tamano * (tm[0] or 1) * (cm[0] or 1))
        nivel = perfil.get((nombre_fuente, tamano_real))
        if nivel is not None and nivel == estado["nivel_anterior"]:
            texto_previo, _ = titulos[-1]
            titulos[-1] = (texto_previo + " " + texto.strip(), nivel)   # continúa
        elif nivel is not None:
            titulos.append((texto.strip(), nivel))                       # título nuevo
        estado["nivel_anterior"] = nivel

    pagina_pdf.extract_text(visitor_text=visitor)
    return titulos


def capitulos_del_indice(lector: PdfReader) -> dict[int, str]:
    """
    Títulos de primer nivel de los marcadores del PDF: {índice de página: título}.
    Sirven de respaldo cuando el título de capítulo es decorativo y Docling no
    lo extrae (p. ej. la portadilla de "Reglas").
    """
    capitulos = {}
    for elemento in lector.outline:
        if isinstance(elemento, list):   # las listas son subniveles: se saltan
            continue
        try:
            capitulos[lector.get_destination_page_number(elemento)] = elemento.title.strip()
        except Exception:
            pass
    return capitulos


# ---------------------------------------------------------------------------
# 2) Colocar esos títulos en el Markdown de Docling
# ---------------------------------------------------------------------------

def cortar_prefijo(linea: str, clave: str):
    """
    Si `linea` empieza por el título cuya forma normalizada es `clave`,
    devuelve (título, resto). Si no, devuelve None.
    """
    acumulado = ""
    for i, caracter in enumerate(linea):
        acumulado += normalizar(caracter)
        if not clave.startswith(acumulado):
            return None
        if acumulado == clave:
            resto = linea[i + 1:]
            if resto[:1].isalnum():   # el título acabaría a mitad de palabra
                return None
            return linea[: i + 1], resto
    return None


def buscar_titulo(lineas: list[str], i: int, pendientes: list):
    """
    Intenta reconocer en lineas[i] uno de los títulos pendientes de la página.

    Devuelve (posición en pendientes, nivel, título, resto, última línea usada)
    o None. "resto" es el texto que iba pegado detrás del título.
    """
    linea = lineas[i]
    if linea.startswith("|"):          # no buscamos títulos dentro de tablas
        return None
    es_titulo_docling = linea.startswith("#")
    texto = linea.lstrip("#").strip()
    if len(normalizar(texto)) < 3:     # líneas vacías o solo símbolos
        return None

    for k, (_, clave, nivel) in enumerate(pendientes):
        # Docling a veces parte un título largo en varias líneas
        # ("círculo de protección" / "contra ghouls"): si la línea es solo el
        # principio del título, le añadimos las siguientes.
        candidato, j = texto, i
        while (clave.startswith(normalizar(candidato)) and normalizar(candidato) != clave
               and j + 1 < len(lineas) and j - i < MAX_LINEAS_TITULO):
            j += 1
            if lineas[j].strip():
                candidato += " " + lineas[j].lstrip("#").strip()

        corte = cortar_prefijo(candidato, clave)
        if not corte:
            continue
        titulo, resto = corte
        # La puntuación de cierre pertenece al título: "¿Cómo Cazas" + "?"
        cierre = len(resto) - len(resto.lstrip("?!)»”"))
        titulo, resto = titulo + resto[:cierre], resto[cierre:]
        resto = resto.lstrip(" :.;,—–-")   # "armas arrojadizas: Un..." -> "Un..."

        # Título pegado a un párrafo: solo si lo que sigue empieza una frase
        # nueva (mayúscula). Evita partir "Rasgos centrales son..." por
        # coincidir con el título "Rasgos".
        if not normalizar(resto) or resto[:1].isupper():
            return k, nivel, titulo, resto, j
        if es_titulo_docling and j == i:
            # Docling ya dijo que la línea es un título y lo que sigue va en
            # minúscula: es el final del propio título, que pypdf vio partido
            # ("Experiencia y" + "perfeccionamiento"). Nos quedamos la línea entera.
            return k, nivel, texto, "", j
    return None


def estructurar_pagina(texto_md: str, titulos: list[tuple[str, int]]):
    """
    Reescribe el Markdown de una página con la jerarquía de títulos.
    Devuelve (texto nuevo, niveles colocados, títulos no encontrados).
    """
    # Cada título del PDF se puede colocar una sola vez.
    pendientes = [(texto, normalizar(texto), nivel) for texto, nivel in titulos
                  if len(normalizar(texto)) >= 3]
    lineas = texto_md.splitlines()
    salida, niveles_colocados = [], []

    i = 0
    while i < len(lineas):
        encontrado = buscar_titulo(lineas, i, pendientes)
        if encontrado:
            k, nivel, titulo, resto, ultima = encontrado
            pendientes.pop(k)
            niveles_colocados.append(nivel)
            titulo = titulo.strip().rstrip(":")
            titulo = re.sub(r"(\w)- (\w)", r"\1\2", titulo)   # "fuer- za" -> "fuerza"
            salida.append("#" * nivel + " " + titulo[:1].upper() + titulo[1:])
            if normalizar(resto):
                salida.extend(["", resto.strip()])
            i = ultima + 1
            continue
        if lineas[i].startswith("#"):
            # "##" de Docling que no es título según el perfil (p. ej. "EJEMPLO:"):
            # lo dejamos en negrita para que no corte la sección.
            salida.append("**" + lineas[i].lstrip("#").strip() + "**")
        else:
            salida.append(lineas[i])
        i += 1

    no_encontrados = [(texto, nivel) for texto, _, nivel in pendientes]
    return "\n".join(salida), niveles_colocados, no_encontrados


def estructurar_documento(ruta_md, ruta_pdf, perfil: dict, rangos: list) -> str:
    """Aplica estructurar_pagina a todas las páginas e imprime un informe."""
    trozos = MARCADOR.split(ruta_md.read_text(encoding="utf-8"))
    # trozos = [texto_previo, nº página, texto, nº página, texto, ...]
    paginas_md = list(zip(trozos[1::2], trozos[2::2]))
    lector = PdfReader(str(ruta_pdf))
    # El Markdown tiene un marcador por cada página del PDF, en el mismo orden.
    assert len(paginas_md) == len(lector.pages), "El .md no corresponde a este PDF"
    capitulos = capitulos_del_indice(lector)

    salida, total_pdf, total_colocados, perdidos_corpus = [], 0, 0, []
    for indice, ((num_impresa, texto), pagina_pdf) in enumerate(zip(paginas_md, lector.pages)):
        titulos = titulos_de_pagina(pagina_pdf, perfil)
        nuevo, niveles, no_encontrados = estructurar_pagina(texto, titulos)
        # Respaldo: si aquí empieza un capítulo del índice y no se ha colocado
        # ningún título de nivel 1, lo añadimos al principio de la página.
        if indice in capitulos and 1 not in niveles:
            nuevo = f"# {capitulos[indice]}\n\n{nuevo}"
            no_encontrados = [(t, n) for t, n in no_encontrados if n != 1]
        salida.append(f"<!-- pagina: {num_impresa} -->\n\n{nuevo.strip()}\n")
        total_pdf += len(titulos)
        total_colocados += len(niveles)
        n = int(num_impresa)
        if any(a <= n <= b for a, b in rangos):
            perdidos_corpus += [(n, nivel, t) for t, nivel in no_encontrados]

    print(f"  Títulos en el PDF: {total_pdf} | colocados en el Markdown: {total_colocados}")
    print(f"  No colocados dentro del corpus: {len(perdidos_corpus)}")
    for n, nivel, t in perdidos_corpus[:30]:
        print(f"    pág. {n}, nivel {nivel}: {t!r}")
    return "\n".join(salida)


def main() -> None:
    config.CARPETA_ESTRUCTURADOS.mkdir(parents=True, exist_ok=True)
    for ruta_md in sorted(config.CARPETA_PROCESADOS.glob("*.md")):
        destino = config.CARPETA_ESTRUCTURADOS / ruta_md.name
        info = config.DOCUMENTOS.get(ruta_md.stem, {})
        ruta_pdf = config.CARPETA_RAW / f"{ruta_md.stem}.pdf"
        print(f"Estructurando: {ruta_md.name}")
        if "titulos" not in info or not ruta_pdf.exists():
            print("  Sin perfil tipográfico (o sin PDF): se copia sin cambios.")
            destino.write_text(ruta_md.read_text(encoding="utf-8"), encoding="utf-8")
            continue
        markdown = estructurar_documento(ruta_md, ruta_pdf, info["titulos"],
                                         info.get("rangos_paginas", []))
        destino.write_text(markdown, encoding="utf-8")
        print(f"  -> {destino}")


if __name__ == "__main__":
    main()
