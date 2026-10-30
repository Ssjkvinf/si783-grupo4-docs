"""
Validación automática (app/services/validacion_auto.py): la persona no tiene que elegir entre «cantidad de filas» y «valor».
Las ejecuciones usan el sustituto SQLite de Oracle (tests/fake_oracle.py); no es Oracle.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.validacion_auto import calcula_un_unico_valor, inferir_validacion
from fake_oracle import connect_factory, make_database

client = TestClient(app)


@pytest.mark.parametrize("sql, esperado, tipo, normalizado", [
    ("SELECT COUNT(*) FROM T", "5", "SCALAR_VALUE", "5"),                       # la confusión clásica: COUNT devuelve 1 fila
    ("select count(*) as total from t where a = 1", "0", "SCALAR_VALUE", "0"),
    ("SELECT MAX(ID) FROM T", "9", "SCALAR_VALUE", "9"),
    ("SELECT SUM(MONTO) total FROM VENTAS", "10.5", "SCALAR_VALUE", "10.5"),
    ("SELECT COUNT(*) FROM (SELECT C FROM T GROUP BY C HAVING COUNT(*) > 1)", "0", "SCALAR_VALUE", "0"),  # GROUP BY solo en la subconsulta
    ("SELECT ID FROM T WHERE ACTIVE = 1", "4", "ROW_COUNT", "4"),
    ("SELECT 1 FROM DUAL", "1", "ROW_COUNT", "1"),
    ("SELECT C, COUNT(*) FROM T GROUP BY C", "3", "ROW_COUNT", "3"),             # varias filas: cuenta filas
    ("SELECT COUNT(*), MAX(ID) FROM T", "1", "ROW_COUNT", "1"),                  # dos columnas: no es un único valor
    ("SELECT ID FROM T WHERE ID = 3", "sí", "EXISTS", "true"),
    ("SELECT ID FROM T WHERE ID = 3", "No", "EXISTS", "false"),
    ("SELECT ID FROM T WHERE ID = 3", "true", "EXISTS", "true"),
    ("SELECT NAME FROM T WHERE ID = 3", "Regla", "SCALAR_VALUE", "Regla"),
    ("SELECT NAME FROM T WHERE ID = 3", "NULL", "SCALAR_VALUE", "NULL"),
    ("INSERT INTO T (ID) VALUES (1)", "1", "ROW_COUNT", "1"),
    ("SELECT 'FROM' AS X FROM T", "2", "ROW_COUNT", "2"),                        # un FROM dentro de un literal no confunde
    ("SELECT COUNT(*) FROM T;", "007", "SCALAR_VALUE", "007"),
])
def test_inferencia(sql, esperado, tipo, normalizado):
    t, n, motivo = inferir_validacion(sql, esperado)
    assert (t, n) == (tipo, normalizado)
    assert motivo


def test_detector_de_valor_unico():
    assert calcula_un_unico_valor("SELECT COUNT(*) FROM T")
    assert not calcula_un_unico_valor("WITH X AS (SELECT 1 FROM DUAL) SELECT COUNT(*) FROM X")   # conservador: sin seguridad, no adivina
    assert not calcula_un_unico_valor("SELECT ID FROM T")
    assert not calcula_un_unico_valor("SELECT COUNT(*) FROM T GROUP BY C")


@pytest.fixture()
def conn(tmp_path):
    ruta = make_database(tmp_path / "o.sqlite")
    with patch("oracledb.connect", connect_factory(ruta)):
        proj = client.post("/api/projects/", json={"name": "Auto"}).json()
        c = client.post("/api/connections/", json={"project_id": proj["id"], "name": "p", "engine": "ORACLE", "host": "oracle.local",
                                                   "port": 1521, "service_name": "FREEPDB1", "username": "U", "environment_type": "TEST"}).json()
        yield proj["id"], c["id"]


def _quick(conn_id, sql, esperado, **extra):
    return client.post("/api/execute/quick", json={"connection_profile_id": conn_id, "password": "x", "sql_query": sql,
                                                   "expected_result": esperado, **extra})


def test_la_prueba_rapida_sin_tipo_compara_el_valor_de_un_count(conn):
    _, c = conn
    r = _quick(c, "SELECT COUNT(*) FROM FRAMEWORK_TEST_ITEMS", "5")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "PASS" and d["validation_type"] == "SCALAR_VALUE"
    assert d["validation_auto"] is True and "único valor" in d["validation_reason"]


def test_auto_explicito_y_si_no(conn):
    _, c = conn
    d = _quick(c, "SELECT ID FROM FRAMEWORK_TEST_ITEMS WHERE ID = 3", "sí", validation_type="AUTO").json()
    assert d["status"] == "PASS" and d["validation_type"] == "EXISTS" and d["expected_result"] == "true"
    d = _quick(c, "SELECT ID FROM FRAMEWORK_TEST_ITEMS WHERE ACTIVE = 1", "4").json()
    assert d["status"] == "PASS" and d["validation_type"] == "ROW_COUNT"


def test_si_la_persona_elige_el_tipo_se_respeta(conn):
    _, c = conn
    d = _quick(c, "SELECT COUNT(*) FROM FRAMEWORK_TEST_ITEMS", "1", validation_type="ROW_COUNT").json()
    assert d["validation_type"] == "ROW_COUNT" and d["validation_auto"] is False and d["validation_reason"] is None
    assert d["status"] == "PASS"            # 1 fila: lo que pidió, aunque no sea lo que probablemente quería


def test_un_caso_guardado_sin_tipo_queda_con_el_tipo_deducido(conn):
    proj, _ = conn
    r = client.post("/api/test-cases/", json={"project_id": proj, "name": "conteo", "sql_query": "SELECT COUNT(*) FROM T", "expected_result": "5"})
    assert r.status_code == 201, r.text
    assert r.json()["validation_type"] == "SCALAR_VALUE"
    r = client.post("/api/test-cases/", json={"project_id": proj, "name": "existe", "sql_query": "SELECT 1 FROM T WHERE ID = 1",
                                              "validation_type": "AUTO", "expected_result": "no"})
    assert r.status_code == 201 and r.json()["validation_type"] == "EXISTS" and r.json()["expected_result"] == "false"
