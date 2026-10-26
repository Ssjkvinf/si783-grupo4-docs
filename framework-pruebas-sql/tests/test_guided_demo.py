"""
Demostración guiada (POST /api/demo/guided): reglas -> FAIL/ERROR -> control de cambios (INSERT revertido, DROP rechazado).

Se ejecuta de verdad contra una SQLite que imita la tabla de demostración (tests/fake_oracle.py): comprueba el flujo, el orden de los
casos, el rollback y el rechazo del DROP en ESTE sustituto. NO es Oracle; con Oracle real esto lo cubre tests/test_oracle_phase2.py.
"""
import sqlite3
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from fake_oracle import connect_factory, make_database

client = TestClient(app)
CLAVE = "clave_ficticia_de_prueba_123"


def _perfil(env="TEST"):
    proj = client.post("/api/projects/", json={"name": f"Guiada {env}"}).json()
    conn = client.post("/api/connections/", json={"project_id": proj["id"], "name": "perfil", "engine": "ORACLE", "host": "oracle.local",
                                                  "port": 1521, "service_name": "FREEPDB1", "username": "FRAMEWORK_TEST",
                                                  "environment_type": env}).json()
    return proj["id"], conn["id"]


def _filas(ruta):
    con = sqlite3.connect(ruta)
    try:
        return con.execute("SELECT COUNT(*) FROM FRAMEWORK_TEST_ITEMS").fetchone()[0]
    finally:
        con.close()


@pytest.fixture()
def base(tmp_path):
    ruta = make_database(tmp_path / "objetivo.sqlite")
    llamadas = []
    with patch("oracledb.connect", connect_factory(ruta, llamadas)):
        yield {"ruta": ruta, "llamadas": llamadas}


def test_la_demostracion_completa_da_lo_que_el_guion_espera_y_no_deja_cambios(base):
    proj, conn = _perfil()
    r = client.post("/api/demo/guided", json={"connection_profile_id": conn, "password": CLAVE})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ambiente"] == "TEST" and d["todo_como_se_esperaba"] is True
    assert [p["passed"] for p in d["pasos"]] == [5, 0, 3] and [p["failed"] for p in d["pasos"]] == [0, 1, 0] and [p["errors"] for p in d["pasos"]] == [0, 1, 1]
    control = {c["case_name"]: c for c in d["pasos"][2]["casos"]}
    insert = control["Control: INSERT de prueba (se revierte)"]
    assert insert["status"] == "PASS"
    drop = control["Control: DROP TABLE rechazado antes de llegar a Oracle"]
    assert drop["status"] == "ERROR" and "Rechazado" in (drop["error_message"] or "") and drop["como_se_esperaba"] is True
    assert _filas(base["ruta"]) == 5, "el INSERT debía revertirse"
    assert CLAVE not in r.text


def test_el_insert_se_ejecuta_antes_que_los_conteos_porque_la_suite_tiene_orden_fijo(base):
    proj, conn = _perfil()
    esc = client.post("/api/demo/scenario", json={"project_id": proj}).json()
    suite = client.get(f"/api/suites/{esc['control_suite']['suite_id']}").json()
    assert [c["name"] for c in suite["test_cases"]][0] == "Control: INSERT de prueba (se revierte)"
    ids = [c["id"] for c in suite["test_cases"]]
    assert ids == sorted(ids)


def test_con_un_dato_roto_la_demostracion_lo_dice_en_lugar_de_fingir(tmp_path):
    ruta = make_database(tmp_path / "roto.sqlite", rows=[(1, "Cuaderno", 1), (2, "Lapicero", 1), (3, "Regla", 1), (4, "Borrador", 7), (5, "Tijera", 1)])
    with patch("oracledb.connect", connect_factory(ruta)):
        proj, conn = _perfil()
        d = client.post("/api/demo/guided", json={"connection_profile_id": conn, "password": CLAVE}).json()
    assert d["todo_como_se_esperaba"] is False
    reglas = d["pasos"][0]
    assert reglas["failed"] == 1 and reglas["todo_como_se_esperaba"] is False
    mala = [c for c in reglas["casos"] if not c["como_se_esperaba"]]
    assert len(mala) == 1 and mala[0]["case_name"] == "ACTIVE solo vale 0 o 1" and mala[0]["status"] == "FAIL"


@pytest.mark.parametrize("env", ["STAGING", "PRODUCTION"])
def test_fuera_de_test_se_rechaza_sin_abrir_ninguna_conexion(base, env):
    proj, conn = _perfil(env)
    r = client.post("/api/demo/guided", json={"connection_profile_id": conn, "password": CLAVE})
    assert r.status_code == 409 and "TEST" in r.json()["detail"]
    assert base["llamadas"] == []


def test_perfil_inexistente_y_campos_de_mas(base):
    assert client.post("/api/demo/guided", json={"connection_profile_id": 99999, "password": CLAVE}).status_code == 404
    proj, conn = _perfil()
    assert client.post("/api/demo/guided", json={"connection_profile_id": conn, "password": CLAVE, "dsn": "otro:1521/x"}).status_code == 422
    assert base["llamadas"] == []


def test_con_una_contrasena_incorrecta_todo_es_error_y_no_se_filtra_la_clave(tmp_path):
    ruta = make_database(tmp_path / "o.sqlite")
    # por defecto, la clave «mala» es la que el sustituto de Oracle rechaza
    with patch("oracledb.connect", connect_factory(ruta)):
        proj, conn = _perfil()
        r = client.post("/api/demo/guided", json={"connection_profile_id": conn, "password": "mala"})
    assert r.status_code == 200 and r.json()["todo_como_se_esperaba"] is False
    assert "mala" not in r.text.replace("malas", "")


def test_las_demostraciones_quedan_contadas_en_el_panel_de_uso(base):
    proj, conn = _perfil()
    client.post("/api/demo/scenario", json={"project_id": proj})
    client.post("/api/demo/guided", json={"connection_profile_id": conn, "password": CLAVE})
    eventos = {e["tipo"]: e["cantidad"] for e in client.get(f"/api/usage/summary?days=7&project_id={proj}").json()["eventos"]}
    assert eventos.get("demo_scenario_loaded") == 1 and eventos.get("demo_guided_run") == 1
