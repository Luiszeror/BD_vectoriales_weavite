"""Interfaz gráfica del taller: Librería inteligente con Weaviate.

Uso:
    python app.py        # se abre en el navegador (http://127.0.0.1:7860)

Pestañas:
  1. Consultas del taller  - elige una consulta de consultas.json y ejecútala
  2. Búsqueda libre        - escribe una palabra/frase; semántica, palabra clave o híbrida
  3. Colección             - todos los libros guardados en Weaviate
  4. Embeddings            - el vector de un libro, sus vecinos más cercanos
  5. Mapa 2D               - todos los libros proyectados en un plano, por género
"""
import atexit
import json
import os

import gradio as gr
import numpy as np
import pandas as pd
from weaviate.classes.query import Filter, MetadataQuery, Sort

from config import DATOS, LIBRO, conectar

# --------------------------------------------------------------------------
# Datos locales (no requieren Weaviate; la interfaz puede construirse sin él)
# --------------------------------------------------------------------------
CONSULTAS = json.loads((DATOS / "consultas.json").read_text(encoding="utf-8"))
_LIBROS_JSON = json.loads((DATOS / "libros.json").read_text(encoding="utf-8"))
GENEROS = sorted({l["genero"] for l in _LIBROS_JSON})
TITULOS = sorted(l["titulo"] for l in _LIBROS_JSON)
ANIO_MIN = min(l["anio"] for l in _LIBROS_JSON)
ANIO_MAX = max(l["anio"] for l in _LIBROS_JSON)
VECTORES = ["sinopsis", "resenas"]

NOMBRE_TIPO = {
    "semantica": "Semántica", "keyword": "Palabra clave", "hibrida": "Híbrida",
    "filtro": "Con filtros", "rag": "RAG",
}

# Las consultas de tipo "filtro" necesitan filtros que el JSON no guarda.
CONFIG_FILTRO = {
    "ciencia ficción publicada desde 2021": {"generos": ["Ciencia ficción"], "anio_min": 2021},
    "libros con rating mayor a 4.4": {"rating_min": 4.45, "sin_texto": True},
}

# --------------------------------------------------------------------------
# Conexión a Weaviate (perezosa: se abre al primer uso)
# --------------------------------------------------------------------------
_client = None
_col = None
_todos = None


def coleccion():
    global _client, _col
    if _col is None:
        _client = conectar()
        atexit.register(_client.close)
        _col = _client.collections.get(LIBRO)
    return _col


def todos():
    """Todos los libros con sus vectores (son pocos; se guardan en memoria)."""
    global _todos
    if _todos is None:
        _todos = coleccion().query.fetch_objects(limit=500, include_vector=True).objects
    return _todos


# --------------------------------------------------------------------------
# Búsquedas
# --------------------------------------------------------------------------
def armar_filtros(generos=None, anio_min=None, rating_min=None):
    filtros = []
    if generos:
        filtros.append(Filter.any_of([Filter.by_property("genero").equal(g) for g in generos]))
    if anio_min and int(anio_min) > ANIO_MIN:
        filtros.append(Filter.by_property("anio").greater_or_equal(int(anio_min)))
    if rating_min and float(rating_min) > 0:
        filtros.append(Filter.by_property("rating").greater_or_equal(float(rating_min)))
    if not filtros:
        return None
    return filtros[0] if len(filtros) == 1 else Filter.all_of(filtros)


def a_tabla(objetos, metrica):
    """Convierte los resultados de Weaviate en una tabla para mostrar."""
    nombre = {"distance": "Distancia", "score": "Puntaje"}.get(metrica)
    filas = []
    for i, o in enumerate(objetos, start=1):
        p = o.properties
        fila = {"#": i, "Título": p["titulo"], "Autor": p["autor"], "Género": p["genero"],
                "Año": p["anio"], "Rating": p["rating"]}
        if nombre:
            valor = getattr(o.metadata, metrica, None)
            fila[nombre] = round(valor, 3) if valor is not None else None
        fila["Sinopsis"] = (p["sinopsis"][:110] + "…") if len(p["sinopsis"]) > 110 else p["sinopsis"]
        filas.append(fila)
    return pd.DataFrame(filas)


