"""
Comparar con la ejecución anterior, corridas de una suite y reporte descargable de una corrida.

Corre contra la SQLite de tests/fake_oracle.py (NO es Oracle): ejecuta la suite de reglas de la demostración dos veces, rompe un dato
entre medio y comprueba que la segunda corrida marca el «nuevo fallo», que /history/runs agrupa las corridas y que el reporte
HTML y el Excel por corrida se descargan con el contenido esperado.
"""
import io
import sqlite3
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.main import app
from app.services.comparacion import clasificar
from fake_oracle import connect_factory, make_database

client = TestClient(app)
CLAVE = "clave_ficticia_de_prueba_123"


@pytest.fixture()
def escenario(tmp_path):
    ruta = make_database(tmp_path / "objetivo.sqlite")
    with patch("oracledb.connect", connect_factory(ruta)):
        proj = client.post("/api/projects/", json={"name": "Comparación"}).json()["id"]
        conn = client.post("/api/connections/", json={"project_id": proj, "name": "perfil", "engine": "ORACLE", "host": "oracle.local",
                                                      "port": 1521, "service_name": "FREEPDB1", "username": "FRAMEWORK_TEST",
                                                      "environment_type": "TEST"}).json()["id"]
        esc = client.post("/api/demo/scenario", json={"project_id": proj}).json()
        yield {"ruta": ruta, "conn": conn, "suite": esc["rules_suite"]["suite_id"]}


def _ejecutar(e):
    r = client.post(f"/api/execute/suite/{e['suite']}", json={"connection_profile_id": e["conn"], "password": CLAVE})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("antes,ahora,esperado", [(None, "PASS", "primera_vez"), ("PASS", "PASS", "igual"), ("PASS", "FAIL", "nuevo_fallo"),
                                                  ("ERROR", "PASS", "corregido"), ("FAIL", "ERROR", "cambio")])
def test_clasificar(antes, ahora, esperado):
    assert clasificar(antes, ahora) == esperado


def test_la_segunda_corrida_marca_el_nuevo_fallo(escenario):
    primera = _ejecutar(escenario)
    assert {c["change"] for c in primera["case_results"]} == {"primera_vez"}
    assert primera["new_failures"] == 0

    con = sqlite3.connect(escenario["ruta"])
    con.execute("UPDATE FRAMEWORK_TEST_ITEMS SET ACTIVE = 7 WHERE ID = 4")
    con.commit()
    con.close()

    segunda = _ejecutar(escenario)
    nuevos = [c for c in segunda["case_results"] if c["change"] == "nuevo_fallo"]
    assert segunda["new_failures"] == len(nuevos) >= 1
    assert all(c["previous_status"] == "PASS" and c["status"] != "PASS" for c in nuevos)
    assert any(c["change"] == "igual" for c in segunda["case_results"])


def test_corridas_de_la_suite_y_reporte(escenario):
    primera = _ejecutar(escenario)
    segunda = _ejecutar(escenario)
    corridas = client.get(f"/api/history/runs?suite_id={escenario['suite']}").json()
    assert [c["run_id"] for c in corridas] == [segunda["run_id"], primera["run_id"]]
    assert corridas[0]["total"] == segunda["total_tests"] and corridas[0]["passed"] == segunda["passed"]

    r = client.get(f"/api/history/runs/{segunda['run_id']}/report")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    assert "default-src 'none'" in r.headers["content-security-policy"]
    html = r.text
    assert "Reporte de ejecución" in html and segunda["suite_name"] in html
    assert "Igual que la vez anterior" in html and CLAVE not in html
    assert "<script" not in html.lower()

    x = client.get(f"/api/excel/results/export?run_id={segunda['run_id']}")
    assert x.status_code == 200
    hoja = load_workbook(io.BytesIO(x.content)).worksheets[0]
    filas_con_datos = [f for f in hoja.iter_rows(values_only=True) if any(v is not None for v in f)]
    assert len(filas_con_datos) >= segunda["total_tests"]


def test_reporte_inexistente_y_suite_inexistente():
    assert client.get("/api/history/runs/no-existe/report").status_code == 404
    assert client.get("/api/history/runs?suite_id=999999").status_code == 404


def test_el_reporte_escapa_el_texto_guardado(setup_isolated_db):
    from app.models.history import ExecutionHistory
    from app.models.project import Project
    p = Project(name="Escape")
    setup_isolated_db.add(p)
    setup_isolated_db.commit()
    setup_isolated_db.add(ExecutionHistory(project_id=p.id, status="FAIL", duration_ms=1, executed_sql="SELECT '<script>x</script>' FROM DUAL",
                                           expected_result="<b>1</b>", actual_result="0", run_id="corrida-escape"))
    setup_isolated_db.commit()
    html = client.get("/api/history/runs/corrida-escape/report").text
    assert "<script>x</script>" not in html and "&lt;script&gt;" in html and "&lt;b&gt;1&lt;/b&gt;" in html
