"""
Fase 4 — CLI (python -m app.cli) y flujo de GitHub Actions.

La CLI se prueba ejecutando el código REAL (importar Excel, ejecutar suites, escribir reportes, códigos de salida) contra una
base de pruebas SQLite que imita las tablas de la demostración a través de la interfaz de oracledb (tests/fake_oracle.py).
No es Oracle: la verificación contra Oracle real depende de un Oracle disponible (ver docs/integraciones-fase4.md).
"""
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import pytest
from openpyxl import load_workbook

from app import cli
from app.core.database import get_db
from app.main import app
from app.models.history import ExecutionHistory
from fake_oracle import SEED, connect_factory, make_database

ROOT = Path(__file__).resolve().parents[1]
CHECKS = ROOT / "checks" / "reglas_demo.xlsx"
SUITE = "Reglas de calidad (demo)"
PASSWORD = "clave_secreta_de_prueba_XYZ"


@pytest.fixture()
def sesion():
    return lambda: next(app.dependency_overrides[get_db]())


@pytest.fixture()
def oracle(tmp_path, monkeypatch):
    """Base desechable con los datos de la demostración y la contraseña solo en el entorno."""
    ruta = make_database(tmp_path / "objetivo.sqlite")
    llamadas = []
    monkeypatch.setenv("FW_ORACLE_PASSWORD", PASSWORD)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with patch("oracledb.connect", connect_factory(ruta, llamadas)):
        yield {"ruta": ruta, "llamadas": llamadas}


def ejecutar(sesion, *args):
    return cli.main(list(args), session_factory=sesion)


def importar_demo(sesion, proyecto="CI"):
    return ejecutar(sesion, "import-excel", str(CHECKS), "--project", proyecto, "--create-project")


def correr(sesion, *extra, proyecto="CI", suite=SUITE):
    return ejecutar(sesion, "run", "--project", proyecto, "--suite", suite, "--host", "127.0.0.1", "--service", "FREEPDB1",
                    "--user", "FRAMEWORK_TEST", *extra)


# ------------------------------------------------------------------------- Excel versionado en el repositorio

def test_el_excel_versionado_coincide_con_lo_que_genera_el_script():
    """checks/reglas_demo.xlsx es la fuente de las comprobaciones de CI: no debe divergir de su generador."""
    sys.path.insert(0, str(ROOT / "scripts" / "checks"))
    import generate_demo_checks
    from app.services import excel_io
    versionado, e1 = excel_io.parse_cases(CHECKS.read_bytes())
    generado, e2 = excel_io.parse_cases(excel_io.build_cases_file(generate_demo_checks.demo_rows()))
    assert not e1 and not e2
    quitar_fila = lambda rows: [{k: v for k, v in r.items() if k != "fila"} for r in rows]   # noqa: E731
    assert quitar_fila(versionado) == quitar_fila(generado) and len(versionado) == 5


# ----------------------------------------------------------------------------------------- importar

def test_importar_excel_simulacion_real_y_reimportacion(sesion, capsys):
    assert ejecutar(sesion, "import-excel", str(CHECKS), "--project", "CI", "--create-project", "--dry-run") == cli.EXIT_OK
    assert "(simulación)" in capsys.readouterr().out
    assert ejecutar(sesion, "run", "--project", "CI", "--password-env", "NO_EXISTE") == cli.EXIT_USAGE      # el proyecto no se creó

    assert importar_demo(sesion) == cli.EXIT_OK
    assert "a crear: 5" in capsys.readouterr().out
    assert importar_demo(sesion) == cli.EXIT_OK
    assert "omitidos (ya existen): 5" in capsys.readouterr().out


