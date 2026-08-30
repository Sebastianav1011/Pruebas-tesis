"""
Etapa 1: Evaluacion de indicadores (LLM-as-judge, local con Ollama)

Esto NO es RAG - es una evaluacion exhaustiva: cada uno de los 60
proyectos se evalua contra CADA UNO de los 48 indicadores del catalogo,
sin filtrar ni buscar nada. El resultado es una tabla de 60 x 48 filas
que despues sirve de base de conocimiento para el RAG hibrido
(ver rag_hybrid.py).

Convencion de este archivo:
  - Nombres de variables, funciones y archivos: en ingles
  - Comentarios y docstrings: en espanol

Cada funcion tiene un TODO. Completa en ese orden y prueba con
un solo proyecto antes de correr los 60 completos (los modelos
locales pueden tardar, no querras esperar hasta el final para
descubrir un error).
"""

import difflib
import json
import re
from pathlib import Path

import pandas as pd
import requests


# ---- Config -----------------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"
PROJECTS_FILE = DATA_DIR / "60_proyectos.csv"
INDICATORS_FILE = DATA_DIR / "catalogo_indicadores.xlsx"
OUTPUT_FILE = Path(__file__).parent / "evaluation_results.csv"

OLLAMA_MODEL_NAME = "llama3.2:3b"
OLLAMA_URL = "http://localhost:11434/api/generate"

VALID_STATES = {"EVIDENCIA_CLARA", "EVIDENCIA_PARCIAL", "SIN_EVIDENCIA", "NO_APLICA"}

# Evaluar de a un indicador por request es muy confiable pero muy lento
# (cada llamada repite el procesamiento de titulo+resumen+instrucciones).
# En lotes de 8, llama3.2:3b responde ~8x mas rapido en total (aunque a
# veces devuelve un objeto {id_indicador: {...}} en vez de un arreglo -
# lo manejamos en _parse_batch_response).
BATCH_SIZE = 8
# A veces (parece ~30% de las veces) el modelo colapsa el lote a un
# solo objeto en vez de los 8 pedidos. Con 3 reintentos todavia se
# puede agotar; 5 baja bastante la probabilidad de fallo total.
MAX_ATTEMPTS_PER_BATCH = 5


# ---- Paso 1: cargar proyectos e indicadores ----------------------------

def load_projects():
    """
    Carga el CSV de proyectos. Solo necesitamos titulo y resumen para
    evaluar contra los indicadores (el resto de columnas se conservan
    para usarlas despues como metadata en la tabla de resultados).
    """
    df = pd.read_csv(PROJECTS_FILE, encoding="utf-8-sig")
    df["nombre_producto"] = df["nombre_producto"].fillna("")
    df["resumen"] = df["resumen"].fillna("")
    return df


def load_indicators():
    """
    Carga el catalogo de 48 indicadores desde el Excel. Rellena nulos
    con "" para que no truene al convertir a JSON en el prompt.
    """
    df = pd.read_excel(INDICATORS_FILE, sheet_name="Catalogo_Indicadores")
    df = df.fillna("")
    return df


# ---- Paso 2: armar el prompt y evaluar un proyecto ----------------------

