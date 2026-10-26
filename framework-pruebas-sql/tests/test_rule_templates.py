"""
Asistente de reglas (app/services/rule_templates.py y /api/rules/*).

Las consultas generadas se EJECUTAN de verdad contra una base SQLite que imita la tabla de demostración a través de la interfaz de
oracledb (tests/fake_oracle.py). Eso comprueba que el SQL es válido y que da PASS/FAIL como corresponde; NO prueba el dialecto de
Oracle (para eso están las pruebas contra Oracle real).
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.security.sql_policy import validate_sql_statement
from app.services import rule_templates as rt
from fake_oracle import connect_factory, make_database

client = TestClient(app)

EJEMPLOS = {r["id"]: {p["nombre"]: p["ejemplo"] for p in r["parametros"]} for r in rt.REGLAS}


def test_el_catalogo_tiene_ocho_reglas_con_campos_y_ejemplos():
    assert len(rt.REGLAS) == 8
    assert len({r["id"] for r in rt.REGLAS}) == 8
    for r in rt.REGLAS:
        assert r["titulo"] and r["descripcion"] and r["validacion"] in ("SCALAR_VALUE", "EXISTS", "ROW_COUNT")
        assert r["parametros"] and all(p["nombre"] and p["etiqueta"] and p["ejemplo"] for p in r["parametros"])


@pytest.mark.parametrize("regla", [r["id"] for r in rt.REGLAS])
def test_cada_regla_genera_un_select_aceptado_incluso_en_produccion(regla):
    out = rt.construir(regla, EJEMPLOS[regla])
    assert out["sql"].upper().startswith("SELECT")
    for ambiente in ("TEST", "STAGING", "PRODUCTION"):
        ok, tipo, error = validate_sql_statement(out["sql"], ambiente)
        assert ok and tipo == "SELECT", (ambiente, error)
    assert out["validation_type"] == next(r["validacion"] for r in rt.REGLAS if r["id"] == regla)
    assert out["explicacion"] and out["expected_result"] != ""


def test_las_consultas_generadas_son_las_esperadas():
    assert rt.construir("sin_nulos", {"tabla": "CLIENTES", "columna": "EMAIL"})["sql"] == "SELECT COUNT(*) FROM CLIENTES WHERE EMAIL IS NULL"
    out = rt.construir("solo_valores", {"tabla": "ESQ.PEDIDOS", "columna": "ESTADO", "valores": "NUEVO, PAGADO, 3"})
    assert out["sql"] == "SELECT COUNT(*) FROM ESQ.PEDIDOS WHERE ESTADO NOT IN ('NUEVO', 'PAGADO', 3)"
    assert out["expected_result"] == "0"
    out = rt.construir("contar_con_valor", {"tabla": "T", "columna": "C", "valor": "ok", "n": "7"})
    assert out["sql"] == "SELECT COUNT(*) FROM T WHERE C = 'ok'" and out["expected_result"] == "7"
    out = rt.construir("rango_numerico", {"tabla": "T", "columna": "C", "minimo": "0", "maximo": "10.5"})
    assert out["sql"] == "SELECT COUNT(*) FROM T WHERE C < 0 OR C > 10.5"


@pytest.fixture()
def oracle_simulado(tmp_path):
    ruta = make_database(tmp_path / "objetivo.sqlite")
    with patch("oracledb.connect", connect_factory(ruta)):
        yield


def _perfil():
    proj = client.post("/api/projects/", json={"name": "Asistente"}).json()
    conn = client.post("/api/connections/", json={"project_id": proj["id"], "name": "perfil", "engine": "ORACLE", "host": "oracle.local",
                                                  "port": 1521, "service_name": "FREEPDB1", "username": "FRAMEWORK_TEST",
                                                  "environment_type": "TEST"}).json()
    return conn["id"]


def _ejecutar(conn, regla, params):
    out = client.post("/api/rules/build", json={"rule_id": regla, "params": params})
    assert out.status_code == 200, out.text
    b = out.json()
    r = client.post("/api/execute/quick", json={"connection_profile_id": conn, "password": "clave_de_prueba", "sql_query": b["sql"],
                                                "validation_type": b["validation_type"], "expected_result": b["expected_result"]})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("regla", [r["id"] for r in rt.REGLAS])
def test_con_los_datos_de_demostracion_todas_las_reglas_de_ejemplo_dan_pass(oracle_simulado, regla):
    res = _ejecutar(_perfil(), regla, EJEMPLOS[regla])
    assert res["status"] == "PASS", res


def test_si_los_datos_no_cumplen_la_regla_da_fail_con_explicacion(oracle_simulado):
    conn = _perfil()
    res = _ejecutar(conn, "filas_exactas", {"tabla": "FRAMEWORK_TEST_ITEMS", "n": "6"})
    assert res["status"] == "FAIL" and "esperabas 6 y devolvió 5" in res["reason"]
    res = _ejecutar(conn, "solo_valores", {"tabla": "FRAMEWORK_TEST_ITEMS", "columna": "ACTIVE", "valores": "1"})
    assert res["status"] == "FAIL" and res["obtained_value"] == "1"
    res = _ejecutar(conn, "existe_fila", {"tabla": "FRAMEWORK_TEST_ITEMS", "columna": "ID", "valor": "99"})
    assert res["status"] == "FAIL"


def test_una_tabla_inexistente_da_error_y_no_fail(oracle_simulado):
    res = _ejecutar(_perfil(), "sin_nulos", {"tabla": "TABLA_QUE_NO_EXISTE", "columna": "X"})
    assert res["status"] == "ERROR"


@pytest.mark.parametrize("tabla", ["T; DROP TABLE X", "T WHERE 1=1", "T--", "T,U", "A.B.C", '"T"', "1T", "", "T U"])
def test_las_tablas_con_sql_o_caracteres_raros_se_rechazan(tabla):
    r = client.post("/api/rules/build", json={"rule_id": "sin_nulos", "params": {"tabla": tabla, "columna": "C"}})
    assert r.status_code == 422, tabla


@pytest.mark.parametrize("columna", ["C) OR (1=1", "C; DELETE FROM T", "DROP", "select", "MERGE", "C C", "C'--"])
def test_las_columnas_peligrosas_o_reservadas_se_rechazan(columna):
    r = client.post("/api/rules/build", json={"rule_id": "sin_nulos", "params": {"tabla": "T", "columna": columna}})
    assert r.status_code == 422, columna


@pytest.mark.parametrize("valor", ["x' OR '1'='1", "a;b", "a\nb", "x" * 51, "a(b)", "a\\b"])
def test_los_valores_con_comillas_o_signos_peligrosos_se_rechazan(valor):
    r = client.post("/api/rules/build", json={"rule_id": "existe_fila", "params": {"tabla": "T", "columna": "C", "valor": valor}})
    assert r.status_code == 422, valor
    r = client.post("/api/rules/build", json={"rule_id": "solo_valores", "params": {"tabla": "T", "columna": "C", "valores": f"1, {valor}"}})
    assert r.status_code == 422, valor


def test_otros_datos_invalidos():
    def codigo(regla, **p):
        return client.post("/api/rules/build", json={"rule_id": regla, "params": p}).status_code
    assert codigo("filas_exactas", tabla="T", n="-1") == 422
    assert codigo("filas_exactas", tabla="T", n="3.5") == 422
    assert codigo("filas_exactas", tabla="T", n="abc") == 422
    assert codigo("rango_numerico", tabla="T", columna="C", minimo="5", maximo="1") == 422
    assert codigo("rango_numerico", tabla="T", columna="C", minimo="a", maximo="1") == 422
    assert codigo("solo_valores", tabla="T", columna="C", valores=",".join(str(i) for i in range(21))) == 422
    assert codigo("regla_que_no_existe", tabla="T") == 422
    assert codigo("sin_nulos", tabla="T") == 422                      # falta la columna


def test_el_mensaje_de_campos_faltantes_es_claro_y_la_api_no_acepta_campos_extra():
    r = client.post("/api/rules/build", json={"rule_id": "sin_nulos", "params": {"tabla": "T"}})
    assert r.status_code == 422 and "Complete: Columna" in r.json()["detail"]
    r = client.post("/api/rules/build", json={"rule_id": "sin_nulos", "params": {}, "sql": "DROP TABLE X"})
    assert r.status_code == 422


def test_el_catalogo_se_publica_por_la_api():
    r = client.get("/api/rules/templates")
    assert r.status_code == 200 and len(r.json()) == 8
    assert {x["id"] for x in r.json()} == {x["id"] for x in rt.REGLAS}
