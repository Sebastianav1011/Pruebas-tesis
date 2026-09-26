"""Extrae departamento y municipio (códigos DIVIPOLA del DANE) de los fragmentos.

No usa embeddings: busca los nombres oficiales de ``Tabla_Codigos_Dane.xlsx``
dentro del texto de cada fragmento ya generado por ``graphrag_10.py``.

- MENCIONADO_EN_TEXTO: el lugar aparece en campos de contenido (resumen,
  objetivos, metodología...). Si solo se nombra Colombia, el departamento es
  NACIONAL.
- INFERIDO_AFILIACION: el contenido no nombra lugares, pero la afiliación de
  los autores sí. Indica dónde trabajan, no confirma dónde se investigó.
- SIN INFORMACIÓN: no hay ninguna mención utilizable.

Muchos municipios comparten nombre con palabras, apellidos, países o con otros
municipios. Esas menciones solo se aceptan con contexto geográfico o con su
departamento nombrado; las que no se aceptan quedan en ``descartados`` para
revisión.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[2]
TABLA_DANE_PATH = BASE_DIR / "shared" / "datos" / "Tabla_Codigos_Dane.xlsx"
APROXIMACION_02 = BASE_DIR / "02_aproximacion_plantilla_final"
FUENTES_02 = {
    fuente: (
        APROXIMACION_02 / "grafo" / fuente / "fragmentos" / "fragmentos_10.json",
        APROXIMACION_02 / "resultados" / fuente / "territorio" / "territorios_10.json",
    )
    for fuente in ("proyectos", "articulos")
}

SIN_INFORMACION = "SIN INFORMACIÓN"
NACIONAL = "NACIONAL"
MENCIONADO = "MENCIONADO_EN_TEXTO"
INFERIDO = "INFERIDO_AFILIACION"

# Mismos campos de contenido que pueden respaldar un indicador en graphrag_10.py.
CAMPOS_TEXTO = {
    "nombre_producto", "resumen", "palabras_clave", "objetivos", "metodologia",
    "resultados_investigacion", "justificacion",
}
CAMPOS_AFILIACION = {"afiliacion_coautores"}

ALIAS_DEPARTAMENTOS = {
    "54": ["norte de santander"],
    "44": ["guajira"],
    "88": ["archipielago de san andres", "san andres y providencia", "san andres, providencia y santa catalina"],
}
# Bogotá figura como departamento 11 y municipio 11001; se trata como municipio.
ALIAS_MUNICIPIOS = {
    "11001": ["bogota", "bogota d.c.", "bogota dc", "bogota d. c.", "santafe de bogota", "santa fe de bogota"],
    "13001": ["cartagena de indias"],
    "13468": ["mompox", "santa cruz de mompox"],
    "52835": ["tumaco"],
    "54001": ["san jose de cucuta"],
    "76111": ["buga"],
    "05042": ["santa fe de antioquia"],
    "70820": ["tolu"],
    "05148": ["carmen de viboral"],
    "94001": ["puerto inirida"],
}
# Departamentos cuyo nombre también es una palabra, persona, río o lugar
# extranjero: requieren contexto ("en el Meta", "departamento de Bolívar").
DEPARTAMENTOS_RIESGOSOS = {"08", "13", "17", "19", "20", "23", "47", "50", "52", "68", "70", "91"}
# Municipios con nombre de palabra común, apellido o lugar extranjero: solo se
# aceptan si el texto también nombra su departamento.
REQUIERE_DEPARTAMENTO = {
    "alban", "albania", "alvarado", "anzoategui", "arbelaez", "arboleda", "argelia", "armenia",
    "barbosa", "belen", "beltran", "betania", "buenos aires", "cabrera", "caceres", "caicedo",
    "california", "candelaria", "cartago", "casabianca", "ciudad bolivar", "coello", "colombia",
    "concordia", "cota", "chia", "dolores", "el banco", "el carmen", "el cerrito", "el colegio",
    "el paso", "el retiro", "esperanza", "flandes", "florencia", "florida", "fonseca", "gama",
    "garzon", "ginebra", "granada", "guadalupe", "gutierrez", "herran", "hispania", "honda",
    "jerusalen", "junin", "la cruz", "la ceja", "la dorada", "la estrella", "la gloria",
    "la merced", "la mesa", "la paz", "la plata", "la primavera", "la union", "la vega",
    "la victoria", "lerida", "libano", "linares", "madrid", "mariquita", "medina", "morales",
    "mosquera", "murillo", "neira", "nilo", "ospina", "padilla", "paez", "palestina", "piedras",
    "pinillos", "prado", "primavera", "providencia", "puerto rico", "purificacion", "remolino",
    "restrepo", "ricaurte", "rivera", "rosario", "rovira", "salgar", "san antonio", "san carlos",
    "san juan", "san luis", "san martin", "san pablo", "san pedro", "santa ana", "santa isabel",
    "santa maria", "santa rosa", "santiago", "sevilla", "suarez", "tenerife", "toledo", "une",
    "union", "utica", "valencia", "velez", "venecia", "vergara", "victoria", "villahermosa",
    "villarrica",
}
# Capitales (código terminado en 001) que también son palabras, nombres o
# apellidos frecuentes: no se aceptan solo por ser capitales.
CAPITALES_CON_OTRO_SIGNIFICADO = {"pasto", "pereira", "leticia"}
# El municipio Colombia (Huila) se confunde siempre con el país; el país se
# trata aparte como NACIONAL.
NOMBRES_EXCLUIDOS = {"colombia"}

CONTEXTO_PREVIO = re.compile(
    r"(?:\b(?:municipio|municipios|ciudad|corregimiento|vereda|veredas|region|departamento|"
    r"depto\.?|dpto\.?|localidad|provincia)\s+(?:de|del)\s+|\b(?:en|desde|hacia|entre|y)\s+"
    r"(?:el\s+|la\s+)?|,\s*)$"
)
CONTEXTO_POSTERIOR = re.compile(r"^\s*[,(\-]?\s*colombia(?![a-z])")
# Apellido dentro de una cita: "Buritica OF (2014)", "Pereira et al., 2024".
CITA_POSTERIOR = re.compile(r"^\s*(?:et\s+al\b|,?\s*[A-Z]{1,3}(?:\.|,|;|\s|\)|$)(?![a-z]))")
MENCION_COLOMBIA = re.compile(r"(?<![a-z])colombi(?:a|an[oa]s?)(?![a-z])")


def normalizar_caracteres(valor: str) -> str:
    """Quita tildes y pasa a minúsculas sin cambiar la longitud del texto."""
    salida = []
    for caracter in valor:
        base = "".join(c for c in unicodedata.normalize("NFKD", caracter) if not unicodedata.combining(c))
        salida.append((base or caracter).lower()[:1] or caracter)
    return "".join(salida)


def clave(valor: str) -> str:
    return re.sub(r"\s+", " ", normalizar_caracteres(str(valor))).strip()


def cargar_divipola(ruta: Path = TABLA_DANE_PATH) -> pd.DataFrame:
    """Lee la tabla del DANE ignorando encabezados decorativos y filas vacías."""
    tabla = pd.read_excel(ruta, header=None, dtype=str).iloc[:, :4]
    tabla.columns = ["cod_departamento", "nombre_departamento", "cod_municipio", "nombre_municipio"]
    tabla = tabla.apply(lambda columna: columna.str.strip())
    validas = (tabla["cod_departamento"].str.fullmatch(r"\d{1,2}", na=False)
               & tabla["cod_municipio"].str.fullmatch(r"\d{1,3}", na=False))
    tabla = tabla[validas].copy()
    tabla["cod_departamento"] = tabla["cod_departamento"].str.zfill(2)
    tabla["cod_municipio"] = tabla["cod_departamento"] + tabla["cod_municipio"].str.zfill(3)
    if tabla.empty or tabla["cod_municipio"].duplicated().any():
        raise ValueError(f"La tabla DANE no tiene códigos de municipio únicos: {ruta}")
    return tabla.reset_index(drop=True)


class Gazetteer:
    """Índice de nombres DANE normalizados para buscar en texto libre."""

    def __init__(self, tabla: pd.DataFrame) -> None:
        self.departamentos = dict(zip(tabla["cod_departamento"], tabla["nombre_departamento"]))
        self.municipios = {
            fila.cod_municipio: (fila.cod_departamento, fila.nombre_municipio)
            for fila in tabla.itertuples()
        }
        self.alias_departamento: dict[str, str] = {}
        for codigo, nombre in self.departamentos.items():
            if codigo != "11":
                self.alias_departamento[clave(nombre)] = codigo
        for codigo, alias in ALIAS_DEPARTAMENTOS.items():
            for nombre in alias:
                self.alias_departamento[clave(nombre)] = codigo
        self.alias_municipio: dict[str, list[str]] = defaultdict(list)
        for codigo, (_, nombre) in self.municipios.items():
            self.alias_municipio[clave(nombre)].append(codigo)
        for codigo, alias in ALIAS_MUNICIPIOS.items():
            for nombre in alias:
                if codigo not in self.alias_municipio[clave(nombre)]:
                    self.alias_municipio[clave(nombre)].append(codigo)
        # Un nombre que también es departamento (Córdoba, Sucre, Arauca...) se
        # interpreta como departamento: el texto no permite distinguirlos.
        for nombre in [*self.alias_departamento, *NOMBRES_EXCLUIDOS]:
            self.alias_municipio.pop(nombre, None)
        todos = sorted(set(self.alias_departamento) | set(self.alias_municipio), key=len, reverse=True)
        alternativas = "|".join(r"\s+".join(re.escape(p) for p in nombre.split(" ")) for nombre in todos)
        self.patron = re.compile(rf"(?<![a-z0-9])(?:{alternativas})(?![a-z0-9])")


def menciones(fragmentos: list[dict[str, str]], gazetteer: Gazetteer, estricto: bool) -> list[dict[str, Any]]:
    """Busca nombres DANE. En modo estricto (afiliaciones) solo cuenta como
    contexto que después aparezca Colombia: "Universidad X, Ciudad" no basta."""
    encontradas = []
    for fragmento in fragmentos:
        original = fragmento["texto"]
        normal = normalizar_caracteres(original)
        for coincidencia in gazetteer.patron.finditer(normal):
            inicio, fin = coincidencia.span()
            # Los nombres propios van en mayúscula; evita "honda", "cota", "meta"...
            if not original[inicio].isupper():
                continue
            previo = not estricto and bool(CONTEXTO_PREVIO.search(normal[max(0, inicio - 40):inicio]))
            encontradas.append({
                "clave": clave(coincidencia.group()),
                "mencion": original[inicio:fin],
                "id_fragmento": fragmento["id_fragmento"],
                "campo_origen": fragmento["campo_origen"],
                "con_contexto": previo or bool(CONTEXTO_POSTERIOR.search(normal[fin:fin + 30])),
                "en_cita": bool(CITA_POSTERIOR.search(original[fin:fin + 12])),
            })
    return encontradas


def evidencia(mencion: dict[str, Any]) -> dict[str, str]:
    return {"mencion": mencion["mencion"], "id_fragmento": mencion["id_fragmento"],
            "campo_origen": mencion["campo_origen"]}


def descarte(mencion: dict[str, Any], motivo: str) -> dict[str, str]:
    return {**evidencia(mencion), "motivo": motivo}


def resolver(fragmentos: list[dict[str, str]], gazetteer: Gazetteer, estricto: bool = False) -> tuple[
    dict[str, list[dict[str, str]]], dict[str, list[dict[str, str]]], list[dict[str, str]]
]:
    """Devuelve departamentos y municipios aceptados, con evidencias y descartes."""
    departamentos: dict[str, list[dict[str, str]]] = defaultdict(list)
    municipios: dict[str, list[dict[str, str]]] = defaultdict(list)
    descartados: list[dict[str, str]] = []
    pendientes: list[tuple[str, dict[str, Any]]] = []
    encontradas = []
    for mencion in menciones(fragmentos, gazetteer, estricto):
        if mencion["en_cita"]:
            descartados.append(descarte(mencion, "Parece apellido en una cita bibliográfica"))
        else:
            encontradas.append(mencion)

    for mencion in encontradas:
        codigo = gazetteer.alias_departamento.get(mencion["clave"])
        if codigo is None:
            continue
        if codigo in DEPARTAMENTOS_RIESGOSOS and not mencion["con_contexto"]:
            pendientes.append((codigo, mencion))
        else:
            departamentos[codigo].append(evidencia(mencion))

    for mencion in encontradas:
        codigos = gazetteer.alias_municipio.get(mencion["clave"])
        if not codigos:
            continue
        confirmados = [c for c in codigos if c[:2] in departamentos]
        if len(codigos) > 1 or mencion["clave"] in REQUIERE_DEPARTAMENTO:
            if len(confirmados) == 1:
                municipios[confirmados[0]].append(evidencia(mencion))
            else:
                descartados.append(descarte(mencion, "Nombre ambiguo o de uso común sin su departamento en el texto"))
            continue
        codigo = codigos[0]
        es_capital = codigo.endswith("001") and mencion["clave"] not in CAPITALES_CON_OTRO_SIGNIFICADO
        if confirmados or es_capital or mencion["con_contexto"]:
            municipios[codigo].append(evidencia(mencion))
        else:
            descartados.append(descarte(mencion, "Municipio sin contexto geográfico"))

    for codigo, mencion in pendientes:
        if any(c[:2] == codigo for c in municipios):
            departamentos[codigo].append(evidencia(mencion))
        else:
            descartados.append(descarte(mencion, "Nombre de departamento con otro significado posible y sin contexto geográfico"))

    for codigo, evidencias in municipios.items():
        departamentos[codigo[:2]].extend(evidencias)
    return departamentos, municipios, descartados


def territorios_desde(
    departamentos: dict[str, list[dict[str, str]]], municipios: dict[str, list[dict[str, str]]],
    gazetteer: Gazetteer,
) -> list[dict[str, Any]]:
    salida = []
    for codigo in sorted(departamentos):
        evidencias = []
        for item in departamentos[codigo]:
            if item not in evidencias:
                evidencias.append(item)
        salida.append({
            "cod_departamento": codigo,
            "nombre_departamento": gazetteer.departamentos[codigo],
            "municipios": [
                {"cod_municipio": c, "nombre_municipio": gazetteer.municipios[c][1]}
                for c in sorted(municipios) if c[:2] == codigo
            ],
            "evidencias": evidencias,
        })
    return salida


def mencion_colombia(fragmentos: list[dict[str, str]]) -> list[dict[str, str]]:
    evidencias = []
    for fragmento in fragmentos:
        original = fragmento["texto"]
        coincidencia = MENCION_COLOMBIA.search(normalizar_caracteres(original))
        if coincidencia:
            evidencias.append({"mencion": original[coincidencia.start():coincidencia.end()],
                               "id_fragmento": fragmento["id_fragmento"],
                               "campo_origen": fragmento["campo_origen"]})
    return evidencias


def extraer_documento(fragmentos: list[dict[str, str]], gazetteer: Gazetteer) -> dict[str, Any]:
    texto = [f for f in fragmentos if f["campo_origen"] in CAMPOS_TEXTO]
    afiliacion = [f for f in fragmentos if f["campo_origen"] in CAMPOS_AFILIACION]
    departamentos, municipios, descartados = resolver(texto, gazetteer)
    if departamentos:
        return {"origen_territorio": MENCIONADO, "territorios": territorios_desde(departamentos, municipios, gazetteer),
                "descartados": descartados}
    evidencias_colombia = mencion_colombia(texto)
    if evidencias_colombia:
        return {"origen_territorio": MENCIONADO, "territorios": [{
            "cod_departamento": NACIONAL, "nombre_departamento": "COLOMBIA (SIN DEPARTAMENTO ESPECÍFICO)",
            "municipios": [], "evidencias": evidencias_colombia[:3],
        }], "descartados": descartados}
    dep_afiliacion, mun_afiliacion, desc_afiliacion = resolver(afiliacion, gazetteer, estricto=True)
    if dep_afiliacion:
        return {"origen_territorio": INFERIDO, "territorios": territorios_desde(dep_afiliacion, mun_afiliacion, gazetteer),
                "descartados": descartados + desc_afiliacion}
    return {"origen_territorio": SIN_INFORMACION, "territorios": [], "descartados": descartados + desc_afiliacion}


def extraer_fuente(ruta_fragmentos: Path, ruta_salida: Path, gazetteer: Gazetteer) -> dict[str, Any]:
    fragmentos = json.loads(ruta_fragmentos.read_text(encoding="utf-8"))
    por_documento: dict[str, list[dict[str, str]]] = defaultdict(list)
    for fragmento in fragmentos:
        por_documento[fragmento["id_proyecto"]].append(fragmento)
    documentos = {id_documento: extraer_documento(items, gazetteer) for id_documento, items in por_documento.items()}
    resultado = {
        "tabla_dane": TABLA_DANE_PATH.name,
        "fragmentos": str(ruta_fragmentos.relative_to(BASE_DIR)) if ruta_fragmentos.is_relative_to(BASE_DIR) else str(ruta_fragmentos),
        "campos_texto": sorted(CAMPOS_TEXTO),
        "campos_afiliacion": sorted(CAMPOS_AFILIACION),
        "documentos": documentos,
    }
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    ruta_salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    return resultado


def imprimir_resumen(nombre: str, resultado: dict[str, Any]) -> None:
    print(f"\n{nombre.upper()}")
    for id_documento, datos in resultado["documentos"].items():
        lugares = []
        for territorio in datos["territorios"]:
            municipios = ", ".join(m["nombre_municipio"] for m in territorio["municipios"])
            lugares.append(f"{territorio['cod_departamento']} {territorio['nombre_departamento']}"
                           + (f" [{municipios}]" if municipios else ""))
        print(f"  {id_documento[:28]:<28} {datos['origen_territorio']:<20} {' | '.join(lugares) or '-'}"
              f"  (descartados: {len(datos['descartados'])})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extrae departamento y municipio DANE de fragmentos GraphRAG.")
    parser.add_argument("--fragmentos", type=Path, help="fragmentos_10.json de una ejecución. Sin este argumento procesa las dos fuentes de la aproximación 02.")
    parser.add_argument("--salida", type=Path, help="JSON de salida; obligatorio con --fragmentos.")
    args = parser.parse_args()
    try:
        gazetteer = Gazetteer(cargar_divipola())
        if args.fragmentos:
            if not args.salida:
                raise ValueError("--salida es obligatorio cuando se usa --fragmentos.")
            trabajos = {args.fragmentos.stem: (args.fragmentos.resolve(), args.salida.resolve())}
        else:
            trabajos = FUENTES_02
        for nombre, (entrada, salida) in trabajos.items():
            imprimir_resumen(nombre, extraer_fuente(entrada, salida, gazetteer))
    except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as error:
        print(f"Error: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
