"""
Analizar una tabla: lee la estructura de una tabla Oracle y cómo están hoy sus datos, y propone reglas de calidad listas para
guardar como suite (la misma idea que el «profiling» de Great Expectations o Soda, pero con las reglas del asistente).

- Solo ejecuta SELECT (diccionario de datos USER_/ALL_TAB_COLUMNS y conteos sobre la tabla), a través del mismo ejecutor y la
  misma política de SQL que cualquier caso. No se permite en PRODUCTION: allí las filas se ocultan y no se podría perfilar.
- Las propuestas describen el estado ACTUAL de los datos («hoy no hay vacíos en EMAIL»): sirven para detectar cuando algo cambia,
  no prueban que los datos de hoy sean correctos. La persona revisa y elige cuáles guardar.
- La tabla y las columnas se validan como identificadores simples (app/services/rule_templates.py); los nombres de tabla viajan
  como parámetros enlazados en las consultas al diccionario. Las columnas con nombres raros (minúsculas, espacios) se omiten.
"""
import re
from typing import Any, Dict, List, Optional

from app.services.rule_templates import IDENTIFICADOR, TEXTO_SEGURO, NUMERO, ReglaInvalida, _tabla, construir

MAX_COLUMNAS = 25
MAX_VALORES_LISTA = 5
TIPOS_NUMERICOS = ("NUMBER", "INTEGER", "INT", "FLOAT", "BINARY_FLOAT", "BINARY_DOUBLE", "DECIMAL", "NUMERIC", "REAL", "SMALLINT")
TIPOS_SIN_PERFIL = ("CLOB", "NCLOB", "BLOB", "LONG", "RAW", "XMLTYPE", "BFILE", "JSON")
PISTAS_UNICO = re.compile(r"(^ID$|_ID$|^COD|CODIGO|CODE|EMAIL|CORREO|DNI|RUC|SKU|USUARIO|USERNAME|LOGIN|PLACA|SERIE)", re.I)
PISTAS_NO_NEGATIVO = re.compile(r"(PRECIO|PRICE|MONTO|AMOUNT|IMPORTE|TOTAL|CANTIDAD|QTY|STOCK|SALDO|EDAD|AGE|COSTO|COST)", re.I)


class AnalisisError(ValueError):
    """Problema que se muestra tal cual a la persona usuaria."""


def _valor(res: Dict[str, Any]):
    filas = res.get("rows") or []
    return filas[0][0] if filas and filas[0] else None


def _consulta(executor, sql: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    res = executor.execute_query(sql, params)
    if not res.get("success"):
        raise AnalisisError(res.get("error_message") or res.get("message") or "No se pudo ejecutar la consulta de análisis.")
    return res


def _es_numerico(tipo: str) -> bool:
    return str(tipo or "").upper().split("(")[0].strip() in TIPOS_NUMERICOS


def _perfilable(tipo: str) -> bool:
    return not any(str(tipo or "").upper().startswith(t) for t in TIPOS_SIN_PERFIL)


def _texto_num(v) -> str:
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v)


