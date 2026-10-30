"""
Historial legible: cada registro trae los nombres del caso, la suite y la conexión, y se puede filtrar por quién ejecutó.
"""
from fastapi.testclient import TestClient

from app.main import app
from app.models.connection import ConnectionProfile
from app.models.history import ExecutionHistory
from app.models.project import Project
from app.models.suite import TestSuite
from app.models.test_case import TestCase

client = TestClient(app)


def _escenario(db):
    p = Project(name="Proyecto historial")
    db.add(p)
    db.commit()
    conn = ConnectionProfile(project_id=p.id, name="Oracle QA", host="db.example.com", port=1521, service_name="FREEPDB1",
                             username="qa", environment_type="TEST")
    tc = TestCase(project_id=p.id, name="Hay clientes", sql_query="SELECT * FROM clientes", validation_type="ROW_COUNT", expected_result="3")
    suite = TestSuite(project_id=p.id, name="Reglas de clientes")
    db.add_all([conn, tc, suite])
    db.commit()
    comun = dict(project_id=p.id, duration_ms=1.0, executed_sql="SELECT 1", status="PASS")
    db.add_all([
        ExecutionHistory(test_case_id=tc.id, suite_id=suite.id, connection_profile_id=conn.id, executed_by="ana.qa", **comun),
        ExecutionHistory(test_case_id=None, connection_profile_id=conn.id, executed_by="luis", **comun),
        ExecutionHistory(test_case_id=tc.id, executed_by=None, **comun),
    ])
    db.commit()
    return p.id


def test_historial_incluye_nombres_de_caso_suite_y_conexion(setup_isolated_db):
    pid = _escenario(setup_isolated_db)
    filas = client.get(f"/api/history/?project_id={pid}").json()
    con_suite = next(h for h in filas if h["suite_id"] is not None)
    assert con_suite["case_name"] == "Hay clientes"
    assert con_suite["suite_name"] == "Reglas de clientes"
    assert con_suite["connection_name"] == "Oracle QA"
    rapida = next(h for h in filas if h["test_case_id"] is None)
    assert rapida["case_name"] is None and rapida["suite_name"] is None


def test_historial_se_filtra_por_quien_ejecuto(setup_isolated_db):
    pid = _escenario(setup_isolated_db)
    filas = client.get(f"/api/history/?project_id={pid}&executed_by=ana.qa").json()
    assert [h["executed_by"] for h in filas] == ["ana.qa"]
    assert client.get(f"/api/history/?project_id={pid}&executed_by=nadie").json() == []


def test_detalle_de_un_registro_tambien_trae_los_nombres(setup_isolated_db):
    pid = _escenario(setup_isolated_db)
    hid = client.get(f"/api/history/?project_id={pid}&executed_by=ana.qa").json()[0]["id"]
    assert client.get(f"/api/history/{hid}").json()["suite_name"] == "Reglas de clientes"
