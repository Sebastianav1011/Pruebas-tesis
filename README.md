# Pruebas — Trabajo de Grado

Repositorio destinado a centralizar las **pruebas, experimentos, scripts y resultados** desarrollados durante el trabajo de grado:

**“Analítica de datos para la caracterización de la investigación y la identificación de su impacto regional en la Vicerrectoría de Investigación de la Pontificia Universidad Javeriana.”**

## Objetivo del repositorio

Mantener organizadas y reproducibles las diferentes pruebas realizadas durante el desarrollo del proyecto, especialmente aquellas relacionadas con:

* preparación y exploración de datos;
* análisis de proyectos de investigación;
* evaluación de indicadores de impacto;
* pruebas con modelos de lenguaje (LLMs);
* comparación de diferentes enfoques y modelos;
* validación de resultados.

## Organización

Cada prueba se almacena en una carpeta independiente.

```text
Pruebas/
├── Prueba 1/
│   ├── README.md
│   ├── scripts/
│   ├── datos/
│   └── resultados/
│
├── Prueba 2/
│   └── ...
│
└── ...
```

Cada carpeta debe contener su propio `README.md` con la información específica necesaria para ejecutar y comprender la prueba.

## Consideraciones

Los datos utilizados en cada experimento deben mantenerse separados de los resultados generados.

Siempre que sea posible, las pruebas deben conservar:

* la muestra utilizada;
* los parámetros o criterios aplicados;
* los scripts de ejecución;
* los resultados obtenidos.

Esto permite repetir los experimentos y comparar los resultados obtenidos a medida que evoluciona la solución.