def analizar(executor, tabla: str) -> Dict[str, Any]:
    """Perfila la tabla con el ejecutor ya creado (la conexión la abre el ejecutor y la cierra quien llama)."""
    if getattr(executor, "environment_type", "PRODUCTION") == "PRODUCTION":
        raise AnalisisError("El análisis no está disponible en PRODUCTION: allí las filas se ocultan. Use una conexión TEST o STAGING.")
    try:
        t = _tabla(tabla)
    except ReglaInvalida as e:
        raise AnalisisError(str(e))
    partes = t.upper().split(".")
    duenio, nombre = (partes[0], partes[1]) if len(partes) == 2 else (None, partes[0])

    if duenio:
        cols_sql = ("SELECT COLUMN_NAME, DATA_TYPE, NULLABLE FROM ALL_TAB_COLUMNS "
                    "WHERE OWNER = :duenio AND TABLE_NAME = :tabla ORDER BY COLUMN_ID")
        pk_sql = ("SELECT cc.COLUMN_NAME FROM ALL_CONSTRAINTS c JOIN ALL_CONS_COLUMNS cc "
                  "ON c.OWNER = cc.OWNER AND c.CONSTRAINT_NAME = cc.CONSTRAINT_NAME "
                  "WHERE c.CONSTRAINT_TYPE = 'P' AND c.OWNER = :duenio AND c.TABLE_NAME = :tabla")
        params = {"duenio": duenio, "tabla": nombre}
    else:
        cols_sql = "SELECT COLUMN_NAME, DATA_TYPE, NULLABLE FROM USER_TAB_COLUMNS WHERE TABLE_NAME = :tabla ORDER BY COLUMN_ID"
        pk_sql = ("SELECT cc.COLUMN_NAME FROM USER_CONSTRAINTS c JOIN USER_CONS_COLUMNS cc "
                  "ON c.CONSTRAINT_NAME = cc.CONSTRAINT_NAME WHERE c.CONSTRAINT_TYPE = 'P' AND c.TABLE_NAME = :tabla")
        params = {"tabla": nombre}

    consultas = 0
    columnas_meta = _consulta(executor, cols_sql, params).get("rows") or []
    consultas += 1
    if not columnas_meta:
        donde = f"en el esquema {duenio}" if duenio else "en el esquema del usuario de la conexión"
        raise AnalisisError(f"No se encontró la tabla {nombre} {donde}. Revise el nombre o escríbalo como ESQUEMA.TABLA.")

    try:
        pk = {str(r[0]).upper() for r in (executor.execute_query(pk_sql, params).get("rows") or [])}
    except Exception:
        pk = set()
    consultas += 1

    total = int(_valor(_consulta(executor, f"SELECT COUNT(*) FROM {t}")) or 0)
    consultas += 1

    columnas: List[Dict[str, Any]] = []
    omitidas: List[str] = []
    for nombre_col, tipo, nullable in columnas_meta:
        col = str(nombre_col)
        if not IDENTIFICADOR.match(col) or len(columnas) >= MAX_COLUMNAS:
            omitidas.append(col)
            continue
        info: Dict[str, Any] = {"nombre": col, "tipo": str(tipo), "admite_vacios": str(nullable).upper() == "Y",
                                "clave_primaria": col.upper() in pk, "vacios": None, "distintos": None,
                                "minimo": None, "maximo": None, "valores": None}
        if _perfilable(tipo) and total > 0:
            if info["admite_vacios"]:
                info["vacios"] = int(_valor(_consulta(executor, f"SELECT COUNT(*) FROM {t} WHERE {col} IS NULL")) or 0)
                consultas += 1
            else:
                info["vacios"] = 0
            info["distintos"] = int(_valor(_consulta(executor, f"SELECT COUNT(DISTINCT {col}) FROM {t}")) or 0)
            consultas += 1
            if _es_numerico(tipo):
                fila = (_consulta(executor, f"SELECT MIN({col}), MAX({col}) FROM {t}").get("rows") or [[None, None]])[0]
                info["minimo"], info["maximo"] = fila[0], fila[1]
                consultas += 1
            if 0 < info["distintos"] <= MAX_VALORES_LISTA and info["distintos"] < total:
                filas = _consulta(executor, f"SELECT DISTINCT {col} FROM {t} WHERE {col} IS NOT NULL").get("rows") or []
                info["valores"] = sorted((_texto_num(r[0]) for r in filas), key=str)
                consultas += 1
        columnas.append(info)

    return {
        "tabla": t, "filas": total, "columnas": columnas, "columnas_omitidas": omitidas,
        "clave_primaria": sorted(pk), "consultas_ejecutadas": consultas,
        "propuestas": proponer(t, total, columnas),
        "aviso": "Las reglas propuestas describen cómo están HOY los datos: avisan cuando algo cambia, no prueban que hoy estén bien. Revíselas antes de guardar.",
    }


def _propuesta(regla: str, params: Dict[str, str], motivo: str, recomendada: bool, columna: Optional[str] = None) -> Optional[Dict[str, Any]]:
    try:
        construida = construir(regla, params)
    except ReglaInvalida:
        return None
    return {"regla": regla, "params": params, "columna": columna, "motivo": motivo, "recomendada": recomendada,
            "nombre": nombre_de_caso(regla, params), **construida}


