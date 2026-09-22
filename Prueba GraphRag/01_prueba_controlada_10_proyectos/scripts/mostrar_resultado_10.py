"""Visor de resultados estructurados; no ejecuta embeddings ni modifica datos."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
CONSULTAS = BASE_DIR / "01_prueba_controlada_10_proyectos" / "resultados" / "consultas"
LINEA = "=" * 76


def imprimir_seccion(titulo: str) -> None:
    print(f"\n{titulo}\n{'-' * len(titulo)}")


def cargar(ingles: bool) -> dict:
    ruta = CONSULTAS / ("resultado_graphrag_10_en.json" if ingles else "resultado_graphrag_10_es.json")
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"No se pudo leer {ruta}: {error}") from error


def main() -> None:
    parser = argparse.ArgumentParser(description="Muestra un resultado GraphRAG ya generado.")
    parser.add_argument("--ingles", action="store_true", help="Muestra resultado_graphrag_10_en.json.")
    args = parser.parse_args()
    try:
        resultado = cargar(args.ingles)
    except RuntimeError as error:
        print(error)
        sys.exit(1)

    print(f"{LINEA}\nGRAPHRAG — {'INGLÉS' if args.ingles else 'ESPAÑOL'}\n{LINEA}")
    print(f"Consulta: {resultado.get('consulta', '')}")
    print(f"Modelo: {resultado.get('modelo_embeddings', '')}")

    imprimir_seccion("1. PROYECTOS RECUPERADOS SEMÁNTICAMENTE")
    for proyecto in resultado.get("proyectos_recuperados_semanticamente", []):
        print(f"[{proyecto.get('id_proyecto', '')}] score_semantico={proyecto.get('score_semantico', '')}")
        print(proyecto.get("titulo", ""))
        for fragmento in proyecto.get("fragmentos_relevantes", []):
            print(f"  - {fragmento.get('id_fragmento', '')} | {fragmento.get('campo_origen', '')} | score={fragmento.get('score_semantico', '')}")
            print(f"    {fragmento.get('texto', '')}")

    imprimir_seccion("2. PROYECTOS AGREGADOS POR GRAFO")
    agregados = resultado.get("proyectos_agregados_por_grafo", [])
    if not agregados:
        print("No se agregaron proyectos por grafo.")
    for proyecto in agregados:
        print(f"[{proyecto.get('id_proyecto', '')}] score_grafo={proyecto.get('score_grafo', '')}")
        print(proyecto.get("titulo", ""))
        for enlace in proyecto.get("relacionado_mediante", []):
            print(f"  - {enlace.get('tipo', '')}: {enlace.get('valor', '')} (peso={enlace.get('peso', '')})")

    imprimir_seccion("3. INDICADORES DETECTADOS")
    detectados = resultado.get("indicadores_detectados", [])
    if not detectados:
        print("No se detectaron indicadores por encima del umbral.")
    for indicador in detectados:
        print(f"[{indicador.get('id_proyecto', '')}] {indicador.get('id_indicador', '')} | score_semantico={indicador.get('score_semantico', '')}")
        print(f"{indicador.get('indicador', '')} [{indicador.get('categoria', '')}]")
        print(f"Fragmento: {indicador.get('id_fragmento', '')} | Campo: {indicador.get('campo_origen', '')}")
        print(f"Evidencia original: {indicador.get('evidencia_original', '')}")

    imprimir_seccion("4. INDICADORES COMPARTIDOS")
    compartidos = resultado.get("indicadores_compartidos", [])
    if not compartidos:
        print("No hay indicadores detectados en más de un proyecto.")
    for indicador in compartidos:
        print(f"{indicador.get('indicador', '')}: {', '.join(indicador.get('proyectos', []))}")

    imprimir_seccion("5. RESUMEN TÉCNICO")
    for clave, valor in resultado.get("resumen_tecnico", {}).items():
        print(f"{clave}: {valor}")


if __name__ == "__main__":
    main()
