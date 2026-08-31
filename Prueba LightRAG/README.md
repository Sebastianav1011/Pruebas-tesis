# Prueba LightRAG
## Objetivo

Evaluar si **LightRAG** puede automatizar una tarea que se hace manualmente en la
VRI: dado el resumen de un proyecto de investigación, identificar qué indicadores
institucionales de impacto le aplican, con evidencia textual real que lo justifique.

Esta es la primera de tres pruebas comparativas (RAG simple, **LightRAG**, GraphRAG)
para decidir qué arquitectura conviene para el sistema final.

## Resumen 
- **Es posible** hacer que LightRAG con un modelo local pequeño identifique varios
  indicadores por proyecto, con evidencia real en muchos casos.
- **Pero la confiabilidad es limitada:** aproximadamente la mitad de las relaciones
  proyecto-indicador encontradas no son evidencia real, sino la definición del
  indicador repetida, traducida o confundida con otra.
- Se requirieron **9 cambios de diseño** distintos para llegar a un resultado
  utilizable, partiendo de una configuración inicial que ni siquiera lograba
  completar el procesamiento por límites de la API usada al comienzo.

## Datos y alcance

| | Total disponible | Usado en la corrida final |
|---|---|---|
| Proyectos (`60_proyectos.csv`) | 60 | 5 |
| Indicadores (`catalogo_indicadores.xlsx`) | 48 | 15 (evaluados en lotes de 4) |

La muestra se redujo deliberadamente, dado que el modelo local sin GPU es lento y el objetivo
de esta prueba es comparar arquitecturas.

## Decisiones tomadas en la etapa inicial

| Etapa | Prueba | Resultado |
|---|---|---|
| 1 | **Groq API** con `openai/gpt-oss-20b` (modelo de razonamiento) | El modelo gastaba casi todo su presupuesto de tokens "pensando" antes de responder, dejando la respuesta vacía |
| 2 | Groq con `llama-3.3-70b-versatile` | El modelo ya no existía en Groq (fue retirado el 17 de junio de 2026) — error 404 |
| 3 | Groq con `openai/gpt-oss-20b` ajustado (`reasoning_effort=low`, más tokens) | Funcionó, pero se chocó con el límite de **8,000 tokens/minuto** de la cuenta gratuita |
| 4 | Se redujo la concurrencia y el tamaño de los fragmentos | Redujo los errores de minuto, pero apareció el límite de **200,000 tokens/día** — la cuenta se quedaba sin presupuesto a medio proceso, todos los días |
| 5 | **Cambio a Ollama (modelo local `qwen2.5:3b`)** | Elimina cualquier límite de tokens (corre en la propia máquina), a cambio de ser más lento sin GPU |

Con Groq, el límite diario de tokens hacía imposible completar ni siquiera 40 de los 60 proyectos en una sola sesión, sin importar cuánto se optimizara el código. Pasar a un modelo local resolvió el problema de presupuesto, pero introdujo nuevos problemas de calidad y velocidad que se fueron resolviendo uno por uno (ver siguiente sección).

## Problemas encontrados con Ollama 

| # | Problema | Decisión |
|---|---|---|
| 1 | `low_level_keywords is empty` en todas las consultas | El modo `hybrid` requiere que el modelo extraiga palabras clave en un formato JSON exacto; `qwen2.5:3b` no lo lograba de forma confiable → se cambió al modo `naive` (sin ese paso) |
| 2 | Cada consulta tardaba más de 8 minutos y se cortaba por timeout | Se redujo `chunk_top_k` de 20 a un número menor, y se ajustó el timeout global |
| 3 | El grafo de indicadores no distinguía un indicador de otro (todos fusionados bajo 7 "entidades" genéricas como `Indicator ID`, `Category`...) | El modelo confundía las *etiquetas* de los campos con las entidades reales → se cambió el texto de los indicadores a prosa natural, y finalmente a inserción estructurada directa (`ainsert_custom_kg`, sin depender de que el LLM "descubra" la estructura) |
| 4 | La búsqueda recuperaba definiciones de indicadores en vez del resumen del proyecto | El catálogo completo de indicadores iba dentro de la pregunta de búsqueda, dominándola → se separó: la búsqueda usa solo título+palabras clave del proyecto, el catálogo se pasa aparte como `user_prompt` |
| 5 | Con resúmenes largos, el título quedaba separado de las palabras clave en distintos fragmentos | Se reordenó el texto del proyecto: palabras clave antes del resumen, no después |
| 6 | Proyectos sin `eid` (no indexados en Scopus) rompían la inserción | Se creó un ID sintético consistente (`project-row-N`) usado tanto en el grafo como en los resultados |
| 7 | La evidencia devuelta era la definición del indicador, no el contenido real del proyecto | Se inyectó el texto del proyecto explícitamente en el prompt, sin depender de que la recuperación automática lo trajera |
| 8 | `LLM_TIMEOUT` no tomaba efecto | Se descubrió que se estaba fijando *después* de importar la librería `lightrag` → se movió antes de los imports |
| 9 | Solo se detectaba 1 indicador por proyecto (de 15 posibles) | Con 15 indicadores en una sola consulta, la salida del modelo (limitada a 500 tokens) apenas alcanzaba para uno → se evaluaron los indicadores **en lotes de 4** en vez de todos a la vez |

