---
title: Libreria inteligente Weaviate
emoji: :)
colorFrom: indigo
colorTo: blue
sdk: gradio
sdk_version: 6.30.0
python_version: "3.11"
app_file: app.py
pinned: false
---


#  Librería inteligente: taller de bases de datos vectoriales con Weaviate

Taller práctico en Python para aprender búsqueda vectorial con **Weaviate Cloud** sobre un catálogo
ficticio de 48 libros en español. Incluye una interfaz gráfica para explorar consultas, la colección
y los embeddings.

## Qué se aprende

- Qué es un embedding y cómo Weaviate lo genera por ti (`text2vec-weaviate`).
- Búsqueda **semántica**, por **palabra clave (BM25)** e **híbrida**, y cuándo conviene cada una.
- **Filtros** sobre metadatos (género, año, rating) combinados con la búsqueda vectorial.
- **Named vectors**: dos vectores distintos en el mismo objeto (`sinopsis` y `resenas`).
- Visualizar embeddings y su cercanía en un mapa 2D.

## Requisitos

- Python 3.11 o superior
- Una cuenta gratuita en [Weaviate Cloud](https://console.weaviate.cloud) con un clúster **Free sandbox**
  y **Weaviate Embeddings** activado en la organización.

> El sandbox gratuito permite **una sola colección** y vence a los 30 días.
> Por eso el catálogo usa una colección (`Libro`) con el autor y las reseñas integrados.

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate          # En Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Crear archivo de credenciales:

```bash
cp .env.example .env
```

Y completar con los datos del clúster (consola de Weaviate Cloud):

```
WEAVIATE_URL=https://tu-cluster.weaviate.cloud     # "REST Endpoint"
WEAVIATE_API_KEY=tu_api_key_de_administrador       # se crea en "API Keys"
WEAVIATE_EMBED_MODEL=                              # déjalo vacío
```

## Uso, paso a paso

| Paso | Comando | Qué hace |
|---|---|---|
| 1 | `python test_conexion.py` | Comprueba la conexión. Debe imprimir `Conectado: True`. |
| 2 | `python schema.py` | Crea la colección `Libro` (`--reset` borra y recrea). |
| 3 | `python load_data.py` | Carga los 48 libros y genera sus embeddings. |
| 4 | `python diagnostico.py` | (Opcional) Verifica que los dos vectores existen en todos los libros. |
| 5 | `python app.py` | Abre la interfaz en http://127.0.0.1:7860 |

Después de cargar, el índice puede tardar unos segundos en estar listo. Si una primera búsqueda
sale vacía, espera un momento y repítela.

## Interfaz gráfica

- **Consultas del taller:** 15 consultas preparadas, con los libros esperados y comparación de los 3 modos.
- **Búsqueda libre:** semántica, palabra clave o híbrida, con filtros.
- **Colección:** los 48 libros guardados en Weaviate.
- **Embeddings:** el vector de un libro y sus vecinos más cercanos.
- **Mapa 2D:** todos los libros proyectados por género.

## Estructura del proyecto

```
├── app.py               Interfaz gráfica (Gradio)
├── config.py            Lectura del .env y conexión a Weaviate
├── schema.py            Crea la colección Libro con sus dos vectores
├── load_data.py         Une libros, autores y reseñas y los carga por lotes
├── test_conexion.py     Primer ejercicio: probar la conexión
├── diagnostico.py       Revisa los vectores guardados
├── build_dataset.py     Genera los datos ficticios (data/*.json)
├── data/                autores, libros, reseñas y consultas de prueba
├── requirements.txt
└── .env.example         Plantilla de credenciales
```

