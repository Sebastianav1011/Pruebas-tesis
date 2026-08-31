import asyncio
import difflib
import json
import os
import re
import shutil
from pathlib import Path

# Debe ir ANTES de importar lightrag o no tiene efecto.
os.environ["LLM_TIMEOUT"] = "900"

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

from lightrag import LightRAG, QueryParam
from lightrag.utils import EmbeddingFunc
from lightrag.llm.ollama import ollama_model_complete


# Rutas

DATA_DIR = Path(__file__).parent / "data"
RESULTS_DIR = Path(__file__).parent / "results"
WORKING_DIR = Path(__file__).parent / "lightrag_workspace"

PROJECTS_FILE = DATA_DIR / "60_proyectos.csv"
INDICATORS_FILE = DATA_DIR / "catalogo_indicadores.xlsx"
RESULTS_FILE = RESULTS_DIR / "resultados_indicadores.csv"


# Modelos

LLM_MODEL = "qwen2.5:3b"
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


# Configuracion general

INSERT_DELAY_SECONDS = 2

# "bypass" ignora user_prompt en esta version de LightRAG (probado). Usar "naive".
EVAL_QUERY_MODE = "naive"

MAX_PROJECTS = 5
MAX_INDICATORS = 15

# NUEVO: en lugar de evaluar los 15 indicadores en una sola consulta,
# se evaluan en lotes pequenos. Esto ataca dos problemas observados en
# la corrida anterior:
#   1. Recall bajo: con 15 indicadores y una salida limitada
#      (LLM_NUM_PREDICT), el modelo se quedaba sin espacio para
#      reportar mas de uno. Con lotes chicos, cada respuesta cabe
#      completa dentro del limite de tokens.
#   2. Evidencia parafraseada: comparar el proyecto contra 15
#      indicadores a la vez es mucha carga para un modelo de 3B:
#      es mas facil que "pierda de vista" cual texto es el resumen
#      real. Con menos indicadores por consulta, hay menos que
#      comparar a la vez.
INDICATOR_BATCH_SIZE = 4

# Borra el workspace antes de correr para partir de cero cada vez.
CLEAN_RUN = True

# Contexto del modelo. Se mantiene bajo para que sea rapido en CPU.
LLM_NUM_CTX = 8192

# Limite de tokens de salida por lote. Con lotes de 4 indicadores en
# vez de 15, este limite ya no deberia ser el cuello de botella.
LLM_NUM_PREDICT = 500

# Chunks que recupera "naive". Bajo porque el contexto real ya va en el prompt.
EVAL_CHUNK_TOP_K = 2

# Umbral de similitud (0 a 1) para marcar una evidencia como sospechosa
# de ser un parafraseo de la definicion del indicador, en lugar de
# evidencia real tomada del proyecto. No descarta la fila, solo la
# marca para revision manual (transparencia, no caja negra).
PARAPHRASE_SIMILARITY_THRESHOLD = 0.6


# Cargar modelo de embeddings

embedding_model = SentenceTransformer(EMBEDDING_MODEL)


# Limpiar workspace

def clean_workspace():

    if CLEAN_RUN and WORKING_DIR.exists():

        shutil.rmtree(WORKING_DIR)

        print(f"Workspace limpiado: {WORKING_DIR}")


# Cargar datos

def load_data():

    projects_df = pd.read_csv(PROJECTS_FILE)

    indicators_df = pd.read_excel(
        INDICATORS_FILE,
        sheet_name="Catalogo_Indicadores"
    )

    return projects_df, indicators_df


# Preparar proyectos

def prepare_projects(projects_df):

    project_columns = [
        "eid",
        "nombre_producto",
        "resumen",
        "palabras_clave"
    ]

    projects = projects_df[project_columns].copy()

    projects = projects.fillna("")

    return projects


# Preparar indicadores

def prepare_indicators(indicators_df):

    indicator_columns = [
        "id_indicador",
        "categoria",
        "ambito",
        "indicador",
        "tipo",
        "forma_evaluacion",
        "unidad",
    ]

    indicators = indicators_df[indicator_columns].copy()

    indicators = indicators.fillna("")

    return indicators


# Corta titulos con traducciones repetidas entre corchetes: "ES [EN] [PT]" -> "ES"

def trim_multilang_title(title):

    title = str(title)

    cut_index = title.find("[")

    if cut_index == -1:

        return title.strip()

    return title[:cut_index].strip()


# Convertir proyecto a texto (version completa, usada para insertar en el KG)

