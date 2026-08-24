from pathlib import Path
import json
import os
import subprocess

import pandas as pd


CARPETA = Path(r"C:\Users\sebas\Workspace\Docs Tesis\Pruebas\Prueba LLMS")
ARCHIVO_PROYECTOS = CARPETA / "15_proyectos.csv"
ARCHIVO_INDICADORES = CARPETA / "catalogo_indicadores.xlsx"
ARCHIVO_RESULTADOS = CARPETA / "resultados_indicadores_codex.csv"
CODIGO_ESTADOS = {"EVIDENCIA_CLARA", "EVIDENCIA_PARCIAL", "SIN_EVIDENCIA", "NO_APLICA"}


def cargar_proyectos():
    # Cargar proyectos e identificar título, resumen e identificador.
    proyectos = pd.read_csv(ARCHIVO_PROYECTOS, encoding="utf-8-sig")
    columnas = {columna.lower(): columna for columna in proyectos.columns}
    titulo = next((columnas[nombre] for nombre in ("nombre_producto", "titulo", "título", "title") if nombre in columnas), None)
    resumen = next((columnas[nombre] for nombre in ("resumen", "abstract", "descripcion", "descripción") if nombre in columnas), None)
    identificador = next((columnas[nombre] for nombre in ("id_proyecto", "eid", "doi", "handle") if nombre in columnas), None)

    if not titulo or not resumen:
        raise ValueError("No se encontró una columna de título y resumen en 15_proyectos.csv.")
    return proyectos, titulo, resumen, identificador


def cargar_indicadores():
    # Cargar el catálogo maestro.
    indicadores = pd.read_excel(ARCHIVO_INDICADORES, sheet_name="Catalogo_Indicadores").fillna("")
    return indicadores


def analizar_con_codex(titulo, resumen, indicadores):
    # Ejecutar Codex una vez por proyecto y recibir un arreglo JSON.
    catalogo = indicadores.to_dict(orient="records")
    prompt = f"""Analiza un proyecto académico usando únicamente su título y resumen.

No uses conocimiento externo. No inventes información. No asumas que la falta de información significa incumplimiento. No confundas intenciones con resultados: por ejemplo, 'busca mejorar' no demuestra que mejoró.

Evalúa todos los indicadores del catálogo. Para cada uno usa exactamente un estado:
- EVIDENCIA_CLARA: el resumen contiene evidencia directa.
- EVIDENCIA_PARCIAL: hay información relacionada pero incompleta.
- SIN_EVIDENCIA: el resumen no permite respaldar el indicador.
- NO_APLICA: el indicador claramente no corresponde con la naturaleza del proyecto.

Para indicadores cuantitativos, valor_detectado debe contener solo un número explícito del resumen; de lo contrario usa null. evidencia debe ser una cita breve y literal del resumen, o null si no hay evidencia. justificacion debe tener máximo dos frases. confianza debe ser un número entre 0 y 1.

Devuelve únicamente un arreglo JSON válido. Incluye cada id_indicador del catálogo exactamente una vez, sin texto adicional. Cada elemento debe tener:
{{"id_indicador": "...", "estado": "...", "valor_detectado": null, "evidencia": null, "justificacion": "...", "confianza": 0.0}}

TÍTULO:
{titulo}

RESUMEN:
{resumen}

CATÁLOGO DE INDICADORES:
{json.dumps(catalogo, ensure_ascii=False)}
"""
    comando = "codex.cmd" if os.name == "nt" else "codex"
    resultado = subprocess.run(
        [comando, "exec", "--ephemeral", "--skip-git-repo-check", "--color", "never", "-"],
        input=prompt,
        text=True,
        capture_output=True,
        encoding="utf-8",
    )
    if resultado.returncode != 0:
        detalle = resultado.stderr.strip() or resultado.stdout.strip()
        raise RuntimeError(f"Codex no pudo completar el análisis. Comprueba la autenticación. {detalle[-500:]}")

    texto = resultado.stdout.strip()
    if texto.startswith("```"):
        texto = texto.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    analisis = json.loads(texto)
    if not isinstance(analisis, list):
        raise ValueError("Codex no devolvió un arreglo JSON.")
    esperados = set(indicadores["id_indicador"])
    recibidos = {fila.get("id_indicador") for fila in analisis}
    if len(analisis) != len(esperados) or recibidos != esperados:
        raise ValueError("Codex no devolvió exactamente un resultado por indicador.")
    if any(fila.get("estado") not in CODIGO_ESTADOS for fila in analisis):
        raise ValueError("Codex devolvió un estado no permitido.")
    return {fila["id_indicador"]: fila for fila in analisis}


def main():
    comando = "codex.cmd" if os.name == "nt" else "codex"
    try:
        version = subprocess.run([comando, "--version"], capture_output=True, text=True, encoding="utf-8")
    except FileNotFoundError:
        print("Error: Codex CLI no está disponible.\nComprueba la instalación o el PATH.")
        return
    if version.returncode != 0:
        print("Error: Codex CLI no está disponible.\nComprueba la instalación o el PATH.")
        return

    proyectos, columna_titulo, columna_resumen, columna_id = cargar_proyectos()
    indicadores = cargar_indicadores()
    if len(proyectos) != 15:
        raise ValueError(f"Se esperaban 15 proyectos y se encontraron {len(proyectos)}.")

    print("Codex detectado.\n")
    print(f"Proyectos: {len(proyectos)}")
    print(f"Indicadores: {len(indicadores)}\n")

    resultados = []
    for numero, (_, proyecto) in enumerate(proyectos.iterrows(), 1):
        titulo = str(proyecto[columna_titulo])
        resumen = str(proyecto[columna_resumen])
        print(f"[{numero}/{len(proyectos)}] Analizando {titulo[:70]}...")
        analisis = analizar_con_codex(titulo, resumen, indicadores)
        id_proyecto = proyecto[columna_id] if columna_id and pd.notna(proyecto[columna_id]) else numero

        for _, indicador in indicadores.iterrows():
            respuesta = analisis[indicador["id_indicador"]]
            resultados.append({
                "numero_proyecto": numero,
                "id_proyecto": id_proyecto,
                "titulo": titulo,
                "id_indicador": indicador["id_indicador"],
                "categoria": indicador["categoria"],
                "ambito": indicador["ambito"],
                "indicador": indicador["indicador"],
                "tipo_indicador": indicador["tipo"],
                "forma_evaluacion": indicador["forma_evaluacion"],
                "unidad": indicador["unidad"],
                "estado": respuesta.get("estado"),
                "valor_detectado": respuesta.get("valor_detectado"),
                "evidencia": respuesta.get("evidencia"),
                "justificacion": respuesta.get("justificacion"),
                "confianza": respuesta.get("confianza"),
            })

    columnas = [
        "numero_proyecto", "id_proyecto", "titulo", "id_indicador", "categoria", "ambito", "indicador",
        "tipo_indicador", "forma_evaluacion", "unidad", "estado", "valor_detectado",
        "evidencia", "justificacion", "confianza",
    ]
    pd.DataFrame(resultados, columns=columnas).to_csv(ARCHIVO_RESULTADOS, index=False, encoding="utf-8-sig")
    comprobacion = pd.read_csv(ARCHIVO_RESULTADOS, encoding="utf-8-sig")

    print("\nAnálisis terminado.")
    print(f"Proyectos analizados: {len(proyectos)}")
    print(f"Indicadores: {len(indicadores)}")
    print(f"Resultados generados: {len(comprobacion)}")
    print(f"\nArchivo generado:\n{ARCHIVO_RESULTADOS}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"Error: {error}")
