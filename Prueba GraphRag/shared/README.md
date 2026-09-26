# Recursos compartidos

- `datos/catalogo_indicadores.xlsx`: catálogo utilizado por la prueba controlada y por la aproximación orientada a la plantilla final.
- `datos/Tabla_Codigos_Dane.xlsx`: tabla DIVIPOLA del DANE (código y nombre de departamento, código y nombre de municipio). El código de municipio se usa con 5 dígitos: departamento (2) + municipio (3).
- `scripts/graphrag_10.py`: motor común. Acepta entrada, directorio de resultados y tipo de fuente mediante argumentos; por defecto apunta a una nueva ejecución aislada de la prueba 01.
- `scripts/extraer_territorio.py`: busca en los fragmentos ya generados los nombres de la tabla DANE y asigna departamento y municipio a cada documento. No usa embeddings. Clasifica el origen como `MENCIONADO_EN_TEXTO` (contenido del documento; `NACIONAL` si solo nombra Colombia), `INFERIDO_AFILIACION` (solo la afiliación de los autores lo sugiere) o `SIN INFORMACIÓN`. Las menciones ambiguas (apellidos en citas, nombres de otros países, municipios homónimos sin su departamento) quedan en `descartados` para revisión.

## Preparar el entorno

`.venv` y el modelo no se suben a GitHub. Desde la carpeta `Prueba GraphRag`:

    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    .\.venv\Scripts\python.exe -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2', cache_folder='.venv/model_cache')"

El último comando descarga el modelo una sola vez desde Hugging Face; después el motor funciona sin internet.

El catálogo no se duplicó porque es una fuente general y el motor es realmente compartido por ambas líneas históricas.