def nombre_de_caso(regla: str, p: Dict[str, str]) -> str:
    t, c = p.get("tabla", ""), p.get("columna", "")
    return {
        "tabla_con_datos": f"{t} tiene filas",
        "filas_exactas": f"{t} tiene {p.get('n')} filas",
        "sin_nulos": f"{t}.{c} sin vacíos",
        "sin_repetidos": f"{t}.{c} sin repetidos",
        "solo_valores": f"{t}.{c} solo vale {p.get('valores')}",
        "rango_numerico": f"{t}.{c} entre {p.get('minimo')} y {p.get('maximo')}",
        "existe_fila": f"{t}: existe {c} = {p.get('valor')}",
        "contar_con_valor": f"{t}: {p.get('n')} filas con {c} = {p.get('valor')}",
    }.get(regla, f"{t}: {regla}")[:120]


def proponer(t: str, total: int, columnas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Reglas sugeridas a partir del perfil. Las «recomendadas» vienen marcadas para guardarlas con un clic."""
    props: List[Optional[Dict[str, Any]]] = []
    if total > 0:
        props.append(_propuesta("tabla_con_datos", {"tabla": t}, f"Hoy la tabla tiene {total} filas; la regla avisa si queda vacía.", True))
        props.append(_propuesta("filas_exactas", {"tabla": t, "n": str(total)},
                                "Solo para tablas de referencia que no deberían cambiar (catálogos, parámetros).", False))
    for c in columnas:
        col, nombre = c["nombre"], c["nombre"].upper()
        if c["vacios"] is None:
            continue
        base = {"tabla": t, "columna": col}
        if c["clave_primaria"]:
            props.append(_propuesta("sin_repetidos", base, "Es la clave primaria: no debe repetirse.", True, col))
        elif c["distintos"] == total and total > 1:
            pista = bool(PISTAS_UNICO.search(nombre))
            props.append(_propuesta("sin_repetidos", base,
                                    "Hoy no se repite ningún valor" + (" y por su nombre parece un código o identificador." if pista else "."), pista, col))
        if c["admite_vacios"] and c["vacios"] == 0:
            props.append(_propuesta("sin_nulos", base, "La columna admite vacíos, pero hoy no tiene ninguno; la regla avisa si aparecen.", True, col))
        if c["valores"] and len(c["valores"]) >= 1 and all(NUMERO.match(v) or TEXTO_SEGURO.match(v) for v in c["valores"]):
            valores = ", ".join(c["valores"])
            props.append(_propuesta("solo_valores", {**base, "valores": valores},
                                    f"Hoy solo tiene los valores {valores}; la regla avisa si aparece otro.", True, col))
        if _es_numerico(c["tipo"]) and c["minimo"] is not None and c["maximo"] is not None and not c["valores"]:
            mn, mx = _texto_num(c["minimo"]), _texto_num(c["maximo"])
            if PISTAS_NO_NEGATIVO.search(nombre) and float(c["minimo"]) >= 0:
                props.append(_propuesta("rango_numerico", {**base, "minimo": "0", "maximo": mx},
                                        f"Por su nombre parece un monto o cantidad; hoy va de {mn} a {mx}. Ajuste el máximo si hace falta.", False, col))
    return [p for p in props if p]


def guardar_como_suite(db, project_id: int, nombre_suite: str, descripcion: Optional[str], propuestas: List[Dict[str, Any]]):
    """Crea un caso por propuesta (el SQL se vuelve a generar en el servidor) y una suite que los agrupa."""
    from app.models.suite import TestSuite
    from app.models.test_case import TestCase

    if not propuestas:
        raise AnalisisError("Elija al menos una regla para guardar.")
    construidas = []
    for p in propuestas:
        try:
            r = construir(str(p.get("regla")), {k: str(v) for k, v in (p.get("params") or {}).items()})
        except ReglaInvalida as e:
            raise AnalisisError(f"Regla no válida: {e}")
        construidas.append((nombre_de_caso(r["regla"], p.get("params") or {}), r))
    suite = TestSuite(project_id=project_id, name=nombre_suite.strip()[:120],
                      description=(descripcion or "").strip() or "Creada con «Analizar una tabla».")
    db.add(suite)
    for nombre, r in construidas:
        tc = TestCase(project_id=project_id, name=nombre, description=r["explicacion"], sql_query=r["sql"],
                      validation_type=r["validation_type"], expected_result=r["expected_result"])
        db.add(tc)
        suite.test_cases.append(tc)
    db.commit()
    db.refresh(suite)
    return suite
