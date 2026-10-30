"""
Fase 4 — dashboard de utilización: las métricas salen SOLO de datos persistidos.
Pruebas locales con base SQLite desechable en memoria (conftest) y Oracle simulado donde hace falta ejecutar.
"""
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.history import ExecutionHistory
from app.models.project import Project
from app.models.suite import TestSuite
from app.models.test_case import TestCase
from app.services.usage_service import build_summary, record_event

client = TestClient(app)
AHORA = datetime(2026, 10, 19, 15, 30, 0)          # instante fijo (UTC) para que las pruebas sean deterministas


def _db():
    return next(app.dependency_overrides[get_db]())


def _hist(db, project_id, status="PASS", dias_atras=0, caso=None, suite=None, run_id=None, origen=None, duracion=10.0):
    h = ExecutionHistory(project_id=project_id, test_case_id=caso, suite_id=suite, status=status, duration_ms=duracion,
                         executed_sql="SELECT 1 FROM DUAL", executed_at=AHORA - timedelta(days=dias_atras, hours=1),
                         trigger_source=origen, run_id=run_id, rowcount=1)
    db.add(h)
    db.commit()
    return h


@pytest.fixture()
def escenario():
    """Dos proyectos, casos y suites, y un historial repartido en varios días."""
    db = _db()
    p1, p2 = Project(name="Proyecto Uno"), Project(name="Proyecto Dos")
    db.add_all([p1, p2])
    db.commit()
    c1 = TestCase(project_id=p1.id, name="Caso A", sql_query="SELECT 1 FROM DUAL", expected_result="1", validation_type="ROW_COUNT")
    c2 = TestCase(project_id=p1.id, name="Caso B", sql_query="SELECT 2 FROM DUAL", expected_result="1", validation_type="ROW_COUNT")
    c3 = TestCase(project_id=p2.id, name="Caso C", sql_query="SELECT 3 FROM DUAL", expected_result="1", validation_type="ROW_COUNT")
    s1 = TestSuite(project_id=p1.id, name="Suite 1")
    db.add_all([c1, c2, c3, s1])
    db.commit()
    s1.test_cases.extend([c1, c2])
    db.commit()
    run_a, run_b = str(uuid.uuid4()), str(uuid.uuid4())
    # hoy (AHORA - 1 h): una corrida de suite con 2 casos (PASS, FAIL) desde la UI
    _hist(db, p1.id, "PASS", 0, c1.id, s1.id, run_a, "UI")
    _hist(db, p1.id, "FAIL", 0, c2.id, s1.id, run_a, "UI")
    # hace 2 días: otra corrida de la suite desde GitHub Actions (PASS, PASS)
    _hist(db, p1.id, "PASS", 2, c1.id, s1.id, run_b, "GITHUB_ACTIONS")
    _hist(db, p1.id, "PASS", 2, c2.id, s1.id, run_b, "GITHUB_ACTIONS")
    # caso suelto desde la CLI, ayer; una prueba rápida (sin caso) hoy; un ERROR antiguo sin origen en el proyecto 2
    _hist(db, p1.id, "PASS", 1, c1.id, None, None, "CLI")
    _hist(db, p1.id, "PASS", 0, None, None, None, "INICIO")
    _hist(db, p2.id, "ERROR", 3, c3.id, None, None, None)
    # fuera del periodo de 30 días (hace 40 días): no debe contarse en el periodo, pero sí en el histórico
    _hist(db, p1.id, "FAIL", 40, c1.id, None, None, "UI")
    return {"p1": p1.id, "p2": p2.id, "c1": c1.id, "c2": c2.id, "c3": c3.id, "s1": s1.id, "db": db}


# ------------------------------------------------------------------------------------------ cifras

