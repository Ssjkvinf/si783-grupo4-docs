"""
Pruebas de la Fase 2 SIN Oracle (Oracle simulado con unittest.mock):
 - validación por valor escalar (SCALAR_VALUE) y diferencia con ROW_COUNT;
 - escenario de demostración (casos y suites) e informe legible de la suite;
 - restricción de destinos: sin dsn libre, sintaxis de host/servicio y ORACLE_ALLOWED_HOSTS.

Las pruebas contra un Oracle real están en tests/test_oracle_phase2.py (marcadas oracle_integration).
"""
import re
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.engine.validator import ScalarValueValidation, format_scalar, scalar_equals
from app.main import app
from app.services import demo_scenario
from app.services.execution_service import describe_scalar, explain_execution

client = TestClient(app)


def _perfil(environment_type="TEST", host="oracle.local"):
    proj = client.post("/api/projects/", json={"name": f"Proyecto {environment_type} {host}"}).json()
    conn = client.post("/api/connections/", json={
        "project_id": proj["id"], "name": f"Perfil {environment_type}", "engine": "ORACLE",
        "host": host, "port": 1521, "service_name": "FREEPDB1",
        "username": "usuario_prueba", "environment_type": environment_type,
    })
    assert conn.status_code == 201, conn.text
    return proj["id"], conn.json()["id"]


def _oracle(mock_connect, rows, columns=("C",), execute_error=None):
    conexion, cursor = MagicMock(), MagicMock()
    mock_connect.return_value = conexion
    conexion.cursor.return_value = cursor
    cursor.fetchmany.return_value = rows
    cursor.description = [(c,) for c in columns]
    if execute_error:
        cursor.execute.side_effect = Exception(execute_error)
    return conexion, cursor


def _quick(conn_id, sql, validation, expected):
    return client.post("/api/execute/quick", json={
        "connection_profile_id": conn_id, "password": "clave_de_prueba",
        "sql_query": sql, "validation_type": validation, "expected_result": expected,
    })


# ---------------------------------------------------------------- validador de valor escalar

def _data(rows, success=True, stmt="SELECT"):
    return {"success": success, "statement_type": stmt, "rows": rows, "rowcount": len(rows)}


@pytest.mark.parametrize("rows,expected,resultado", [
    ([(0,)], "0", True),
    ([(Decimal("0"),)], "0", True),
    ([(Decimal("5.0"),)], "5", True),          # Oracle devuelve NUMBER como int/Decimal
    ([(5,)], "5.00", True),
    ([(5,)], "6", False),
    ([(5,)], "05", True),                      # comparación numérica, no de texto
    ([("Cuaderno",)], "Cuaderno", True),
    ([("Cuaderno",)], "cuaderno", False),      # texto: exacto
    ([(None,)], "NULL", True),
    ([(None,)], "0", False),
    ([], "0", False),                          # 0 filas: no hay valor que comparar
    ([(1,), (2,)], "1", False),                # varias filas: ambiguo -> no pasa
    ([()], "0", False),
])
def test_scalar_validation_comparaciones(rows, expected, resultado):
    assert ScalarValueValidation().evaluate(_data(rows), expected) is resultado


def test_scalar_validation_no_pasa_si_la_consulta_fallo_o_no_es_select():
    assert ScalarValueValidation().evaluate(_data([(0,)], success=False), "0") is False
    assert ScalarValueValidation().evaluate(_data([(0,)], stmt="INSERT"), "0") is False


def test_format_scalar_y_equals():
    assert format_scalar(Decimal("100")) == "100"
    assert format_scalar(Decimal("2.50")) == "2.5"
    assert format_scalar(None) == "NULL"
    assert scalar_equals(Decimal("0"), "0")


def test_describe_scalar():
    assert describe_scalar([(7,)]) == ("valor", "7")
    assert describe_scalar([])[0] == "sin_filas"
    assert describe_scalar([(1,), (2,)])[0] == "varias_filas"


# ---------------------------------------------------- la confusión de COUNT(*) queda explicada