def build_evaluation_prompt(title, summary, batch_df):
    """
    Arma el prompt que le pide al modelo evaluar TODOS los indicadores
    de 'batch_df' contra un proyecto, devolviendo solo JSON (sin texto
    adicional).
    """
    catalog = batch_df.to_dict(orient="records")

    prompt = f"""Analiza un proyecto academico usando UNICAMENTE su titulo y resumen.

No uses conocimiento externo. No inventes informacion. No asumas que
la falta de informacion significa incumplimiento. No confundas
intenciones con resultados: por ejemplo, "busca mejorar" no demuestra
que mejoro.

Evalua TODOS los indicadores del catalogo. Para cada uno usa
exactamente un estado:
- EVIDENCIA_CLARA: el resumen contiene evidencia directa.
- EVIDENCIA_PARCIAL: hay informacion relacionada pero incompleta.
- SIN_EVIDENCIA: el resumen no permite respaldar el indicador.
- NO_APLICA: el indicador claramente no corresponde con la naturaleza
  del proyecto.

Para cada indicador, evidencia debe ser una cita textual LITERAL del
resumen, copiada EXACTAMENTE en el mismo idioma en que esta escrito el
resumen (si el resumen esta en ingles, la cita debe estar en ingles;
NO traduzcas la cita al espanol). justificacion si puede estar en
espanol. justificacion debe tener maximo dos frases. confianza debe
ser un numero entre 0 y 1.

Devuelve UNICAMENTE un arreglo JSON valido, con un objeto por cada
id_indicador del catalogo, con este formato:
{{"id_indicador": "...", "estado": "...", "evidencia": null, "justificacion": "...", "confianza": 0.0}}

TITULO:
{title}

RESUMEN:
{summary}

CATALOGO DE INDICADORES:
{json.dumps(catalog, ensure_ascii=False)}
"""
    return prompt


def _evaluate_batch_once(title, summary, batch_df):
    """Una sola llamada a Ollama para un lote (sin reintento ni validacion)."""
    prompt = build_evaluation_prompt(title, summary, batch_df)

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL_NAME,
            "prompt": prompt,
            "stream": False,
            "format": "json",  # fuerza sintaxis JSON valida (grammar-constrained)
            "options": {"num_ctx": 8192},
        },
    )
    response.raise_for_status()
    text = response.json()["response"].strip()

    # Algunos modelos envuelven el JSON en ```json ... ``` aunque se
    # les pida que no lo hagan - lo limpiamos por si acaso.
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    return text


def _normalize_estado(raw_estado):
    """
    Los modelos locales a veces trunca/tipean mal 'estado' (ej.
    "EVIDENCIA_CLAR" en vez de "EVIDENCIA_CLARA"). Si lo recibido es un
    prefijo inequivoco de un unico estado valido, lo corrige en vez de
    gastar un reintento completo por un typo.
    """
    if raw_estado in VALID_STATES:
        return raw_estado

    if isinstance(raw_estado, str) and raw_estado:
        candidatos = [s for s in VALID_STATES if s.startswith(raw_estado)]
        if len(candidatos) == 1:
            return candidatos[0]

    return raw_estado


def _parse_batch_response(text):
    """
    Los modelos locales devuelven el lote evaluado en formas distintas
    segun el dia: un arreglo JSON (lo pedido), o un objeto JSON con
    cada id_indicador como clave (mas comun con llama3.2:3b en modo
    format=json). Normaliza ambos casos a una lista de evaluaciones.
    """
    parsed = json.loads(text)

    if isinstance(parsed, list):
        return parsed

    if isinstance(parsed, dict):
        # Caso {"COL-01": {...}, "COL-02": {...}, ...}. A veces el objeto
        # interno no repite el id_indicador (solo esta como clave) - lo
        # completamos con la clave en ese caso.
        if all(isinstance(v, dict) for v in parsed.values()):
            evaluations = []
            for key, value in parsed.items():
                if "id_indicador" not in value:
                    value = {**value, "id_indicador": key}
                evaluations.append(value)
            return evaluations
        # Caso de un solo objeto de evaluacion (colapso a un item).
        if "id_indicador" in parsed:
            return [parsed]

    raise ValueError("No se pudo interpretar la respuesta como evaluaciones.")


# Que tanto (0-1) del texto citado como 'evidencia' tiene que coincidir
# con el resumen real (via el bloque comun mas largo) para aceptarlo
# como una cita genuina. Tolera parafraseo leve, puntuacion distinta o
# recortes con "...", pero rechaza evidencia inventada/copiada de otro
# lado (que tipicamente comparte muy poco texto literal con el resumen).
GROUNDING_THRESHOLD = 0.6