def buscar(texto, modo, vector, alpha, filtros, limite):
    col = coleccion()
    texto = (texto or "").strip()
    limite = int(limite)

    if not texto:  # sin texto: solo filtros, ordenado por rating
        r = col.query.fetch_objects(
            limit=limite, filters=filtros, sort=Sort.by_property("rating", ascending=False))
        return a_tabla(r.objects, None)

    if modo == "Semántica":
        r = col.query.near_text(
            query=texto, target_vector=vector, limit=limite, filters=filtros,
            return_metadata=MetadataQuery(distance=True))
        return a_tabla(r.objects, "distance")

    if modo == "Palabra clave":
        r = col.query.bm25(
            query=texto, limit=limite, filters=filtros,
            return_metadata=MetadataQuery(score=True))
        return a_tabla(r.objects, "score")

    r = col.query.hybrid(
        query=texto, alpha=float(alpha), target_vector=vector, limit=limite, filters=filtros,
        return_metadata=MetadataQuery(score=True))
    return a_tabla(r.objects, "score")


def busqueda_libre(texto, modo, vector, alpha, generos, anio_min, rating_min, limite):
    filtros = armar_filtros(generos, anio_min, rating_min)
    tabla = buscar(texto, modo, vector, alpha, filtros, limite)
    if tabla.empty:
        return "Sin resultados. Si acabas de cargar los datos, espera unos segundos y repite.", tabla
    leyenda = {
        "Semántica": "Distancia: **menor = más parecido** en significado.",
        "Palabra clave": "Puntaje BM25: **mayor = más coincidencias** de las palabras buscadas.",
        "Híbrida": "Puntaje híbrido: **mayor = mejor**. `alpha` 0 = solo palabras, 1 = solo significado.",
    }
    nota = leyenda[modo] if (texto or "").strip() else "Sin texto: se listan los libros que cumplen los filtros, por rating."
    return f"{len(tabla)} resultados. {nota}", tabla


# --------------------------------------------------------------------------
# Pestaña 1: consultas del taller
# --------------------------------------------------------------------------
OPCIONES_CONSULTAS = [
    (f"{i + 1}. [{NOMBRE_TIPO[c['tipo']]}] {c['consulta']}", i) for i, c in enumerate(CONSULTAS)
]


def aciertos(esperados, tabla):
    if not esperados:
        return ""
    hallados = [t for t in esperados if t in set(tabla["Título"])] if not tabla.empty else []
    faltan = [t for t in esperados if t not in hallados]
    texto = f"\n\n**Aciertos:** {len(hallados)} de {len(esperados)}"
    if faltan:
        texto += " — no aparecieron: " + "; ".join(faltan)
    return texto


def correr_consulta(indice):
    c = CONSULTAS[int(indice)]
    tipo, texto, limite = c["tipo"], c["consulta"], 5
    cfg = CONFIG_FILTRO.get(texto, {})

    modo = {"semantica": "Semántica", "keyword": "Palabra clave", "hibrida": "Híbrida",
            "filtro": "Semántica", "rag": "Semántica"}[tipo]
    if tipo == "rag":
        limite = 3
    filtros = armar_filtros(cfg.get("generos"), cfg.get("anio_min"), cfg.get("rating_min"))
    tabla = buscar("" if cfg.get("sin_texto") else texto, modo, "sinopsis", 0.5, filtros, limite)

    info = (f"**Consulta:** {texto}  \n**Tipo:** {NOMBRE_TIPO[tipo]}  \n**Nota:** {c['nota']}")
    if c["esperados"]:
        info += "  \n**Esperados:** " + "; ".join(c["esperados"])
    info += aciertos(c["esperados"], tabla)
    if tipo == "rag":
        info += ("\n\n*Esta consulta está pensada para RAG (módulo generativo), que aún no está "
                 "configurado. Aquí se muestran los 3 libros que se le pasarían al modelo como contexto.*")
    return info, tabla


def comparar_modos(indice):
    """La misma consulta con los tres modos, lado a lado (módulo 4 del taller)."""
    texto = CONSULTAS[int(indice)]["consulta"]
    esperados = CONSULTAS[int(indice)]["esperados"]
    salidas = []
    for modo in ("Semántica", "Palabra clave", "Híbrida"):
        tabla = buscar(texto, modo, "sinopsis", 0.5, None, 5)
        salidas += [f"**{modo}**" + aciertos(esperados, tabla),
                    tabla[["#", "Título", "Género"] + [c for c in ("Distancia", "Puntaje") if c in tabla]]]
    return salidas