def test_dashboard_sin_datos_explica_el_estado_y_no_inventa_cifras():
    db = _db()
    r = build_summary(db, days=30, now=AHORA)

    assert r["hay_datos"] is False
    assert "Todavía no hay ejecuciones" in r["mensaje_vacio"]
    assert r["tarjetas"]["total_ejecuciones"] == 0
    assert r["tarjetas"]["tasa_pass"] is None and r["tarjetas"]["duracion_media_ms"] is None   # None, no 0 %: no hay base de cálculo
    assert len(r["por_fecha"]) == 30 and all(d["total"] == 0 for d in r["por_fecha"])
    assert r["top_casos"] == [] and r["top_suites"] == [] and r["proyectos"] == [] and r["historico"]["total"] == 0


def test_dashboard_periodo_vacio_pero_con_historico_lo_dice(escenario):
    db = escenario["db"]
    r = build_summary(db, days=1, now=AHORA + timedelta(days=100))     # ventana sin ejecuciones, histórico existente
    assert r["hay_datos"] is False
    assert "Hay 8 ejecuciones anteriores" in r["mensaje_vacio"]


def test_dashboard_cifras_del_periodo(escenario):
    r = build_summary(escenario["db"], days=30, now=AHORA)
    t = r["tarjetas"]

    assert t["total_ejecuciones"] == 7                      # la de hace 40 días queda fuera
    assert (t["pass"], t["fail"], t["error"]) == (5, 1, 1)
    assert t["tasa_pass"] == pytest.approx(71.4, abs=0.05)
    assert t["casos_distintos"] == 3                        # A, B y C (la prueba rápida no cuenta como caso guardado)
    assert t["proyectos_activos"] == 2
    assert t["corridas_de_suite"] == 2                      # dos run_id distintos de la suite
    assert t["duracion_media_ms"] == 10.0
    assert r["historico"]["total"] == 8
    assert r["periodo"]["zona"] == "UTC"


def test_dashboard_ejecuciones_por_fecha_con_ceros(escenario):
    r = build_summary(escenario["db"], days=7, now=AHORA)
    por = {d["fecha"]: d for d in r["por_fecha"]}

    assert len(r["por_fecha"]) == 7 and r["por_fecha"][-1]["fecha"] == "2026-10-19"
    assert (por["2026-10-19"]["total"], por["2026-10-19"]["pass"], por["2026-10-19"]["fail"]) == (3, 2, 1)
    assert por["2026-10-18"]["total"] == 1 and por["2026-10-17"]["total"] == 2 and por["2026-10-16"]["error"] == 1
    assert por["2026-10-15"]["total"] == 0 and por["2026-10-14"]["total"] == 0        # sin ejecuciones: aparece en cero
    assert sum(d["total"] for d in r["por_fecha"]) == r["tarjetas"]["total_ejecuciones"]


def test_dashboard_casos_y_suites_mas_usados(escenario):
    r = build_summary(escenario["db"], days=30, now=AHORA)

    top = {c["nombre"]: c for c in r["top_casos"]}
    assert r["top_casos"][0]["nombre"] == "Caso A" and r["top_casos"][0]["ejecuciones"] == 3
    assert top["Caso B"]["ejecuciones"] == 2 and top["Caso B"]["fail"] == 1 and top["Caso B"]["ultimo_estado"] == "FAIL"
    assert top["Pruebas rápidas (sin caso guardado)"]["ejecuciones"] == 1

    suite = r["top_suites"][0]
    assert suite["nombre"] == "Suite 1" and suite["corridas"] == 2 and suite["ejecuciones"] == 4 and suite["pct_pass"] == 75.0


def test_dashboard_origen_proyectos_y_alcance(escenario):
    r = build_summary(escenario["db"], days=30, now=AHORA)
    origen = {o["origen"]: o["ejecuciones"] for o in r["por_origen"]}
    assert origen == {"UI": 2, "GITHUB_ACTIONS": 2, "CLI": 1, "INICIO": 1, "SIN_REGISTRAR": 1}
    assert {p["nombre"]: p["ejecuciones"] for p in r["proyectos"]} == {"Proyecto Uno": 6, "Proyecto Dos": 1}

    uno = build_summary(escenario["db"], days=30, project_id=escenario["p1"], now=AHORA)
    assert uno["tarjetas"]["total_ejecuciones"] == 6 and uno["alcance"]["proyecto"] == "Proyecto Uno"
    assert uno["tarjetas"]["error"] == 0 and uno["totales_actuales"]["casos"] == 2


