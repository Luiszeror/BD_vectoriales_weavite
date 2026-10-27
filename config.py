"""Configuración común: lectura del .env y conexión a Weaviate Cloud."""
import os
import uuid
from pathlib import Path

import weaviate
from dotenv import load_dotenv
from weaviate.classes.init import Auth

load_dotenv()

RAIZ = Path(__file__).parent
DATOS = RAIZ / "data"

# Nombres de las colecciones (en Weaviate deben empezar con mayúscula)
AUTOR = "Autor"
LIBRO = "Libro"
RESENA = "Resena"

# Espacio de nombres fijo: así cada registro siempre recibe el mismo UUID
# y podemos recargar los datos sin crear duplicados.
_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def uuid_de(clave: str) -> str:
    """UUID determinista a partir del id del registro (ej. 'L001')."""
    return str(uuid.uuid5(_NAMESPACE, clave))


def conectar() -> weaviate.WeaviateClient:
    """Abre la conexión con Weaviate Cloud usando las variables del .env."""
    url = os.getenv("WEAVIATE_URL")
    clave = os.getenv("WEAVIATE_API_KEY")
    if not url or not clave:
        raise SystemExit("Faltan WEAVIATE_URL o WEAVIATE_API_KEY en el archivo .env")

    return weaviate.connect_to_weaviate_cloud(
        cluster_url=url,
        auth_credentials=Auth.api_key(clave),
    )
