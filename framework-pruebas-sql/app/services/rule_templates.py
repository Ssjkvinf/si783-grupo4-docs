"""
Asistente de reglas: convierte una regla en lenguaje común («ninguna fila con la columna X vacía») en la consulta SELECT, el tipo
de validación y el resultado esperado que entiende el motor de ejecución.

Es la misma idea que las «pruebas genéricas» de dbt o las reglas de Soda (not_null, unique, accepted_values), pero generando SQL
Oracle. Solo produce SELECT; el SQL generado pasa después por la política de SQL como cualquier otra sentencia.

Seguridad: la tabla y la columna deben ser identificadores simples (sin comillas, espacios ni signos) y los valores son números
o textos cortos con caracteres seguros. Nada del usuario se concatena sin pasar por esas comprobaciones.
"""
import re
from typing import Any, Dict, List

from app.security.sql_policy import FORBIDDEN_KEYWORDS, validate_sql_statement

IDENTIFICADOR = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]{0,29}$")
NUMERO = re.compile(r"^-?\d{1,18}(\.\d{1,9})?$")
TEXTO_SEGURO = re.compile(r"^[A-Za-z0-9_ .:/-]{1,50}$")
MAX_VALORES = 20


class ReglaInvalida(ValueError):
    """Los datos de la regla no son válidos; el mensaje está pensado para mostrarse a la persona usuaria."""


def _identificador(valor: Any, etiqueta: str) -> str:
    v = str(valor or "").strip()
    if not IDENTIFICADOR.match(v):
        raise ReglaInvalida(f"{etiqueta}: use solo letras, números y _ (empieza con una letra, máximo 30 caracteres). Recibido: «{v}».")
    if v.upper() in FORBIDDEN_KEYWORDS or v.upper() in {"SELECT", "FROM", "WHERE", "UNION", "INSERT", "UPDATE", "DELETE", "FOR"}:
        raise ReglaInvalida(f"{etiqueta}: «{v}» es una palabra reservada del SQL; indique el nombre real de la tabla o la columna.")
    return v


def _tabla(valor: Any) -> str:
    """Acepta TABLA o ESQUEMA.TABLA."""
    partes = str(valor or "").strip().split(".")
    if len(partes) > 2 or not all(partes):
        raise ReglaInvalida("Tabla: escriba TABLA o ESQUEMA.TABLA.")
    return ".".join(_identificador(p, "Tabla") for p in partes)


def _literal(valor: Any, etiqueta: str) -> str:
    v = str(valor if valor is not None else "").strip()
    if NUMERO.match(v):
        return v
    if TEXTO_SEGURO.match(v):
        return "'" + v + "'"
    raise ReglaInvalida(f"{etiqueta}: use un número o un texto corto con letras, números, espacio y . : / _ - (sin comillas). Recibido: «{v}».")


def _entero_no_negativo(valor: Any, etiqueta: str) -> str:
    v = str(valor if valor is not None else "").strip()
    if not re.fullmatch(r"\d{1,12}", v):
        raise ReglaInvalida(f"{etiqueta}: debe ser un número entero mayor o igual a 0.")
    return str(int(v))


def _numero(valor: Any, etiqueta: str) -> str:
    v = str(valor if valor is not None else "").strip()
    if not NUMERO.match(v):
        raise ReglaInvalida(f"{etiqueta}: debe ser un número (puede tener decimales con punto).")
    return v


def _lista(valor: Any, etiqueta: str) -> List[str]:
    items = [x.strip() for x in str(valor or "").split(",") if x.strip() != ""]
    if not items:
        raise ReglaInvalida(f"{etiqueta}: escriba al menos un valor, separados por comas.")
    if len(items) > MAX_VALORES:
        raise ReglaInvalida(f"{etiqueta}: máximo {MAX_VALORES} valores.")
    return [_literal(x, etiqueta) for x in items]


