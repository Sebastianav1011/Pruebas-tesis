"""Convierte dos resultados independientes de GraphRAG al Excel final.

No clasifica documentos ni asigna indicadores. Solo normaliza las asociaciones
detectadas por ``graphrag_10.py`` para las fuentes PROYECTO y ARTICULO.
La confianza combina señales ya existentes: similitud semántica, calidad del
campo recuperado y ruta DOCUMENTO -> FRAGMENTO -> INDICADOR del grafo.

El territorio proviene de ``shared/scripts/extraer_territorio.py``: se genera
una fila por departamento detectado y los municipios de ese departamento van
juntos en la misma celda.
"""
from __future__ import annotations

import json
import re
import shutil
import unicodedata
from copy import copy
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter


BASE_DIR = Path(__file__).resolve().parents[1]
DATOS = BASE_DIR / "datos"
MUESTRA_DIR = DATOS / "MuestraFinal"
RESULTADOS = BASE_DIR / "resultados"
GRAFO = BASE_DIR / "grafo"
PLANTILLA_PATH = BASE_DIR / "plantilla" / "plantilla_resultado_final_indicadores.xlsx"
SALIDA_PATH = RESULTADOS / "final" / "resultado_final_indicadores.xlsx"
UMBRAL_CONFIANZA = 0.60
SIN_INFORMACION = "SIN INFORMACIÓN"
ORIGENES_TERRITORIO = {"MENCIONADO_EN_TEXTO", "INFERIDO_AFILIACION", SIN_INFORMACION}

FUENTES = {
    fuente: {
        "entrada": MUESTRA_DIR / f"10_{fuente.lower()}_graphrag.csv",
        "resultado": RESULTADOS / fuente.lower(),
        "grafo": GRAFO / fuente.lower(),
        "territorio": RESULTADOS / fuente.lower() / "territorio" / "territorios_10.json",
    }
    for fuente in ("Proyectos", "Articulos")
}

ENCABEZADOS_PLANTILLA = [
    "proyecto_siap_id", "proyecto_titulo", "indicador_id", "dimension_indicador",
    "ambito_indicador", "indicador", "estado_cumplimiento", "parrafo_evidencia",
    "fuente_evidencia", "ubicacion_evidencia", "territorio_region", "confianza",
]
# territorio_region de la plantilla se reemplaza por los códigos DIVIPOLA.
ENCABEZADOS_TERRITORIO = ["cod_departamento", "cod_municipio", "origen_territorio", "evidencia_territorio"]
ENCABEZADOS_SALIDA = [
    "proyecto_siap_id", "proyecto_titulo", "investigador", "id_investigador",
    "cedula_investigador", "origen_registro", *ENCABEZADOS_PLANTILLA[2:10],
    *ENCABEZADOS_TERRITORIO, "confianza",
]
ENCABEZADOS_ARTICULOS = [
    "articulo_siap_id", "articulo_titulo", *ENCABEZADOS_SALIDA[2:],
]
CALIDAD_CAMPO = {"resumen": 1.00, "objetivos": 1.00, "metodologia": 0.95, "resultados_investigacion": 1.00, "justificacion": 0.90, "nombre_producto": 0.85, "palabras_clave": 0.65}


def texto(valor: Any) -> str:
    if pd.isna(valor):
        return ""
    salida = str(valor).strip()
    return "" if salida.casefold() in {"", "nan", "none", "null", "-"} else salida


