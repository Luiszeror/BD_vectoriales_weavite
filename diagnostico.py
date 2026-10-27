"""Revisa qué vectores tiene realmente cada libro en Weaviate.

Uso:
    python diagnostico.py
"""
from config import LIBRO, conectar

with conectar() as client:
    col = client.collections.get(LIBRO)
    total = col.aggregate.over_all(total_count=True).total_count
    print(f"Objetos en {LIBRO}: {total}\n")

    # 1) ¿Qué vectores tiene cada objeto?
    respuesta = col.query.fetch_objects(limit=48, include_vector=True)
    con_sinopsis = con_resenas = 0
    for o in respuesta.objects:
        vectores = o.vector or {}
        if vectores.get("sinopsis"):
            con_sinopsis += 1
        if vectores.get("resenas"):
            con_resenas += 1
    print(f"Libros con vector 'sinopsis': {con_sinopsis} de {len(respuesta.objects)}")
    print(f"Libros con vector 'resenas':  {con_resenas} de {len(respuesta.objects)}")

    if respuesta.objects:
        v = respuesta.objects[0].vector or {}
        print("\nEjemplo (primer libro):")
        for nombre, valor in v.items():
            print(f"  vector '{nombre}': {len(valor)} dimensiones")

    # 2) Repetir la búsqueda que salió vacía, mostrando la distancia
    from weaviate.classes.query import MetadataQuery

    print("\nBúsqueda 'sinopsis': 'un libro sobre superar el fracaso'")
    r = col.query.near_text(
        query="un libro sobre superar el fracaso",
        target_vector="sinopsis",
        limit=3,
        return_metadata=MetadataQuery(distance=True),
    )
    if not r.objects:
        print("  (sin resultados)")
    for o in r.objects:
        print(f"  - {o.properties['titulo']}  (distancia {o.metadata.distance:.3f})")