P_TABLA = {"nombre": "tabla", "etiqueta": "Tabla", "ejemplo": "FRAMEWORK_TEST_ITEMS", "ayuda": "Nombre de la tabla (o ESQUEMA.TABLA)"}
P_COL = {"nombre": "columna", "etiqueta": "Columna", "ejemplo": "NAME", "ayuda": "Nombre de la columna"}

REGLAS: List[Dict[str, Any]] = [
    {"id": "filas_exactas", "titulo": "La tabla tiene exactamente N filas",
     "descripcion": "Cuenta las filas de la tabla y compara el número con el que usted espera.",
     "validacion": "SCALAR_VALUE",
     "parametros": [P_TABLA, {"nombre": "n", "etiqueta": "Filas esperadas", "ejemplo": "5", "ayuda": "Número entero"}]},
    {"id": "tabla_con_datos", "titulo": "La tabla no está vacía",
     "descripcion": "Comprueba que la tabla tenga al menos una fila.",
     "validacion": "EXISTS",
     "parametros": [P_TABLA]},
    {"id": "sin_nulos", "titulo": "Ninguna fila con la columna vacía (sin NULL)",
     "descripcion": "Cuenta las filas donde la columna está vacía; lo esperado es 0.",
     "validacion": "SCALAR_VALUE",
     "parametros": [P_TABLA, P_COL]},
    {"id": "sin_repetidos", "titulo": "Sin valores repetidos en la columna",
     "descripcion": "Cuenta cuántos valores aparecen más de una vez; lo esperado es 0 (útil para códigos o identificadores).",
     "validacion": "SCALAR_VALUE",
     "parametros": [P_TABLA, {**P_COL, "ejemplo": "NAME"}]},
    {"id": "solo_valores", "titulo": "La columna solo contiene ciertos valores",
     "descripcion": "Cuenta las filas cuyo valor NO está en su lista; lo esperado es 0. Las filas vacías (NULL) no se cuentan aquí: use la regla «sin NULL» para eso.",
     "validacion": "SCALAR_VALUE",
     "parametros": [P_TABLA, {**P_COL, "ejemplo": "ACTIVE"},
                    {"nombre": "valores", "etiqueta": "Valores permitidos", "ejemplo": "0, 1", "ayuda": "Separados por comas"}]},
    {"id": "existe_fila", "titulo": "Existe una fila con cierto valor",
     "descripcion": "Comprueba que haya al menos una fila donde la columna vale lo indicado.",
     "validacion": "EXISTS",
     "parametros": [P_TABLA, {**P_COL, "ejemplo": "ID"}, {"nombre": "valor", "etiqueta": "Valor buscado", "ejemplo": "3", "ayuda": "Número o texto corto"}]},
    {"id": "contar_con_valor", "titulo": "Cuántas filas tienen cierto valor",
     "descripcion": "Cuenta las filas donde la columna vale lo indicado y compara con el número que espera.",
     "validacion": "SCALAR_VALUE",
     "parametros": [P_TABLA, {**P_COL, "ejemplo": "ACTIVE"}, {"nombre": "valor", "etiqueta": "Valor", "ejemplo": "1", "ayuda": "Número o texto corto"},
                    {"nombre": "n", "etiqueta": "Filas esperadas", "ejemplo": "4", "ayuda": "Número entero"}]},
    {"id": "rango_numerico", "titulo": "Los valores numéricos están dentro de un rango",
     "descripcion": "Cuenta las filas cuyo valor queda fuera del rango [mínimo, máximo]; lo esperado es 0.",
     "validacion": "SCALAR_VALUE",
     "parametros": [P_TABLA, {**P_COL, "ejemplo": "ACTIVE"}, {"nombre": "minimo", "etiqueta": "Mínimo", "ejemplo": "0", "ayuda": "Número"},
                    {"nombre": "maximo", "etiqueta": "Máximo", "ejemplo": "1", "ayuda": "Número"}]},
]
_POR_ID = {r["id"]: r for r in REGLAS}