def test_dashboard_eventos_de_excel_se_registran_y_se_cuentan(escenario):
    db = escenario["db"]
    record_event(db, "excel_import_cases", escenario["p1"], "UI", "creados=3")
    record_event(db, "excel_export_results", escenario["p1"], "CLI")
    r = build_summary(db, days=30, project_id=escenario["p1"], now=datetime.utcnow())
    tipos = {e["tipo"]: e["cantidad"] for e in r["eventos"]}
    assert tipos == {"excel_import_cases": 1, "excel_export_results": 1}


def test_dashboard_cada_metrica_tiene_su_definicion_y_los_limites_son_explicitos():
    r = build_summary(_db(), days=7, now=AHORA)
    for clave in ("total_ejecuciones", "corridas_de_suite", "tasa_pass", "casos_distintos", "por_fecha", "top_casos", "por_origen"):
        assert len(r["definiciones"][clave]) > 30
    assert any("por persona" in l for l in r["limitaciones"])
    assert any("UTC" in l for l in r["limitaciones"])


# ------------------------------------------------------------------------------------------ API

def test_api_usage_summary_valida_parametros():
    assert client.get("/api/usage/summary").status_code == 200
    assert client.get("/api/usage/summary?days=0").status_code == 422
    assert client.get("/api/usage/summary?days=366").status_code == 422
    assert client.get("/api/usage/summary?project_id=9999").status_code == 404


def test_api_usage_summary_refleja_la_actividad_real():
    proj = client.post("/api/projects/", json={"name": "P uso"}).json()["id"]
    assert client.get(f"/api/usage/summary?days=7&project_id={proj}").json()["hay_datos"] is False
    db = _db()
    _hist(db, proj, "PASS", 0, None, None, None, "CLI")
    data = client.get(f"/api/usage/summary?days=7&project_id={proj}")
    assert data.status_code == 200
    # _hist usa un instante fijo del pasado: dentro de 7 días reales ya no cae; con 365 sí, y el histórico lo cuenta siempre
    assert data.json()["historico"]["total"] == 1
    amplio = client.get(f"/api/usage/summary?days=365&project_id={proj}").json()
    assert amplio["tarjetas"]["total_ejecuciones"] == 1 and amplio["por_origen"][0]["origen"] == "CLI"


# ------------------------------------------------------------- el origen de las ejecuciones queda registrado

def _perfil(env="TEST"):
    proj = client.post("/api/projects/", json={"name": f"Proyecto {env} {uuid.uuid4().hex[:6]}"}).json()
    conn = client.post("/api/connections/", json={"project_id": proj["id"], "name": "perfil", "engine": "ORACLE", "host": "oracle.local",
                                                  "port": 1521, "service_name": "FREEPDB1", "username": "u", "environment_type": env}).json()
    return proj["id"], conn["id"]


OK_SELECT = {"success": True, "statement_type": "SELECT", "rows": [(1,)], "columns": ["C"], "rowcount": 1, "message": "OK",
             "error_message": None, "rollback_applied": False, "rollback_error": None}