@patch("oracledb.connect")
def test_count_con_valor_escalar_compara_el_numero(mock_connect):
    _, conn_id = _perfil()
    _oracle(mock_connect, [(0,)], columns=("COUNT(*)",))

    ok = _quick(conn_id, "SELECT COUNT(*) FROM T WHERE X IS NULL", "SCALAR_VALUE", "0").json()
    assert ok["status"] == "PASS"
    assert ok["obtained_text"] == "La consulta devolvió el valor 0"
    assert ok["reason"] == "Coincide: esperabas el valor 0 y la consulta devolvió 0."
    assert "valor que devuelve la consulta sea 0" in ok["expected_text"]

    _oracle(mock_connect, [(3,)], columns=("COUNT(*)",))
    ko = _quick(conn_id, "SELECT COUNT(*) FROM T WHERE X IS NULL", "SCALAR_VALUE", "0").json()
    assert ko["status"] == "FAIL"
    assert ko["obtained_text"] == "La consulta devolvió el valor 3"
    assert "esperabas 0 y devolvió 3" in ko["reason"]


@patch("oracledb.connect")
def test_count_con_row_count_cuenta_filas_y_lo_aclara(mock_connect):
    """ROW_COUNT=1 sobre un COUNT(*) pasa SIEMPRE (1 fila), aunque el valor sea 3: la explicación lo dice."""
    _, conn_id = _perfil()
    _oracle(mock_connect, [(3,)], columns=("COUNT(*)",))

    body = _quick(conn_id, "SELECT COUNT(*) FROM T", "ROW_COUNT", "1").json()

    assert body["status"] == "PASS"
    assert "cantidad de filas" in body["expected_text"]
    assert body["obtained_text"] == "La consulta devolvió 1 fila"
    assert "usa COUNT(...)" in body["reason"] and "no el número que calcula" in body["reason"]


@patch("oracledb.connect")
def test_valor_escalar_exige_una_sola_fila(mock_connect):
    _, conn_id = _perfil()
    _oracle(mock_connect, [], columns=("N",))
    sin = _quick(conn_id, "SELECT N FROM T WHERE 1=0", "SCALAR_VALUE", "1").json()
    assert sin["status"] == "FAIL" and "no devolvió ninguna fila" in sin["obtained_text"]

    _oracle(mock_connect, [(1,), (2,)], columns=("N",))
    varias = _quick(conn_id, "SELECT N FROM T", "SCALAR_VALUE", "1").json()
    assert varias["status"] == "FAIL" and "2 filas" in varias["obtained_text"]


@patch("oracledb.connect")
def test_valor_escalar_en_produccion_se_rechaza_sin_ejecutar(mock_connect):
    """En PRODUCTION las filas se ocultan: comparar un valor obligaría a leerlas, así que no se ejecuta."""
    _, conn_id = _perfil("PRODUCTION")

    body = _quick(conn_id, "SELECT COUNT(*) FROM T", "SCALAR_VALUE", "0").json()

    assert body["status"] == "ERROR"
    assert "PRODUCTION" in body["error_message"]
    assert "regla de seguridad" in body["reason"]
    assert body["rows"] == []
    mock_connect.assert_not_called()


def test_tipos_de_validacion_en_la_api_de_casos():
    proj = client.post("/api/projects/", json={"name": "P validaciones"}).json()["id"]
    ok = client.post("/api/test-cases/", json={"project_id": proj, "name": "v", "sql_query": "SELECT COUNT(*) FROM T",
                                               "validation_type": "SCALAR_VALUE", "expected_result": "0"})
    assert ok.status_code == 201 and ok.json()["validation_type"] == "SCALAR_VALUE"
    vacio = client.post("/api/test-cases/", json={"project_id": proj, "name": "v2", "sql_query": "SELECT 1 FROM T",
                                                  "validation_type": "SCALAR_VALUE", "expected_result": "  "})
    assert vacio.status_code == 422
    # las validaciones existentes no cambian
    malo = client.post("/api/test-cases/", json={"project_id": proj, "name": "v3", "sql_query": "SELECT 1 FROM T",
                                                 "validation_type": "ROW_COUNT", "expected_result": "abc"})
    assert malo.status_code == 422