def test_importar_excel_con_errores_devuelve_1_y_no_guarda(sesion, tmp_path, capsys):
    from test_phase4_excel import xlsx
    malo = tmp_path / "malo.xlsx"
    malo.write_bytes(xlsx([["ok", "", "SELECT 1 FROM DUAL", "ROW_COUNT", 1, None], ["mal", "", "DROP TABLE X", "ROW_COUNT", 1, None]]))
    assert ejecutar(sesion, "import-excel", str(malo), "--project", "P", "--create-project") == cli.EXIT_FAIL
    salida = capsys.readouterr().out
    assert "fila 3 · SQL" in salida and "Rechazado" in salida and "No se importó nada" in salida
    from app.models.test_case import TestCase
    assert sesion().query(TestCase).count() == 0


def test_importar_archivo_inexistente_o_proyecto_inexistente_es_error_de_uso(sesion):
    assert ejecutar(sesion, "import-excel", "no_existe.xlsx", "--project", "X") == cli.EXIT_USAGE
    assert ejecutar(sesion, "import-excel", str(CHECKS), "--project", "No existe") == cli.EXIT_USAGE


# --------------------------------------------------------------------------------- run: códigos de salida

def test_run_todo_pass_devuelve_0_y_escribe_los_tres_reportes(sesion, oracle, tmp_path, capsys):
    importar_demo(sesion)
    junit, md, js = tmp_path / "r" / "x.xml", tmp_path / "r" / "x.md", tmp_path / "r" / "x.json"

    codigo = correr(sesion, "--junit", str(junit), "--markdown", str(md), "--json", str(js))

    assert codigo == cli.EXIT_OK
    salida = capsys.readouterr().out
    assert "5 PASS · 0 FAIL · 0 ERROR — código de salida 0" in salida and "esperado:" in salida and "obtenido:" in salida

    suite = ET.parse(junit).getroot()
    assert (suite.get("tests"), suite.get("failures"), suite.get("errors")) == ("5", "0", "0")
    assert {p.get("name"): p.get("value") for p in suite.find("properties")}["origen"] == "CLI"
    reporte = md.read_text(encoding="utf-8")
    assert "TODAS LAS COMPROBACIONES PASARON" in reporte and "Hay 5 productos registrados" in reporte and "Código de salida" in reporte
    datos = json.loads(js.read_text(encoding="utf-8"))
    assert datos["codigo_salida"] == 0 and len(datos["resultados"]) == 5 and datos["meta"]["origen"] == "CLI"


def test_run_deja_historial_con_origen_cli_y_una_sola_corrida(sesion, oracle):
    importar_demo(sesion)
    correr(sesion)
    filas = sesion().query(ExecutionHistory).all()
    assert len(filas) == 5
    assert {f.trigger_source for f in filas} == {"CLI"} and len({f.run_id for f in filas}) == 1 and all(f.run_id for f in filas)
    assert all(f.suite_id is not None and f.status == "PASS" for f in filas)


def test_run_con_fail_devuelve_1(sesion, oracle, tmp_path, capsys):
    importar_demo(sesion)
    import sqlite3
    con = sqlite3.connect(oracle["ruta"])
    con.execute("UPDATE FRAMEWORK_TEST_ITEMS SET ACTIVE = 7 WHERE ID = 4")        # dato inválido
    con.commit()
    con.close()
    junit = tmp_path / "f.xml"

    assert correr(sesion, "--junit", str(junit)) == cli.EXIT_FAIL

    salida = capsys.readouterr().out
    assert "4 PASS · 1 FAIL · 0 ERROR — código de salida 1" in salida and "esperabas 0 y devolvió 1" in salida
    fallos = ET.parse(junit).getroot().findall("testcase/failure")
    assert len(fallos) == 1 and "esperabas 0" in fallos[0].get("message")