def listar() -> List[Dict[str, Any]]:
    """Catálogo para la interfaz (sin funciones; solo datos)."""
    return [dict(r) for r in REGLAS]


def construir(regla_id: str, params: Dict[str, Any]) -> Dict[str, str]:
    """Genera el SELECT, el tipo de validación, el valor esperado y una explicación en lenguaje común."""
    regla = _POR_ID.get(regla_id)
    if not regla:
        raise ReglaInvalida(f"Regla desconocida: «{regla_id}».")
    p = params or {}
    falta = [x["etiqueta"] for x in regla["parametros"] if str(p.get(x["nombre"], "")).strip() == ""]
    if falta:
        raise ReglaInvalida("Complete: " + ", ".join(falta) + ".")
    t = _tabla(p.get("tabla"))
    validacion = regla["validacion"]

    if regla_id == "filas_exactas":
        n = _entero_no_negativo(p["n"], "Filas esperadas")
        sql, esperado = f"SELECT COUNT(*) FROM {t}", n
        texto = f"La tabla {t} debe tener exactamente {n} filas."
    elif regla_id == "tabla_con_datos":
        sql, esperado = f"SELECT 1 FROM {t}", "true"
        texto = f"La tabla {t} debe tener al menos una fila."
    elif regla_id == "sin_nulos":
        c = _identificador(p["columna"], "Columna")
        sql, esperado = f"SELECT COUNT(*) FROM {t} WHERE {c} IS NULL", "0"
        texto = f"En {t} ninguna fila debe tener {c} vacía (0 filas con NULL)."
    elif regla_id == "sin_repetidos":
        c = _identificador(p["columna"], "Columna")
        sql, esperado = f"SELECT COUNT(*) FROM (SELECT {c} FROM {t} GROUP BY {c} HAVING COUNT(*) > 1)", "0"
        texto = f"En {t} ningún valor de {c} debe repetirse (0 valores repetidos)."
    elif regla_id == "solo_valores":
        c = _identificador(p["columna"], "Columna")
        vals = _lista(p["valores"], "Valores permitidos")
        sql, esperado = f"SELECT COUNT(*) FROM {t} WHERE {c} NOT IN ({', '.join(vals)})", "0"
        texto = f"En {t} la columna {c} solo puede valer {', '.join(vals)} (0 filas con otro valor)."
    elif regla_id == "existe_fila":
        c = _identificador(p["columna"], "Columna")
        lit = _literal(p["valor"], "Valor buscado")
        sql, esperado = f"SELECT 1 FROM {t} WHERE {c} = {lit}", "true"
        texto = f"En {t} debe existir al menos una fila con {c} = {lit}."
    elif regla_id == "contar_con_valor":
        c = _identificador(p["columna"], "Columna")
        lit = _literal(p["valor"], "Valor")
        n = _entero_no_negativo(p["n"], "Filas esperadas")
        sql, esperado = f"SELECT COUNT(*) FROM {t} WHERE {c} = {lit}", n
        texto = f"En {t} deben ser {n} las filas con {c} = {lit}."
    else:  # rango_numerico
        c = _identificador(p["columna"], "Columna")
        mn, mx = _numero(p["minimo"], "Mínimo"), _numero(p["maximo"], "Máximo")
        if float(mn) > float(mx):
            raise ReglaInvalida("El mínimo no puede ser mayor que el máximo.")
        sql, esperado = f"SELECT COUNT(*) FROM {t} WHERE {c} < {mn} OR {c} > {mx}", "0"
        texto = f"En {t} todos los valores de {c} deben estar entre {mn} y {mx} (0 filas fuera del rango)."

    ok, tipo, error = validate_sql_statement(sql, "PRODUCTION")   # el SQL generado debe ser un SELECT aceptable incluso en el ambiente más estricto
    if not ok or tipo != "SELECT":
        raise ReglaInvalida(f"No se pudo generar una consulta segura: {error}")
    return {"regla": regla_id, "sql": sql, "validation_type": validacion, "expected_result": esperado, "explicacion": texto}
