# Prueba controlada - 10 proyectos

## Objetivo

Esta implementación utilizó una muestra pequeña y controlada de 10 proyectos para comprobar el funcionamiento inicial del enfoque GraphRAG antes de utilizar conjuntos de datos más amplios. Se probaron fragmentación, embeddings, detección de indicadores, construcción del grafo, recuperación, evidencias, confianza y evaluación posterior.

## Datos utilizados

- `datos/10_proyectos_indicadores_claros.csv`: muestra de 10 registros con campos de referencia usados para construir el CSV de entrada.
- `datos/validacion_10_proyectos.json`: referencia de evaluación abierta después de generar las predicciones.
- `../shared/datos/catalogo_indicadores.xlsx`: catálogo de 48 indicadores, compartido con la aproximación 02.

## Flujo

`10_proyectos_indicadores_claros.csv` → fragmentos trazables → embeddings multilingües locales → candidatos y detecciones → grafo NetworkX → retrieval semántico y por grafo → JSON ES/EN → informe CSV → comparación con ground truth y métricas.

El motor es `../shared/scripts/graphrag_10.py`. La ejecución solicitada se integró en las ubicaciones históricas de esta carpeta y reemplazó los artefactos equivalentes.

## Scripts

| Script | Función | Entrada | Salida |
|---|---|---|---|
| `../shared/scripts/graphrag_10.py` | Fragmentar, generar embeddings, detectar indicadores, construir el grafo, consultar y evaluar | `datos/10_proyectos_indicadores_claros.csv`, catálogo compartido y ground truth | Una ejecución nueva en `resultados/ejecucion/` |
| `scripts/mostrar_resultado_10.py` | Mostrar un JSON ya generado; no recalcula | `resultados/consultas/resultado_graphrag_10_es.json` o `_en.json` | Salida de consola |

## Resultados

- `embeddings/`: matrices y metadatos de embeddings conservados.
- `grafo/`: fragmentos, nodos, relaciones y `grafo_10.graphml`.
- `resultados/indicadores/`: candidatos y detecciones.
- `resultados/consultas/`: respuestas GraphRAG en español e inglés.
- `resultados/evaluacion/`: comparación con ground truth y métricas.
- `resultados/informe/informe_final.csv`: informe auditable legible.

El `HANDOFF.md` conserva el contexto técnico de la ejecución histórica.

## Limitaciones

- Fue una prueba controlada con solo 10 proyectos.
- Los umbrales y pesos son experimentales y no están calibrados como pipeline definitivo.
- El estado de evidencia requiere revisión humana; un score semántico no demuestra cumplimiento.
- No representa todavía el pipeline definitivo.

La ejecución reproducida quedó documentada en `INTERPRETACION_RESULTADOS.md`. No se generaron métricas nuevas porque falta el ground truth.