# --------------------------------------------------------------------------
# Pestaña 3: colección
# --------------------------------------------------------------------------
def ver_coleccion(genero):
    filas = []
    for o in todos():
        p = o.properties
        if genero != "Todos" and p["genero"] != genero:
            continue
        filas.append({
            "ID": p["libro_id"], "Título": p["titulo"], "Autor": p["autor"], "País": p["autor_pais"],
            "Género": p["genero"], "Año": p["anio"], "Páginas": p["paginas"], "Rating": p["rating"],
            "Puntaje reseñas": p["puntaje_promedio"], "ISBN": p["isbn"], "Sinopsis": p["sinopsis"],
        })
    tabla = pd.DataFrame(filas).sort_values("ID") if filas else pd.DataFrame()
    return f"{len(tabla)} libros en Weaviate", tabla


# --------------------------------------------------------------------------
# Pestaña 4: embeddings de un libro
# --------------------------------------------------------------------------
def ver_embedding(titulo, vector):
    objeto = next((o for o in todos() if o.properties["titulo"] == titulo), None)
    if objeto is None:
        return "No encontré ese libro.", pd.DataFrame(), "", pd.DataFrame()
    v = np.array(objeto.vector[vector], dtype=float)

    resumen = (f"**{titulo}** — vector `{vector}`  \n"
               f"Dimensiones: **{len(v)}** · Valor mínimo: {v.min():.4f} · "
               f"máximo: {v.max():.4f} · norma: {np.linalg.norm(v):.4f}\n\n"
               "Cada número es una coordenada del libro en un espacio de "
               f"{len(v)} dimensiones. Libros con significado parecido quedan en coordenadas parecidas.")

    primeras = pd.DataFrame({"dimension": [str(i) for i in range(64)], "valor": v[:64]})
    texto = ", ".join(f"{x:.4f}" for x in v)

    r = coleccion().query.near_object(
        near_object=objeto.uuid, target_vector=vector, limit=7,
        return_metadata=MetadataQuery(distance=True))
    vecinos = a_tabla([o for o in r.objects if o.uuid != objeto.uuid][:6], "distance")
    return resumen, primeras, texto, vecinos[["#", "Título", "Género", "Distancia"]]


# --------------------------------------------------------------------------
# Pestaña 5: mapa 2D (PCA) de todos los vectores
# --------------------------------------------------------------------------
def pca_2d(matriz):
    X = np.asarray(matriz, dtype=float)
    X = X - X.mean(axis=0)
    _, S, Vt = np.linalg.svd(X, full_matrices=False)
    varianza = (S ** 2) / (S ** 2).sum()
    return X @ Vt[:2].T, varianza[:2]


def mapa(vector):
    objetos = [o for o in todos() if o.vector and o.vector.get(vector)]
    coords, var = pca_2d([o.vector[vector] for o in objetos])
    df = pd.DataFrame({
        "x": coords[:, 0], "y": coords[:, 1],
        "titulo": [o.properties["titulo"] for o in objetos],
        "genero": [o.properties["genero"] for o in objetos],
    })
    nota = (f"{len(df)} libros proyectados de {len(objetos[0].vector[vector])} a 2 dimensiones "
            f"(conservan el {var.sum() * 100:.0f}% de la variación). "
            "Los libros del mismo género tienden a agruparse.")
    return nota, df