def test_explain_exists_y_row_count_siguen_igual():
    assert explain_execution("PASS", "ROW_COUNT", "1", 1)["reason"].startswith("Coincide: esperabas 1 fila")
    assert "al menos una fila" in explain_execution("PASS", "EXISTS", "true", 2)["expected_text"]


# ------------------------------------------------------------------- escenario de demostración

def test_demo_scenario_es_idempotente_y_crea_tres_suites():
    proj = client.post("/api/projects/", json={"name": "Proyecto demo"}).json()["id"]

    r1 = client.post("/api/demo/scenario", json={"project_id": proj})
    r2 = client.post("/api/demo/scenario", json={"project_id": proj})
    assert r1.status_code == 200 and r2.status_code == 200
    a, b = r1.json(), r2.json()

    assert a["rules_suite"]["created_suite"] is True and b["rules_suite"]["created_suite"] is False
    assert a["rules_suite"]["suite_id"] == b["rules_suite"]["suite_id"]
    assert a["rules_suite"]["case_ids"] == b["rules_suite"]["case_ids"]
    assert b["rules_suite"]["created_cases"] == 0 and b["examples_suite"]["created_cases"] == 0 and b["control_suite"]["created_cases"] == 0
    assert a["control_suite"]["created_suite"] is True and b["control_suite"]["created_suite"] is False

    # 5 reglas + 2 ejemplos de FAIL/ERROR + 4 casos de control de cambios (Fase 8)
    assert len(client.get(f"/api/test-cases/?project_id={proj}").json()) == 11
    suite = client.get(f"/api/suites/{a['rules_suite']['suite_id']}").json()
    assert len(suite["test_cases"]) == 5
    assert len(client.get(f"/api/suites/{a['examples_suite']['suite_id']}").json()["test_cases"]) == 2
    assert len(client.get(f"/api/suites/{a['control_suite']['suite_id']}").json()["test_cases"]) == 4


def test_demo_scenario_valida_entradas():
    assert client.post("/api/demo/scenario", json={"project_id": 9999}).status_code == 404
    assert client.post("/api/demo/scenario", json={"project_id": 1, "dsn": "x"}).status_code == 422


@patch("oracledb.connect")
def test_suite_devuelve_informe_legible_por_caso(mock_connect):
    proj, conn_id = _perfil()
    ids = client.post("/api/demo/scenario", json={"project_id": proj}).json()
    # Oracle simulado: cada SELECT devuelve 1 fila con el valor correcto según los datos de demostración
    valores = iter([5, 0, 0, 4])   # las 4 reglas de valor, en orden
    conexion, cursor = _oracle(mock_connect, [], columns=("C",))
    def ejecutar(sql, params=None):
        if "WHERE ID = 3" in sql:
            cursor.fetchmany.return_value = [(3, "Regla")]
        else:
            cursor.fetchmany.return_value = [(next(valores),)]
    cursor.execute.side_effect = ejecutar

    res = client.post(f"/api/execute/suite/{ids['rules_suite']['suite_id']}",
                      json={"connection_profile_id": conn_id, "password": "clave_de_prueba"})

    assert res.status_code == 200
    body = res.json()
    assert (body["passed"], body["failed"], body["errors"]) == (5, 0, 0)
    assert len(body["details"]) == 5 and len(body["case_results"]) == 5     # contrato anterior intacto
    nombres = [r["case_name"] for r in body["case_results"]]
    assert "Hay 5 productos registrados" in nombres and "Existe el producto con ID 3" in nombres
    assert all(r["status"] == "PASS" and r["reason"].startswith("Coincide") for r in body["case_results"])
    assert "clave_de_prueba" not in res.text
    # evidencia en el historial: una fila por caso, con la suite
    hist = client.get(f"/api/history/?suite_id={ids['rules_suite']['suite_id']}").json()
    assert len(hist) == 5 and all(h["suite_id"] == ids["rules_suite"]["suite_id"] for h in hist)