def normalizar(valor: Any) -> str:
    base = unicodedata.normalize("NFKD", texto(valor)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", base).casefold().strip()


def confianza_graph_rag(item: dict[str, Any]) -> float:
    """Escala 0--1 sin tratar la similitud coseno como probabilidad."""
    similitud = max(0.0, min(1.0, float(item["score_semantico"])))
    calidad = CALIDAD_CAMPO.get(normalizar(item["campo_origen"]), 0.50)
    return round(min(0.95, similitud * (0.65 + 0.25 * calidad) + 0.12), 2)


def soporte_breve(valor: str, limite: int = 520) -> str:
    limpio = re.sub(r"\s+", " ", texto(valor)).strip()
    if len(limpio) <= limite:
        return limpio
    corte = limpio.rfind(". ", 0, limite)
    return limpio[:corte + 1 if corte >= limite // 2 else limite].rstrip()


def parrafo_evidencia(item: dict[str, Any]) -> str:
    soporte = soporte_breve(item["evidencia_original"])
    return (
        f"La evidencia recuperada en «{texto(item['campo_origen'])}» indica: “{soporte}”. "
        f"Este contenido respalda el indicador «{texto(item['indicador'])}» por su similitud "
        f"semántica de {float(item['score_semantico']):.3f}."
    )


def cargar_contexto(ruta: Path) -> dict[str, dict[str, str]]:
    tabla = pd.read_csv(ruta, encoding="utf-8-sig", low_memory=False)
    requeridas = {"id_proyecto", "nombre_producto", "origen_registro"}
    faltantes = requeridas - set(tabla.columns)
    if faltantes:
        raise ValueError(f"Faltan columnas en {ruta.name}: {', '.join(sorted(faltantes))}")
    contexto = {}
    for _, fila in tabla.iterrows():
        investigador = texto(fila.get("investigador_docente", ""))
        contexto[texto(fila["id_proyecto"])] = {
            "titulo": texto(fila["nombre_producto"]), "investigador": investigador,
            "id_investigador": texto(fila.get("id_investigador", "")) or (f"INVESTIGADOR::{normalizar(investigador)}" if investigador else ""),
            "cedula_investigador": texto(fila.get("cedula", "")),
            "origen_registro": texto(fila["origen_registro"]),
        }
    return contexto


def evidencia_territorio(territorio: dict[str, Any]) -> str:
    """Resume dónde se encontró el lugar: campo «mención», sin repetir."""
    vistas = []
    for item in territorio["evidencias"]:
        descripcion = f"{item['campo_origen']}: «{item['mencion']}»"
        if descripcion not in vistas:
            vistas.append(descripcion)
    return "; ".join(vistas)


def cargar_territorios(ruta: Path) -> dict[str, list[list[str]]]:
    """Devuelve, por documento, una lista de valores de territorio por departamento."""
    documentos = json.loads(ruta.read_text(encoding="utf-8"))["documentos"]
    salida = {}
    for id_documento, datos in documentos.items():
        origen = datos["origen_territorio"]
        if not datos["territorios"]:
            salida[id_documento] = [[SIN_INFORMACION, SIN_INFORMACION, origen, ""]]
            continue
        salida[id_documento] = [[
            territorio["cod_departamento"],
            " | ".join(m["cod_municipio"] for m in territorio["municipios"]) or SIN_INFORMACION,
            origen,
            evidencia_territorio(territorio),
        ] for territorio in datos["territorios"]]
    return salida


def cargar_detectados(directorio: Path) -> list[dict[str, Any]]:
    ruta = directorio / "consultas" / "resultado_graphrag_10_es.json"
    resultado = json.loads(ruta.read_text(encoding="utf-8"))
    detectados = resultado.get("indicadores_detectados", [])
    if not isinstance(detectados, list):
        raise ValueError(f"Salida inválida: {ruta}")
    return detectados


def fuentes_corroborantes(directorio: Path) -> dict[tuple[str, str], list[str]]:
    """Recupera solo campos con evidencia GraphRAG al umbral ya configurado."""
    ruta_detectados = directorio / "indicadores" / "indicadores_detectados_10.json"
    ruta_candidatos = directorio / "indicadores" / "candidatos_indicadores_10.csv"
    metadatos = json.loads(ruta_detectados.read_text(encoding="utf-8"))
    umbral = float(metadatos["umbral_indicador_claro"])
    candidatos = pd.read_csv(ruta_candidatos, encoding="utf-8-sig").fillna("")
    soporte: dict[tuple[str, str], list[str]] = {}
    for _, candidato in candidatos[candidatos["score_semantico"] >= umbral].iterrows():
        clave = (texto(candidato["id_proyecto"]), texto(candidato["id_indicador"]))
        campo = texto(candidato["campo_origen"])
        if campo and campo not in soporte.setdefault(clave, []):
            soporte[clave].append(campo)
    return soporte


def filas_fuente(configuracion: dict[str, Path]) -> list[list[Any]]:
    contexto = cargar_contexto(configuracion["entrada"])
    soporte = fuentes_corroborantes(configuracion["resultado"])
    territorios = cargar_territorios(configuracion["territorio"])
    filas = []
    for item in cargar_detectados(configuracion["resultado"]):
        fuente = contexto.get(texto(item["id_proyecto"]))
        if not fuente:
            continue
        confianza = confianza_graph_rag(item)
        if confianza < UMBRAL_CONFIANZA:
            continue
        fuente_principal = texto(item["campo_origen"])
        fuentes = [fuente_principal, *[
            campo for campo in soporte.get((texto(item["id_proyecto"]), texto(item["id_indicador"])), [])
            if campo != fuente_principal
        ]]
        base = [
            texto(item["id_proyecto"]), texto(item["titulo"]), fuente["investigador"], fuente["id_investigador"],
            fuente["cedula_investigador"], fuente["origen_registro"], texto(item["id_indicador"]),
            texto(item["categoria"]), texto(item.get("ambito", "")), texto(item["indicador"]),
            "CUMPLE", parrafo_evidencia(item), " + ".join(fuentes), f"Fragmento: {texto(item['id_fragmento'])}",
        ]
        if texto(item["id_proyecto"]) not in territorios:
            raise ValueError(f"Falta territorio para {item['id_proyecto']}; ejecute extraer_territorio.py.")
        # Una fila por departamento: el indicador se repite en cada territorio.
        for territorio in territorios[texto(item["id_proyecto"])]:
            filas.append([*base, *territorio, confianza])
    return sorted(filas, key=lambda fila: (fila[5], fila[0], -float(fila[-1]), fila[6], fila[14]))


def validar_relaciones_independientes() -> None:
    proyectos = pd.read_csv(FUENTES["Proyectos"]["grafo"] / "relaciones" / "relaciones_10.csv", encoding="utf-8-sig")
    articulos = pd.read_csv(FUENTES["Articulos"]["grafo"] / "relaciones" / "relaciones_10.csv", encoding="utf-8-sig")
    todas = pd.concat([proyectos, articulos], ignore_index=True)
    cruce = (
        todas["origen"].astype(str).str.startswith("PROYECTO::") & todas["destino"].astype(str).str.startswith("ARTICULO::")
    ) | (
        todas["origen"].astype(str).str.startswith("ARTICULO::") & todas["destino"].astype(str).str.startswith("PROYECTO::")
    )
    if cruce.any():
        raise ValueError("Se detectó una relación directa no permitida entre proyecto y artículo.")


def preparar_hoja(hoja, nombre: str, filas: list[list[Any]], encabezados: list[str]) -> None:
    if [celda.value for celda in hoja[1][:12]] != ENCABEZADOS_PLANTILLA:
        raise ValueError("La plantilla no coincide con el contrato de encabezados.")
    estilos = {celda.value: (copy(celda._style), copy(celda.alignment)) for celda in hoja[1][:12]}
    for columna, encabezado in enumerate(encabezados, start=1):
        if encabezado in {"investigador", "articulo_titulo"}:
            referencia = "proyecto_titulo"
        elif encabezado in ENCABEZADOS_TERRITORIO:
            referencia = "territorio_region"
        else:
            referencia = encabezado if encabezado in estilos else "proyecto_siap_id"
        celda = hoja.cell(1, columna)
        celda.value = encabezado
        celda._style, celda.alignment = estilos[referencia]
    for columna, ancho in {"C": 32, "D": 42, "E": 20, "F": 16, "L": 54, "O": 18, "P": 24, "Q": 22, "R": 40}.items():
        hoja.column_dimensions[columna].width = ancho
    columna_confianza = len(encabezados)
    for indice_fila, fila in enumerate(filas, start=2):
        for columna, valor in enumerate(fila, start=1):
            hoja.cell(indice_fila, columna, valor).alignment = Alignment(vertical="top", wrap_text=True)
        hoja.cell(indice_fila, columna_confianza).number_format = "0.00"
        hoja.row_dimensions[indice_fila].height = 78
    hoja.title = nombre
    hoja.freeze_panes = "A2"
    hoja.auto_filter.ref = f"A1:{get_column_letter(columna_confianza)}{max(2, len(filas) + 1)}"
    hoja.sheet_view.showGridLines = False


def verificar_archivo(salida: Path) -> dict[str, int]:
    libro = load_workbook(salida, data_only=False)
    if libro.sheetnames != ["Proyectos", "Articulos"]:
        raise ValueError(f"Pestañas inesperadas: {libro.sheetnames}")
    conteos = {}
    for hoja, encabezados in ((libro["Proyectos"], ENCABEZADOS_SALIDA), (libro["Articulos"], ENCABEZADOS_ARTICULOS)):
        if [celda.value for celda in hoja[1][:len(encabezados)]] != encabezados:
            raise ValueError(f"Encabezados inválidos en {hoja.title}")
        filas = [fila for fila in hoja.iter_rows(min_row=2, max_col=len(encabezados), values_only=True) if any(fila)]
        for fila in filas:
            if (fila[5] not in {"REAL", "SIMULADO"} or fila[10] != "CUMPLE" or not fila[11]
                    or not fila[12] or "graphrag" in str(fila[12]).casefold()
                    or "revision" in " ".join(str(valor) for valor in fila).casefold()
                    or not fila[14] or not fila[15] or fila[16] not in ORIGENES_TERRITORIO
                    or not 0 <= float(fila[-1]) <= 1):
                raise ValueError(f"Fila inválida en {hoja.title}")
        conteos[hoja.title] = len(filas)
    return conteos


def main() -> None:
    requeridos = [PLANTILLA_PATH]
    for fuente in FUENTES.values():
        requeridos.extend([fuente["entrada"], fuente["resultado"] / "consultas" / "resultado_graphrag_10_es.json",
                           fuente["grafo"] / "relaciones" / "relaciones_10.csv", fuente["territorio"]])
    faltantes = [str(ruta) for ruta in requeridos if not ruta.exists()]
    if faltantes:
        raise FileNotFoundError("Faltan entradas GraphRAG: " + ", ".join(faltantes))
    validar_relaciones_independientes()
    filas_proyectos, filas_articulos = filas_fuente(FUENTES["Proyectos"]), filas_fuente(FUENTES["Articulos"])
    if not filas_proyectos or not filas_articulos:
        raise ValueError("No hay relaciones con confianza igual o superior a 0.60 para exportar.")
    SALIDA_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PLANTILLA_PATH, SALIDA_PATH)
    libro = load_workbook(SALIDA_PATH)
    hoja_proyectos = libro.active
    hoja_articulos = libro.copy_worksheet(hoja_proyectos)
    preparar_hoja(hoja_proyectos, "Proyectos", filas_proyectos, ENCABEZADOS_SALIDA)
    preparar_hoja(hoja_articulos, "Articulos", filas_articulos, ENCABEZADOS_ARTICULOS)
    libro.save(SALIDA_PATH)
    conteos = verificar_archivo(SALIDA_PATH)
    print(f"Archivo: {SALIDA_PATH.relative_to(BASE_DIR)}")
    print(f"Filas: Proyectos={conteos['Proyectos']} | Articulos={conteos['Articulos']}")


if __name__ == "__main__":
    main()
