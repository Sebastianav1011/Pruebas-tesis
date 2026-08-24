# Prueba LLMs: análisis de indicadores con Codex

Esta prueba analiza una muestra fija de 15 proyectos con Codex CLI. Para cada proyecto, el script usa únicamente el título y el resumen como contexto y evalúa la batería institucional de indicadores.

```text
15 proyectos -> título y resumen -> catálogo de indicadores -> Codex CLI -> CSV de resultados
```

## Archivos

- `15_proyectos.csv`: muestra de los 15 proyectos.
- `catalogo_indicadores.xlsx`: catálogo institucional estructurado; la hoja usada es `Catalogo_Indicadores`.
- `analizar_proyectos_codex.py`: ejecuta una llamada a Codex por proyecto.
- `resultados_indicadores_codex.csv`: resultado de una ejecución completa.

## Requisitos

- Python 3
- `pandas`
- `openpyxl`
- Codex CLI instalado y autenticado

```powershell
python -m pip install pandas openpyxl
codex --version
```

## Ejecución

Desde esta carpeta:

```powershell
python analizar_proyectos_codex.py
```

No se requiere copiar prompts ni ejecutar Codex manualmente. El script carga los archivos, invoca `codex exec` secuencialmente para los 15 proyectos y guarda el resultado en un único CSV.

## Criterio de análisis

El resumen es la única fuente de evidencia. Cada fila del CSV representa un proyecto evaluado frente a un indicador y usa uno de estos estados:

```text
EVIDENCIA_CLARA
EVIDENCIA_PARCIAL
SIN_EVIDENCIA
NO_APLICA
```

La ausencia de evidencia en el resumen no significa incumplimiento. El CSV conserva los datos base necesarios para analizar posteriormente la frecuencia de los indicadores por estado, categoría, ámbito y proyecto.
