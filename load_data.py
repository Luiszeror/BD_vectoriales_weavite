"""Carga el catálogo en Weaviate (una sola colección: Libro).

Uso:
    python load_data.py

Ideas que ilustra este módulo:
  * Denormalización: unimos libro + autor + reseñas en un solo objeto.
  * Inserción por lotes (batch): mucho más rápido que insertar uno por uno.
  * UUID deterministas: volver a ejecutar el script actualiza en lugar de duplicar.
  * Los embeddings los genera Weaviate al insertar; no calculamos nada aquí.
"""
import json
from collections import defaultdict

from weaviate.classes.data import DataObject

from config import DATOS, LIBRO, conectar, uuid_de


def leer(nombre: str) -> list[dict]:
    return json.loads((DATOS / f"{nombre}.json").read_text(encoding="utf-8"))


def construir_objetos() -> list[DataObject]:
    """Une libros, autores y reseñas en un objeto por libro."""
    autores = {a["autor_id"]: a for a in leer("autores")}
    resenas_por_libro = defaultdict(list)
    for r in leer("resenas"):
        resenas_por_libro[r["libro_id"]].append(r)

    objetos = []
    for libro in leer("libros"):
        autor = autores[libro["autor_id"]]
        resenas = resenas_por_libro[libro["libro_id"]]
        puntajes = [r["puntaje"] for r in resenas]

        propiedades = {k: v for k, v in libro.items() if k not in ("autor_id", "autor")}
        propiedades.update({
            "autor": autor["nombre"],
            "autor_pais": autor["pais"],
            "autor_bio": autor["bio"],
            "resenas": [r["texto"] for r in resenas],
            "puntaje_promedio": round(sum(puntajes) / len(puntajes), 2) if puntajes else None,
            "num_resenas": len(resenas),
        })
        objetos.append(DataObject(uuid=uuid_de(libro["libro_id"]), properties=propiedades))
    return objetos


def main():
    objetos = construir_objetos()

    with conectar() as client:
        coleccion = client.collections.get(LIBRO)

        resultado = coleccion.data.insert_many(objetos)
        if resultado.has_errors:
            print(f"{len(resultado.errors)} errores. Primeros:")
            for i, error in list(resultado.errors.items())[:3]:
                print(f"   objeto {i}: {error.message}")
        else:
            print(f"{len(objetos)} libros insertados")

        total = coleccion.aggregate.over_all(total_count=True).total_count
        print(f"{LIBRO}: {total} objetos en Weaviate")

        # Primera búsqueda semántica de prueba, con cada vector
        for vector, consulta in (
            ("sinopsis", "un libro sobre superar el fracaso"),
            ("resenas", "me emocioné y lloré leyéndolo"),
        ):
            respuesta = coleccion.query.near_text(query=consulta, target_vector=vector, limit=3)
            print(f"\nPrueba con el vector '{vector}': '{consulta}'")
            for o in respuesta.objects:
                print(f"  - {o.properties['titulo']} ({o.properties['genero']})")


if __name__ == "__main__":
    main()