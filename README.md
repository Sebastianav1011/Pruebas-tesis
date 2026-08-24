# Pruebas — Trabajo de Grado

Repositorio para centralizar las pruebas, scripts y resultados realizados durante el desarrollo del trabajo de grado **“Analítica de datos para la caracterización de la investigación y la identificación de su impacto regional”**.

Cada prueba tendrá su propia carpeta y una breve documentación sobre su objetivo, ejecución y resultados.

---

## Prueba 1 — Análisis de indicadores con Codex

### Objetivo

Analizar una muestra fija de **15 proyectos** utilizando únicamente su título y resumen, y comparar su contenido con el catálogo institucional de indicadores mediante Codex.

El flujo es:

```text
15 proyectos
   ↓
Título + resumen
   ↓
Catálogo de indicadores
   ↓
Codex CLI
   ↓
CSV de resultados
```

### Archivos

```text
Prueba LLMS/
├── 15_proyectos.csv
├── catalogo_indicadores.xlsx
├── analizar_proyectos_codex.py
└── resultados_indicadores_codex.csv
```

* `15_proyectos.csv`: muestra utilizada en la prueba.
* `catalogo_indicadores.xlsx`: catálogo estructurado de indicadores.
* `analizar_proyectos_codex.py`: ejecuta automáticamente el análisis.
* `resultados_indicadores_codex.csv`: resultados generados.

### Requisitos

* Python 3
* `pandas`
* `openpyxl`
* Codex CLI instalado y autenticado

Instalar dependencias:

```bash
pip install pandas openpyxl
```

Comprobar Codex:

```bash
codex --version
```

### Ejecución

Desde la carpeta de la prueba:

```bash
python analizar_proyectos_codex.py
```

No es necesario ejecutar Codex manualmente. El script lo invoca automáticamente para analizar los 15 proyectos.

### Consideraciones

La prueba utiliza únicamente el **resumen** como fuente de evidencia.

Los resultados posibles son:

```text
EVIDENCIA_CLARA
EVIDENCIA_PARCIAL
SIN_EVIDENCIA
NO_APLICA
```

La ausencia de evidencia en el resumen no significa necesariamente que el proyecto no cumpla el indicador.

El archivo generado permite posteriormente analizar cuáles indicadores son más frecuentes, menos frecuentes y cómo se comportan entre los distintos proyectos.