def _normalize_for_matching(text):
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def _grounding_ratio(evidencia_norm, summary_norm):
    if not evidencia_norm:
        return 1.0
    matcher = difflib.SequenceMatcher(None, evidencia_norm, summary_norm)
    match = matcher.find_longest_match(0, len(evidencia_norm), 0, len(summary_norm))
    return match.size / len(evidencia_norm)


def _degrade_ungrounded_evidence(evaluations, summary):
    """
    Los modelos locales a veces marcan EVIDENCIA_CLARA/PARCIAL citando
    la propia definicion del indicador en 'evidencia' en vez de una
    cita real del resumen (evidencia inventada/circular). Si el bloque
    comun mas largo entre la cita y el resumen es corto en relacion al
    tamano de la cita, degradamos el estado a SIN_EVIDENCIA en vez de
    dejar pasar una evidencia falsa - pero guardamos el texto original
    en 'evidencia_original' para poder auditar el criterio despues.
    """
    summary_norm = _normalize_for_matching(summary)

    for item in evaluations:
        evidencia = item.get("evidencia")
        if not isinstance(evidencia, str) or not evidencia.strip():
            continue

        evidencia_norm = _normalize_for_matching(evidencia)
        ratio = _grounding_ratio(evidencia_norm, summary_norm)
        if ratio < GROUNDING_THRESHOLD:
            item["evidencia_original"] = evidencia
            item["estado"] = "SIN_EVIDENCIA"
            item["evidencia"] = None
            item["justificacion"] = (
                (item.get("justificacion") or "").strip()
                + f" [Evidencia citada no coincide suficientemente con el resumen "
                f"(similitud {ratio:.2f} < {GROUNDING_THRESHOLD}); estado degradado "
                "automaticamente a SIN_EVIDENCIA.]"
            ).strip()


def _validate_batch(evaluations, batch_df, batch_num):
    expected_ids = set(batch_df["id_indicador"])
    received_ids = {item.get("id_indicador") for item in evaluations}
    if len(evaluations) != len(expected_ids) or received_ids != expected_ids:
        faltantes = expected_ids - received_ids
        raise ValueError(
            f"Faltan o sobran indicadores en el lote {batch_num}. Faltantes: {faltantes}"
        )

    invalid_states = [
        item.get("estado") for item in evaluations
        if item.get("estado") not in VALID_STATES
    ]
    if invalid_states:
        raise ValueError(
            f"Estados invalidos encontrados en el lote {batch_num}: {invalid_states}"
        )


def _evaluate_single_once(title, summary, indicator):
    """Una sola llamada a Ollama para UN indicador (respaldo cuando el lote falla)."""
    batch_df = indicator.to_frame().T
    prompt = build_evaluation_prompt(title, summary, batch_df)

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL_NAME,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"num_ctx": 4096},
        },
    )
    response.raise_for_status()
    text = response.json()["response"].strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return text


def evaluate_single_indicator(title, summary, indicator, max_attempts=MAX_ATTEMPTS_PER_BATCH):
    """
    Evalua UN indicador a la vez. Mas lento que en lotes, pero mucho
    mas confiable - se usa como respaldo cuando un lote entero falla.
    """
    last_error = None
    for attempt in range(max_attempts):
        text = _evaluate_single_once(title, summary, indicator)
        try:
            evaluations = _parse_batch_response(text)
            if not evaluations or not isinstance(evaluations[0], dict):
                raise ValueError("La respuesta no contiene un objeto JSON evaluable.")
            evaluation = evaluations[0]
            evaluation.setdefault("id_indicador", indicator["id_indicador"])
            evaluation["estado"] = _normalize_estado(evaluation.get("estado"))
            _degrade_ungrounded_evidence([evaluation], summary)
            if evaluation.get("estado") not in VALID_STATES:
                raise ValueError(f"Estado invalido: {evaluation.get('estado')}")
            return evaluation
        except (json.JSONDecodeError, ValueError) as error:
            last_error = error

    raise ValueError(
        f"Indicador {indicator['id_indicador']} para '{title[:50]}...' "
        f"fallo tras {max_attempts} intentos: {last_error}"
    )


