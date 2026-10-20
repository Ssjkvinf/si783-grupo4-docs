"""
Pruebas del recorrido guiado (Fase 1): endpoint POST /api/execute/quick,
explicación del resultado y comprobaciones estáticas de la pantalla «Inicio».

Todas las pruebas usan Oracle SIMULADO (unittest.mock sobre oracledb.connect);
ninguna se conecta a una base real ni ejecuta DML/DDL.
"""
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.execution_service import explain_execution

client = TestClient(app)

SECRET = "clave_oracle_de_prueba_123"


def _crear_conexion(environment_type="TEST"):
    proj = client.post("/api/projects/", json={"name": f"Proyecto {environment_type}", "description": ""})
    assert proj.status_code == 201
    conn = client.post("/api/connections/", json={
        "project_id": proj.json()["id"],
        "name": f"Conexión {environment_type}",
        "engine": "ORACLE",
        "host": "oracle.local",
        "port": 1521,
        "service_name": "FREEPDB1",
        "username": "FRAMEWORK_TEST",
        "environment_type": environment_type,
    })
    assert conn.status_code == 201
    return proj.json()["id"], conn.json()["id"]


def _oracle_simulado(mock_connect, rows, columns=("ID", "NAME"), execute_error=None):
    conexion, cursor = MagicMock(), MagicMock()
    mock_connect.return_value = conexion
    conexion.cursor.return_value = cursor
    cursor.fetchmany.return_value = rows
    cursor.description = [(c,) for c in columns]
    if execute_error:
        cursor.execute.side_effect = Exception(execute_error)
    return conexion, cursor


def _payload(conn_id, **extra):
    base = {
        "connection_profile_id": conn_id,
        "password": SECRET,
        "sql_query": "SELECT ID, NAME FROM FRAMEWORK_TEST_ITEMS",
        "validation_type": "ROW_COUNT",
        "expected_result": "2",
    }
    base.update(extra)
    return base


@patch("oracledb.connect")
def test_quick_pass_row_count_con_filas_y_explicacion(mock_connect):
    _, conn_id = _crear_conexion()
    _oracle_simulado(mock_connect, [(1, "Uno"), (2, "Dos")])

    res = client.post("/api/execute/quick", json=_payload(conn_id))

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "PASS"
    assert body["rowcount"] == 2
    assert body["columns"] == ["ID", "NAME"]
    assert body["rows"] == [[1, "Uno"], [2, "Dos"]]
    assert "exactamente 2 filas" in body["expected_text"]
    assert body["obtained_text"] == "La consulta devolvió 2 filas"
    assert body["reason"].startswith("Coincide")
    assert SECRET not in res.text


@patch("oracledb.connect")
def test_quick_fail_explica_esperado_y_obtenido(mock_connect):
    _, conn_id = _crear_conexion()
    _oracle_simulado(mock_connect, [(1, "Uno")])

    body = client.post("/api/execute/quick", json=_payload(conn_id, expected_result="5")).json()

    assert body["status"] == "FAIL"
    assert body["rowcount"] == 1
    assert "esperabas 5" in body["reason"] and "devolvió 1" in body["reason"]
    assert "no coincide" in body["reason"]


@patch("oracledb.connect")
def test_quick_exists_fail_cuando_no_hay_filas(mock_connect):
    _, conn_id = _crear_conexion()
    _oracle_simulado(mock_connect, [])

    body = client.post("/api/execute/quick", json=_payload(
        conn_id, validation_type="EXISTS", expected_result="true")).json()

    assert body["status"] == "FAIL"
    assert "al menos una fila" in body["expected_text"]
    assert "no devolvió ninguna" in body["reason"]


@patch("oracledb.connect")
def test_quick_error_de_oracle_se_clasifica_como_error(mock_connect):
    _, conn_id = _crear_conexion()
    _oracle_simulado(mock_connect, [], execute_error="ORA-00942: table or view does not exist")

    body = client.post("/api/execute/quick", json=_payload(conn_id)).json()

    assert body["status"] == "ERROR"
    assert body["obtained_text"] == "No se obtuvo resultado"
    assert "No es un fallo de los datos" in body["reason"]
    assert "ORA-00942" in body["error_message"]
    assert body["rows"] == []


@patch("oracledb.connect")
def test_quick_el_error_no_filtra_la_contrasena(mock_connect):
    """Si Oracle repite la contraseña en su mensaje, no debe llegar a la respuesta ni al historial."""
    proj_id, conn_id = _crear_conexion()
    _oracle_simulado(mock_connect, [], execute_error=f"ORA-01017: fallo con la clave {SECRET}")

    res = client.post("/api/execute/quick", json=_payload(conn_id))

    assert res.json()["status"] == "ERROR"
    assert SECRET not in res.text
    assert SECRET not in client.get(f"/api/history/?project_id={proj_id}").text


