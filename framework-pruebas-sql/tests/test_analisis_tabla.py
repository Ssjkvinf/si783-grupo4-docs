"""
«Analizar una tabla» (POST /api/analysis/table y /api/analysis/save-suite).

Corre contra la SQLite de tests/fake_oracle.py, que imita la tabla de demostración y las vistas del diccionario de datos
(USER_TAB_COLUMNS, restricciones de clave primaria). Comprueba el perfil, las propuestas, que solo se ejecuta SELECT y que la suite
guardada da PASS sobre los mismos datos. NO es Oracle: el dialecto real del diccionario no se prueba aquí.
"""
import sqlite3
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import analisis_tabla
from fake_oracle import connect_factory, make_database

client = TestClient(app)
CLAVE = "clave_ficticia_de_prueba_123"


def _perfil(env="TEST"):
    proj = client.post("/api/projects/", json={"name": f"Análisis {env}"}).json()
    conn = client.post("/api/connections/", json={"project_id": proj["id"], "name": "perfil", "engine": "ORACLE", "host": "oracle.local",
                                                  "port": 1521, "service_name": "FREEPDB1", "username": "FRAMEWORK_TEST",
                                                  "environment_type": env}).json()
    return proj["id"], conn["id"]


@pytest.fixture()
def base(tmp_path):
    ruta = make_database(tmp_path / "objetivo.sqlite")
    with patch("oracledb.connect", connect_factory(ruta)):
        yield ruta


def _analizar(conn, tabla="FRAMEWORK_TEST_ITEMS"):
    return client.post("/api/analysis/table", json={"connection_profile_id": conn, "password": CLAVE, "tabla": tabla})


def test_perfila_la_tabla_y_propone_reglas_a_partir_de_los_datos(base):
    _, conn = _perfil()
    r = _analizar(conn)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["filas"] == 5 and d["clave_primaria"] == ["ID"]
    cols = {c["nombre"]: c for c in d["columnas"]}
    assert cols["ID"]["clave_primaria"] is True and cols["ACTIVE"]["valores"] == ["0", "1"]
    assert cols["NAME"]["distintos"] == 5
    recomendadas = {(p["regla"], p["columna"]) for p in d["propuestas"] if p["recomendada"]}
    assert ("tabla_con_datos", None) in recomendadas
    assert ("sin_repetidos", "ID") in recomendadas
    assert ("solo_valores", "ACTIVE") in recomendadas
    assert all(p["sql"].upper().startswith("SELECT") for p in d["propuestas"])
    assert CLAVE not in r.text and "aviso" in d


def test_la_suite_guardada_pasa_sobre_los_mismos_datos_y_falla_si_cambian(base):
    proj, conn = _perfil()
    d = _analizar(conn).json()
    elegidas = [{"regla": p["regla"], "params": p["params"]} for p in d["propuestas"] if p["recomendada"]]
    g = client.post("/api/analysis/save-suite", json={"project_id": proj, "nombre_suite": "Calidad de FRAMEWORK_TEST_ITEMS", "propuestas": elegidas})
    assert g.status_code == 201, g.text
    suite_id = g.json()["suite_id"]
    assert len(g.json()["casos"]) == len(elegidas)

    res = client.post(f"/api/execute/suite/{suite_id}", json={"connection_profile_id": conn, "password": CLAVE}).json()
    assert res["passed"] == res["total_tests"] and res["failed"] == 0 and res["errors"] == 0

    con = sqlite3.connect(base)
    con.execute("UPDATE FRAMEWORK_TEST_ITEMS SET ACTIVE = 7 WHERE ID = 4")
    con.commit()
    con.close()
    res = client.post(f"/api/execute/suite/{suite_id}", json={"connection_profile_id": conn, "password": CLAVE}).json()
    fallidos = [c["case_name"] for c in res["case_results"] if c["status"] == "FAIL"]
    assert fallidos == ["FRAMEWORK_TEST_ITEMS.ACTIVE solo vale 0, 1"]


def test_tabla_inexistente_y_nombre_inseguro(base):
    _, conn = _perfil()
    r = _analizar(conn, "NO_EXISTE")
    assert r.status_code == 422 and "No se encontró la tabla" in r.json()["detail"]
    r = _analizar(conn, "X; DROP TABLE FRAMEWORK_TEST_ITEMS")
    assert r.status_code == 422


def test_no_se_permite_en_production(base):
    _, conn = _perfil("PRODUCTION")
    r = _analizar(conn)
    assert r.status_code == 409


def test_solo_ejecuta_select():
    class Espia:
        environment_type = "TEST"

        def __init__(self):
            self.sql = []

        def execute_query(self, sql, params=None, confirm_staging_dml=False):
            self.sql.append(sql)
            if "TAB_COLUMNS" in sql:
                return {"success": True, "rows": [("ID", "NUMBER", "N"), ("ESTADO", "VARCHAR2", "Y")]}
            if "CONSTRAINT" in sql:
                return {"success": True, "rows": [("ID",)]}
            if "DISTINCT ESTADO FROM" in sql:
                return {"success": True, "rows": [("A",), ("B",)]}
            if "COUNT(DISTINCT ESTADO)" in sql:
                return {"success": True, "rows": [(2,)]}
            if "MIN(" in sql:
                return {"success": True, "rows": [(1, 9)]}
            return {"success": True, "rows": [(9,)] if "COUNT(*) FROM CLIENTES" == sql.split(" WHERE")[0].replace("SELECT ", "") else [(0,)]}

    espia = Espia()
    d = analisis_tabla.analizar(espia, "CLIENTES")
    assert espia.sql and all(s.strip().upper().startswith("SELECT") for s in espia.sql)
    assert any(p["regla"] == "solo_valores" and p["params"]["valores"] == "A, B" for p in d["propuestas"])


def test_guardar_suite_vuelve_a_validar_las_reglas(base):
    proj, _ = _perfil()
    r = client.post("/api/analysis/save-suite", json={"project_id": proj, "nombre_suite": "Mala",
                                                      "propuestas": [{"regla": "sin_nulos", "params": {"tabla": "T; DROP", "columna": "C"}}]})
    assert r.status_code == 422
