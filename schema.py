"""Crea la colección Libro (el sandbox gratuito permite una sola colección).

Uso:
    python schema.py            # crea la colección (si no existe)
    python schema.py --reset    # borra todo lo anterior y la vuelve a crear

Ideas que ilustra este módulo:
  * Vectorizador integrado: Weaviate genera los embeddings (text2vec-weaviate).
  * Named vectors: dos vectores distintos en el mismo objeto
      - "sinopsis": significado de la historia (título + sinopsis)
      - "resenas":  lo que opinan los lectores
  * source_properties: solo se vectorizan los campos con significado;
    año, rating o ISBN quedan para filtros y búsqueda por palabra clave.
  * Datos denormalizados: autor y reseñas viven dentro de cada libro,
    porque con una sola colección no hay referencias cruzadas.
"""
import os
import sys

from weaviate.classes.config import Configure, DataType, Property

from config import AUTOR, LIBRO, RESENA, conectar


def _vectorizador(nombre: str, campos: list[str]):
    """Un vector con nombre, generado por Weaviate Embeddings a partir de ciertos campos."""
    opciones = {"name": nombre, "source_properties": campos}
    modelo = os.getenv("WEAVIATE_EMBED_MODEL")
    if modelo:
        opciones["model"] = modelo
    return Configure.Vectors.text2vec_weaviate(**opciones)


def crear_libro(client):
    return client.collections.create(
        name=LIBRO,
        description="Libro del catálogo, con su autor y las reseñas de los lectores",
        vector_config=[
            _vectorizador("sinopsis", ["titulo", "sinopsis"]),
            _vectorizador("resenas", ["resenas"]),
        ],
        properties=[
            Property(name="libro_id", data_type=DataType.TEXT),
            Property(name="titulo", data_type=DataType.TEXT),
            Property(name="genero", data_type=DataType.TEXT),
            Property(name="anio", data_type=DataType.INT),
            Property(name="paginas", data_type=DataType.INT),
            Property(name="rating", data_type=DataType.NUMBER),
            Property(name="idioma", data_type=DataType.TEXT),
            Property(name="isbn", data_type=DataType.TEXT),
            Property(name="sinopsis", data_type=DataType.TEXT),
            # Datos del autor (integrados en el libro)
            Property(name="autor", data_type=DataType.TEXT),
            Property(name="autor_pais", data_type=DataType.TEXT),
            Property(name="autor_bio", data_type=DataType.TEXT),
            # Reseñas de lectores (integradas en el libro)
            Property(name="resenas", data_type=DataType.TEXT_ARRAY),
            Property(name="puntaje_promedio", data_type=DataType.NUMBER),
            Property(name="num_resenas", data_type=DataType.INT),
        ],
    )


def main(reset: bool = False):
    with conectar() as client:
        if reset:
            # También borra Autor y Resena por si quedaron de un intento anterior
            for nombre in (RESENA, LIBRO, AUTOR):
                if client.collections.exists(nombre):
                    client.collections.delete(nombre)
                    print(f"Borrada: {nombre}")

        if client.collections.exists(LIBRO):
            print(f"Ya existe: {LIBRO}")
        else:
            crear_libro(client)
            print(f"Creada: {LIBRO}")


if __name__ == "__main__":
    main(reset="--reset" in sys.argv)