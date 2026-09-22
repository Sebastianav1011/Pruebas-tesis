# Handoff — GraphRAG local definitivo con 10 proyectos

## Objetivo y estado

Esta versión sustituye el experimento que dependía de extracciones curadas por
Codex. El pipeline vigente, graphrag_10.py, usa Python para fragmentar,
generar embeddings, asociar indicadores, construir el grafo, recuperar,
exportar informe CSV y evaluar. Codex no interviene en el pipeline.

- Implementado: pipeline local sin OpenAI, sin API, sin TF-IDF y sin
  produccion-limpio.csv.
- Ejecutado: reconstrucción limpia de Resultados con los datos actuales.
- Validado: sintaxis, carga local del modelo, 10 proyectos, 48 indicadores,
  exportaciones, consultas ES/EN, visor y métricas posteriores.

## Datos y aislamiento

Entradas reales:

- 01_prueba_controlada_10_proyectos/datos/10_proyectos_indicadores_claros.csv: 10 filas y 10 id_proyecto
  únicos. Constituye toda la muestra.
- shared/datos/catalogo_indicadores.xlsx: hoja Catalogo_Indicadores, 48 indicadores,
  cuatro categorías.
- 01_prueba_controlada_10_proyectos/datos/validacion_10_proyectos.json: referencia que se abre solo después de
  escribir predicciones.

El código usa campos originales existentes: facultad, programa_creacion,
tipo_documental, investigador_docente, anio, nombre_producto, resumen,
palabras_clave, nombre_revista_libro, editorial, fuente, coautores,
afiliacion_coautores, pais_coautores y financiadores.

Antes de procesar imprime campos usados y excluidos. En la muestra actual
excluye clave_consolidacion, fila_origen_evidencia, indicador_principal,
otros_indicadores_claros, indicador_validado, categoria_indicador,
confianza_indicador, campo_evidencia, evidencia_indicador y
justificacion_indicador. También reconoce por nombre patrones de ground truth,
validación, evidencia validada, indicador esperado y respuesta esperada.

No hay ruta, importación ni lectura de
C:\Users\sebas\Workspace\Docs Tesis\DatosLimpios\Datos Limpios\produccion-limpio.csv.
La única función que abre ground truth es evaluar_despues_de_predecir(), al
final de main().

## Flujo real

    CSV de 10 proyectos
    → fragmentos trazables
    → embeddings multilingües locales
    → similitud fragmento × indicador
    → candidatos y detecciones por proyecto
    → NetworkX MultiDiGraph
    → retrieval semántico + graph retrieval
    → JSON ES/EN
    → informe CSV desde JSON ES
    → ground truth y métricas

1. cargar_proyectos() lee el CSV directamente, exige 10 IDs únicos y conserva
   solo campos permitidos.
2. crear_fragmentos() produce id_fragmento, id_proyecto, campo_origen, texto e
   idioma. Resumen se divide por párrafos/oraciones en bloques de hasta 900
   caracteres; los demás campos se conservan completos. No hay traducción.
   Todos los campos se mantienen como contexto, pero solo nombre_producto,
   resumen y palabras_clave pueden producir evidencia de indicador.
3. cargar_catalogo() elige la hoja con indicador/categoria y usa indicador,
   categoría, ámbito, tipo, forma de evaluación y unidad cuando existen.
4. cargar_modelo() carga solo desde .venv/model_cache con local_files_only.
   Si el modelo no está disponible falla; no existe fallback TF-IDF.
5. codificar() genera vectores L2-normalizados de proyectos, fragmentos e
   indicadores; guardar_embeddings() escribe las tres matrices y metadatos.
6. generar_candidatos() calcula producto punto de vectores normalizados
   (similitud coseno), conserva hasta tres indicadores por fragmento y exporta
   candidatos_indicadores_10.csv.
7. consolidar_indicadores() conserva la mayor asociación proyecto–indicador
   sobre el umbral claro. El campo score_semantico no es probabilidad.
8. construir_grafo() y guardar_grafo() generan el grafo y sus exportaciones.
9. ejecutar_consulta() realiza top-k semántico, luego expandir_grafo(), y
   escribe resultados español e inglés.
10. Evaluar abre ground truth después de ambas predicciones y escribe TP/FP/FN,
    precision, recall y F1. No ajusta ni repite nada.

## Modelo, umbrales y pesos

Modelo local: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2.
Dimensión comprobada: 384.

| Constante | Valor |
|---|---:|
| TOP_INDICADORES_POR_FRAGMENTO | 3 |
| UMBRAL_CANDIDATO | 0.42 |
| UMBRAL_INDICADOR_CLARO | 0.55 |
| TOP_K_PROYECTOS | 3 |
| TOP_FRAGMENTOS_POR_PROYECTO | 2 |
| UMBRAL_GRAFO | 0.50 |

Pesos de conexiones compartidas: indicador 1.00, palabra clave 0.70,
investigador/coautor/financiador 0.65, afiliación 0.55, programa 0.40,
facultad 0.35 y país 0.10. País no alcanza por sí solo el umbral de grafo.
Los valores se fijaron antes de abrir la referencia.

## Grafo

Se construye un networkx.MultiDiGraph. Tiene nodos PROYECTO, FRAGMENTO,
INDICADOR, CATEGORIA_INDICADOR, FACULTAD, PROGRAMA, INVESTIGADOR,
PALABRA_CLAVE, COAUTOR, AFILIACION, PAIS y FINANCIADOR cuando el CSV trae el
valor de forma explícita.

