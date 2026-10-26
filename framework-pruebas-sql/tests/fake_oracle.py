"""
Sustituto de Oracle para pruebas: una base SQLite con las mismas tablas de la demostración que se usa a través de la
interfaz de `oracledb.connect`. Ejecuta SQL REAL (no respuestas enlatadas), pero NO ES ORACLE: sirve para probar la CLI,
la API y los reportes de extremo a extremo sin Docker. Las pruebas contra Oracle real están en test_oracle_*.py.
"""
import sqlite3
from pathlib import Path
from typing import List, Optional, Tuple

SEED = [(1, "Cuaderno", 1), (2, "Lapicero", 1), (3, "Regla", 1), (4, "Borrador", 0), (5, "Tijera", 1)]


class _Cursor:
    def __init__(self, cur: sqlite3.Cursor):
        self._c = cur

    def execute(self, sql, params=None):
        self._c.execute(sql, params or {})
        return self

    def fetchmany(self, n):
        return self._c.fetchmany(n)

    @property
    def description(self):
        return self._c.description

    @property
    def rowcount(self):
        return self._c.rowcount

    def close(self):
        self._c.close()


class _Connection:
    call_timeout = 0
    autocommit = False

    def __init__(self, path: str):
        self._conn = sqlite3.connect(path, check_same_thread=False)

    def cursor(self):
        return _Cursor(self._conn.cursor())

    def rollback(self):
        self._conn.rollback()

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def _crear_diccionario(con: sqlite3.Connection) -> None:
    """Vistas con los nombres del diccionario de datos de Oracle (USER_/ALL_TAB_COLUMNS, restricciones de clave primaria).
    Imitan solo las columnas que usa «Analizar una tabla»; los tipos se traducen a los de Oracle (INTEGER → NUMBER, TEXT → VARCHAR2)."""
    tipo = "CASE UPPER(p.type) WHEN 'INTEGER' THEN 'NUMBER' WHEN 'TEXT' THEN 'VARCHAR2' WHEN 'REAL' THEN 'NUMBER' ELSE UPPER(p.type) END"
    columnas = (f"m.name AS TABLE_NAME, p.name AS COLUMN_NAME, {tipo} AS DATA_TYPE, "
                "CASE WHEN p.\"notnull\" = 1 OR p.pk > 0 THEN 'N' ELSE 'Y' END AS NULLABLE, p.cid + 1 AS COLUMN_ID "
                "FROM sqlite_master m, pragma_table_info(m.name) p WHERE m.type = 'table'")
    con.execute(f"CREATE VIEW USER_TAB_COLUMNS AS SELECT {columnas}")
    con.execute(f"CREATE VIEW ALL_TAB_COLUMNS AS SELECT 'FRAMEWORK_TEST' AS OWNER, {columnas}")
    restricciones = ("'PK_' || m.name AS CONSTRAINT_NAME, 'P' AS CONSTRAINT_TYPE, m.name AS TABLE_NAME FROM sqlite_master m "
                     "WHERE m.type = 'table' AND EXISTS (SELECT 1 FROM pragma_table_info(m.name) q WHERE q.pk > 0)")
    con.execute(f"CREATE VIEW USER_CONSTRAINTS AS SELECT {restricciones}")
    con.execute(f"CREATE VIEW ALL_CONSTRAINTS AS SELECT 'FRAMEWORK_TEST' AS OWNER, {restricciones}")
    cols_pk = ("'PK_' || m.name AS CONSTRAINT_NAME, m.name AS TABLE_NAME, p.name AS COLUMN_NAME "
               "FROM sqlite_master m, pragma_table_info(m.name) p WHERE m.type = 'table' AND p.pk > 0")
    con.execute(f"CREATE VIEW USER_CONS_COLUMNS AS SELECT {cols_pk}")
    con.execute(f"CREATE VIEW ALL_CONS_COLUMNS AS SELECT 'FRAMEWORK_TEST' AS OWNER, {cols_pk}")


def make_database(path: Path, rows: Optional[List[Tuple[int, str, int]]] = None) -> str:
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE DUAL (DUMMY TEXT)")
    con.execute("INSERT INTO DUAL VALUES ('X')")
    con.execute("CREATE TABLE FRAMEWORK_TEST_ITEMS (ID INTEGER PRIMARY KEY, NAME TEXT NOT NULL, ACTIVE INTEGER NOT NULL DEFAULT 1)")
    con.executemany("INSERT INTO FRAMEWORK_TEST_ITEMS VALUES (?, ?, ?)", SEED if rows is None else rows)
    _crear_diccionario(con)
    con.commit()
    con.close()
    return str(path)


def connect_factory(path: str, calls: Optional[list] = None, wrong_password: str = "mala"):
    """Devuelve una función con la firma de oracledb.connect que abre la base falsa (y registra las llamadas)."""
    def connect(user=None, password=None, dsn=None, **kwargs):
        if calls is not None:
            calls.append({"user": user, "dsn": dsn})
        if password == wrong_password:
            raise Exception("ORA-01017: invalid username/password; logon denied")
        return _Connection(path)
    return connect
