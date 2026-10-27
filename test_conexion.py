"""Primer ejercicio del taller: comprobar que la conexión funciona."""
from config import conectar

with conectar() as client:
    print("Conectado:", client.is_ready())
    meta = client.get_meta()
    print("Versión de Weaviate:", meta.get("version"))
    print("Colecciones existentes:", list(client.collections.list_all().keys()))