@patch("oracledb.connect")
def test_quick_registra_historial_sin_crear_caso(mock_connect):
    proj_id, conn_id = _crear_conexion()
    _oracle_simulado(mock_connect, [(1, "Uno")])

    body = client.post("/api/execute/quick", json=_payload(conn_id, expected_result="1")).json()

    historial = client.get(f"/api/history/?project_id={proj_id}").json()
    assert len(historial) == 1
    registro = historial[0]
    assert registro["id"] == body["history_id"]
    assert registro["test_case_id"] is None            # caso transitorio: no se guarda en test_cases
    assert registro["connection_profile_id"] == conn_id
    assert registro["expected_result"] == "1"           # lo indicado por la persona
    assert client.get("/api/test-cases/").json() == []  # no se creó ningún caso automáticamente


@patch("oracledb.connect")
def test_quick_el_esperado_no_se_deriva_del_resultado(mock_connect):
    """El esperado lo define la persona: un resultado distinto debe dar FAIL, nunca PASS por copia."""
    _, conn_id = _crear_conexion()
    _oracle_simulado(mock_connect, [(1,), (2,), (3,)])

    body = client.post("/api/execute/quick", json=_payload(conn_id, expected_result="1")).json()

    assert body["expected_result"] == "1"
    assert body["rowcount"] == 3
    assert body["status"] == "FAIL"


@patch("oracledb.connect")
def test_quick_rechaza_dsn_libre_y_no_se_conecta(mock_connect):
    _, conn_id = _crear_conexion()

    for campo in ({"dsn": "servidor-externo/xe"}, {"user": "otro"}, {"host": "10.0.0.5"}):
        res = client.post("/api/execute/quick", json=_payload(conn_id, **campo))
        assert res.status_code == 422, campo
    mock_connect.assert_not_called()


@patch("oracledb.connect")
def test_quick_requiere_perfil_guardado(mock_connect):
    res = client.post("/api/execute/quick", json=_payload(99999))
    assert res.status_code == 404
    mock_connect.assert_not_called()


@patch("oracledb.connect")
@pytest.mark.parametrize("sql", [
    "INSERT INTO FRAMEWORK_TEST_ITEMS (ID, NAME) VALUES (1, 'x')",
    "UPDATE FRAMEWORK_TEST_ITEMS SET NAME = 'x'",
    "DELETE FROM FRAMEWORK_TEST_ITEMS",
])
def test_quick_solo_admite_select_y_no_llega_a_oracle(mock_connect, sql):
    _, conn_id = _crear_conexion("TEST")

    res = client.post("/api/execute/quick", json=_payload(conn_id, sql_query=sql, expected_result="1"))

    assert res.status_code == 422
    assert "solo admite consultas SELECT" in res.json()["detail"]
    mock_connect.assert_not_called()


@patch("oracledb.connect")
@pytest.mark.parametrize("sql", ["DROP TABLE FRAMEWORK_TEST_ITEMS", "TRUNCATE TABLE FRAMEWORK_TEST_ITEMS",
                                 "SELECT 1 FROM DUAL; SELECT 2 FROM DUAL"])
def test_quick_sigue_aplicando_la_politica_sql(mock_connect, sql):
    """DDL y sentencias múltiples se rechazan antes de conectar; queda ERROR registrado."""
    _, conn_id = _crear_conexion("TEST")

    body = client.post("/api/execute/quick", json=_payload(conn_id, sql_query=sql, expected_result="1")).json()

    assert body["status"] == "ERROR"
    assert "Rechazado" in body["error_message"]
    assert "regla de seguridad" in body["reason"]
    mock_connect.assert_not_called()


@patch("oracledb.connect")
def test_quick_produccion_rechaza_dml_sin_conectar(mock_connect):
    _, conn_id = _crear_conexion("PRODUCTION")

    body = client.post("/api/execute/quick", json=_payload(
        conn_id, sql_query="INSERT INTO FRAMEWORK_TEST_ITEMS (ID, NAME) VALUES (9, 'x')",
        expected_result="1")).json()

    assert body["status"] == "ERROR"
    assert "solo se permiten sentencias SELECT" in body["error_message"]
    mock_connect.assert_not_called()


@patch("oracledb.connect")
def test_quick_produccion_no_muestra_filas(mock_connect):
    _, conn_id = _crear_conexion("PRODUCTION")
    _oracle_simulado(mock_connect, [("dato-sensible", 1), ("otro-dato", 2)])

    res = client.post("/api/execute/quick", json=_payload(conn_id, expected_result="2"))

    body = res.json()
    assert body["status"] == "PASS"
    assert body["environment_type"] == "PRODUCTION"
    assert body["rows_hidden"] is True
    assert body["rows"] == [] and body["columns"] == []
    assert body["rowcount"] == 2
    assert "dato-sensible" not in res.text


@patch("oracledb.connect")
def test_quick_produccion_enmascara_errores_de_oracle(mock_connect):
    _, conn_id = _crear_conexion("PRODUCTION")
    _oracle_simulado(mock_connect, [], execute_error="ORA-00942: tabla SECRETA_HR no existe")

    res = client.post("/api/execute/quick", json=_payload(conn_id))

    assert res.json()["status"] == "ERROR"
    assert "SECRETA_HR" not in res.text