Relaciones: CONTIENE, EVIDENCIA_CANDIDATA_DE, PERTENECE_A,
PERTENECE_FACULTAD, PERTENECE_PROGRAMA, TIENE_INVESTIGADOR,
TIENE_PALABRA_CLAVE, TIENE_COAUTOR, AFILIACION_RELACIONADA,
PAIS_RELACIONADO y TIENE_FINANCIADOR. No hay proyecto → proyecto directo.

La expansión prioriza proyecto → fragmento → indicador ← fragmento ← proyecto.
Después suma metadatos compartidos con los pesos anteriores. score_grafo se
mantiene separado de score_semantico.

## Artefactos

Tras la reorganización, las ubicaciones actuales son: `grafo/fragmentos/`,
`grafo/nodos/`, `grafo/relaciones/`, `grafo/grafo_10.graphml`,
`embeddings/` y `resultados/{indicadores,consultas,evaluacion,informe}/`.
El listado siguiente conserva los nombres de artefactos de la ejecución
histórica para facilitar la comparación.

    01_prueba_controlada_10_proyectos/
    ├── fragmentos/fragmentos_10.json
    ├── embeddings/embeddings_proyectos.npy
    ├── embeddings/embeddings_fragmentos.npy
    ├── embeddings/embeddings_indicadores.npy
    ├── embeddings/metadata_embeddings.json
    ├── indicadores/candidatos_indicadores_10.csv
    ├── indicadores/indicadores_detectados_10.json
    ├── nodos/nodos_10.csv
    ├── relaciones/relaciones_10.csv
    ├── grafo/grafo_10.graphml
    ├── consultas/resultado_graphrag_10_es.json
    ├── consultas/resultado_graphrag_10_en.json
    ├── evaluacion/comparacion_ground_truth.json
    ├── evaluacion/metricas.json
    └── informe/informe_final.csv

La ejecución actual produjo 152 fragmentos, embeddings de dimensión 384,
199 candidatos, 27 asociaciones detectadas, 440 nodos y 661 relaciones.

## Consultas ejecutadas

Consulta ES: ¿Qué proyectos presentan evidencia relacionada con los indicadores
institucionales?

Top inicial ES:

1. Modelo de referencia para detección de contaminación industrial — 0.408659.
2. Monitoring air pollution… — 0.380647.
3. A nutritionally focused program… — 0.348739.

Consulta EN: Which projects show evidence related to the institutional impact
indicators?

Top inicial EN: los mismos tres proyectos, con 0.391086, 0.344426 y 0.317570.
En ambos resultados se agregaron siete proyectos por grafo. Esto es un
resultado observado, no una garantía de equivalencia bilingüe.

## Evaluación ejecutada

| Métrica | Valor |
|---|---:|
| True Positives | 0 |
| False Positives | 27 |
| False Negatives | 10 |
| Precision | 0.000000 |
| Recall | 0.000000 |
| F1 | 0.000000 |

Esta evaluación se produjo después de las predicciones y no se ajustaron
umbrales, pesos ni asociaciones.

## Informe CSV legible

Python genera 01_prueba_controlada_10_proyectos/resultados/informe/informe_final.csv después de escribir el
JSON español y antes de abrir ground truth. Lo crea leyendo solo ese JSON final.
Cada fila representa una asociación proyecto–indicador detectada e incluye
las primeras columnas en orden humano: Proyecto, Indicador detectado por
Python, Categoría, Estado de evidencia, Evidencia original a revisar, Campo de
origen y Score semántico. Luego añade prioridad, recuperación/grafo,
indicadores compartidos e identificadores técnicos.

El estado es EVIDENCIA DETECTADA — REVISIÓN HUMANA PENDIENTE. No afirma
CUMPLE porque un score semántico no demuestra cumplimiento; la columna Nota de
lectura pide validar la evidencia original.

## Ejecución

    cd "C:\Users\sebas\Workspace\Docs Tesis\Pruebas\Prueba GraphRag"
    .\.venv\Scripts\python.exe .\shared\scripts\graphrag_10.py --reconstruir
    .\.venv\Scripts\python.exe .\01_prueba_controlada_10_proyectos\scripts\mostrar_resultado_10.py
    .\.venv\Scripts\python.exe .\01_prueba_controlada_10_proyectos\scripts\mostrar_resultado_10.py --ingles

--reconstruir elimina y recrea solo la ejecución aislada bajo
01_prueba_controlada_10_proyectos/resultados/ejecucion. No modifica los
artefactos históricos reorganizados, los datos, .venv ni .venv/model_cache.

## Limitaciones observadas

- La ejecución anterior permitía evidencia desde fragmentos administrativos
  como facultad y afiliacion_coautores. La regla actual los conserva en el
  grafo, pero los excluye de la comparación fragmento–indicador. La nueva
  evaluación debe interpretarse como una versión metodológica distinta.
- La expansión es demasiado amplia: agrega los siete proyectos no iniciales y
  acumula varios indicadores compartidos en score_grafo.
- Umbrales fijos no están calibrados y no deben cambiarse con esta referencia
  sin versionar conscientemente una nueva prueba.
- La detección de idioma es heurística y no influye en el embedding.
- El CSV es una exportación automática de detecciones; la revisión humana sigue
  siendo necesaria antes de declarar que un proyecto cumple un indicador.