def test_run_con_error_devuelve_2_aunque_tambien_haya_fail(sesion, oracle, tmp_path, capsys):
    from test_phase4_excel import xlsx
    f = tmp_path / "c.xlsx"
    f.write_bytes(xlsx([["falla", "", "SELECT COUNT(*) FROM FRAMEWORK_TEST_ITEMS", "SCALAR_VALUE", 99, "S"],
                        ["rota", "", "SELECT COUNT(*) FROM TABLA_QUE_NO_EXISTE", "SCALAR_VALUE", 0, "S"]]))
    ejecutar(sesion, "import-excel", str(f), "--project", "CI", "--create-project")
    junit = tmp_path / "e.xml"

    assert correr(sesion, "--junit", str(junit), suite="S") == cli.EXIT_ERROR

    suite = ET.parse(junit).getroot()
    assert (suite.get("failures"), suite.get("errors")) == ("1", "1")
    assert "no such table" in suite.find("testcase/error").text
    assert "código de salida 2" in capsys.readouterr().out


def test_run_con_contrasena_incorrecta_es_error_2_y_la_clave_no_aparece_en_ninguna_salida(sesion, oracle, tmp_path, monkeypatch, capsys):
    importar_demo(sesion)
    monkeypatch.setenv("FW_ORACLE_PASSWORD", "mala")
    md, js = tmp_path / "m.md", tmp_path / "m.json"
    assert correr(sesion, "--markdown", str(md), "--json", str(js)) == cli.EXIT_ERROR
    todo = capsys.readouterr().out + md.read_text(encoding="utf-8") + js.read_text(encoding="utf-8")
    assert "ORA-01017" in todo and "mala" not in todo.replace("ORA-01017: invalid username/password; logon denied", "")


def test_la_contrasena_nunca_aparece_en_reportes_historial_ni_salida(sesion, oracle, tmp_path, capsys):
    importar_demo(sesion)
    md, js, xm = tmp_path / "a.md", tmp_path / "a.json", tmp_path / "a.xml"
    correr(sesion, "--markdown", str(md), "--json", str(js), "--junit", str(xm))
    historial = " ".join(f"{h.executed_sql} {h.actual_result} {h.error_message}" for h in sesion().query(ExecutionHistory).all())
    for texto in (capsys.readouterr().out, md.read_text(encoding="utf-8"), js.read_text(encoding="utf-8"), xm.read_text(encoding="utf-8"), historial):
        assert PASSWORD not in texto


def test_la_cli_no_acepta_la_contrasena_como_argumento(sesion, oracle):
    assert correr(sesion, "--password", PASSWORD) == cli.EXIT_USAGE            # no existe esa opción


def test_run_errores_de_uso_devuelven_3_sin_conectar(sesion, oracle, monkeypatch):
    importar_demo(sesion)
    assert correr(sesion, proyecto="No existe") == cli.EXIT_USAGE
    assert correr(sesion, suite="No existe") == cli.EXIT_USAGE
    assert ejecutar(sesion, "run", "--project", "CI", "--suite", SUITE) == cli.EXIT_USAGE                         # faltan host/servicio/usuario
    assert ejecutar(sesion, "run", "--project", "CI", "--suite", SUITE, "--profile", "no_existe") == cli.EXIT_USAGE
    assert ejecutar(sesion, "run", "--project", "CI", "--suite", SUITE, "--host", "x)(HOST=evil", "--service", "S", "--user", "u") == cli.EXIT_USAGE
    monkeypatch.delenv("FW_ORACLE_PASSWORD")
    assert correr(sesion) == cli.EXIT_USAGE
    assert oracle["llamadas"] == [], "los errores de uso no deben abrir ninguna conexión"


def test_run_sin_casos_devuelve_4(sesion, oracle):
    from app.models.project import Project
    from app.models.suite import TestSuite
    db = sesion()
    p = Project(name="Vacío")
    db.add(p)
    db.commit()
    db.add(TestSuite(project_id=p.id, name="Sin casos"))
    db.commit()
    assert correr(sesion, proyecto="Vacío", suite="Sin casos") == cli.EXIT_NO_CASES
    assert oracle["llamadas"] == []