@patch("oracledb.connect")
def test_quick_limita_las_filas_mostradas(mock_connect):
    _, conn_id = _crear_conexion()
    _oracle_simulado(mock_connect, [(i, f"n{i}") for i in range(35)])

    body = client.post("/api/execute/quick", json=_payload(conn_id, expected_result="35")).json()

    assert body["status"] == "PASS"
    assert body["rowcount"] == 35
    assert body["rows_shown"] == 20 and len(body["rows"]) == 20
    assert body["rows_truncated"] is True


@pytest.mark.parametrize("campos", [
    {"validation_type": "ROW_COUNT", "expected_result": "abc"},
    {"validation_type": "ROW_COUNT", "expected_result": "-1"},
    {"validation_type": "EXISTS", "expected_result": "quizas"},
    {"expected_result": "   "},
    {"password": ""},
    {"sql_query": "  "},
])
def test_quick_valida_entradas(campos):
    _, conn_id = _crear_conexion()
    res = client.post("/api/execute/quick", json=_payload(conn_id, **campos))
    assert res.status_code == 422


# ---- explicación en lenguaje natural ----

def test_explain_pass_y_fail_row_count():
    ok = explain_execution("PASS", "ROW_COUNT", "1", 1)
    assert ok["reason"] == "Coincide: esperabas 1 fila y la consulta devolvió 1 fila."
    ko = explain_execution("FAIL", "ROW_COUNT", "1", 3)
    assert "esperabas 1" in ko["reason"] and "devolvió 3" in ko["reason"]


def test_explain_exists_false_con_filas():
    ko = explain_execution("FAIL", "EXISTS", "false", 4)
    assert "no devuelva ninguna fila" in ko["expected_text"]
    assert "4 filas" in ko["reason"]


def test_explain_error_distingue_regla_de_seguridad():
    seg = explain_execution("ERROR", "ROW_COUNT", "1", 0, "Rechazado por seguridad: DROP")
    otro = explain_execution("ERROR", "ROW_COUNT", "1", 0, "ORA-01017: invalid credential")
    assert "regla de seguridad" in seg["reason"]
    assert "No es un fallo de los datos" in otro["reason"]


# ---- comprobaciones estáticas de la interfaz ----

FRONTEND = Path("frontend")


def test_inicio_html_contiene_todos_los_elementos_que_usa_inicio_js():
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    js = (FRONTEND / "js/modulos/inicio.js").read_text(encoding="utf-8")

    ids = set(re.findall(r"el\('([a-z0-9-]+)'\)", js))
    assert ids, "inicio.js debería referenciar elementos por id"
    # los botones del resultado se crean dinámicamente dentro de inicio.js; el resto debe estar en index.html
    dinamicos = {"inicio-btn-repetir", "inicio-btn-guardar", "inicio-btn-historial",
                 "inicio-btn-suite-repetir", "inicio-btn-suite-historial"}
    for dinamico in dinamicos:
        assert f'id="{dinamico}"' in js
    faltan = [i for i in ids - dinamicos if f'id="{i}"' not in html]
    assert faltan == []


def test_inicio_explica_problema_que_hace_y_para_quien_sin_prometer_cliente():
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    inicio = html[html.index('id="section-inicio"'):html.index('id="section-ayuda"')]

    assert "¿Qué problema atiende?" in inicio
    assert "¿Qué hace?" in inicio
    assert "¿Para quién es?" in inicio
    assert "desarrolladores o analistas de pruebas" in inicio
    assert "aún no se ha evaluado con una empresa" in inicio
    for frase in ("nuestro cliente", "empresa cliente", "ahorro de", "% de"):
        assert frase not in inicio.lower()


def test_inicio_js_no_abre_dsn_libre_ni_guarda_contrasena_ni_copia_el_resultado():
    js = (FRONTEND / "js/modulos/inicio.js").read_text(encoding="utf-8")

    assert "dsn" not in js.lower()
    assert "localStorage" not in js and "sessionStorage" not in js
    assert "/execute/quick" in js
    # Al guardar un caso, el esperado sale de lo que la persona indicó antes de ejecutar...
    assert "expected_result: u.expected_result" in js
    # ...nunca del resultado obtenido, y se pide confirmación explícita.
    assert "rowcount" not in js[js.index("function guardarComoCaso"):]
    assert "confirmar:" in js

    casos = (FRONTEND / "js/modulos/casos.js").read_text(encoding="utf-8")
    assert "f-caso-confirm" in casos
    assert "Confirme que el resultado esperado es el correcto" in casos


def test_plantillas_solo_usan_objetos_del_entorno_de_demostracion():
    js = (FRONTEND / "js/modulos/inicio.js").read_text(encoding="utf-8")
    bloque = js[js.index("const PLANTILLAS"):js.index("let irASeccion")]
    tablas = set(re.findall(r"\bFROM\s+([A-Z_]+)", bloque))
    assert tablas <= {"DUAL", "FRAMEWORK_TEST_ITEMS"}

    esquema = Path("infra/oracle/init/001_test_schema.sh").read_text(encoding="utf-8")
    assert "FRAMEWORK_TEST_ITEMS" in esquema
    for columna in ("ID", "NAME", "ACTIVE"):
        assert columna in esquema