def project_to_text(project):

    return (
        f"Project ID: {project['eid']}\n"
        f"Title: {project['nombre_producto']}\n"
        f"Keywords: {project['palabras_clave']}\n"
        f"Abstract: {project['resumen']}"
    )


# Version recortada del texto del proyecto, para el prompt de evaluacion

def project_to_text_for_eval(project):

    return (
        f"Title: {trim_multilang_title(project['nombre_producto'])}\n"
        f"Keywords: {project['palabras_clave']}\n"
        f"Abstract: {project['resumen']}"
    )


# Convertir indicador a texto

def indicator_to_text(indicator):

    return (
        f"El indicador {indicator['id_indicador']} pertenece a la "
        f"categoria {indicator['categoria']}. "
        f"{indicator['indicador']} "
        f"Este indicador es de tipo {indicator['tipo']} y se evalua "
        f"mediante {indicator['forma_evaluacion']}."
    )


# Divide un DataFrame en trozos consecutivos de tamano fijo.
# Se usa para partir el catalogo de indicadores en lotes pequenos.

def batch_dataframe(df, batch_size):

    for start in range(0, len(df), batch_size):

        yield df.iloc[start:start + batch_size]


# Generar embeddings

async def embedding_func(texts):

    embeddings = embedding_model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    return np.asarray(embeddings)


# Inicializar LightRAG

async def initialize_rag():

    WORKING_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    rag = LightRAG(
        working_dir=str(WORKING_DIR),

        llm_model_func=ollama_model_complete,

        llm_model_name=LLM_MODEL,

        llm_model_kwargs={
            "host": "http://localhost:11434",
            "options": {
                "num_ctx": LLM_NUM_CTX,
                "num_predict": LLM_NUM_PREDICT,
            },
            # Respaldo por si LLM_TIMEOUT no aplica en tu version.
            "timeout": 900,
        },

        embedding_func=EmbeddingFunc(
            embedding_dim=embedding_model.get_embedding_dimension(),
            max_token_size=32768,
            func=embedding_func,
        ),

        entity_extract_max_gleaning=0,

        chunk_token_size=600,

        llm_model_max_async=1,
    )

    await rag.initialize_storages()

    return rag


# Crear indicadores como conocimiento estructurado

def build_indicators_custom_kg(indicators):

    chunks = []
    entities = []

    for idx, row in indicators.iterrows():

        indicator_id = str(row["id_indicador"]).strip()

        if not indicator_id:

            indicator_id = f"indicator-row-{idx}"

            print(
                f"ADVERTENCIA: fila {idx} tiene 'id_indicador' vacio. "
                f"Se asigno ID sintetico: {indicator_id}"
            )

        source_id = f"indicator-{indicator_id}"

        chunks.append({
            "content": indicator_to_text(row),
            "source_id": source_id,
            "source_chunk_index": 0,
        })

        entities.append({
            "entity_name": indicator_id,
            "entity_type": "Indicator",
            "description": indicator_to_text(row),
            "source_id": source_id,
        })

    return {
        "chunks": chunks,
        "entities": entities,
        "relationships": [],
    }


# ID de proyecto consistente entre grafo y resultados (fallback si eid esta vacio)

def get_project_id(row, idx):

    project_id = str(row["eid"]).strip()

    if not project_id:

        project_id = f"project-row-{idx}"

    return project_id


# Proyectos como KG estructurado, sin extraccion LLM (evita costo + errores de formato)

def build_projects_custom_kg(projects):

    chunks = []
    entities = []

    for idx, row in projects.iterrows():

        project_id = get_project_id(row, idx)

        if not str(row["eid"]).strip():

            print(
                f"ADVERTENCIA: fila {idx} tiene 'eid' vacio. "
                f"Titulo: '{row['nombre_producto']}'. "
                f"Se asigno ID sintetico: {project_id}"
            )

        source_id = f"project-{project_id}"

        chunks.append({
            "content": project_to_text(row),
            "source_id": source_id,
            "source_chunk_index": 0,
        })

        entities.append({
            "entity_name": project_id,
            "entity_type": "Project",
            "description": project_to_text(row),
            "source_id": source_id,
        })

    return {
        "chunks": chunks,
        "entities": entities,
        "relationships": [],
    }


# Relaciones proyecto -> indicador desde la evaluacion LLM.

def build_relations_custom_kg(results_df):

    relationships = []

    valid_rows = results_df.dropna(subset=["id_indicador"])

    for _, row in valid_rows.iterrows():

        relationships.append({
            "src_id": str(row["project_id"]),
            "tgt_id": str(row["id_indicador"]),
            "description": row["evidence"] or "",
            "keywords": "aplica_a",
            "weight": 1.0,
            "source_id": f"eval-{row['project_id']}-{row['id_indicador']}",
        })

    return {
        "chunks": [],
        "entities": [],
        "relationships": relationships,
    }


