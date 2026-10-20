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


def make_database(path: Path, rows: Optional[List[Tuple[int, str, int]]] = None) -> str:
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE DUAL (DUMMY TEXT)")
    con.execute("INSERT INTO DUAL VALUES ('X')")
    con.execute("CREATE TABLE FRAMEWORK_TEST_ITEMS (ID INTEGER PRIMARY KEY, NAME TEXT NOT NULL, ACTIVE INTEGER NOT NULL DEFAULT 1)")
    con.executemany("INSERT INTO FRAMEWORK_TEST_ITEMS VALUES (?, ?, ?)", SEED if rows is None else rows)
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
