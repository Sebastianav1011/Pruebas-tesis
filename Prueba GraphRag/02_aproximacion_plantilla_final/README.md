# Aproximación orientada a la plantilla final

## Objetivo

Esta implementación representa una evolución respecto a la prueba controlada. El objetivo ya no era solamente comprobar que GraphRAG funcionara, sino acercar su salida al formato esperado del proyecto, separando fuentes de Proyectos y Artículos y exportando un libro final con evidencias y confianza.

## Diferencia con la prueba de 10 proyectos

- **Prueba 01:** validación controlada del funcionamiento sobre una muestra anotada de 10 proyectos.
- **Prueba 02:** aproximación orientada al resultado final requerido, con fuentes independientes y una plantilla de salida.

## Datos utilizados

- `datos/MuestraFinal/5_proyectos_reales.csv` y `5_articulos_reales.csv`: subconjuntos reales seleccionados.
- `datos/MuestraFinal/10_proyectos_graphrag.csv` y `10_articulos_graphrag.csv`: entradas canónicas de las dos ejecuciones.
- `../shared/datos/catalogo_indicadores.xlsx`: catálogo utilizado por el motor compartido.

Los CSV de `MuestraFinal` contienen nombres, identificadores de investigadores y, en algunos casos, campos `cedula`/`documento`. Son datos restringidos para revisión antes de publicar en GitHub; no deben subirse sin autorización o anonimización.

## Flujo

Fuentes externas → `preparar_muestra_final.py` → muestras canónicas de Proyectos y Artículos → dos ejecuciones del motor GraphRAG compartido → embeddings, fragmentos y grafos separados por fuente → consultas ES/EN e informes → `generar_resultado_final.py` → libro final basado en la plantilla.

Las fuentes no se relacionan directamente entre sí; el investigador funciona como entidad común cuando la fuente lo aporta.

## Plantilla

La plantilla relevante es `plantilla/plantilla_resultado_final_indicadores.xlsx`. Su ubicación anterior era `Datos/plantilla_resultado_final_indicadores.xlsx`; ahora es la entrada de `scripts/generar_resultado_final.py`, no un resultado parcial. Define las columnas base de la salida: proyecto, indicador, dimensión/ámbito, estado, párrafo de evidencia, fuente/ubicación, territorio y confianza. El resultado generado se conserva en `resultados/final/resultado_final_indicadores.xlsx`.

## Scripts

| Script | Función | Entrada | Salida |
|---|---|---|---|
| `scripts/preparar_muestra_final.py` | Seleccionar 5 registros reales por fuente, añadir registros demo y crear entradas canónicas | Fuentes externas indicadas en el script | `datos/MuestraFinal/` |
| `../shared/scripts/graphrag_10.py` | Ejecutar GraphRAG independientemente para cada fuente | `10_proyectos_graphrag.csv` o `10_articulos_graphrag.csv`, catálogo compartido | Nueva ejecución aislada indicada por `--resultados` |
| `scripts/generar_resultado_final.py` | Leer resultados existentes, validar relaciones independientes y llenar la plantilla | `resultados/`, `grafo/` y `plantilla/` | `resultados/final/resultado_final_indicadores.xlsx` |

## Resultados relevantes

- `grafo/proyectos/` y `grafo/articulos/`: fragmentos, nodos, relaciones y GraphML por fuente.
- `embeddings/proyectos/` y `embeddings/articulos/`: embeddings conservados por ejecución.
- `resultados/proyectos/` y `resultados/articulos/`: indicadores, consultas e informes.
- `resultados/final/resultado_final_indicadores.xlsx`: salida final histórica relevante para entender esta aproximación.

## Estado

Sigue siendo una aproximación experimental. No debe confundirse con el GraphRAG definitivo que se está diseñando actualmente.