# Insertar datos

async def insert_all_data(
    rag,
    projects,
    indicators
):

    print(f"Insertando {len(indicators)} indicadores...")

    indicators_kg = build_indicators_custom_kg(indicators)

    await rag.ainsert_custom_kg(indicators_kg)

    print("Indicadores insertados.")

    print(
        f"Insertando {len(projects)} proyectos "
        "(KG estructurado, sin extraccion LLM)..."
    )

    projects_kg = build_projects_custom_kg(projects)

    await rag.ainsert_custom_kg(projects_kg)

    print("Proyectos insertados.")


# Insertar relaciones proyecto-indicador ya evaluadas

async def insert_relations(rag, results_df):

    relations_kg = build_relations_custom_kg(results_df)

    if not relations_kg["relationships"]:

        print("No hay relaciones validas para insertar en el grafo.")

        return

    print(
        f"Insertando {len(relations_kg['relationships'])} "
        f"relaciones proyecto-indicador en el grafo..."
    )

    try:

        await rag.ainsert_custom_kg(relations_kg)

        print("Relaciones insertadas.")

    except Exception as error:

        print(
            "Error insertando relaciones (revisa el schema esperado "
            f"por tu version de LightRAG): {error}"
        )


# Crear referencia de un LOTE de indicadores (no del catalogo completo)

def build_indicators_reference(indicators_batch):

    lines = [
        f"- {row['id_indicador']}: {row['indicador']}"
        for _, row in indicators_batch.iterrows()
    ]

    return "\n".join(lines)


# Crear consulta de busqueda (para el retrieval de "naive", no para el LLM)

def build_query(project):

    return (
        f"{trim_multilang_title(project['nombre_producto'])} "
        f"{project['palabras_clave']}"
    )


# Texto del proyecto va explicito aqui (no depende del retrieval).
# Se agrega una instruccion mas estricta contra el parafraseo: se le
# pide al modelo explicitamente que NO reutilice frases similares a
# la descripcion del indicador.

def build_indicator_instructions(project_text, indicators_reference):

    return (
        "Analiza UNICAMENTE el siguiente proyecto de investigacion. "
        "No mezcles evidencia de otros proyectos.\n\n"

        f"{project_text}\n\n"

        "Del siguiente catalogo de indicadores institucionales, identifica "
        "cuales aplican a ESTE proyecto especifico:\n"

        f"{indicators_reference}\n\n"

        "REGLA IMPORTANTE sobre la evidencia: la evidencia de cada "
        "indicador debe ser una cita o parafraseo CORTO tomado "
        "unicamente del Title, Keywords o Abstract del proyecto "
        "mostrado arriba. NUNCA copies ni repitas el texto de la "
        "descripcion del indicador como si fuera evidencia -- si no "
        "encuentras texto especifico del proyecto que lo sustente, "
        "no incluyas ese indicador.\n\n"

        "Responde UNICAMENTE con un objeto JSON valido, "
        "sin texto adicional antes ni despues, "
        "con esta forma exacta:\n"

        '{"applicable_indicators": '
        '[{"id_indicador": "...", "evidence": "..."}]}'
    )


# Leer respuesta del modelo

def parse_llm_response(raw_response):

    if raw_response is None:

        return []

    if not isinstance(raw_response, str):

        raw_response = str(raw_response)

    match = re.search(
        r"\{.*\}",
        raw_response,
        re.DOTALL
    )

    if not match:

        return []

    try:

        parsed = json.loads(
            match.group(0)
        )

        return parsed.get(
            "applicable_indicators",
            []
        )

    except json.JSONDecodeError:

        return []


# Heuristica de deteccion de parafraseo: compara la evidencia devuelta
# contra la descripcion original del indicador. Si son muy parecidas,
# es probable que el modelo haya copiado la definicion en lugar de dar
# evidencia real del proyecto. No descarta la fila, solo la marca para
# que quede visible y se pueda revisar manualmente -- transparencia en
# vez de ocultar el problema.

def looks_like_paraphrase(evidence_text, indicator_description):

    if not evidence_text or not indicator_description:

        return False

    similarity = difflib.SequenceMatcher(
        None,
        evidence_text.lower().strip(),
        indicator_description.lower().strip(),
    ).ratio()

    return similarity >= PARAPHRASE_SIMILARITY_THRESHOLD


# Evaluar un proyecto contra TODOS los indicadores, en lotes pequenos