def test_run_dentro_de_github_actions_registra_ese_origen(sesion, oracle, monkeypatch, tmp_path):
    importar_demo(sesion)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    xm = tmp_path / "g.xml"
    assert correr(sesion, "--junit", str(xm)) == cli.EXIT_OK
    assert {h.trigger_source for h in sesion().query(ExecutionHistory).all()} == {"GITHUB_ACTIONS"}
    assert {p.get("name"): p.get("value") for p in ET.parse(xm).getroot().find("properties")}["origen"] == "GITHUB_ACTIONS"


def test_run_en_production_no_muestra_filas_y_rechaza_el_valor_escalar(sesion, oracle, capsys):
    importar_demo(sesion)
    codigo = ejecutar(sesion, "run", "--project", "CI", "--suite", SUITE, "--host", "127.0.0.1", "--service", "FREEPDB1",
                      "--user", "FRAMEWORK_TEST", "--env", "PRODUCTION")
    assert codigo == cli.EXIT_ERROR
    assert "regla de seguridad" in capsys.readouterr().out
    # SCALAR_VALUE (4 reglas) se rechaza sin ejecutar nada; solo la regla de existencia llega a la base, con una única conexión
    assert len(oracle["llamadas"]) == 1
    filas = sesion().query(ExecutionHistory).all()
    assert sorted(f.status for f in filas) == ["ERROR"] * 4 + ["PASS"]
    assert all("Rechazado" in (f.error_message or "") for f in filas if f.status == "ERROR")


def test_run_con_perfil_guardado_y_con_casos_sueltos(sesion, oracle):
    from app.models.connection import ConnectionProfile
    importar_demo(sesion)
    from app.models.project import Project
    db = sesion()
    pid = db.query(Project).filter(Project.name == "CI").first().id
    db.add(ConnectionProfile(project_id=pid, name="mi-perfil", engine="ORACLE", host="oracle.local", port=1521, service_name="FREEPDB1",
                             username="FRAMEWORK_TEST", environment_type="TEST"))
    db.commit()
    assert ejecutar(sesion, "run", "--project", "CI", "--profile", "mi-perfil", "--case", "Hay 5 productos registrados",
                    "--case", "Existe el producto con ID 3") == cli.EXIT_OK
    assert db.query(ExecutionHistory).count() == 2


# ------------------------------------------------------------------------------------------ exportar

def test_exportar_resultados_y_casos_desde_la_cli(sesion, oracle, tmp_path):
    importar_demo(sesion)
    correr(sesion)
    res, cas = tmp_path / "res.xlsx", tmp_path / "cas.xlsx"
    assert ejecutar(sesion, "export-excel", "results", "--project", "CI", "--out", str(res)) == cli.EXIT_OK
    assert ejecutar(sesion, "export-excel", "cases", "--project", "CI", "--out", str(cas)) == cli.EXIT_OK
    ws = load_workbook(res)["Resultados"]
    assert ws.max_row == 6 and ws.cell(row=2, column=12).value == "CLI"
    assert load_workbook(cas)["Casos"].max_row == 6
    assert ejecutar(sesion, "export-excel", "cases", "--project", "CI", "--out", str(cas)) == cli.EXIT_USAGE     # no sobrescribe sin --force
    assert ejecutar(sesion, "export-excel", "cases", "--project", "CI", "--out", str(cas), "--force") == cli.EXIT_OK


# ------------------------------------------------------------------------ ejecución real como proceso

def _proceso(*args, env_extra=None, cwd=ROOT):
    env = {k: v for k, v in os.environ.items() if k not in ("FRAMEWORK_DB_URL", "FW_ORACLE_PASSWORD", "GITHUB_ACTIONS")}
    env.update(env_extra or {})
    return subprocess.run([sys.executable, "-m", "app.cli", *args], cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)


