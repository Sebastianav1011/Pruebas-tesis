"""Prepara la entrada controlada de dos fuentes para el GraphRAG existente.

Los cinco registros reales de cada fuente se copian sin modificar desde los
CSV institucionales. Los cinco DEMO se almacenan únicamente dentro de
Datos/MuestraFinal y se describen como documentos académicos, sin asignarles
indicadores: la asociación sigue siendo calculada por GraphRAG.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
MUESTRA_DIR = BASE_DIR / "datos" / "MuestraFinal"
PROYECTOS_ORIGEN = Path(r"C:\Users\sebas\Workspace\Docs Tesis\DatosLimpios\Datos Limpios\descriptores-limpio.csv")
ARTICULOS_ORIGEN = Path(r"C:\Users\sebas\Workspace\Docs Tesis\DatosLimpios\Datos Limpios\produccion-limpio.csv")
MIEMBROS_ORIGEN = Path(r"C:\Users\sebas\Workspace\Docs Tesis\DatosLimpios\Datos Limpios\miembros-doc-limpio.csv")


def texto(valor: Any) -> str:
    if pd.isna(valor):
        return ""
    salida = str(valor).strip()
    return "" if salida.casefold() in {"", "nan", "none", "null", "-"} else salida


def longitud(tabla: pd.DataFrame, columnas: list[str]) -> pd.Series:
    return sum(tabla[columna].map(texto).str.len() for columna in columnas)


def seleccionar_variados(tabla: pd.DataFrame, id_columna: str, grupo_columna: str, puntaje: pd.Series) -> pd.DataFrame:
    """Elige los registros más completos, priorizando grupos distintos."""
    ordenada = tabla.assign(_puntaje=puntaje).sort_values("_puntaje", ascending=False).drop_duplicates(id_columna)
    seleccion, grupos = [], set()
    for indice, fila in ordenada.iterrows():
        grupo = texto(fila.get(grupo_columna, "")) or "SIN_GRUPO"
        if grupo not in grupos:
            seleccion.append(indice)
            grupos.add(grupo)
        if len(seleccion) == 5:
            break
    if len(seleccion) < 5:
        seleccion.extend(indice for indice in ordenada.index if indice not in seleccion)
    return tabla.loc[seleccion[:5]].copy()


def proyectos_demo() -> list[dict[str, str]]:
    return [
        {"id_proyecto": "PROY-DEMO-001", "nombre_producto": "Monitoreo comunitario de calidad del agua en veredas rurales", "investigador_docente": "Investigadora Demo, Laura", "cedula": "DEMO-INV-001", "tipo_documental": "PROYECTO", "resumen": "El estudio desarrolla una red de monitoreo de calidad del agua junto con juntas comunitarias rurales. Las familias participan en talleres de diagnóstico, toman muestras y validan un tablero abierto para reportar resultados a las autoridades locales.", "objetivos": "Fortalecer capacidades comunitarias para vigilar fuentes hídricas y comunicar riesgos sanitarios.", "metodologia": "Investigación participativa con talleres, muestreo colaborativo y validación de prototipos con líderes veredales.", "resultados_investigacion": "Se entregarán protocolos comprensibles, datos abiertos y jornadas de devolución de resultados.", "palabras_clave": "agua; participación comunitaria; datos abiertos; salud ambiental", "gran_area": "CIENCIAS AGRÍCOLAS", "area_conocimiento": "CIENCIAS AMBIENTALES", "objetivo_socioeconomico": "PROTECCIÓN AMBIENTAL", "origen_registro": "SIMULADO"},
        {"id_proyecto": "PROY-DEMO-002", "nombre_producto": "Acompañamiento digital para adherencia terapéutica en jóvenes", "investigador_docente": "Investigador Demo, Mateo", "cedula": "DEMO-INV-002", "tipo_documental": "PROYECTO", "resumen": "El proyecto co-diseña con jóvenes, profesionales de salud y organizaciones de pacientes una herramienta digital para acompañar tratamientos crónicos. Se realizarán pruebas de usabilidad, sesiones educativas y seguimiento de resultados de bienestar.", "objetivos": "Mejorar la comunicación entre jóvenes y equipos de atención mediante una solución digital accesible.", "metodologia": "Diseño centrado en usuarios, entrevistas, pruebas piloto y evaluación de experiencia de uso.", "resultados_investigacion": "Se espera una guía de implementación y materiales educativos para instituciones de salud.", "palabras_clave": "salud digital; jóvenes; adherencia terapéutica; co-diseño", "gran_area": "CIENCIAS MÉDICAS Y DE LA SALUD", "area_conocimiento": "CIENCIAS DE LA SALUD", "objetivo_socioeconomico": "SALUD", "origen_registro": "SIMULADO"},
        {"id_proyecto": "PROY-DEMO-003", "nombre_producto": "Laboratorio de economía circular para aprovechamiento de residuos orgánicos", "investigador_docente": "Investigadora Demo, Camila", "cedula": "DEMO-INV-003", "tipo_documental": "PROYECTO", "resumen": "Investigadores, asociaciones de recicladores y pequeños productores experimentan procesos de aprovechamiento de residuos orgánicos. El laboratorio documenta costos, prototipos y oportunidades de comercialización local.", "objetivos": "Construir alternativas productivas circulares con organizaciones de recicladores.", "metodologia": "Laboratorios colaborativos, prototipado, análisis de cadena de valor y evaluación con usuarios.", "resultados_investigacion": "Se publicarán manuales de proceso y una ruta de transferencia para emprendimientos locales.", "palabras_clave": "economía circular; residuos; emprendimiento; transferencia tecnológica", "gran_area": "INGENIERÍA Y TECNOLOGÍA", "area_conocimiento": "INGENIERÍA AMBIENTAL", "objetivo_socioeconomico": "DESARROLLO ECONÓMICO", "origen_registro": "SIMULADO"},
        {"id_proyecto": "PROY-DEMO-004", "nombre_producto": "Archivo vivo de memorias y prácticas culturales barriales", "investigador_docente": "Investigador Demo, Julián", "cedula": "DEMO-INV-004", "tipo_documental": "PROYECTO", "resumen": "El proyecto crea con colectivos culturales y escuelas un archivo digital de memoria local. Los participantes registran relatos, seleccionan materiales y diseñan una exposición itinerante para compartir saberes intergeneracionales.", "objetivos": "Preservar y divulgar prácticas culturales mediante procesos de apropiación colectiva.", "metodologia": "Etnografía colaborativa, talleres de memoria, curaduría participativa y producción de contenidos abiertos.", "resultados_investigacion": "Se dispondrá de un repositorio abierto y materiales pedagógicos para las escuelas participantes.", "palabras_clave": "cultura; memoria; apropiación social; divulgación", "gran_area": "HUMANIDADES", "area_conocimiento": "ARTE", "objetivo_socioeconomico": "CULTURA", "origen_registro": "SIMULADO"},
        {"id_proyecto": "PROY-DEMO-005", "nombre_producto": "Movilidad sostenible y decisión pública basada en evidencia", "investigador_docente": "Investigadora Demo, Sara", "cedula": "DEMO-INV-005", "tipo_documental": "PROYECTO", "resumen": "El equipo analiza patrones de movilidad y calidad del aire con una alcaldía, empresas de transporte y ciudadanía. Los hallazgos se discuten en mesas técnicas para diseñar medidas de movilidad activa y reducir emisiones.", "objetivos": "Aportar evidencia para decisiones públicas de movilidad y ambiente urbano.", "metodologia": "Análisis de datos, talleres intersectoriales, evaluación de escenarios y validación de recomendaciones.", "resultados_investigacion": "Se entregarán tableros de indicadores, recomendaciones técnicas y materiales de divulgación ciudadana.", "palabras_clave": "movilidad sostenible; política pública; calidad del aire; colaboración", "gran_area": "CIENCIAS SOCIALES", "area_conocimiento": "POLÍTICA PÚBLICA", "objetivo_socioeconomico": "TRANSPORTE Y MEDIO AMBIENTE", "origen_registro": "SIMULADO"},
    ]


def articulos_demo() -> list[dict[str, str]]:
    return [
        {"id_proyecto": "ART-DEMO-001", "nombre_producto": "Participatory evaluation of a community telehealth program for rural caregivers", "investigador_docente": "Autora Demo, Elena", "cedula": "DEMO-ART-001", "tipo_documental": "ARTICLE", "resumen": "This article reports a participatory evaluation of a telehealth program with rural caregivers, community leaders and primary care teams. External academic and non-academic actors participated actively in defining the problem, implementing the service and evaluating the results. Workshops identified needs, tested the service and discussed changes in access to support.", "palabras_clave": "telehealth; caregivers; active participation; rural health", "anio": "2026", "doi": "10.0000/demo.art.001", "nombre_revista_libro": "Demo Journal of Community Health", "fuente": "DEMO", "coautores": "Autor Demo, Andrés", "afiliacion_coautores": "Universidad Demo", "pais_coautores": "Colombia", "origen_registro": "SIMULADO"},
        {"id_proyecto": "ART-DEMO-002", "nombre_producto": "Open sensors and citizen science for urban air quality communication", "investigador_docente": "Autor Demo, Nicolás", "cedula": "DEMO-ART-002", "tipo_documental": "ARTICLE", "resumen": "The study documents an open sensor network developed with schools and neighborhood organizations to measure urban air quality. Participants interpreted results, created and used accessible communication materials for non-specialized publics, and proposed local mitigation actions.", "palabras_clave": "citizen science; open sensors; air quality; public communication", "anio": "2026", "doi": "10.0000/demo.art.002", "nombre_revista_libro": "Demo Environmental Technology Review", "fuente": "DEMO", "coautores": "Autora Demo, Valeria", "afiliacion_coautores": "Universidad Demo", "pais_coautores": "Colombia", "origen_registro": "SIMULADO"},
        {"id_proyecto": "ART-DEMO-003", "nombre_producto": "Cultural memory workshops and digital storytelling with displaced youth", "investigador_docente": "Autora Demo, Manuela", "cedula": "DEMO-ART-003", "tipo_documental": "ARTICLE", "resumen": "This article presents digital storytelling workshops conducted with displaced youth and cultural organizations. Young participants curated narratives, preserved and revitalized cultural memory and community identity, produced audiovisual materials and shared them in public exhibitions.", "palabras_clave": "cultural memory; community identity; heritage; digital storytelling", "anio": "2026", "doi": "10.0000/demo.art.003", "nombre_revista_libro": "Demo Culture and Society", "fuente": "DEMO", "coautores": "Autor Demo, Felipe", "afiliacion_coautores": "Universidad Demo", "pais_coautores": "Colombia", "origen_registro": "SIMULADO"},
        {"id_proyecto": "ART-DEMO-004", "nombre_producto": "Circular bioeconomy pathways for farmer cooperatives", "investigador_docente": "Autor Demo, Tomás", "cedula": "DEMO-ART-004", "tipo_documental": "ARTICLE", "resumen": "Researchers and farmer cooperatives assessed circular bioeconomy pathways for agricultural residues. The study tested value-added prototypes that generated additional income through implementation and commercialization, analyzed local markets and co-produced a transfer guide for cooperative enterprises.", "palabras_clave": "bioeconomy; cooperatives; additional income; value chain", "anio": "2026", "doi": "10.0000/demo.art.004", "nombre_revista_libro": "Demo Journal of Sustainable Economy", "fuente": "DEMO", "coautores": "Autora Demo, Diana", "afiliacion_coautores": "Universidad Demo", "pais_coautores": "Colombia", "origen_registro": "SIMULADO"},
        {"id_proyecto": "ART-DEMO-005", "nombre_producto": "Evidence briefs for local climate adaptation policy", "investigador_docente": "Autora Demo, Paula", "cedula": "DEMO-ART-005", "tipo_documental": "ARTICLE", "resumen": "The article analyzes the co-production of evidence briefs with local government, environmental groups and residents to support climate adaptation decisions. Findings informed a local policy program, were translated into accessible materials and discussed in public policy roundtables.", "palabras_clave": "climate adaptation; policy program; evidence briefs; public policy", "anio": "2026", "doi": "10.0000/demo.art.005", "nombre_revista_libro": "Demo Public Policy Review", "fuente": "DEMO", "coautores": "Autor Demo, Sergio", "afiliacion_coautores": "Universidad Demo", "pais_coautores": "Colombia", "origen_registro": "SIMULADO"},
    ]


def enriquecer_articulos_demo(registros: list[dict[str, str]]) -> list[dict[str, str]]:
    """Añade objetivos académicos demostrativos, no etiquetas de indicador."""
    objetivos = {
        "ART-DEMO-001": "Documentar la participación de organizaciones comunitarias y equipos de salud durante la formulación, ejecución y evaluación del servicio.",
        "ART-DEMO-002": "Diseñar y utilizar productos de comunicación del conocimiento para públicos no especializados.",
        "ART-DEMO-003": "Fortalecer la preservación y revitalización de la memoria e identidad cultural en la comunidad participante.",
        "ART-DEMO-004": "Analizar ingresos adicionales derivados de la implementación y comercialización de procesos productivos mejorados.",
        "ART-DEMO-005": "Examinar programas públicos implementados a partir de los hallazgos y recomendaciones del estudio.",
    }
    for registro in registros:
        registro["objetivos"] = objetivos[registro["id_proyecto"]]
    return registros


def main() -> None:
    MUESTRA_DIR.mkdir(parents=True, exist_ok=True)
    proyectos = pd.read_csv(PROYECTOS_ORIGEN, encoding="utf-8-sig", low_memory=False)
    articulos = pd.read_csv(ARTICULOS_ORIGEN, encoding="utf-8-sig", low_memory=False)
    miembros = pd.read_csv(MIEMBROS_ORIGEN, encoding="utf-8-sig", low_memory=False)

    puntaje_proyectos = longitud(proyectos, ["resumen", "objetivos", "metodologia", "resultados_investigacion", "palabras_clave"])
    elegibles_proyectos = proyectos[(proyectos["id_actividad"].map(texto) != "") & (proyectos["convocatoria_nombre"].map(texto) != "") & (puntaje_proyectos >= 500)]
    reales_proyectos = seleccionar_variados(elegibles_proyectos, "id_actividad", "gran_area", puntaje_proyectos.loc[elegibles_proyectos.index])
    reales_proyectos.to_csv(MUESTRA_DIR / "5_proyectos_reales.csv", index=False, encoding="utf-8-sig")
    ids_reales = set(reales_proyectos["id_actividad"].map(texto))
    responsables = miembros[
        miembros["id_actividad"].map(texto).isin(ids_reales)
        & miembros["responsable"].map(texto).str.upper().eq("SÍ")
    ].drop_duplicates("id_actividad")
    responsables_por_actividad = {
        texto(fila["id_actividad"]): {
            "investigador_docente": texto(fila["nombre_completo"]),
            "id_investigador": texto(fila["id_empleado"]),
            "cedula": texto(fila["documento"]),
        }
        for _, fila in responsables.iterrows()
    }

    puntaje_articulos = longitud(articulos, ["resumen", "palabras_clave"])
    tipos_articulo = articulos["tipo_documental"].map(texto).str.upper().eq("ARTICLE")
    elegibles_articulos = articulos[(articulos["eid"].map(texto) != "") & (articulos["nombre_producto"].map(texto) != "") & tipos_articulo & (puntaje_articulos >= 500)]
    reales_articulos = seleccionar_variados(elegibles_articulos, "eid", "facultad", puntaje_articulos.loc[elegibles_articulos.index])
    reales_articulos.to_csv(MUESTRA_DIR / "5_articulos_reales.csv", index=False, encoding="utf-8-sig")

    proyectos_canonicos = []
    for _, fila in reales_proyectos.iterrows():
        miembro = responsables_por_actividad.get(texto(fila["id_actividad"]), {})
        proyectos_canonicos.append({
            "id_proyecto": texto(fila["id_actividad"]), "nombre_producto": texto(fila["convocatoria_nombre"]),
            "resumen": texto(fila["resumen"]), "objetivos": texto(fila["objetivos"]),
            "metodologia": texto(fila["metodologia"]), "resultados_investigacion": texto(fila["resultados_investigacion"]),
            "justificacion": texto(fila["justificacion"]), "palabras_clave": texto(fila["palabras_clave"]),
            "gran_area": texto(fila["gran_area"]), "area_conocimiento": texto(fila["area_conocimiento"]),
            "objetivo_socioeconomico": texto(fila["objetivo_socioeconomico"]),
            "investigador_docente": miembro.get("investigador_docente", ""),
            "id_investigador": miembro.get("id_investigador", ""), "cedula": miembro.get("cedula", ""),
            "tipo_documental": "PROYECTO", "origen_registro": "REAL",
        })
    proyectos_canonicos.extend(proyectos_demo())
    pd.DataFrame(proyectos_canonicos).to_csv(MUESTRA_DIR / "10_proyectos_graphrag.csv", index=False, encoding="utf-8-sig")

    columnas_articulo = ["cedula", "investigador_docente", "tipo_documental", "anio", "resumen", "palabras_clave", "objetivos", "doi", "nombre_revista_libro", "fuente", "coautores", "afiliacion_coautores", "pais_coautores", "facultad", "programa_creacion", "editorial", "financiadores"]
    articulos_canonicos = []
    for _, fila in reales_articulos.iterrows():
        registro = {columna: texto(fila.get(columna, "")) for columna in columnas_articulo}
        registro.update({"id_proyecto": texto(fila["eid"]), "nombre_producto": texto(fila["nombre_producto"]), "origen_registro": "REAL"})
        articulos_canonicos.append(registro)
    articulos_canonicos.extend(enriquecer_articulos_demo(articulos_demo()))
    pd.DataFrame(articulos_canonicos).to_csv(MUESTRA_DIR / "10_articulos_graphrag.csv", index=False, encoding="utf-8-sig")
    print(f"Muestra creada en {MUESTRA_DIR}")
    print(f"Proyectos reales: {len(reales_proyectos)} | Artículos reales: {len(reales_articulos)}")


if __name__ == "__main__":
    main()
