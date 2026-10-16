"""
Conversión PDF -> Markdown con Docling. Se ejecuta UNA sola vez.

Para cada PDF de data/raw/ genera en data/processed/:
    - <nombre>.md    Markdown con un marcador antes de cada página:
                         <!-- pagina: 128 -->
    - <nombre>.json  Documento completo de Docling. Permite regenerar el
                     Markdown sin repetir la conversión (que es lo lento).

El número del marcador es la PÁGINA IMPRESA (la que se ve en el libro), que es
la que usaremos en las citas:  página impresa = página del PDF - desfase.

Este script NO limpia el texto: guarda la salida de Docling tal cual. La
limpieza (viñetas duplicadas, marcadores de imagen...) se hace en el loader.

Uso:
    python -m src.ingest.convert_docling --desfase 2
    python -m src.ingest.convert_docling --pdf data/raw/otro.pdf      (uno solo)
    python -m src.ingest.convert_docling --desfase 2 --forzar         (reconvertir)
"""

import argparse
import time
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

from src import config

CARPETA_ENTRADA = config.CARPETA_RAW
CARPETA_SALIDA = config.CARPETA_PROCESADOS


def crear_convertidor() -> DocumentConverter:
    """Configura Docling: sin OCR (el PDF ya tiene texto) y con tablas."""
    opciones = PdfPipelineOptions()
    opciones.do_ocr = False              # el PDF tiene capa de texto: OCR sobra
    opciones.do_table_structure = True   # reconstruir tablas como tablas Markdown
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opciones)}
    )


def markdown_con_paginas(doc, desfase: int) -> str:
    """
    Exporta el documento página a página, anteponiendo a cada una su marcador.

    doc.pages es un diccionario {número de página del PDF (desde 1): info}.
    """
    partes = []
    for n_pdf in sorted(doc.pages):
        # Las páginas iniciales (portada...) no tienen número impreso: quedan en 0.
        n_impresa = max(n_pdf - desfase, 0)
        texto = doc.export_to_markdown(page_no=n_pdf)
        partes.append(f"<!-- pagina: {n_impresa} -->\n\n{texto.strip()}\n")
    return "\n".join(partes)


def convertir_pdf(convertidor: DocumentConverter, ruta_pdf: Path, desfase: int) -> None:
    """Convierte un PDF y guarda su .md (con marcadores) y su .json."""
    print(f"Convirtiendo: {ruta_pdf.name}  (desfase de páginas = {desfase})")
    inicio = time.time()

    doc = convertidor.convert(str(ruta_pdf)).document

    ruta_json = CARPETA_SALIDA / f"{ruta_pdf.stem}.json"
    doc.save_as_json(ruta_json)

    ruta_md = CARPETA_SALIDA / f"{ruta_pdf.stem}.md"
    markdown = markdown_con_paginas(doc, desfase)
    ruta_md.write_text(markdown, encoding="utf-8")

    minutos = (time.time() - inicio) / 60
    print(f"  Páginas: {len(doc.pages)} | Tablas: {len(doc.tables)} | "
          f"Caracteres: {len(markdown):,} | Tiempo: {minutos:.1f} min")
    print(f"  -> {ruta_md}")
    print(f"  -> {ruta_json}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convertir PDFs a Markdown con Docling.")
    parser.add_argument("--desfase", type=int, default=0,
                        help="Página del PDF - página impresa (p. ej. 2). Por defecto 0.")
    parser.add_argument("--pdf", type=Path, default=None,
                        help="Convertir solo este PDF (por defecto, todos los de data/raw/).")
    parser.add_argument("--forzar", action="store_true",
                        help="Reconvertir aunque ya exista el .md de salida.")
    args = parser.parse_args()

    pdfs = [args.pdf] if args.pdf else sorted(CARPETA_ENTRADA.glob("*.pdf"))
    if not pdfs:
        print(f"No hay PDFs en {CARPETA_ENTRADA}/")
        return

    CARPETA_SALIDA.mkdir(parents=True, exist_ok=True)
    convertidor = crear_convertidor()

    for ruta_pdf in pdfs:
        # La conversión es lenta: no la repetimos salvo que se pida.
        if (CARPETA_SALIDA / f"{ruta_pdf.stem}.md").exists() and not args.forzar:
            print(f"Ya convertido (usa --forzar para repetir): {ruta_pdf.name}")
            continue
        convertir_pdf(convertidor, ruta_pdf, args.desfase)


if __name__ == "__main__":
    main()
