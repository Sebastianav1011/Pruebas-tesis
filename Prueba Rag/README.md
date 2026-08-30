# Prueba RAG — 60 proyectos

## Qué es esta prueba

Este proyecto no es un RAG "simple" de solo búsqueda semántica — es un
**RAG con retrieval híbrido (estructurado + semántico) sobre una base
de conocimiento derivada de evaluación automática de indicadores.**

Tiene tres scripts, cada uno una etapa distinta:

1. **`rag.py`** — RAG semántico simple sobre el CSV crudo de proyectos.
   Dada una pregunta, busca los proyectos más parecidos por significado
   (embeddings) y le pide a un LLM local que responda usando solo esos
   proyectos como contexto.

2. **`evaluate_indicators.py`** — Evaluación / anotación automática
   (LLM-as-a-judge). Esto **no es RAG**: cada uno de los 60 proyectos se
   evalúa contra **cada uno** de los 48 indicadores del
   `catalogo_indicadores.xlsx` (60 × 48 = 2,880 evaluaciones, sin
   filtrar nada). El resultado es una tabla donde cada fila tiene un
   estado (`EVIDENCIA_CLARA`, `EVIDENCIA_PARCIAL`, `SIN_EVIDENCIA`,
   `NO_APLICA`), una cita de evidencia y una justificación.

3. **`rag_hybrid.py`** — El RAG propiamente dicho, sobre la tabla ya
   evaluada por el paso 2 (no sobre el CSV crudo). Combina:
   - **Filtro estructurado (exacto)**: por `ambito`, `categoria` o
     `estado` (ej. `ambito == "MEDIO_AMBIENTE"` AND
     `estado == "EVIDENCIA_CLARA"`)
   - **Filtro semántico (embeddings)**: dentro de lo que ya pasó el
     filtro estructurado

   Esto permite responder tanto preguntas abiertas ("¿qué proyectos
   hablan de sostenibilidad?") como preguntas de cumplimiento ("¿qué
   proyectos cumplen más indicadores del ámbito Medio Ambiente?").

## Estado actual

Las tres funciones/scripts están **completos y probados**. Lo que falta:

- Solo se corrió `evaluate_indicators.py` sobre **5 de los 60**
  proyectos (`evaluation_results_test5.csv`, 240 filas) — correr los 60
  completos toma ~9 horas con un modelo local en CPU, así que quedó
  pendiente para cuando se pueda dejar la compu corriendo sin que se
  suspenda.
- `rag_hybrid.py` por ahora apunta a esa muestra de 5 proyectos
  (`RESULTS_FILE` en la config), no a los 60.
- La validación de "evidencia inventada" (ver Limitaciones) detecta
  citas que no existen en el resumen, pero no detecta citas reales
  usadas para un indicador que no les corresponde.

## Estructura de carpetas

```
Prueba Rag/
├── README.md              <- este archivo
├── rag.py                 <- Paso 1: RAG semántico simple
├── evaluate_indicators.py <- Paso 2: evaluación LLM-as-judge
├── rag_hybrid.py           <- Paso 3: RAG híbrido sobre la evaluación
├── evaluation_results_test5.csv  <- resultado de evaluar 5/60 proyectos
└── data/
    ├── 60_proyectos.csv
    └── catalogo_indicadores.xlsx   <- catálogo de 48 indicadores
```

> Nota: además de estos archivos vas a ver un montón de `test_*.py`,
> `debug_*.txt` y `resultado_*.txt` sueltos en la carpeta — son
> scripts y salidas descartables que se fueron armando para probar
> cada función de a una mientras se completaban. **No son necesarios
> para correr nada**; se pueden borrar sin perder funcionalidad. Los
> tres scripts reales (`rag.py`, `evaluate_indicators.py`,
> `rag_hybrid.py`) se corren directo, como se explica abajo.

## Cómo correrlo

### Paso 1 — Instalar Ollama
Descarga e instala desde https://ollama.com (Windows/Mac/Linux).

Bajá los modelos usados en este proyecto:

```bash
ollama pull llama3.2:3b     # el que usa evaluate_indicators.py (rapido en CPU)
ollama pull deepseek-r1:7b  # el que usan rag.py y rag_hybrid.py (mas lento, mejor calidad)
```

Verificá que funciona:
```bash
ollama run llama3.2:3b "hola, funcionas?"
```

### Paso 2 — Instalar librerías de Python
```bash
pip install pandas sentence-transformers numpy requests openpyxl
```

### Paso 3 — Correr cada script
Cada uno tiene un `main()` que corre una pregunta de ejemplo de punta a
punta (podés cambiar la pregunta editando la variable `question`/
`pregunta` dentro del `main()` de cada archivo):

```bash
python rag.py                 # RAG simple sobre los 60 proyectos crudos
python evaluate_indicators.py # evalua TODOS los proyectos de data/ contra los 48 indicadores
python rag_hybrid.py          # RAG hibrido sobre evaluation_results_test5.csv
```

> ⚠️ `python evaluate_indicators.py` corre por defecto sobre los **60**
> proyectos completos (2,880 evaluaciones) — con un modelo local en
> CPU esto puede tardar varias horas. Para una prueba rápida, editá
> `main()` para usar `load_projects().head(N)` con pocos proyectos
> primero.

## Notas / decisiones de diseño

- **Modelo de embeddings multilingüe:** el dataset mezcla títulos y
  resúmenes en español, inglés y portugués. Se usa
  `paraphrase-multilingual-MiniLM-L12-v2` (no un modelo solo-inglés)
  porque las preguntas suelen hacerse en español — con un modelo
  monolingüe, proyectos relevantes en inglés pueden perder mucha
  similitud frente a la pregunta.
- **Evaluación en lotes con respaldo:** `evaluate_indicators.py` evalúa
  los indicadores en lotes de 8 (más rápido que uno por uno), pero si
  un lote falla repetidamente cae automáticamente a evaluar esos
  indicadores uno por uno (más lento, pero no rompe la corrida).
- **Validación de evidencia:** antes de aceptar un estado
  `EVIDENCIA_CLARA`/`PARCIAL`, se verifica que el texto citado
  realmente aparezca (con tolerancia a parafraseo) en el resumen del
  proyecto. Si no, se degrada a `SIN_EVIDENCIA` automáticamente y se
  guarda la cita original en la columna `evidencia_original` para
  poder auditarla. Esto existe porque, sin esta validación, el LLM
  local a veces "inventaba" evidencia citando la propia definición del
  indicador en vez del resumen real.
- Ollama corre un servidor local en `http://localhost:11434` — por eso
  los scripts no necesitan ninguna API key.
- Si tu compu es lenta, `deepseek-r1:1.5b` es más rápido pero responde
  peor (puede alucinar). `llama3.2:3b` es un buen punto medio para la
  evaluación de indicadores en lotes.