## Configuración final

- **LLM:** `qwen2.5:3b` vía Ollama, local — sin costo, sin límite de tokens, sin GPU
- **Embeddings:** `paraphrase-multilingual-MiniLM-L12-v2`, local (español e inglés)
- **Inserción de proyectos e indicadores:** `ainsert_custom_kg()` — estructura definida
  directamente, sin extracción automática de entidades vía LLM
- **Evaluación:** por proyecto, en lotes de 4 indicadores por consulta (`naive` mode),
  con el texto del proyecto inyectado explícitamente en cada consulta
- **Control de calidad automático:** cada evidencia se compara (con `difflib`, sin usar
  otro LLM) contra la definición original del indicador; si son muy parecidas, se
  marca `posible_parafraseo = True` para revisión manual

## Resultados de la corrida final

- **43 relaciones proyecto-indicador** encontradas entre los 5 proyectos (frente a solo
  4 en la corrida anterior sin lotes) — el recall mejoró claramente.
- **16 de 43 (37%)** quedaron marcadas automáticamente como `posible_parafraseo`.
- **Revisión manual de las 43 filas** encontró problemas adicionales que el detector
  automático no capturó (ver Hallazgo principal) — el porcentaje real de relaciones
  poco confiables ronda el **50%**.

## Hallazgo principal

**Los lotes pequeños mejoraron el recall (más indicadores detectados por proyecto),
pero no resolvieron la confiabilidad de la evidencia — y revelaron patrones de falla
más sutiles que el sistema de control de calidad original no detecta:**

1. **"Aprobación en bloque":** en varios lotes, el modelo marcó **los 4 indicadores del
   lote como aplicables simultáneamente**, cada uno con su propia definición como
   evidencia — un patrón de "aprobar todo" en vez de evaluar cada indicador por
   separado.
2. **Parafraseo traducido:** en el proyecto en inglés (`project-row-4`), el modelo
   tradujo la definición del indicador al inglés antes de repetirla como evidencia.
   El detector automático compara texto en español, así que **no detecta este caso**.
3. **Contaminación cruzada entre indicadores:** en al menos dos filas, la evidencia
   reportada para un indicador (ej. `SOC-01`) es en realidad la definición de **otro
   indicador distinto** del mismo lote (`SOC-02` o `CUL-02`) — el modelo confundió
   cuál definición correspondía a cuál ID.
4. **Copia del contexto completo como "evidencia":** en al menos un caso, la
   "evidencia" no es un fragmento relevante sino **el texto completo del proyecto**
   (título + palabras clave + resumen) copiado sin selección.

**Conclusión:** el detector heurístico de parafraseo (`difflib`) es un buen primer
filtro, pero tiene puntos ciegos reales (no detecta traducciones ni contaminación
cruzada entre indicadores). Un detector más robusto necesitaría comparar la evidencia
contra **todas** las definiciones del catálogo, no solo contra la del indicador
asignado, y posiblemente usar una medida de similitud que tolere cambios de idioma.

## Resultados favorables

Vale la pena anotar que **no todos los resultados fueron problemáticos**: el proyecto
sobre DIALOG+ (`2-s2.0-85142381467`) obtuvo evidencia genuina y específica en 8 de 9
indicadores detectados — citando contenido real del abstract (fases del estudio,
población objetivo, contexto de conflicto armado), no definiciones copiadas. Esto
sugiere que el enfoque **puede** funcionar bien, pero el comportamiento no es
consistente entre proyectos ni entre lotes.

## Limitaciones y pendientes

- **No se ha probado con los 48 indicadores y 60 proyectos completos** — el
  comportamiento con lotes múltiples a mayor escala es desconocido.
- **El detector de parafraseo necesita mejorarse** (ver Hallazgo principal, puntos 2 y 3).
- **Sin datos de tiempo por proyecto:** falta documentar tiempos reales, necesarios
  para el eje de "costo computacional" frente a RAG y GraphRAG.
- **No se ha determinado** si el patrón de "aprobación en bloque" depende del tamaño
  del lote (`INDICATOR_BATCH_SIZE = 4`) — podría probarse con lotes de 2 o 3 para ver
  si mejora la discriminación.

## Cómo reproducir

```bash
ollama pull qwen2.5:3b
python analyze_projects_lightrag.py
```

Los resultados se guardan en `results/resultados_indicadores.csv`. El workspace del
grafo se borra y reconstruye desde cero en cada corrida (`CLEAN_RUN = True`).

## Archivos de esta prueba

- `analyze_projects_lightrag.py` — script principal (inserción estructurada +
  evaluación por lotes)
- `data/60_proyectos.csv`, `data/catalogo_indicadores.xlsx` — datos de entrada
- `results/resultados_indicadores.csv` — resultados de la corrida final (5 proyectos /
  15 indicadores, en lotes de 4)
