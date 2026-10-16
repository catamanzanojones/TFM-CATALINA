"""
Clientes de los modelos. Todo acceso a la API de Gemini pasa por aquí, de modo
que el resto del código no sabe nada del proveedor: si hubiera que cambiar a la
alternativa (Groq + sentence-transformers), solo cambiaría este archivo.

Día 2: embeddings. Día 3: generación.
"""

import os
import time
from functools import lru_cache

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from src import config


@lru_cache(maxsize=1)
def cliente_gemini() -> genai.Client:
    """Crea el cliente de Gemini una sola vez, con la clave de .env."""
    load_dotenv(config.RAIZ / ".env")
    clave = os.environ.get("GEMINI_API_KEY")
    if not clave:
        raise RuntimeError("Falta GEMINI_API_KEY en el archivo .env (ver .env.example)")
    return genai.Client(api_key=clave)


def con_reintentos(funcion, *args, **kwargs):
    """
    Ejecuta una llamada a la API y, si falla por cuota (error 429) o por el
    servidor (5xx), espera y reintenta. La espera se duplica en cada intento
    (espera exponencial): 10 s, 20 s, 40 s...
    """
    espera = config.ESPERA_INICIAL
    for intento in range(1, config.REINTENTOS_MAX + 1):
        try:
            return funcion(*args, **kwargs)
        except errors.APIError as error:
            reintentable = error.code == 429 or (error.code or 0) >= 500
            if not reintentable or intento == config.REINTENTOS_MAX:
                raise
            print(f"  [API] error {error.code}: reintento {intento} dentro de {espera} s...")
            time.sleep(espera)
            espera *= 2


def embeber_textos(textos: list[str]) -> list[list[float]]:
    """
    Embeddings de una lista de textos ya formateados (con su prefijo de tarea).
    Hace una llamada por cada lote de config.EMBEDDINGS_POR_LOTE textos.
    """
    vectores = []
    for inicio in range(0, len(textos), config.EMBEDDINGS_POR_LOTE):
        lote = textos[inicio: inicio + config.EMBEDDINGS_POR_LOTE]
        respuesta = con_reintentos(
            cliente_gemini().models.embed_content,
            model=config.MODELO_EMBEDDINGS,
            # Cada texto en su propio Content: así se obtiene un vector por texto
            # (varios textos en un mismo Content darían un único vector conjunto).
            contents=[types.Content(parts=[types.Part.from_text(text=t)]) for t in lote],
            config=types.EmbedContentConfig(output_dimensionality=config.DIMENSION_EMBEDDINGS),
        )
        vectores.extend(e.values for e in respuesta.embeddings)
    return vectores