@patch("app.services.execution_service.TargetDatabaseExecutor.execute_query", return_value=OK_SELECT)
def test_caso_suite_e_inicio_registran_origen_y_corrida(_mock):
    proj, conn = _perfil()
    caso = client.post("/api/test-cases/", json={"project_id": proj, "name": "c", "sql_query": "SELECT 1 FROM dual", "expected_result": "1"}).json()["id"]
    caso2 = client.post("/api/test-cases/", json={"project_id": proj, "name": "c2", "sql_query": "SELECT 1 FROM dual", "expected_result": "1"}).json()["id"]
    suite = client.post("/api/suites/", json={"project_id": proj, "name": "s"}).json()["id"]
    client.post(f"/api/suites/{suite}/test-cases/{caso}")
    client.post(f"/api/suites/{suite}/test-cases/{caso2}")
    cred = {"connection_profile_id": conn, "password": "p"}

    h = client.post(f"/api/execute/test-case/{caso}", json=cred).json()
    assert h["trigger_source"] == "UI" and h["run_id"]

    s = client.post(f"/api/execute/suite/{suite}", json=cred).json()
    assert "run_id" in s, s
    assert s["details"][0]["status"] == "PASS", s["details"][0]      # los detalles de la suite traen los datos de cada ejecución
    assert s["run_id"] and {d["run_id"] for d in s["details"]} == {s["run_id"]} and {d["trigger_source"] for d in s["details"]} == {"UI"}

    q = client.post("/api/execute/quick", json={**cred, "sql_query": "SELECT 1 FROM dual", "validation_type": "ROW_COUNT", "expected_result": "1"}).json()
    assert client.get(f"/api/history/{q['history_id']}").json()["trigger_source"] == "INICIO"

    resumen = client.get(f"/api/usage/summary?days=7&project_id={proj}").json()
    assert resumen["tarjetas"]["total_ejecuciones"] == 4 and resumen["tarjetas"]["corridas_de_suite"] == 1
    assert {o["origen"]: o["ejecuciones"] for o in resumen["por_origen"]} == {"UI": 3, "INICIO": 1}


# ------------------------------------------------------------------------------------ migración

def test_migracion_agrega_columnas_y_tabla_y_se_puede_revertir(tmp_path):
    import os
    import sqlite3
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    db = tmp_path / "m.sqlite"
    env = dict(os.environ, FRAMEWORK_DB_URL=f"sqlite:///{db.as_posix()}")

    def alembic(*a):
        return subprocess.run([sys.executable, "-m", "alembic", *a], cwd=root, env=env, capture_output=True, text=True)

    assert alembic("upgrade", "head").returncode == 0
    con = sqlite3.connect(db)
    cols = {r[1] for r in con.execute("PRAGMA table_info(execution_history)")}
    assert {"trigger_source", "run_id"} <= cols
    assert "usage_events" in {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    con.execute("INSERT INTO execution_history (project_id, status, duration_ms, executed_sql) VALUES (1, 'PASS', 1, 'x')")
    con.commit()
    assert con.execute("SELECT trigger_source FROM execution_history").fetchone()[0] is None      # origen = no registrado
    con.close()

    assert alembic("check").returncode == 0, "los modelos y las migraciones no coinciden"
    # Volver a la revisión anterior a la Fase 4 (también revierte la de usuarios, que vino después).
    assert alembic("downgrade", "d10691d55c95").returncode == 0
    con = sqlite3.connect(db)
    assert "trigger_source" not in {r[1] for r in con.execute("PRAGMA table_info(execution_history)")}
    assert con.execute("SELECT COUNT(*) FROM execution_history").fetchone()[0] == 1               # los datos se conservan
    con.close()
    assert alembic("upgrade", "head").returncode == 0


# ---------------------------------------------------------------------------------- interfaz (estática)

def test_dashboard_en_la_interfaz_tiene_explicaciones_y_estados_vacios():
    from pathlib import Path
    html = Path("frontend/index.html").read_text(encoding="utf-8")
    uso = Path("frontend/js/modulos/uso.js").read_text(encoding="utf-8")
    nav = Path("frontend/js/modulos/navegacion.js").read_text(encoding="utf-8")

    assert 'id="section-dashboard"' in html and 'id="uso-contenido"' in html and 'id="uso-dias"' in html and 'id="uso-alcance"' in html
    assert "Uso del producto" in nav and "cargarUso" in nav
    assert "/usage/summary" in uso                                  # las cifras vienen del servidor
    for frase in ("Sin ejecuciones en este periodo", "No se pudieron calcular las métricas", "Cómo leer estas cifras", "mensaje_vacio"):
        assert frase in uso
    assert "Math.random" not in uso                                 # nada inventado en el navegador