@patch("oracledb.connect")
def test_suite_de_ejemplos_muestra_fail_y_error(mock_connect):
    proj, conn_id = _perfil()
    ids = client.post("/api/demo/scenario", json={"project_id": proj}).json()
    conexion, cursor = _oracle(mock_connect, [(5,)], columns=("COUNT(*)",))
    def ejecutar(sql, params=None):
        if "TABLA_QUE_NO_EXISTE" in sql:
            raise Exception("ORA-00942: table or view does not exist")
    cursor.execute.side_effect = ejecutar

    body = client.post(f"/api/execute/suite/{ids['examples_suite']['suite_id']}",
                       json={"connection_profile_id": conn_id, "password": "clave_de_prueba"}).json()

    estados = {r["case_name"]: r["status"] for r in body["case_results"]}
    assert sorted(estados.values()) == ["ERROR", "FAIL"]
    fail = next(r for r in body["case_results"] if r["status"] == "FAIL")
    assert "esperabas 6 y devolvió 5" in fail["reason"]


def test_scripts_y_reglas_de_demostracion_son_coherentes():
    """Los valores esperados de las reglas deben coincidir con los datos del script de carga."""
    seed = Path("infra/oracle/demo/seed_demo_data.sql").read_text(encoding="utf-8")
    filas = re.findall(r"VALUES\s*\(\s*(\d+)\s*,\s*'([^']*)'\s*,\s*(\d+)\s*\)", seed, re.IGNORECASE)
    assert len(filas) == 5
    activos = [f for f in filas if f[2] == "1"]
    assert (len(filas), len(activos)) == (5, 4)
    assert any(f[0] == "3" for f in filas)
    assert not [f for f in filas if not f[1].strip()]            # ningún nombre en blanco
    assert not [f for f in filas if f[2] not in ("0", "1")]      # ACTIVE solo 0/1

    esperados = {c[0]: c[4] for c in demo_scenario.RULES_CASES}
    assert esperados["Hay 5 productos registrados"] == str(len(filas))
    assert esperados["Hay 4 productos activos"] == str(len(activos))
    assert esperados["No hay productos sin nombre"] == "0"
    assert esperados["ACTIVE solo vale 0 o 1"] == "0"

    esquema = Path("infra/oracle/init/001_test_schema.sh").read_text(encoding="utf-8")
    for c in demo_scenario.RULES_CASES + demo_scenario.EXAMPLES_CASES[:1]:
        assert set(re.findall(r"\bFROM\s+([A-Z_]+)", c[2])) <= {"FRAMEWORK_TEST_ITEMS"}
    for col in ("ID", "NAME", "ACTIVE"):
        assert col in esquema


# ---------------------------------------------------------------- restricción de destinos

@patch("oracledb.connect")
@pytest.mark.parametrize("host", [
    "x)(ADDRESS=(PROTOCOL=tcp)(HOST=evil)(PORT=1521",
    "host con espacios", "host/otro", "user@host", "(DESCRIPTION=(ADDRESS=...))", "-empieza-con-guion", "host=otro",
])
def test_perfil_rechaza_hosts_que_inyectan_el_descriptor(mock_connect, host):
    proj = client.post("/api/projects/", json={"name": f"P {abs(hash(host))}"}).json()["id"]
    res = client.post("/api/connections/", json={"project_id": proj, "name": "x", "engine": "ORACLE", "host": host,
                                                 "port": 1521, "service_name": "FREEPDB1", "username": "u"})
    assert res.status_code == 422
    mock_connect.assert_not_called()


def test_perfil_rechaza_service_name_peligroso_y_acepta_nombres_validos():
    proj = client.post("/api/projects/", json={"name": "P svc"}).json()["id"]
    base = {"project_id": proj, "name": "x", "engine": "ORACLE", "port": 1521, "username": "u"}
    assert client.post("/api/connections/", json={**base, "host": "oracle_db", "service_name": "A)(B=1"}).status_code == 422
    for host in ("localhost", "oracle_db", "db-1.empresa.pe", "10.0.0.5"):
        assert client.post("/api/connections/", json={**base, "host": host, "service_name": "FREEPDB1"}).status_code == 201


