# Interpretación de la ejecución reproducida

## Ejecución

- Entrada: `../../datos/10_proyectos_indicadores_claros.csv`.
- Catálogo: `../../../../shared/datos/catalogo_indicadores.xlsx`.
- Modelo: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- Dimensión de embeddings: 384.
- La ejecución se hizo el 22 de septiembre de 2026 en `resultados/ejecucion/`.
- Se usó `--sin-evaluacion` porque no está disponible `datos/validacion_10_proyectos.json` en el workspace actual.

## Resumen técnico

El pipeline procesó 10 proyectos, produjo 152 fragmentos, 48 indicadores de catálogo, 99 candidatos y 11 indicadores detectados. El grafo contiene 440 nodos y 561 relaciones.

La recuperación semántica inicial devolvió tres proyectos. La expansión por grafo añadió siete proyectos más. Esto significa que la consulta terminó mostrando evidencia relacionada en los 10 proyectos, aunque no todos fueron recuperados por similitud semántica directa.

## Hallazgos principales

1. El resultado más sólido aparece en el artículo sobre una plataforma de salud mental juvenil: el texto contiene codiseño, talleres participativos y pruebas de usabilidad con usuarios. El sistema lo vinculó con `TEC-02` con score 0.628831.
2. El artículo sobre contaminación industrial fue recuperado semánticamente y produjo tres asociaciones: `DIV-04` (0.619431), `TEC-01` (0.601599) y `TEC-05` (0.590465). La evidencia menciona un prototipo, publicación/visualización de datos y aplicación en una empresa, pero requiere revisión humana para confirmar cada indicador.
3. El artículo sobre biodiversidad produjo `AMB-01` con score 0.678049. La señal procede de palabras clave, por lo que es una detección útil para revisión, no una prueba suficiente por sí misma.
4. El programa nutricional para adultos mayores produjo `SAL-03` con score 0.571826 y evidencia en el resumen sobre intervención nutricional, educación y seguimiento.
5. Varios resultados proceden de palabras clave (`SAL-06`, `SOC-02`, `SAL-01`, `DIV-05`, `AMB-01`). Son candidatos razonables, pero tienen menor trazabilidad textual que las detecciones sustentadas por un párrafo de resumen.
6. `SAL-06` aparece compartido entre dos proyectos. Esto muestra que el grafo está propagando conexiones entre documentos, pero también exige verificar que el indicador no se esté generalizando demasiado por similitud o entidades compartidas.

## Interpretación como LLM

La ejecución demuestra que el pipeline funciona técnicamente: carga el catálogo, crea embeddings, construye el grafo, recupera documentos y genera evidencias trazables. Sin embargo, el resultado debe interpretarse como una lista priorizada de candidatos, no como una clasificación definitiva de cumplimiento.

La principal debilidad observable es la expansión por grafo: los scores de grafo son altos y agregan siete proyectos que no estaban entre los tres primeros semánticos. Esa expansión puede ser útil para explorar relaciones, pero puede introducir falsos positivos si una palabra clave, investigador, afiliación u otra entidad compartida conecta proyectos que no tienen evidencia directa del indicador.

Las detecciones basadas en `resumen` son las más apropiadas para revisión humana. Las basadas solo en `palabras_clave` deben considerarse señales débiles hasta comprobar el texto completo del proyecto. El CSV marca correctamente todos los casos como `EVIDENCIA DETECTADA — REVISIÓN HUMANA PENDIENTE`.

## Evaluación pendiente

No se calcularon precisión, recall ni F1 porque falta `validacion_10_proyectos.json`. No se debe interpretar `precision=nan`, `recall=nan` o `f1=nan` como buen o mal desempeño: significa que la evaluación no se ejecutó.

## Archivos principales

- Informe reproducido: `informe/informe_final.csv`.
- Copia visible en la carpeta histórica: `../../resultados/informe/informe_final_reproducido.csv`.
- Consulta en español: `consultas/resultado_graphrag_10_es.json`.
- Consulta en inglés: `consultas/resultado_graphrag_10_en.json`.
- Grafo: `grafo/grafo_10.graphml`.
- Candidatos: `indicadores/candidatos_indicadores_10.csv`.