def evaluate_batch(title, summary, batch_df, batch_num=1, max_attempts=MAX_ATTEMPTS_PER_BATCH):
    """
    Evalua un lote de indicadores, con reintentos si Ollama no devuelve
    un JSON valido o completo para el lote. Si el lote entero sigue
    fallando, cae a evaluar cada indicador del lote por separado (mas
    lento, pero confiable) en vez de perder el lote completo.
    """
    last_error = None
    for attempt in range(max_attempts):
        text = _evaluate_batch_once(title, summary, batch_df)
        try:
            evaluations = _parse_batch_response(text)
            for item in evaluations:
                if isinstance(item, dict):
                    item["estado"] = _normalize_estado(item.get("estado"))
            _degrade_ungrounded_evidence(evaluations, summary)
            _validate_batch(evaluations, batch_df, batch_num)
            return {item["id_indicador"]: item for item in evaluations}
        except (json.JSONDecodeError, ValueError) as error:
            last_error = error

    print(
        f"  Lote {batch_num} fallo tras {max_attempts} intentos ({last_error}); "
        "evaluando indicador por indicador como respaldo..."
    )
    return {
        indicator["id_indicador"]: evaluate_single_indicator(title, summary, indicator)
        for _, indicator in batch_df.iterrows()
    }


def evaluate_project(title, summary, indicators_df, batch_size=BATCH_SIZE):
    """
    Evalua un proyecto contra todo el catalogo de indicadores, en
    lotes de 'batch_size' para no repetir el procesamiento del
    titulo/resumen/instrucciones en cada llamada.
    """
    results = {}
    for start in range(0, len(indicators_df), batch_size):
        batch_df = indicators_df.iloc[start:start + batch_size]
        batch_num = start // batch_size + 1
        results.update(evaluate_batch(title, summary, batch_df, batch_num))

    return results


# ---- Paso 3: correr sobre los 60 proyectos y guardar --------------------

def run_full_evaluation(projects_df, indicators_df):
    """
    Evalua cada proyecto de projects_df contra todo el catalogo de
    indicadores y arma la tabla de resultados (N proyectos x 48
    indicadores), combinando metadata del proyecto + del indicador +
    el resultado de la evaluacion.
    """
    total = len(projects_df)
    all_rows = []

    for i, (_, project) in enumerate(projects_df.iterrows(), start=1):
        print(f"[{i}/{total}] Evaluando: {project['nombre_producto'][:60]}...")
        evaluations = evaluate_project(project["nombre_producto"], project["resumen"], indicators_df)

        for _, indicator in indicators_df.iterrows():
            evaluation = evaluations[indicator["id_indicador"]]
            all_rows.append({
                "nombre_producto": project["nombre_producto"],
                "facultad": project["facultad"],
                "investigador_docente": project["investigador_docente"],
                "anio": project["anio"],
                "id_indicador": indicator["id_indicador"],
                "categoria": indicator["categoria"],
                "ambito": indicator["ambito"],
                "estado": evaluation.get("estado"),
                "evidencia": evaluation.get("evidencia"),
                "evidencia_original": evaluation.get("evidencia_original"),
                "justificacion": evaluation.get("justificacion"),
                "confianza": evaluation.get("confianza"),
            })

    return all_rows


# ---- Main -----------------------------------------------------------------

def main():
    print("Cargando proyectos e indicadores...")
    projects_df = load_projects()
    indicators_df = load_indicators()
    print(f"Proyectos: {len(projects_df)} | Indicadores: {len(indicators_df)}")

    print("\nEvaluando (esto puede tardar, corre 60 x 48 evaluaciones)...")
    results = run_full_evaluation(projects_df, indicators_df)

    results_df = pd.DataFrame(results)
    results_df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    print(f"\nListo. {len(results_df)} filas guardadas en:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()