async def evaluate_one_project(rag, row, project_id, indicators):

    query_text = build_query(row)

    project_text = project_to_text_for_eval(row)

    project_rows = []

    for batch in batch_dataframe(indicators, INDICATOR_BATCH_SIZE):

        indicators_reference = build_indicators_reference(batch)

        instructions = build_indicator_instructions(
            project_text,
            indicators_reference
        )

        try:

            response = await rag.aquery(
                query_text,
                param=QueryParam(
                    mode=EVAL_QUERY_MODE,
                    chunk_top_k=EVAL_CHUNK_TOP_K,
                    enable_rerank=False,
                    user_prompt=instructions,
                )
            )

            applicable = parse_llm_response(response)

        except Exception as error:

            print(
                f"    Error en lote de indicadores para "
                f"{project_id}: {error}"
            )

            continue

        # Mapa rapido id_indicador -> descripcion, para la
        # verificacion de parafraseo.
        descriptions_by_id = dict(
            zip(batch["id_indicador"], batch["indicador"])
        )

        for item in applicable:

            if not isinstance(item, dict):

                continue

            ind_id = item.get("id_indicador")

            if ind_id not in descriptions_by_id:

                # El modelo respondio un id que no estaba en ESTE
                # lote (posible alucinacion); se descarta.
                continue

            evidence = item.get("evidence", "")

            suspicious = looks_like_paraphrase(
                evidence,
                descriptions_by_id[ind_id]
            )

            project_rows.append({
                "project_id": project_id,
                "id_indicador": ind_id,
                "evidence": evidence,
                "posible_parafraseo": suspicious,
                "raw_response": response,
            })

    return project_rows


# Evaluar todos los proyectos

async def evaluate_all_projects(rag, projects, indicators):

    all_rows = []

    total_batches = (
        len(indicators) + INDICATOR_BATCH_SIZE - 1
    ) // INDICATOR_BATCH_SIZE

    for i, row in projects.iterrows():

        project_id = get_project_id(row, i)

        print(
            f"[{i + 1}/{len(projects)}] Consultando indicadores para "
            f"{project_id} ({total_batches} lotes de "
            f"{INDICATOR_BATCH_SIZE} indicadores)..."
        )

        project_rows = await evaluate_one_project(
            rag, row, project_id, indicators
        )

        if not project_rows:

            all_rows.append({
                "project_id": project_id,
                "id_indicador": None,
                "evidence": None,
                "posible_parafraseo": None,
                "raw_response": None,
            })

        else:

            print(
                f"    -> {len(project_rows)} indicador(es) detectados."
            )

            all_rows.extend(project_rows)

    return pd.DataFrame(all_rows)


# Ejecutar todo

async def main():

    clean_workspace()

    projects_df, indicators_df = load_data()

    projects = prepare_projects(projects_df)

    indicators = prepare_indicators(indicators_df)

    projects = projects.head(MAX_PROJECTS)
    indicators = indicators.head(MAX_INDICATORS)

    print(
        f"Projects loaded: {len(projects_df)} "
        f"(usando {len(projects)} para esta prueba)"
    )

    print(
        f"Indicators loaded: {len(indicators_df)} "
        f"(usando {len(indicators)} para esta prueba, "
        f"en lotes de {INDICATOR_BATCH_SIZE})"
    )

    rag = await initialize_rag()

    print("LightRAG initialized successfully")

    await insert_all_data(rag, projects, indicators)

    results_df = await evaluate_all_projects(rag, projects, indicators)

    await insert_relations(rag, results_df)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    try:

        results_df.to_csv(
            RESULTS_FILE,
            index=False,
            encoding="utf-8-sig"
        )

        saved_path = RESULTS_FILE

    except PermissionError:

        fallback_path = (
            RESULTS_DIR / "resultados_indicadores_ultima_corrida.csv"
        )

        print(
            f"ADVERTENCIA: no se pudo escribir en {RESULTS_FILE} "
            "(posiblemente esta abierto en Excel u otro programa). "
            f"Guardando en {fallback_path} en su lugar."
        )

        results_df.to_csv(
            fallback_path,
            index=False,
            encoding="utf-8-sig"
        )

        saved_path = fallback_path

    print(f"\nResultados guardados en: {saved_path}")

    print(
        f"Total de relaciones proyecto-indicador encontradas: "
        f"{len(results_df)}"
    )

    sospechosas = results_df["posible_parafraseo"].sum() if (
        "posible_parafraseo" in results_df.columns
    ) else 0

    print(
        f"De esas, marcadas como posible parafraseo: {sospechosas}"
    )


if __name__ == "__main__":

    asyncio.run(main())
