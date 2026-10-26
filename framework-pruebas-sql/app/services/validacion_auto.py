"""
Validación automática: la persona escribe la consulta y lo que espera, y la aplicación decide cómo compararlo.

Evita la confusión entre «cantidad de filas» (ROW_COUNT) y «valor que devuelve la consulta» (SCALAR_VALUE), que fue una de
las críticas recibidas: un `SELECT COUNT(*)` siempre devuelve UNA fila, así que compararlo como cantidad de filas no tiene sentido.

Reglas (en este orden; se explican en pantalla y siempre se puede elegir a mano):
  1. Lo esperado es sí / no (true / false)            -> EXISTS: ¿la consulta devuelve filas?
  2. La consulta calcula un único valor                -> SCALAR_VALUE: se compara ese valor.
     (lista del SELECT = una sola función COUNT, SUM, AVG, MIN o MAX, sin GROUP BY en el nivel principal)
  3. Lo esperado es un número entero                   -> ROW_COUNT: cantidad de filas devueltas (o afectadas por un DML).
  4. Cualquier otro valor (texto, decimal, NULL)        -> SCALAR_VALUE: valor de la única fila que debe devolver.
"""
import re
from typing import Optional, Tuple

AGREGADO_UNICO = re.compile(r"(?is)^(COUNT|SUM|AVG|MIN|MAX)\s*\(.*\)(\s+(AS\s+)?[A-Za-z_][\w$#]*)?$")
SI = {"true", "sí", "si", "yes", "verdadero"}
NO = {"false", "no", "falso"}


def _es_palabra(texto: str, i: int, palabra: str) -> bool:
    fin = i + len(palabra)
    if texto[i:fin].upper() != palabra:
        return False
    antes_ok = i == 0 or not (texto[i - 1].isalnum() or texto[i - 1] in "_$#")
    despues_ok = fin >= len(texto) or not (texto[fin].isalnum() or texto[fin] in "_$#")
    return antes_ok and despues_ok


def _partes_select(sql: str) -> Optional[Tuple[str, str]]:
    """Devuelve (lista del SELECT, resto desde el FROM principal) o None si no empieza por SELECT."""
    s = sql.strip().rstrip(";").strip()
    m = re.match(r"(?is)^select\s+(distinct\s+|all\s+)?", s)
    if not m:
        return None
    nivel, i, inicio = 0, m.end(), m.end()
    while i < len(s):
        c = s[i]
        if c in "'\"":                       # salta literales completos
            cierre = s.find(c, i + 1)
            i = len(s) if cierre == -1 else cierre + 1
            continue
        if c == "(":
            nivel += 1
        elif c == ")":
            nivel -= 1
        elif nivel == 0 and _es_palabra(s, i, "FROM"):
            return s[inicio:i].strip(), s[i:]
        i += 1
    return s[inicio:].strip(), ""


def _tiene_en_nivel_principal(texto: str, palabra_doble: Tuple[str, str]) -> bool:
    """¿Aparece p. ej. GROUP BY fuera de paréntesis?"""
    nivel, i = 0, 0
    a, b = palabra_doble
    while i < len(texto):
        c = texto[i]
        if c in "'\"":
            cierre = texto.find(c, i + 1)
            i = len(texto) if cierre == -1 else cierre + 1
            continue
        if c == "(":
            nivel += 1
        elif c == ")":
            nivel -= 1
        elif nivel == 0 and _es_palabra(texto, i, a):
            resto = texto[i + len(a):].lstrip()
            if resto.upper().startswith(b):
                return True
        i += 1
    return False


def _hay_coma_en_nivel_principal(lista: str) -> bool:
    nivel = 0
    for c in lista:
        if c == "(":
            nivel += 1
        elif c == ")":
            nivel -= 1
        elif c == "," and nivel == 0:
            return True
    return False


def calcula_un_unico_valor(sql: str) -> bool:
    """True si la consulta es un SELECT cuya lista es una sola función de agregación sin GROUP BY principal."""
    partes = _partes_select(sql)
    if not partes:
        return False
    lista, resto = partes
    if not lista or _hay_coma_en_nivel_principal(lista) or _tiene_en_nivel_principal(resto, ("GROUP", "BY")):
        return False
    return bool(AGREGADO_UNICO.match(lista))


def inferir_validacion(sql: str, esperado: str) -> Tuple[str, str, str]:
    """Devuelve (tipo de validación, esperado normalizado, motivo en lenguaje común)."""
    e = (esperado or "").strip()
    el = e.lower()
    if el in SI or el in NO:
        return ("EXISTS", "true" if el in SI else "false",
                "Usted respondió sí/no: se comprueba si la consulta devuelve alguna fila.")
    if calcula_un_unico_valor(sql):
        return ("SCALAR_VALUE", e,
                "La consulta calcula un único valor (COUNT, SUM, AVG, MIN o MAX): se compara ese valor con el esperado.")
    if re.fullmatch(r"\d+", e):
        return ("ROW_COUNT", str(int(e)),
                "Usted indicó un número entero y la consulta devuelve filas: se compara la cantidad de filas (o de filas afectadas).")
    return ("SCALAR_VALUE", e,
            "Usted indicó un valor que no es una cantidad de filas: se compara el valor de la única fila que debe devolver la consulta.")
