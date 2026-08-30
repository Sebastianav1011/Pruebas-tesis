"""
RAG local - Camino 1 (Ollama, gratis)

Flujo:
  1. Cargar y limpiar el CSV de proyectos
  2. Generar embeddings (texto semantico -> vector)
  3. Dado una pregunta, buscar los proyectos mas parecidos (retrieval)
  4. Armar el prompt con ese contexto y mandarlo a Ollama (generacion)

Convencion de este archivo:
  - Nombres de variables, funciones y archivos: en ingles
  - Comentarios y docstrings: en espanol

Cada funcion tiene un TODO. Completa en ese orden, no hace falta
que hagas todo de una - prueba funcion por funcion con un print()
antes de seguir a la siguiente.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import requests
from sentence_transformers import SentenceTransformer


# ---- Config ---------------------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"
PROJECTS_FILE = DATA_DIR / "60_proyectos.csv"

EMBEDDING_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"   # modelo local, gratis, multilingue
OLLAMA_MODEL_NAME = "deepseek-r1:7b"        # el que hayas hecho `ollama pull`
OLLAMA_URL = "http://localhost:11434/api/generate"

TOP_K = 5  # cuantos proyectos recupera el retrieval por pregunta


# ---- Paso 1: cargar y limpiar ---------------------------------------------

def load_and_clean_data():
    """
    Carga el CSV de proyectos y arma la columna 'semantic_text', que es
    el texto que se va a convertir en embedding (titulo + resumen +
    palabras_clave). El resto de columnas se dejan intactas como
    metadata.
    """
    df = pd.read_csv(PROJECTS_FILE, encoding="utf-8-sig")

    # Rellenar nulos en los campos de texto antes de concatenar
    # (si no, un NaN en palabras_clave rompe la concatenacion)
    df["nombre_producto"] = df["nombre_producto"].fillna("")
    df["resumen"] = df["resumen"].fillna("")
    df["palabras_clave"] = df["palabras_clave"].fillna("")

    df["semantic_text"] = (
        df["nombre_producto"] + ". " + df["resumen"] + ". " + df["palabras_clave"]
    )

    return df


# ---- Paso 2: generar embeddings --------------------------------------------

def generate_embeddings(df, embedding_model):
    """
    Genera un embedding (vector numerico) por cada fila, a partir de
    su 'semantic_text'. Se le pasa la lista completa de textos de una
    sola vez porque es mas rapido que fila por fila.
    """
    texts = df["semantic_text"].tolist()
    embeddings = embedding_model.encode(texts, show_progress_bar=True)
    return embeddings


# ---- Paso 3: retrieval (busqueda por similitud) ----------------------------

def find_similar_projects(question, df, embeddings, embedding_model, top_k=TOP_K):
    """
    Busca los top_k proyectos mas parecidos a 'question', comparando
    el embedding de la pregunta contra los embeddings de todos los
    proyectos usando similitud coseno.
    """
    question_embedding = embedding_model.encode([question])[0]

    # Similitud coseno = producto punto / (norma_A * norma_B)
    norms = np.linalg.norm(embeddings, axis=1) * np.linalg.norm(question_embedding)
    similarities = embeddings @ question_embedding / norms

    top_indices = np.argsort(similarities)[::-1][:top_k]

    return df.iloc[top_indices]


# ---- Paso 4: generacion con Ollama -----------------------------------------

def ask_ollama(question, retrieved_rows):
    """
    Arma un prompt con el contexto recuperado y se lo manda a Ollama
    (corriendo local en localhost:11434) para que genere la respuesta.
    """
    context_parts = []
    for _, row in retrieved_rows.iterrows():
        context_parts.append(
            f"Titulo: {row['nombre_producto']}\n"
            f"Facultad: {row['facultad']}\n"
            f"Investigador: {row['investigador_docente']}\n"
            f"Resumen: {row['resumen']}\n"
        )
    context = "\n---\n".join(context_parts)

    prompt = f"""Responde la pregunta usando SOLO la informacion de estos
proyectos de investigacion. Si no hay informacion suficiente, dilo
explicitamente. Responde en espanol.

PROYECTOS:
{context}

PREGUNTA: {question}"""

    response = requests.post(
        OLLAMA_URL,
        json={"model": OLLAMA_MODEL_NAME, "prompt": prompt, "stream": False},
    )
    response.raise_for_status()

    return response.json()["response"]


# ---- Main -------------------------------------------------------------------

def main():
    print("Cargando y limpiando datos...")
    df = load_and_clean_data()

    print("Generando embeddings (una sola vez)...")
    embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    embeddings = generate_embeddings(df, embedding_model)

    # Cambia esta pregunta por la que quieras probar
    question = "que proyectos hablan de sostenibilidad o materiales ecologicos?"

    print(f"\nPregunta: {question}")
    print("Buscando proyectos relevantes...")
    retrieved_rows = find_similar_projects(question, df, embeddings, embedding_model)
    print(f"Encontrados {len(retrieved_rows)} proyectos relevantes.")

    print("Generando respuesta con Ollama...")
    answer = ask_ollama(question, retrieved_rows)

    print("\n--- RESPUESTA ---")
    print(answer)


if __name__ == "__main__":
    main()
    