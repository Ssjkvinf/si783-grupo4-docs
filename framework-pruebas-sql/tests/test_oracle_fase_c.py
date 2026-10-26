"""
Funciones nuevas contra un Oracle LOCAL DESECHABLE (nunca contra la VM de Azure): comparación automática, Analizar una tabla
(diccionario de datos real USER_TAB_COLUMNS / USER_CONSTRAINTS), guardar como suite, comparar con la ejecución anterior, reporte de
una corrida, demostración guiada y «ejecutado por».

Requisitos y guardia: los mismos que tests/test_oracle_phase2.py (RUN_ORACLE_TESTS=1, FRAMEWORK_TEST_PASSWORD, ORACLE_HOST local).
Las pruebas que rompen un dato lo restauran con los datos de infra/oracle/demo/seed_demo_data.sql.
"""
import oracledb
import pytest
from fastapi.testclient import TestClient

from app.main import app
from test_oracle_phase2 import DEMO_USER, _connect, _perfil, _quick, _scalar, _seed_demo_data, pytestmark, test_password  # noqa: F401

client = TestClient(app)
TABLA = "FRAMEWORK_TEST_ITEMS"


@pytest.fixture()
def datos():
    _seed_demo_data()
    yield
    _seed_demo_data()


def _romper_active():
    with _connect(DEMO_USER, test_password) as conn:
        conn.cursor().execute(f"UPDATE {TABLA} SET ACTIVE = 7 WHERE ID = 4")
        conn.commit()


def test_comparacion_automatica_con_oracle(datos):
    _, conn, pwd = _perfil(DEMO_USER, test_password, name="Fase C automática")
    r = client.post("/api/execute/quick", json={"connection_profile_id": conn, "password": pwd,
                                                "sql_query": f"SELECT COUNT(*) FROM {TABLA} WHERE ACTIVE = 1", "expected_result": "4"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "PASS" and d["validation_type"] == "SCALAR_VALUE" and d["validation_auto"] is True
    r = client.post("/api/execute/quick", json={"connection_profile_id": conn, "password": pwd,
                                                "sql_query": f"SELECT * FROM {TABLA} WHERE ID = 3", "expected_result": "sí"})
    assert r.json()["status"] == "PASS" and r.json()["validation_type"] == "EXISTS"


def test_analizar_tabla_lee_el_diccionario_real(datos):
    _, conn, pwd = _perfil(DEMO_USER, test_password, name="Fase C análisis")
    r = client.post("/api/analysis/table", json={"connection_profile_id": conn, "password": pwd, "tabla": TABLA})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["filas"] == 5 and d["clave_primaria"] == ["ID"]
    cols = {c["nombre"]: c for c in d["columnas"]}
    assert set(cols) == {"ID", "NAME", "ACTIVE"}
    assert cols["ACTIVE"]["valores"] == ["0", "1"] and cols["NAME"]["admite_vacios"] is False
    recomendadas = {(p["regla"], p["columna"]) for p in d["propuestas"] if p["recomendada"]}
    assert {("tabla_con_datos", None), ("sin_repetidos", "ID"), ("solo_valores", "ACTIVE")} <= recomendadas
    assert test_password not in r.text

    con_esquema = client.post("/api/analysis/table", json={"connection_profile_id": conn, "password": pwd, "tabla": f"{DEMO_USER}.{TABLA}"})
    assert con_esquema.status_code == 200, con_esquema.text
    assert con_esquema.json()["clave_primaria"] == ["ID"]
    assert client.post("/api/analysis/table", json={"connection_profile_id": conn, "password": pwd, "tabla": "NO_EXISTE_XYZ"}).status_code == 422


def test_suite_analizada_compara_corridas_y_genera_reporte(datos):
    proj, conn, pwd = _perfil(DEMO_USER, test_password, name="Fase C suite")
    d = client.post("/api/analysis/table", json={"connection_profile_id": conn, "password": pwd, "tabla": TABLA}).json()
    elegidas = [{"regla": p["regla"], "params": p["params"]} for p in d["propuestas"] if p["recomendada"]]
    g = client.post("/api/analysis/save-suite", json={"project_id": proj, "nombre_suite": "Fase C: calidad", "propuestas": elegidas})
    assert g.status_code == 201, g.text
    suite = g.json()["suite_id"]

    primera = client.post(f"/api/execute/suite/{suite}", json={"connection_profile_id": conn, "password": pwd}).json()
    assert primera["passed"] == primera["total_tests"]

    _romper_active()
    segunda = client.post(f"/api/execute/suite/{suite}", json={"connection_profile_id": conn, "password": pwd}).json()
    assert segunda["new_failures"] == 1
    assert [c["case_name"] for c in segunda["case_results"] if c["change"] == "nuevo_fallo"] == [f"{TABLA}.ACTIVE solo vale 0, 1"]

    corridas = client.get(f"/api/history/runs?suite_id={suite}").json()
    assert [c["run_id"] for c in corridas] == [segunda["run_id"], primera["run_id"]]
    html = client.get(f"/api/history/runs/{segunda['run_id']}/report").text
    assert "Antes pasaba y ahora no" in html and test_password not in html


def test_demostracion_guiada_con_oracle(datos):
    _, conn, pwd = _perfil(DEMO_USER, test_password, name="Fase C guiada")
    antes = _scalar(DEMO_USER, test_password, f"SELECT COUNT(*) FROM {TABLA}")
    r = client.post("/api/demo/guided", json={"connection_profile_id": conn, "password": pwd})
    assert r.status_code == 200, r.text
    assert r.json()["todo_como_se_esperaba"] is True
    assert _scalar(DEMO_USER, test_password, f"SELECT COUNT(*) FROM {TABLA}") == antes, "el INSERT de control debía revertirse"


def test_ejecutado_por_con_usuarios_y_oracle(datos, monkeypatch):
    monkeypatch.setenv("APP_ACCESS_ENABLED", "true")
    monkeypatch.setenv("APP_ACCESS_USERNAME", "admin")
    monkeypatch.setenv("APP_ACCESS_PASSWORD", "clave" + "-admin-ficticia")
    monkeypatch.setenv("APP_SESSION_SECRET", "secreto-de-prueba-ficticio")
    monkeypatch.setenv("ENVIRONMENT", "development")
    c = TestClient(app)
    assert c.post("/api/login", json={"username": "admin", "password": "clave" + "-admin-ficticia"}).status_code == 200
    proj = c.post("/api/projects/", json={"name": "Fase C usuarios"}).json()["id"]
    conn = c.post("/api/connections/", json={"project_id": proj, "name": "Oracle", "engine": "ORACLE", "host": "127.0.0.1", "port": 1521,
                                             "service_name": "FREEPDB1", "username": DEMO_USER, "environment_type": "TEST"}).json()["id"]
    r = c.post("/api/execute/quick", json={"connection_profile_id": conn, "password": test_password,
                                           "sql_query": f"SELECT COUNT(*) FROM {TABLA}", "expected_result": "5"})
    assert r.status_code == 200 and r.json()["status"] == "PASS", r.text
    hist = c.get(f"/api/history/?project_id={proj}").json()
    assert hist[0]["executed_by"] == "admin" and hist[0]["connection_name"] == "Oracle"