def test_actualizar_perfil_tambien_valida_el_host():
    _, conn_id = _perfil()
    assert client.put(f"/api/connections/{conn_id}", json={"host": "a)(b"}).status_code == 422


@patch("oracledb.connect")
def test_lista_de_hosts_permitidos_bloquea_crear_probar_y_ejecutar(mock_connect, monkeypatch):
    proj, conn_id = _perfil(host="oracle.local")                # creado cuando no había lista

    monkeypatch.setenv("ORACLE_ALLOWED_HOSTS", "oracle_db, localhost")
    # crear / editar a un destino no permitido
    base = {"project_id": proj, "name": "n", "engine": "ORACLE", "port": 1521, "service_name": "S", "username": "u"}
    assert client.post("/api/connections/", json={**base, "host": "otro.servidor"}).status_code == 422
    assert client.post("/api/connections/", json={**base, "host": "localhost"}).status_code == 201
    assert client.put(f"/api/connections/{conn_id}", json={"host": "otro.servidor"}).status_code == 422
    # un perfil guardado antes de la lista tampoco puede probar ni ejecutar
    assert client.post(f"/api/connections/{conn_id}/test", json={"password": "p"}).status_code == 400
    assert client.post("/api/execute/quick", json={
        "connection_profile_id": conn_id, "password": "p", "sql_query": "SELECT 1 FROM DUAL",
        "validation_type": "ROW_COUNT", "expected_result": "1"}).status_code == 400
    assert client.post("/api/execute/raw", json={
        "connection_profile_id": conn_id, "password": "p", "sql_query": "SELECT 1 FROM DUAL"}).status_code == 400
    mock_connect.assert_not_called()


@patch("oracledb.connect")
def test_perfil_antiguo_con_host_invalido_no_se_ejecuta(mock_connect):
    """Un perfil guardado antes de existir la validación (host con sintaxis de descriptor) no llega a Oracle."""
    _, conn_id = _perfil()
    from app.models.connection import ConnectionProfile
    db = next(app.dependency_overrides[get_db]())
    try:
        db.query(ConnectionProfile).filter(ConnectionProfile.id == conn_id).update(
            {"host": "x)(ADDRESS=(PROTOCOL=tcp)(HOST=evil)(PORT=1521"})
        db.commit()
    finally:
        db.close()

    res = client.post("/api/execute/quick", json={
        "connection_profile_id": conn_id, "password": "p", "sql_query": "SELECT 1 FROM DUAL",
        "validation_type": "ROW_COUNT", "expected_result": "1"})

    assert res.status_code == 400
    assert "caracteres no permitidos" in res.json()["detail"]
    mock_connect.assert_not_called()


# ------------------------------------------------------------------------ interfaz (estática)

def test_inicio_usa_tres_validaciones_y_avisa_del_count():
    html = Path("frontend/index.html").read_text(encoding="utf-8")
    js = Path("frontend/js/modulos/inicio.js").read_text(encoding="utf-8")
    for valor in ("ROW_COUNT", "SCALAR_VALUE", "EXISTS"):
        assert f'value="{valor}"' in html
    assert "Cantidad de filas que devuelve la consulta" in html
    assert "Valor que devuelve la consulta" in html
    assert "COUNT\\s*\\(" in js and "Comparar el valor" in html
    # la plantilla de COUNT(*) usa el valor escalar, no la cantidad de filas
    plantilla = js[js.index("id: 'contar'"):js.index("id: 'invalidos'")]
    assert "SCALAR_VALUE" in plantilla and "ROW_COUNT" not in plantilla
    casos = Path("frontend/js/modulos/casos.js").read_text(encoding="utf-8")
    assert "SCALAR_VALUE" in casos
