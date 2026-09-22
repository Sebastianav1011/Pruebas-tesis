"""Pipeline GraphRAG local y auditable para diez proyectos.

No usa OpenAI, APIs ni extracciones producidas por Codex. Python construye
fragmentos, embeddings multilingües, candidatos, grafo, consultas y métricas.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer


BASE_DIR = Path(__file__).resolve().parents[2]
CONTROLLED_DIR = BASE_DIR / "01_prueba_controlada_10_proyectos"
DATOS = CONTROLLED_DIR / "datos"
# Las ejecuciones nuevas se aíslan en un subdirectorio para no sobrescribir
# los artefactos históricos reorganizados.
RESULTADOS = CONTROLLED_DIR / "resultados" / "ejecucion"
SELECCION_PATH = DATOS / "10_proyectos_indicadores_claros.csv"
CATALOGO_PATH = BASE_DIR / "shared" / "datos" / "catalogo_indicadores.xlsx"
GROUND_TRUTH_PATH = DATOS / "validacion_10_proyectos.json"
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODEL_CACHE = BASE_DIR / ".venv" / "model_cache"

FRAGMENTOS_PATH = RESULTADOS / "fragmentos" / "fragmentos_10.json"
EMBEDDINGS_DIR = RESULTADOS / "embeddings"
EMBEDDINGS_PROYECTOS = EMBEDDINGS_DIR / "embeddings_proyectos.npy"
EMBEDDINGS_FRAGMENTOS = EMBEDDINGS_DIR / "embeddings_fragmentos.npy"
EMBEDDINGS_INDICADORES = EMBEDDINGS_DIR / "embeddings_indicadores.npy"
METADATA_EMBEDDINGS = EMBEDDINGS_DIR / "metadata_embeddings.json"
CANDIDATOS_PATH = RESULTADOS / "indicadores" / "candidatos_indicadores_10.csv"
DETECTADOS_PATH = RESULTADOS / "indicadores" / "indicadores_detectados_10.json"
NODOS_PATH = RESULTADOS / "nodos" / "nodos_10.csv"
RELACIONES_PATH = RESULTADOS / "relaciones" / "relaciones_10.csv"
GRAFO_PATH = RESULTADOS / "grafo" / "grafo_10.graphml"
RESULTADO_ES_PATH = RESULTADOS / "consultas" / "resultado_graphrag_10_es.json"
RESULTADO_EN_PATH = RESULTADOS / "consultas" / "resultado_graphrag_10_en.json"
COMPARACION_PATH = RESULTADOS / "evaluacion" / "comparacion_ground_truth.json"
METRICAS_PATH = RESULTADOS / "evaluacion" / "metricas.json"
INFORME_CSV_PATH = RESULTADOS / "informe" / "informe_final.csv"
TIPO_FUENTE = "PROYECTO"

# Valores fijos antes de abrir el ground truth; no se ajustan durante la ejecución.
TOP_INDICADORES_POR_FRAGMENTO = 3
UMBRAL_CANDIDATO = 0.42
UMBRAL_INDICADOR_CLARO = 0.55
TOP_K_PROYECTOS = 3
TOP_FRAGMENTOS_POR_PROYECTO = 2
UMBRAL_GRAFO = 0.50
PESOS_GRAFO = {
    "INDICADOR": 1.00,
    "PALABRA_CLAVE": 0.70,
    "INVESTIGADOR": 0.65,
    "COAUTOR": 0.65,
    "FINANCIADOR": 0.65,
    "AFILIACION": 0.55,
    "PROGRAMA": 0.40,
    "FACULTAD": 0.35,
    "GRAN_AREA": 0.35,
    "AREA_CONOCIMIENTO": 0.35,
    "OBJETIVO_SOCIOECONOMICO": 0.35,
    "PAIS": 0.10,
}

COLUMNAS_TEXTO_PREFERIDAS = (
    "facultad", "programa_creacion", "tipo_documental", "investigador_docente",
    "anio", "nombre_producto", "resumen", "palabras_clave",
    "nombre_revista_libro", "editorial", "fuente", "coautores",
    "afiliacion_coautores", "pais_coautores", "financiadores", "objetivos",
    "metodologia", "resultados_investigacion", "justificacion", "gran_area",
    "area_conocimiento", "objetivo_socioeconomico",
)
# Se conservan todos los campos originales como fragmentos/contexto de grafo.
# Solo estos campos describen contenido apto para respaldar un indicador.
CAMPOS_EVIDENCIA_INDICADORES = {
    "nombre_producto",
    "resumen",
    "palabras_clave",
    "objetivos",
    "metodologia",
    "resultados_investigacion",
    "justificacion",
}
PATRONES_GROUND_TRUTH = (
    "clave_consolidacion", "fila_origen_evidencia", "indicador_principal",
    "otros_indicadores", "indicador_validado", "categoria_indicador",
    "confianza_indicador", "campo_evidencia", "evidencia_indicador",
    "justificacion_indicador", "ground_truth", "validacion",
    "evidencia_validada", "indicador_esperado", "respuesta_esperada",
    "id_indicador", "indicador_catalogo", "estado_revision",
    "fuente_revision", "evidencia_textual",
)
NODOS_COLUMNA = {
    "facultad": ("FACULTAD", "PERTENECE_FACULTAD"),
    "programa_creacion": ("PROGRAMA", "PERTENECE_PROGRAMA"),
    "investigador_docente": ("INVESTIGADOR", "TIENE_INVESTIGADOR"),
    "palabras_clave": ("PALABRA_CLAVE", "TIENE_PALABRA_CLAVE"),
    "coautores": ("COAUTOR", "TIENE_COAUTOR"),
    "afiliacion_coautores": ("AFILIACION", "AFILIACION_RELACIONADA"),
    "pais_coautores": ("PAIS", "PAIS_RELACIONADO"),
    "financiadores": ("FINANCIADOR", "TIENE_FINANCIADOR"),
    "gran_area": ("GRAN_AREA", "PERTENECE_GRAN_AREA"),
    "area_conocimiento": ("AREA_CONOCIMIENTO", "PERTENECE_AREA_CONOCIMIENTO"),
    "objetivo_socioeconomico": ("OBJETIVO_SOCIOECONOMICO", "TIENE_OBJETIVO_SOCIOECONOMICO"),
}


def configurar_ejecucion(entrada: Path, directorio_resultados: Path, tipo_fuente: str) -> None:
    """Configura una ejecución independiente sin alterar el motor GraphRAG."""
    global SELECCION_PATH, RESULTADOS, FRAGMENTOS_PATH, EMBEDDINGS_DIR
    global EMBEDDINGS_PROYECTOS, EMBEDDINGS_FRAGMENTOS, EMBEDDINGS_INDICADORES
    global METADATA_EMBEDDINGS, CANDIDATOS_PATH, DETECTADOS_PATH, NODOS_PATH
    global RELACIONES_PATH, GRAFO_PATH, RESULTADO_ES_PATH, RESULTADO_EN_PATH
    global COMPARACION_PATH, METRICAS_PATH, INFORME_CSV_PATH, GROUND_TRUTH_PATH, TIPO_FUENTE
    SELECCION_PATH = entrada
    RESULTADOS = directorio_resultados
    GROUND_TRUTH_PATH = CONTROLLED_DIR / "datos" / "validacion_10_proyectos.json"
    TIPO_FUENTE = tipo_fuente
    FRAGMENTOS_PATH = RESULTADOS / "fragmentos" / "fragmentos_10.json"
    EMBEDDINGS_DIR = RESULTADOS / "embeddings"
    EMBEDDINGS_PROYECTOS = EMBEDDINGS_DIR / "embeddings_proyectos.npy"
    EMBEDDINGS_FRAGMENTOS = EMBEDDINGS_DIR / "embeddings_fragmentos.npy"
    EMBEDDINGS_INDICADORES = EMBEDDINGS_DIR / "embeddings_indicadores.npy"
    METADATA_EMBEDDINGS = EMBEDDINGS_DIR / "metadata_embeddings.json"
    CANDIDATOS_PATH = RESULTADOS / "indicadores" / "candidatos_indicadores_10.csv"
    DETECTADOS_PATH = RESULTADOS / "indicadores" / "indicadores_detectados_10.json"
    NODOS_PATH = RESULTADOS / "nodos" / "nodos_10.csv"
    RELACIONES_PATH = RESULTADOS / "relaciones" / "relaciones_10.csv"
    GRAFO_PATH = RESULTADOS / "grafo" / "grafo_10.graphml"
    RESULTADO_ES_PATH = RESULTADOS / "consultas" / "resultado_graphrag_10_es.json"
    RESULTADO_EN_PATH = RESULTADOS / "consultas" / "resultado_graphrag_10_en.json"
    COMPARACION_PATH = RESULTADOS / "evaluacion" / "comparacion_ground_truth.json"
    METRICAS_PATH = RESULTADOS / "evaluacion" / "metricas.json"
    INFORME_CSV_PATH = RESULTADOS / "informe" / "informe_final.csv"


def id_nodo_fuente(id_fuente: str) -> str:
    return f"{TIPO_FUENTE}::{id_fuente}"


def texto(valor: Any) -> str:
    if pd.isna(valor):
        return ""
    salida = str(valor).strip()
    return "" if salida.casefold() in {"", "nan", "none", "null", "-"} else salida


def normalizar(valor: Any) -> str:
    base = unicodedata.normalize("NFKD", texto(valor)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", base).casefold().strip()


def es_ground_truth(columna: str) -> bool:
    clave = normalizar(columna)
    return any(patron in clave for patron in PATRONES_GROUND_TRUTH)


def separar_valores(valor: str) -> list[str]:
    """Separa listas explícitas sin inferir entidades nuevas."""
    return [x.strip() for x in re.split(r"\s*(?:\||;|\n---\n)\s*", valor) if texto(x)]


def detectar_idioma(valor: str) -> str:
    palabras = re.findall(r"[a-záéíóúüñ]+", valor.casefold())
    es = sum(p in {"el", "la", "los", "las", "de", "del", "en", "para", "con", "una", "por"} for p in palabras)
    en = sum(p in {"the", "and", "of", "in", "for", "with", "to", "a", "an", "is"} for p in palabras)
    if es and en:
        return "mixto"
    if es:
        return "es"
    if en:
        return "en"
    return "desconocido"


def preparar_resultados(reconstruir: bool) -> None:
    if reconstruir and RESULTADOS.exists():
        bloqueados = []
        for archivo in RESULTADOS.rglob("*"):
            if not archivo.is_file():
                continue
            try:
                with archivo.open("ab"):
                    pass
            except PermissionError:
                bloqueados.append(str(archivo.relative_to(RESULTADOS)))
        if bloqueados:
            raise PermissionError(
                "Cierre los archivos abiertos antes de reconstruir Resultados/: "
                + ", ".join(bloqueados)
            )
        shutil.rmtree(RESULTADOS)
    for ruta in (
        FRAGMENTOS_PATH.parent, EMBEDDINGS_DIR, CANDIDATOS_PATH.parent,
        NODOS_PATH.parent, RELACIONES_PATH.parent, GRAFO_PATH.parent,
        RESULTADO_ES_PATH.parent, COMPARACION_PATH.parent, INFORME_CSV_PATH.parent,
    ):
        ruta.mkdir(parents=True, exist_ok=True)


def cargar_proyectos() -> tuple[list[dict[str, Any]], list[str], list[str]]:
    tabla = pd.read_csv(SELECCION_PATH, encoding="utf-8-sig", low_memory=False)
    if "id_proyecto" not in tabla.columns:
        raise ValueError("Falta id_proyecto en el CSV de selección.")
    if len(tabla) != 10 or tabla["id_proyecto"].map(texto).nunique() != 10:
        raise ValueError("La prueba exige exactamente 10 filas y 10 id_proyecto únicos.")
    excluidas = [str(c) for c in tabla.columns if es_ground_truth(str(c))]
    usadas = [c for c in COLUMNAS_TEXTO_PREFERIDAS if c in tabla.columns and c not in excluidas]
    if "nombre_producto" not in usadas:
        raise ValueError("No existe nombre_producto como campo original permitido.")
    print("COLUMNAS DE DATOS UTILIZADAS:")
    print(", ".join(usadas))
    print("COLUMNAS EXCLUIDAS POR GROUND TRUTH:")
    print(", ".join(excluidas) if excluidas else "(ninguna detectada)")
    proyectos = []
    for _, fila in tabla.iterrows():
        campos = {col: texto(fila[col]) for col in usadas if texto(fila[col])}
        proyectos.append({
            "id_proyecto": texto(fila["id_proyecto"]),
            "titulo": campos.get("nombre_producto", ""),
            "campos": campos,
        })
    return proyectos, usadas, excluidas


def cargar_catalogo() -> tuple[list[dict[str, str]], str, list[str]]:
    libro = pd.ExcelFile(CATALOGO_PATH)
    candidatas: list[tuple[int, str, pd.DataFrame]] = []
    for hoja in libro.sheet_names:
        tabla = pd.read_excel(CATALOGO_PATH, sheet_name=hoja)
        if {"indicador", "categoria"}.issubset(tabla.columns):
            candidatas.append((int(tabla["indicador"].notna().sum()), hoja, tabla))
    if not candidatas:
        raise ValueError("El catálogo no tiene hoja con indicador y categoria.")
    _, hoja, tabla = max(candidatas, key=lambda item: item[0])
    indicadores = []
    campos_descriptivos = [c for c in ("categoria", "ambito", "tipo", "forma_evaluacion", "unidad") if c in tabla]
    for _, fila in tabla.iterrows():
        nombre, categoria = texto(fila.get("indicador")), texto(fila.get("categoria"))
        if not nombre or not categoria:
            continue
        descriptor = " | ".join([nombre, *[texto(fila.get(c)) for c in campos_descriptivos if texto(fila.get(c))]])
        indicadores.append({
            "id_indicador": texto(fila.get("id_indicador")),
            "indicador": nombre,
            "categoria": categoria,
            # Se conserva para las salidas estructuradas; no interviene en el
            # embedding ni cambia la detección semántica.
            "ambito": texto(fila.get("ambito")),
            "texto_embedding": descriptor,
        })
    if len(indicadores) != 48:
        raise ValueError(f"Se esperaban 48 indicadores; se leyeron {len(indicadores)}.")
    return indicadores, hoja, list(tabla.columns)


def bloques_resumen(texto_resumen: str, limite: int = 900) -> list[str]:
    parrafos = [p.strip() for p in re.split(r"\n\s*\n+", texto_resumen) if p.strip()]
    salida: list[str] = []
    for parrafo in parrafos or [texto_resumen]:
        if len(parrafo) <= limite:
            salida.append(parrafo)
            continue
        oraciones = re.split(r"(?<=[.!?])\s+", parrafo)
        bloque = ""
        for oracion in oraciones:
            if bloque and len(bloque) + len(oracion) + 1 > limite:
                salida.append(bloque)
                bloque = oracion
            else:
                bloque = f"{bloque} {oracion}".strip()
        if bloque:
            salida.append(bloque)
    return salida


def crear_fragmentos(proyectos: list[dict[str, Any]]) -> list[dict[str, str]]:
    fragmentos = []
    for proyecto in proyectos:
        consecutivo = 1
        for campo, contenido in proyecto["campos"].items():
            bloques = bloques_resumen(contenido) if campo == "resumen" else [contenido]
            for bloque in bloques:
                if not texto(bloque):
                    continue
                fragmentos.append({
                    "id_fragmento": f"{proyecto['id_proyecto']}::{campo}::{consecutivo}",
                    "id_proyecto": proyecto["id_proyecto"],
                    "campo_origen": campo,
                    "texto": bloque,
                    "idioma": detectar_idioma(bloque),
                })
                consecutivo += 1
    FRAGMENTOS_PATH.write_text(json.dumps(fragmentos, ensure_ascii=False, indent=2), encoding="utf-8")
    return fragmentos


def cargar_modelo() -> SentenceTransformer:
    if not MODEL_CACHE.exists():
        raise FileNotFoundError(f"No existe caché local del modelo: {MODEL_CACHE}")
    try:
        return SentenceTransformer(MODEL_NAME, cache_folder=str(MODEL_CACHE), local_files_only=True)
    except Exception as error:
        raise RuntimeError(f"No se pudo cargar el modelo multilingüe local: {error}") from error


def codificar(modelo: SentenceTransformer, textos: list[str]) -> np.ndarray:
    return np.asarray(modelo.encode(textos, normalize_embeddings=True, show_progress_bar=False), dtype=np.float32)


def guardar_embeddings(
    proyectos: list[dict[str, Any]], fragmentos: list[dict[str, str]],
    indicadores: list[dict[str, str]], matriz_proyectos: np.ndarray,
    matriz_fragmentos: np.ndarray, matriz_indicadores: np.ndarray,
) -> None:
    np.save(EMBEDDINGS_PROYECTOS, matriz_proyectos)
    np.save(EMBEDDINGS_FRAGMENTOS, matriz_fragmentos)
    np.save(EMBEDDINGS_INDICADORES, matriz_indicadores)
    metadata = {
        "modelo": MODEL_NAME, "dimension": int(matriz_proyectos.shape[1]),
        "cantidad_proyectos": len(proyectos), "cantidad_fragmentos": len(fragmentos),
        "cantidad_indicadores": len(indicadores),
        "ids_proyectos": [p["id_proyecto"] for p in proyectos],
        "ids_fragmentos": [f["id_fragmento"] for f in fragmentos],
        "ids_indicadores": [i["id_indicador"] for i in indicadores],
        "normalizados": True,
    }
    METADATA_EMBEDDINGS.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def generar_candidatos(
    proyectos: list[dict[str, Any]], fragmentos: list[dict[str, str]],
    indicadores: list[dict[str, str]], matriz_fragmentos: np.ndarray,
    matriz_indicadores: np.ndarray,
) -> list[dict[str, Any]]:
    titulos = {p["id_proyecto"]: p["titulo"] for p in proyectos}
    similitudes = matriz_fragmentos @ matriz_indicadores.T
    candidatos = []
    for indice_fragmento, fragmento in enumerate(fragmentos):
        if fragmento["campo_origen"] not in CAMPOS_EVIDENCIA_INDICADORES:
            continue
        orden = np.argsort(similitudes[indice_fragmento])[::-1][:TOP_INDICADORES_POR_FRAGMENTO]
        for indice_indicador in orden:
            score = float(similitudes[indice_fragmento, indice_indicador])
            if score < UMBRAL_CANDIDATO:
                continue
            indicador = indicadores[int(indice_indicador)]
            candidatos.append({
                "id_proyecto": fragmento["id_proyecto"], "titulo": titulos[fragmento["id_proyecto"]],
                "id_fragmento": fragmento["id_fragmento"], "campo_origen": fragmento["campo_origen"],
                "indicador": indicador["indicador"], "id_indicador": indicador["id_indicador"],
                "categoria": indicador["categoria"], "ambito": indicador["ambito"],
                "score_semantico": round(score, 6),
                "evidencia_original": fragmento["texto"],
            })
    columnas = ["id_proyecto", "titulo", "id_fragmento", "campo_origen", "id_indicador",
                "indicador", "categoria", "ambito", "score_semantico", "evidencia_original"]
    pd.DataFrame(candidatos, columns=columnas).to_csv(CANDIDATOS_PATH, index=False, encoding="utf-8-sig")
    return candidatos


def consolidar_indicadores(candidatos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mejores: dict[tuple[str, str], dict[str, Any]] = {}
    for candidato in candidatos:
        if candidato["score_semantico"] < UMBRAL_INDICADOR_CLARO:
            continue
        clave = (candidato["id_proyecto"], candidato["id_indicador"])
        if clave not in mejores or candidato["score_semantico"] > mejores[clave]["score_semantico"]:
            mejores[clave] = candidato.copy()
    detectados = sorted(mejores.values(), key=lambda x: (x["id_proyecto"], -x["score_semantico"], x["id_indicador"]))
    DETECTADOS_PATH.write_text(json.dumps({
        "modelo_embeddings": MODEL_NAME,
        "umbral_indicador_claro": UMBRAL_INDICADOR_CLARO,
        "indicadores_detectados": detectados,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return detectados


def id_nodo(tipo: str, valor: str) -> str:
    return f"{tipo}::{normalizar(valor)}"


def agregar_nodo(grafo: nx.MultiDiGraph, tipo: str, nombre: str, **atributos: str) -> str:
    nodo = id_nodo(tipo, nombre)
    if nodo not in grafo:
        grafo.add_node(nodo, tipo=tipo, nombre=nombre, **atributos)
    return nodo


def construir_grafo(
    proyectos: list[dict[str, Any]], fragmentos: list[dict[str, str]],
    indicadores: list[dict[str, str]], candidatos: list[dict[str, Any]],
) -> nx.MultiDiGraph:
    grafo = nx.MultiDiGraph()
    for indicador in indicadores:
        nodo_indicador = agregar_nodo(grafo, "INDICADOR", indicador["indicador"], id_indicador=indicador["id_indicador"])
        nodo_categoria = agregar_nodo(grafo, "CATEGORIA_INDICADOR", indicador["categoria"])
        if not grafo.has_edge(nodo_indicador, nodo_categoria):
            grafo.add_edge(nodo_indicador, nodo_categoria, tipo_relacion="PERTENECE_A", peso=1.0)
    por_proyecto = defaultdict(list)
    for fragmento in fragmentos:
        por_proyecto[fragmento["id_proyecto"]].append(fragmento)
    for proyecto in proyectos:
        nodo_proyecto = id_nodo_fuente(proyecto["id_proyecto"])
        grafo.add_node(nodo_proyecto, tipo=TIPO_FUENTE, nombre=proyecto["titulo"], id_proyecto=proyecto["id_proyecto"])
        for fragmento in por_proyecto[proyecto["id_proyecto"]]:
            nodo_fragmento = f"FRAGMENTO::{fragmento['id_fragmento']}"
            grafo.add_node(nodo_fragmento, tipo="FRAGMENTO", nombre=fragmento["id_fragmento"],
                            id_fragmento=fragmento["id_fragmento"], campo_origen=fragmento["campo_origen"],
                            idioma=fragmento["idioma"], texto=fragmento["texto"])
            grafo.add_edge(nodo_proyecto, nodo_fragmento, tipo_relacion="CONTIENE", peso=1.0)
        for columna, (tipo, relacion) in NODOS_COLUMNA.items():
            for valor in separar_valores(proyecto["campos"].get(columna, "")):
                nodo = agregar_nodo(grafo, tipo, valor)
                grafo.add_edge(nodo_proyecto, nodo, tipo_relacion=relacion, peso=PESOS_GRAFO[tipo])
    for candidato in candidatos:
        fragmento = f"FRAGMENTO::{candidato['id_fragmento']}"
        indicador = id_nodo("INDICADOR", candidato["indicador"])
        grafo.add_edge(fragmento, indicador, tipo_relacion="EVIDENCIA_CANDIDATA_DE",
                       peso=float(candidato["score_semantico"]),
                       score_semantico=float(candidato["score_semantico"]),
                       campo_origen=candidato["campo_origen"])
    return grafo


def guardar_grafo(grafo: nx.MultiDiGraph) -> None:
    nodos = [{"id_nodo": nodo, **datos} for nodo, datos in grafo.nodes(data=True)]
    aristas = [{"origen": origen, "destino": destino, **datos}
               for origen, destino, datos in grafo.edges(data=True)]
    pd.DataFrame(nodos).to_csv(NODOS_PATH, index=False, encoding="utf-8-sig")
    pd.DataFrame(aristas).to_csv(RELACIONES_PATH, index=False, encoding="utf-8-sig")
    nx.write_graphml(grafo, GRAFO_PATH)


def fragmentos_relevantes(
    id_proyecto: str, fragmentos: list[dict[str, str]], puntajes: np.ndarray,
) -> list[dict[str, Any]]:
    indices = [i for i, f in enumerate(fragmentos) if f["id_proyecto"] == id_proyecto]
    orden = sorted(indices, key=lambda i: float(puntajes[i]), reverse=True)[:TOP_FRAGMENTOS_POR_PROYECTO]
    return [{"id_fragmento": fragmentos[i]["id_fragmento"], "campo_origen": fragmentos[i]["campo_origen"],
             "texto": fragmentos[i]["texto"], "score_semantico": round(float(puntajes[i]), 6)}
            for i in orden]


def recuperar_semanticamente(
    consulta: str, proyectos: list[dict[str, Any]], fragmentos: list[dict[str, str]],
    matriz_proyectos: np.ndarray, matriz_fragmentos: np.ndarray, modelo: SentenceTransformer,
) -> list[dict[str, Any]]:
    vector = codificar(modelo, [consulta])[0]
    puntajes_proyectos = matriz_proyectos @ vector
    puntajes_fragmentos = matriz_fragmentos @ vector
    orden = np.argsort(puntajes_proyectos)[::-1][:TOP_K_PROYECTOS]
    return [{
        "id_proyecto": proyectos[int(i)]["id_proyecto"], "titulo": proyectos[int(i)]["titulo"],
        "score_semantico": round(float(puntajes_proyectos[i]), 6),
        "fragmentos_relevantes": fragmentos_relevantes(proyectos[int(i)]["id_proyecto"], fragmentos, puntajes_fragmentos),
    } for i in orden]


def expandir_grafo(
    grafo: nx.MultiDiGraph, iniciales: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ids_iniciales = {p["id_proyecto"] for p in iniciales}
    acumulados: dict[str, dict[str, Any]] = {}
    for inicial in iniciales:
        nodo_proyecto = id_nodo_fuente(inicial["id_proyecto"])
        # Proyecto -> Fragmento -> Indicador <- Fragmento <- Proyecto: prioridad máxima.
        for _, fragmento, datos_contenido in grafo.out_edges(nodo_proyecto, data=True):
            if datos_contenido.get("tipo_relacion") != "CONTIENE":
                continue
            for _, indicador, datos_evidencia in grafo.out_edges(fragmento, data=True):
                if datos_evidencia.get("tipo_relacion") != "EVIDENCIA_CANDIDATA_DE":
                    continue
                if float(datos_evidencia.get("score_semantico", 0)) < UMBRAL_INDICADOR_CLARO:
                    continue
                for otro_fragmento in grafo.predecessors(indicador):
                    for otro_proyecto in grafo.predecessors(otro_fragmento):
                        datos_otro = grafo.nodes[otro_proyecto]
                        otro_id = datos_otro.get("id_proyecto")
                        if datos_otro.get("tipo") != TIPO_FUENTE or otro_id in ids_iniciales:
                            continue
                        score = PESOS_GRAFO["INDICADOR"] * min(float(datos_evidencia["score_semantico"]),
                                                                max(float(e.get("score_semantico", 0)) for _, _, e in grafo.out_edges(otro_fragmento, data=True) if e.get("tipo_relacion") == "EVIDENCIA_CANDIDATA_DE"))
                        registro = acumulados.setdefault(otro_id, {"id_proyecto": otro_id, "titulo": datos_otro["nombre"],
                                                                    "score_grafo": 0.0, "relacionado_mediante": []})
                        registro["score_grafo"] += score
                        enlace = {"tipo": "INDICADOR", "valor": grafo.nodes[indicador]["nombre"], "peso": PESOS_GRAFO["INDICADOR"]}
                        if enlace not in registro["relacionado_mediante"]:
                            registro["relacionado_mediante"].append(enlace)
        # Proyecto -> metadato compartido <- Proyecto; país por sí solo no alcanza el umbral.
        for _, nodo, arista in grafo.out_edges(nodo_proyecto, data=True):
            if arista.get("tipo_relacion") == "CONTIENE":
                continue
            tipo = grafo.nodes[nodo].get("tipo")
            if tipo not in PESOS_GRAFO:
                continue
            for otro_proyecto in grafo.predecessors(nodo):
                datos_otro = grafo.nodes[otro_proyecto]
                otro_id = datos_otro.get("id_proyecto")
                if datos_otro.get("tipo") != TIPO_FUENTE or otro_id in ids_iniciales:
                    continue
                registro = acumulados.setdefault(otro_id, {"id_proyecto": otro_id, "titulo": datos_otro["nombre"],
                                                            "score_grafo": 0.0, "relacionado_mediante": []})
                registro["score_grafo"] += PESOS_GRAFO[tipo]
                enlace = {"tipo": tipo, "valor": grafo.nodes[nodo]["nombre"], "peso": PESOS_GRAFO[tipo]}
                if enlace not in registro["relacionado_mediante"]:
                    registro["relacionado_mediante"].append(enlace)
    salida = []
    for registro in acumulados.values():
        registro["score_grafo"] = round(registro["score_grafo"], 6)
        if registro["score_grafo"] >= UMBRAL_GRAFO:
            salida.append(registro)
    return sorted(salida, key=lambda x: (-x["score_grafo"], x["id_proyecto"]))


def indicadores_compartidos(detectados: list[dict[str, Any]]) -> list[dict[str, Any]]:
    por_indicador: dict[str, list[str]] = defaultdict(list)
    for item in detectados:
        por_indicador[item["indicador"]].append(item["id_proyecto"])
    return [{"indicador": indicador, "proyectos": sorted(ids)}
            for indicador, ids in sorted(por_indicador.items()) if len(ids) > 1]


def ejecutar_consulta(
    consulta: str, salida: Path, proyectos: list[dict[str, Any]], fragmentos: list[dict[str, str]],
    matriz_proyectos: np.ndarray, matriz_fragmentos: np.ndarray, modelo: SentenceTransformer,
    grafo: nx.MultiDiGraph, detectados: list[dict[str, Any]],
) -> dict[str, Any]:
    recuperados = recuperar_semanticamente(consulta, proyectos, fragmentos, matriz_proyectos, matriz_fragmentos, modelo)
    agregados = expandir_grafo(grafo, recuperados)
    resultado = {
        "consulta": consulta, "modelo_embeddings": MODEL_NAME,
        "proyectos_recuperados_semanticamente": recuperados,
        "proyectos_agregados_por_grafo": agregados,
        "indicadores_detectados": detectados,
        "indicadores_compartidos": indicadores_compartidos(detectados),
        "resumen_tecnico": {
            "proyectos_semanticos": len(recuperados),
            "proyectos_agregados_grafo": len(agregados),
            "indicadores_detectados": len(detectados),
            "top_k_proyectos": TOP_K_PROYECTOS,
            "umbral_candidato": UMBRAL_CANDIDATO,
            "umbral_indicador_claro": UMBRAL_INDICADOR_CLARO,
            "umbral_grafo": UMBRAL_GRAFO,
        },
        "ground_truth_leido_antes_de_prediccion": False,
    }
    salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    return resultado


def guardar_informe_csv_desde_resultado() -> None:
    """Exporta una vista humana desde el resultado estructurado ES."""
    resultado = json.loads(RESULTADO_ES_PATH.read_text(encoding="utf-8"))
    recuperados = {
        item["id_proyecto"]: item["score_semantico"]
        for item in resultado["proyectos_recuperados_semanticamente"]
    }
    agregados = {
        item["id_proyecto"]: item["score_grafo"]
        for item in resultado["proyectos_agregados_por_grafo"]
    }
    compartidos = {
        item["indicador"]: item["proyectos"]
        for item in resultado["indicadores_compartidos"]
    }
    detectados_ordenados = sorted(
        resultado["indicadores_detectados"],
        key=lambda item: (item["titulo"].casefold(), -item["score_semantico"], item["id_indicador"]),
    )
    prioridades: dict[str, int] = defaultdict(int)
    filas = []
    for item in detectados_ordenados:
        prioridades[item["id_proyecto"]] += 1
        proyectos_compartidos = compartidos.get(item["indicador"], [])
        canales = []
        if item["id_proyecto"] in recuperados:
            canales.append("RECUPERADO_SEMANTICAMENTE")
        if item["id_proyecto"] in agregados:
            canales.append("AGREGADO_POR_GRAFO")
        if not canales:
            canales.append("NO_RECUPERADO_EN_LA_CONSULTA")
        filas.append({
            "Proyecto": item["titulo"],
            "Indicador detectado por Python": item["indicador"],
            "Categoría": item["categoria"],
            "Estado de evidencia": "EVIDENCIA DETECTADA — REVISIÓN HUMANA PENDIENTE",
            "Evidencia original a revisar": item["evidencia_original"],
            "Campo de origen": item["campo_origen"],
            "Score semántico": item["score_semantico"],
            "Prioridad dentro del proyecto": prioridades[item["id_proyecto"]],
            "Cómo apareció en la consulta": " + ".join(canales),
            "Indicador compartido": "SÍ" if proyectos_compartidos else "NO",
            "Otros proyectos con el indicador": " | ".join(proyectos_compartidos),
            "ID del proyecto": item["id_proyecto"],
            "Código del indicador": item["id_indicador"],
            "ID del fragmento": item["id_fragmento"],
            "Score semántico del proyecto": recuperados.get(item["id_proyecto"], ""),
            "Score de grafo": agregados.get(item["id_proyecto"], ""),
            "Nota de lectura": "El score no confirma cumplimiento; validar la evidencia antes de marcar CUMPLE.",
        })
    columnas = [
        "Proyecto", "Indicador detectado por Python", "Categoría",
        "Estado de evidencia", "Evidencia original a revisar", "Campo de origen",
        "Score semántico", "Prioridad dentro del proyecto",
        "Cómo apareció en la consulta", "Indicador compartido",
        "Otros proyectos con el indicador", "ID del proyecto",
        "Código del indicador", "ID del fragmento",
        "Score semántico del proyecto", "Score de grafo", "Nota de lectura",
    ]
    pd.DataFrame(filas, columns=columnas).to_csv(
        INFORME_CSV_PATH, index=False, encoding="utf-8-sig"
    )


def evaluar_despues_de_predecir(detectados: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    referencia = json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
    esperados = {(x["id_proyecto"], x["indicador_principal"]["indicador"]) for x in referencia}
    predichos = {(x["id_proyecto"], x["indicador"]) for x in detectados}
    tp, fp, fn = sorted(esperados & predichos), sorted(predichos - esperados), sorted(esperados - predichos)
    precision = len(tp) / (len(tp) + len(fp)) if tp or fp else 0.0
    recall = len(tp) / (len(tp) + len(fn)) if tp or fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    comparacion = {
        "predicciones_generadas_antes_de_ground_truth": True,
        "true_positives": [{"id_proyecto": p, "indicador": i} for p, i in tp],
        "false_positives": [{"id_proyecto": p, "indicador": i} for p, i in fp],
        "false_negatives": [{"id_proyecto": p, "indicador": i} for p, i in fn],
    }
    metricas = {
        "true_positives": len(tp), "false_positives": len(fp), "false_negatives": len(fn),
        "precision": round(precision, 6), "recall": round(recall, 6), "f1": round(f1, 6),
        "pares_esperados": len(esperados), "pares_predichos": len(predichos),
    }
    COMPARACION_PATH.write_text(json.dumps(comparacion, ensure_ascii=False, indent=2), encoding="utf-8")
    METRICAS_PATH.write_text(json.dumps(metricas, ensure_ascii=False, indent=2), encoding="utf-8")
    return comparacion, metricas


def main() -> None:
    parser = argparse.ArgumentParser(description="GraphRAG local multilingüe sobre 10 proyectos.")
    parser.add_argument("--reconstruir", action="store_true", help="Limpia y reconstruye Resultados/.")
    parser.add_argument("--consulta", default="¿Qué proyectos presentan evidencia relacionada con los indicadores institucionales?")
    parser.add_argument("--consulta-ingles", default="Which projects show evidence related to the institutional impact indicators?")
    parser.add_argument("--entrada", type=Path, default=SELECCION_PATH,
                        help="CSV canónico de diez documentos para esta ejecución.")
    parser.add_argument("--resultados", type=Path, default=RESULTADOS,
                        help="Directorio de resultados aislado para la fuente.")
    parser.add_argument("--tipo-fuente", choices=("PROYECTO", "ARTICULO"), default="PROYECTO",
                        help="Tipo de nodo documental que se crea en el grafo.")
    parser.add_argument("--sin-evaluacion", action="store_true",
                        help="No abre ground truth; úselo para muestras nuevas sin referencia validada.")
    args = parser.parse_args()
    try:
        configurar_ejecucion(args.entrada.resolve(), args.resultados.resolve(), args.tipo_fuente)
        preparar_resultados(args.reconstruir)
        proyectos, usadas, excluidas = cargar_proyectos()
        indicadores, hoja_catalogo, columnas_catalogo = cargar_catalogo()
        fragmentos = crear_fragmentos(proyectos)
        modelo = cargar_modelo()
        textos_proyectos = ["\n".join(f"{k}: {v}" for k, v in p["campos"].items()) for p in proyectos]
        matriz_proyectos = codificar(modelo, textos_proyectos)
        matriz_fragmentos = codificar(modelo, [f["texto"] for f in fragmentos])
        matriz_indicadores = codificar(modelo, [i["texto_embedding"] for i in indicadores])
        guardar_embeddings(proyectos, fragmentos, indicadores, matriz_proyectos, matriz_fragmentos, matriz_indicadores)
        candidatos = generar_candidatos(proyectos, fragmentos, indicadores, matriz_fragmentos, matriz_indicadores)
        detectados = consolidar_indicadores(candidatos)
        grafo = construir_grafo(proyectos, fragmentos, indicadores, candidatos)
        guardar_grafo(grafo)
        resultado_es = ejecutar_consulta(args.consulta, RESULTADO_ES_PATH, proyectos, fragmentos, matriz_proyectos, matriz_fragmentos, modelo, grafo, detectados)
        ejecutar_consulta(args.consulta_ingles, RESULTADO_EN_PATH, proyectos, fragmentos, matriz_proyectos, matriz_fragmentos, modelo, grafo, detectados)
        guardar_informe_csv_desde_resultado()
        metricas = ({"precision": float("nan"), "recall": float("nan"), "f1": float("nan")}
                    if args.sin_evaluacion else evaluar_despues_de_predecir(detectados)[1])
    except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError, RuntimeError) as error:
        print(f"Error: {error}")
        sys.exit(1)
    nodos_tipo = Counter(d["tipo"] for _, d in grafo.nodes(data=True))
    relaciones_tipo = Counter(d["tipo_relacion"] for _, _, d in grafo.edges(data=True))
    print(f"Proyectos: {len(proyectos)} | Fragmentos: {len(fragmentos)} | Catálogo: {len(indicadores)} ({hoja_catalogo})")
    print(f"Modelo: {MODEL_NAME} | Dimensión: {matriz_proyectos.shape[1]}")
    print(f"Nodos totales: {grafo.number_of_nodes()} | Relaciones totales: {grafo.number_of_edges()}")
    print(f"Nodos por tipo: {dict(sorted(nodos_tipo.items()))}")
    print(f"Relaciones por tipo: {dict(sorted(relaciones_tipo.items()))}")
    print(f"Candidatos: {len(candidatos)} | Indicadores detectados: {len(detectados)}")
    print(f"ES: {len(resultado_es['proyectos_recuperados_semanticamente'])} semánticos, {len(resultado_es['proyectos_agregados_por_grafo'])} por grafo")
    print(f"Métricas posteriores: precision={metricas['precision']:.3f}, recall={metricas['recall']:.3f}, f1={metricas['f1']:.3f}")


if __name__ == "__main__":
    main()
