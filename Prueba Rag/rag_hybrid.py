"""
Etapa 2: RAG hibrido sobre los resultados de evaluacion

Este es el RAG propiamente dicho. A diferencia de rag.py (que busca
sobre los proyectos crudos), este script busca sobre la TABLA DE
RESULTADOS que genero evaluate_indicators.py (evaluation_results.csv,
60 proyectos x 48 indicadores = 2880 filas).

El retrieval es hibrido, combina dos mecanismos en la misma consulta:
  1. Filtro estructurado (exacto): por campos como 'ambito', 'categoria'
     o 'estado' (ej. solo filas con estado == EVIDENCIA_CLARA)
  2. Filtro semantico (embeddings): similitud de significado, aplicado
     SOLO dentro de lo que ya paso el filtro estructurado (no sobre
     las 2880 filas completas)

Convencion de este archivo:
  - Nombres de variables, funciones y archivos: en ingles
  - Comentarios y docstrings: en espanol

Cada funcion tiene un TODO. Completa en el orden en que aparecen.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import requests
from sentence_transformers import SentenceTransformer


# ---- Config -----------------------------------------------------------

RESULTS_FILE = Path(__file__).parent / "evaluation_results_test5.csv"

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
OLLAMA_MODEL_NAME = "deepseek-r1:7b"
OLLAMA_URL = "http://localhost:11434/api/generate"

# Campos sobre los que se puede filtrar de forma exacta (estructurada)
STRUCTURED_FIELDS = ["ambito", "categoria", "estado"]

TOP_K = 15  # aqui suele convenir un top_k mas alto que en rag.py,
            # porque muchas preguntas piden "todos los que cumplen X",
            # no solo "el mas parecido"


# ---- Paso 1: cargar la tabla de resultados ------------------------------

def load_evaluation_results():
    """
    Carga la tabla de resultados generada por evaluate_indicators.py.
    Arma 'semantic_text' con los campos de texto libre (titulo,
    justificacion, evidencia) para poder buscar por similitud
    semantica dentro de esta tabla.
    """
    df = pd.read_csv(RESULTS_FILE, encoding="utf-8-sig")

    for col in ["justificacion", "evidencia"]:
        df[col] = df[col].fillna("")

    df["semantic_text"] = (
        df["nombre_producto"] + ". " + df["justificacion"] + ". " + df["evidencia"]
    )

    return df


def generate_embeddings(df, embedding_model):
    """Igual que en rag.py: genera un embedding por fila de 'semantic_text'."""
    texts = df["semantic_text"].tolist()
    return embedding_model.encode(texts, show_progress_bar=True)


# ---- Paso 2: interpretar la pregunta y extraer filtros -------------------

def extract_structured_filters(question):
    """
    Reglas simples por palabras clave para detectar filtros
    estructurados en la pregunta (ambito y estado). Version rapida de
    implementar; se puede migrar despues a que el LLM extraiga los
    filtros si se necesita mas flexibilidad.
    """
    question_lower = question.lower()

    filters = {"ambito": None, "categoria": None, "estado": None}

    ambito_keywords = {
        "MEDIO_AMBIENTE": ["ambiente", "medio ambiente", "ambiental"],
        "SALUD": ["salud"],
        "TECNOLOGIA": ["tecnologia", "tecnología"],
        "ECONOMIA": ["economia", "economía"],
        "SOCIEDAD": ["sociedad", "social"],
        "CULTURA": ["cultura", "cultural"],
        "POLITICA_PUBLICA": ["politica publica", "política pública", "politicas publicas"],
    }
    for ambito, keywords in ambito_keywords.items():
        if any(kw in question_lower for kw in keywords):
            filters["ambito"] = ambito
            break

    if any(kw in question_lower for kw in ["evidencia parcial", "parcialmente"]):
        filters["estado"] = "EVIDENCIA_PARCIAL"
    elif any(kw in question_lower for kw in ["cumple", "cumplen", "evidencia clara"]):
        filters["estado"] = "EVIDENCIA_CLARA"

    return filters


# ---- Paso 3: retrieval hibrido -------------------------------------------

def hybrid_search(question, df, embeddings, embedding_model, top_k=TOP_K):
    """
    Retrieval hibrido: primero filtra por metadata exacta (ambito,
    estado), y despues busca por similitud semantica SOLO dentro de
    lo que sobrevivio el filtro.
    """
    filters = extract_structured_filters(question)

    mask = pd.Series(True, index=df.index)
    for field, value in filters.items():
        if value is not None:
            mask &= (df[field] == value)

    filtered_df = df[mask]
    filtered_embeddings = embeddings[mask.values]

    if len(filtered_df) == 0:
        # No hay resultados con el filtro exacto - caemos de vuelta a
        # busqueda semantica sobre todo el df en vez de devolver vacio.
        filtered_df = df
        filtered_embeddings = embeddings

    question_embedding = embedding_model.encode([question])[0]
    norms = np.linalg.norm(filtered_embeddings, axis=1) * np.linalg.norm(question_embedding)
    similarities = filtered_embeddings @ question_embedding / norms

    k = min(top_k, len(filtered_df))
    top_indices = np.argsort(similarities)[::-1][:k]

    return filtered_df.iloc[top_indices]


# ---- Paso 4: generacion con Ollama ----------------------------------------

def ask_ollama(question, retrieved_rows):
    """
    Arma el contexto con las filas recuperadas y le pide a Ollama que
    responda, incluyendo conteos/rankings si la pregunta lo requiere,
    usando SOLO la informacion del contexto.
    """
    context_parts = []
    for _, row in retrieved_rows.iterrows():
        context_parts.append(
            f"Proyecto: {row['nombre_producto']}\n"
            f"Facultad: {row['facultad']}\n"
            f"Indicador: {row['id_indicador']} ({row['ambito'] or row['categoria']})\n"
            f"Estado: {row['estado']}\n"
            f"Evidencia: {row['evidencia']}\n"
            f"Justificacion: {row['justificacion']}\n"
        )
    context = "\n---\n".join(context_parts)

    prompt = f"""Responde la pregunta usando SOLO la informacion de los
siguientes registros de evaluacion de proyectos. Si la pregunta pide
contar, rankear u ordenar, hazlo usando UNICAMENTE los registros de
abajo. Si no hay informacion suficiente, dilo explicitamente. Responde
en espanol.

REGISTROS:
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
    print("Cargando resultados de evaluacion...")
    df = load_evaluation_results()

    print("Generando embeddings...")
    embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    embeddings = generate_embeddings(df, embedding_model)

    # Cambia esta pregunta por la que quieras probar
    question = "que proyectos cumplen mas indicadores del ambito medio ambiente?"

    print(f"\nPregunta: {question}")
    retrieved_rows = hybrid_search(question, df, embeddings, embedding_model)
    print(f"Encontrados {len(retrieved_rows)} registros relevantes.")

    print("Generando respuesta con Ollama...")
    answer = ask_ollama(question, retrieved_rows)

    print("\n--- RESPUESTA ---")
    print(answer)


if __name__ == "__main__":
    main()