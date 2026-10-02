"""
Punto de control del Día 1: comparar la extracción de texto de pypdf frente a
Docling en unas pocas páginas difíciles (tablas, dos columnas).

Objetivo: decidir si el texto sale lo bastante legible como para seguir con este
PDF, o si hay que pivotar al Plan B.

Uso (ejemplo):
    python scripts/compare_extraction.py data/raw/reglas.pdf --paginas 12 13 27 41 58

Genera, en data/processed/comparacion/:
    - pagina_XX_pypdf.txt     (texto crudo de pypdf)
    - pagina_XX_docling.md    (markdown de Docling)
para que compares legibilidad de tablas y columnas lado a lado.
"""

import argparse
import sys
from pathlib import Path


# Carpeta de salida de la comparación.
SALIDA = Path("data/processed/comparacion")


def extraer_con_pypdf(ruta_pdf: Path, paginas: list[int]) -> dict[int, str]:
    """Extrae el texto de las páginas indicadas (1-indexadas) con pypdf."""
    from pypdf import PdfReader

    lector = PdfReader(str(ruta_pdf))
    total = len(lector.pages)
    resultado = {}
    for n in paginas:
        if n < 1 or n > total:
            print(f"  [pypdf] AVISO: la página {n} no existe (el PDF tiene {total}).")
            continue
        # pypdf indexa desde 0; el usuario pasa números humanos (desde 1).
        texto = lector.pages[n - 1].extract_text() or ""
        resultado[n] = texto
    return resultado


def extraer_con_docling(ruta_pdf: Path, paginas: list[int]) -> dict[int, str]:
    """
    Convierte a Markdown con Docling SOLO las páginas indicadas.

    Para no convertir el documento entero (lento), aislamos cada página en un
    PDF temporal de una sola hoja con pypdf y se lo pasamos a Docling.
    """
    from pypdf import PdfReader, PdfWriter
    from docling.document_converter import DocumentConverter

    lector = PdfReader(str(ruta_pdf))
    total = len(lector.pages)
    convertidor = DocumentConverter()

    tmp_dir = SALIDA / "_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    resultado = {}
    for n in paginas:
        if n < 1 or n > total:
            continue  # ya se avisó en la pasada de pypdf
        # Creamos un PDF temporal con solo esa página.
        escritor = PdfWriter()
        escritor.add_page(lector.pages[n - 1])
        ruta_tmp = tmp_dir / f"pagina_{n:02d}.pdf"
        with open(ruta_tmp, "wb") as f:
            escritor.write(f)

        # Docling convierte esa única página a Markdown.
        doc = convertidor.convert(str(ruta_tmp)).document
        resultado[n] = doc.export_to_markdown()

    return resultado


def main() -> int:
    parser = argparse.ArgumentParser(description="Comparar extracción pypdf vs. Docling.")
    parser.add_argument("pdf", type=Path, help="Ruta al PDF (p. ej. data/raw/reglas.pdf)")
    parser.add_argument(
        "--paginas", type=int, nargs="+", required=True,
        help="Números de página difíciles a comparar (1-indexados), p. ej. --paginas 12 13 27",
    )
    args = parser.parse_args()

    if not args.pdf.exists():
        print(f"ERROR: no encuentro el PDF en {args.pdf}")
        print("Coloca el PDF en data/raw/ y vuelve a ejecutar.")
        return 1

    SALIDA.mkdir(parents=True, exist_ok=True)
    print(f"Comparando páginas {args.paginas} de {args.pdf.name}\n")

    print("1/2  Extrayendo con pypdf...")
    txt_pypdf = extraer_con_pypdf(args.pdf, args.paginas)
    for n, texto in txt_pypdf.items():
        destino = SALIDA / f"pagina_{n:02d}_pypdf.txt"
        destino.write_text(texto, encoding="utf-8")
        print(f"     -> {destino}  ({len(texto)} caracteres)")

    print("2/2  Extrayendo con Docling (puede tardar la primera vez)...")
    md_docling = extraer_con_docling(args.pdf, args.paginas)
    for n, md in md_docling.items():
        destino = SALIDA / f"pagina_{n:02d}_docling.md"
        destino.write_text(md, encoding="utf-8")
        print(f"     -> {destino}  ({len(md)} caracteres)")

    print("\nListo. Abre los archivos en data/processed/comparacion/ y juzga:")
    print("  - ¿Se leen bien las tablas?")
    print("  - ¿Se respeta el orden en páginas a dos columnas?")
    print("Si incluso Docling sale ilegible -> pivotar al Plan B.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