# --------------------------------------------------------------------------
# Interfaz
# --------------------------------------------------------------------------
with gr.Blocks(title="Librería inteligente - Weaviate") as demo:
    gr.Markdown("# 📚 Librería inteligente\nBúsqueda vectorial con Weaviate sobre un catálogo de 48 libros.")

    with gr.Tab("Consultas del taller"):
        gr.Markdown("Elige una consulta preparada y ejecútala. Muestra si aparecen los libros esperados.")
        selector = gr.Dropdown(OPCIONES_CONSULTAS, value=0, label="Consulta")
        with gr.Row():
            b_ejecutar = gr.Button("Ejecutar", variant="primary")
            b_comparar = gr.Button("Comparar los 3 modos")
        info = gr.Markdown()
        resultado = gr.Dataframe(label="Resultados", interactive=False, wrap=True)
        b_ejecutar.click(correr_consulta, selector, [info, resultado])

        gr.Markdown("### Comparación: semántica vs. palabra clave vs. híbrida")
        comparacion = []
        with gr.Row():
            for _ in range(3):
                with gr.Column():
                    titulo_modo = gr.Markdown()
                    tabla_modo = gr.Dataframe(interactive=False, wrap=True)
                    comparacion += [titulo_modo, tabla_modo]
        b_comparar.click(comparar_modos, selector, comparacion)

    with gr.Tab("Búsqueda libre"):
        gr.Markdown("Escribe una palabra o frase y mira qué libros son los más cercanos.")
        with gr.Row():
            q = gr.Textbox(label="Buscar", placeholder="ej: miedo, mar, un viaje espacial…", scale=4)
            b_buscar = gr.Button("Buscar", variant="primary", scale=1)
        with gr.Row():
            modo = gr.Radio(["Semántica", "Palabra clave", "Híbrida"], value="Semántica", label="Modo")
            vector = gr.Radio(VECTORES, value="sinopsis", label="Vector (semántica e híbrida)")
            alpha = gr.Slider(0, 1, value=0.5, step=0.1, label="Alpha (híbrida)")
            limite = gr.Slider(1, 20, value=8, step=1, label="Cantidad de resultados")
        with gr.Accordion("Filtros", open=False):
            with gr.Row():
                f_generos = gr.Dropdown(GENEROS, multiselect=True, label="Géneros")
                f_anio = gr.Slider(ANIO_MIN, ANIO_MAX, value=ANIO_MIN, step=1, label="Año mínimo")
                f_rating = gr.Slider(0, 5, value=0, step=0.1, label="Rating mínimo")
        estado = gr.Markdown()
        tabla_libre = gr.Dataframe(interactive=False, wrap=True)
        entradas = [q, modo, vector, alpha, f_generos, f_anio, f_rating, limite]
        b_buscar.click(busqueda_libre, entradas, [estado, tabla_libre])
        q.submit(busqueda_libre, entradas, [estado, tabla_libre])

    with gr.Tab("Colección"):
        with gr.Row():
            f_genero_col = gr.Dropdown(["Todos"] + GENEROS, value="Todos", label="Género", scale=3)
            b_col = gr.Button("Cargar / actualizar", variant="primary", scale=1)
        n_col = gr.Markdown()
        tabla_col = gr.Dataframe(interactive=False, wrap=True)
        b_col.click(ver_coleccion, f_genero_col, [n_col, tabla_col])
        f_genero_col.change(ver_coleccion, f_genero_col, [n_col, tabla_col])

    with gr.Tab("Embeddings"):
        gr.Markdown("Mira el vector que Weaviate guardó para un libro y qué libros quedan cerca.")
        with gr.Row():
            libro = gr.Dropdown(TITULOS, value=TITULOS[0], label="Libro", scale=3)
            vec_e = gr.Radio(VECTORES, value="sinopsis", label="Vector", scale=1)
            b_emb = gr.Button("Ver embedding", variant="primary", scale=1)
        resumen_e = gr.Markdown()
        grafico = gr.BarPlot(x="dimension", y="valor", title="Primeras 64 dimensiones", height=280)
        completo = gr.Textbox(label="Vector completo (copiable)", lines=6, buttons=["copy"])
        gr.Markdown("### Libros más cercanos a este vector")
        vecinos = gr.Dataframe(interactive=False)
        b_emb.click(ver_embedding, [libro, vec_e], [resumen_e, grafico, completo, vecinos])

    with gr.Tab("Mapa 2D"):
        gr.Markdown("Todos los libros en un plano. Cada punto es un libro; el color es su género.")
        with gr.Row():
            vec_m = gr.Radio(VECTORES, value="sinopsis", label="Vector")
            b_mapa = gr.Button("Dibujar mapa", variant="primary")
        nota_m = gr.Markdown()
        grafico_m = gr.ScatterPlot(x="x", y="y", color="genero", tooltip=["titulo", "genero"], height=520)
        b_mapa.click(mapa, vec_m, [nota_m, grafico_m])


if __name__ == "__main__":
    # En un servidor (Render pone la variable PORT; Hugging Face, SPACE_ID) hay que
    # escuchar en todas las interfaces y no abrir ningún navegador local.
    puerto = os.getenv("PORT")
    en_servidor = bool(puerto or os.getenv("SPACE_ID"))
    demo.launch(
        server_name="0.0.0.0" if en_servidor else None,
        server_port=int(puerto) if puerto else None,
        inbrowser=not en_servidor,
    )