def test_la_cli_como_proceso_init_db_importar_y_codigos_de_salida(tmp_path):
    base = tmp_path / "cli.sqlite"
    r = _proceso("--db", str(base), "init-db")
    assert r.returncode == 0 and base.exists(), r.stderr
    r = _proceso("--db", str(base), "import-excel", str(CHECKS), "--project", "Proc", "--create-project")
    assert r.returncode == 0 and "a crear: 5" in r.stdout, r.stdout + r.stderr
    r = _proceso("--db", str(base), "run", "--project", "Proc", "--suite", SUITE, "--host", "127.0.0.1", "--service", "S", "--user", "u")
    assert r.returncode == cli.EXIT_USAGE and "FW_ORACLE_PASSWORD" in r.stderr and PASSWORD not in r.stdout + r.stderr
    r = _proceso("--db", str(base), "run", "--project", "Proc", "--password-env", "OTRA")
    assert r.returncode == cli.EXIT_USAGE
    # Ejecución completa como proceso hasta la conexión: no hay Oracle en el puerto 1, así que debe terminar en ERROR (2)
    # con un mensaje legible y SIN traza de Python (antes fallaba al configurar los modelos de SQLAlchemy).
    r = _proceso("--db", str(base), "run", "--project", "Proc", "--suite", SUITE, "--host", "127.0.0.1", "--port", "1", "--service", "S",
                 "--user", "u", env_extra={"FW_ORACLE_PASSWORD": PASSWORD})
    assert r.returncode == cli.EXIT_ERROR, r.stdout + r.stderr
    assert "Traceback" not in r.stdout + r.stderr and PASSWORD not in r.stdout + r.stderr
    assert "ERROR" in r.stdout and "código de salida 2" in r.stdout
    assert _proceso("--help").returncode == 0
    assert _proceso("comando-inexistente").returncode == cli.EXIT_USAGE


# ----------------------------------------------------------------------------- flujo de GitHub Actions

def test_workflow_sql_checks_usa_cli_excel_y_conserva_reportes_sin_secretos():
    wf = (ROOT.parent / ".github" / "workflows" / "sql-checks.yml").read_text(encoding="utf-8")
    assert "secrets." not in wf, "el flujo usa un Oracle y credenciales efímeros: no necesita secretos"
    assert "python -m app.cli import-excel" in wf and "python -m app.cli run" in wf and "--password-env" not in wf.split("run --project")[0]
    assert "FW_ORACLE_PASSWORD" in wf and re.search(r"--password[ =]", wf) is None, "la contraseña va por entorno, no por argumento"
    assert "--junit" in wf and "--markdown" in wf and "GITHUB_STEP_SUMMARY" in wf
    assert "upload-artifact@v4" in wf and "reporte-sql-checks" in wf and "if: always()" in wf
    assert "pull_request:" in wf and "workflow_call:" in wf and "workflow_dispatch:" in wf
    assert 'exit "$codigo"' in wf, "el job debe fallar con el código de salida de la CLI (compuerta de PR)"
    assert not re.search(r"^\s+environment:", wf, re.M), "no necesita entornos con secretos"
    assert "ARM_" not in wf and "az login" not in wf and "terraform" not in wf, "no debe tocar Azure ni Terraform"


def test_un_excel_rechazado_no_deja_un_proyecto_vacio(sesion, tmp_path, capsys):
    """Auditoría de la Fase 6: con --create-project, un archivo con errores no debe crear el proyecto."""
    from test_phase4_excel import xlsx
    from app.models.project import Project
    malo = tmp_path / "malo.xlsx"
    malo.write_bytes(xlsx([["mal", "", "DROP TABLE X", "ROW_COUNT", 1, None]]))
    assert ejecutar(sesion, "import-excel", str(malo), "--project", "NoDebeCrearse", "--create-project") == cli.EXIT_FAIL
    assert "No se importó nada" in capsys.readouterr().out
    assert sesion().query(Project).filter(Project.name == "NoDebeCrearse").count() == 0
    # y un archivo válido sí crea el proyecto y los casos
    assert importar_demo(sesion, proyecto="NoDebeCrearse") == cli.EXIT_OK
    assert sesion().query(Project).filter(Project.name == "NoDebeCrearse").count() == 1
