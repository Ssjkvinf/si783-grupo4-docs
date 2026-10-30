"""
Pruebas de integración de la API utilizando FastAPI TestClient y base de datos aislada.
"""
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _perfil(environment_type="TEST"):
    """Crea un proyecto y un perfil de conexión guardado; devuelve (project_id, connection_profile_id)."""
    proj = client.post("/api/projects/", json={"name": f"Proyecto {environment_type}"}).json()
    conn = client.post("/api/connections/", json={
        "project_id": proj["id"], "name": f"Perfil {environment_type}", "engine": "ORACLE",
        "host": "oracle.local", "port": 1521, "service_name": "FREEPDB1",
        "username": "usuario_prueba", "environment_type": environment_type,
    }).json()
    return proj["id"], conn["id"]


def test_delete_non_existent_test_case_returns_404():
    """Verifica que eliminar un ID inexistente devuelva HTTP 404."""
    response = client.delete("/api/test-cases/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Caso de prueba no encontrado."


def test_execute_raw_controlled_error_returns_400():
    """Verifica que errores SQL controlados (ej. DDL prohibido) devuelvan HTTP 400."""
    _, conn_id = _perfil("TEST")
    payload = {
        "connection_profile_id": conn_id,
        "password": "super_secret_password_999",
        "sql_query": "DROP TABLE users"
    }
    response = client.post("/api/execute/raw", json=payload)
    assert response.status_code == 400
    assert "Rechazado por seguridad" in response.json()["detail"]
    assert "super_secret_password_999" not in response.text  # Sin fugas de contraseñas


@patch("app.api.executions.TargetDatabaseExecutor.execute_query")
def test_execute_saved_test_case_and_suite_without_exposing_passwords(mock_execute_query):
    """Punto 4.16: Ejecución individual y por suite sin requerir sql_query ni exponer contraseñas."""
    mock_execute_query.return_value = {
        "success": True,
        "statement_type": "SELECT",
        "rows": [("Val1",)],
        "rowcount": 1,
        "message": "OK",
        "error_message": None,
        "rollback_applied": False,
        "rollback_error": None
    }

    proj_id, conn_id = _perfil("TEST")

    # 1. Crear un caso de prueba
    tc_res = client.post("/api/test-cases/", json={
        "project_id": proj_id,
        "name": "TC Secret Test",
        "description": "TestCase de Integración",
        "sql_query": "SELECT * FROM dual",
        "expected_result": "1"
    })
    assert tc_res.status_code == 201
    tc_id = tc_res.json()["id"]

    # 2. Ejecutar el caso guardado pasando sólo credenciales (SIN sql_query en el body)
    secret_pass = "my_top_secret_oracle_pass_777"
    exec_res = client.post(f"/api/execute/test-case/{tc_id}", json={
        "connection_profile_id": conn_id,
        "password": secret_pass
    })
    assert exec_res.status_code == 200
    exec_data = exec_res.json()
    assert exec_data["status"] == "PASS"
    assert secret_pass not in str(exec_data)

    # 3. Crear una Suite y vincularle el caso
    suite_res = client.post("/api/suites/", json={
        "project_id": proj_id,
        "name": "Suite Secreta",
        "description": "Prueba de Suite"
    })
    assert suite_res.status_code == 201
    suite_id = suite_res.json()["id"]


    add_res = client.post(f"/api/suites/{suite_id}/test-cases/{tc_id}")
    assert add_res.status_code == 200

    # 4. Ejecutar la suite completa pasando sólo credenciales (SIN sql_query en el body)
    exec_suite_res = client.post(f"/api/execute/suite/{suite_id}", json={
        "connection_profile_id": conn_id,
        "password": secret_pass
    })
    assert exec_suite_res.status_code == 200
    suite_summary = exec_suite_res.json()
    assert suite_summary["passed"] == 1
    assert secret_pass not in str(suite_summary)


def test_list_cases_and_suites_functional():
    """Verifica el correcto funcionamiento de los endpoints de listado de casos y suites."""
    tc_res = client.get("/api/test-cases/")
    assert tc_res.status_code == 200
    assert isinstance(tc_res.json(), list)

    suites_res = client.get("/api/suites/")
    assert suites_res.status_code == 200
    assert isinstance(suites_res.json(), list)

def test_execute_raw_production_dml_blocked():
    """Verifica que un DML enviado a PRODUCTION por /api/execute/raw falle estrictamente."""
    _, conn_id = _perfil("PRODUCTION")
    payload = {
        "connection_profile_id": conn_id,
        "password": "secret_password",
        "sql_query": "INSERT INTO users(id) VALUES(1)"
    }
    response = client.post("/api/execute/raw", json=payload)
    assert response.status_code == 400
    assert "En producción solo se permiten sentencias SELECT" in response.json()["detail"]


@patch("app.api.executions.resolve_connection_credentials")
def test_execute_raw_staging_dml_requires_confirmation(mock_resolve):
    """Verifica que un DML en STAGING requiera confirm_staging_dml=True."""
    from app.models.connection import ConnectionProfile
    mock_profile = ConnectionProfile(id=99, environment_type="STAGING")
    mock_resolve.return_value = ("localhost/xe", "user", "pass", mock_profile)

    payload_no_confirm = {
        "connection_profile_id": 99,
        "password": "secret_password",
        "sql_query": "DELETE FROM users"
    }
    response_no = client.post("/api/execute/raw", json=payload_no_confirm)
    assert response_no.status_code == 400
    assert "requiere confirmación explícita" in response_no.json()["detail"]

    with patch("app.api.executions.TargetDatabaseExecutor.execute_query") as mock_exec:
        mock_exec.return_value = {
            "success": True,
            "statement_type": "DELETE",
            "rows": [],
            "rowcount": 5,
            "message": "OK",
            "error_message": None,
            "rollback_applied": True,
            "rollback_error": None
        }
        payload_confirm = {**payload_no_confirm, "confirm_staging_dml": True}
        response_yes = client.post("/api/execute/raw", json=payload_confirm)
        assert response_yes.status_code == 200
        mock_exec.assert_called_once_with("DELETE FROM users", confirm_staging_dml=True)

@patch("app.api.executions.resolve_connection_credentials")
def test_invalid_environment_returns_400(mock_resolve):
    """Verifica que un ambiente inválido de BD se rechaza con 400."""
    from unittest.mock import MagicMock
    from app.models.connection import ConnectionProfile
    mock_profile = MagicMock(spec=ConnectionProfile)
    mock_profile.id = 99
    mock_profile.environment_type = "INVALID_ENV"
    mock_resolve.return_value = ("localhost/xe", "user", "pass", mock_profile)

    payload = {
        "connection_profile_id": 99,
        "password": "secret_password",
        "sql_query": "SELECT 1 FROM dual"
    }
    response = client.post("/api/execute/raw", json=payload)
    assert response.status_code == 400
    assert "Ambiente de ejecución inválido" in response.json()["detail"]

def test_execute_raw_production_for_update_blocked():
    """Verifica que SELECT ... FOR UPDATE sea bloqueado en PRODUCTION."""
    _, conn_id = _perfil("PRODUCTION")
    payload = {
        "connection_profile_id": conn_id,
        "password": "secret_password",
        "sql_query": "SELECT * FROM users FOR UPDATE"
    }
    response = client.post("/api/execute/raw", json=payload)
    assert response.status_code == 400
    assert "FOR UPDATE están bloqueadas en Producción" in response.json()["detail"]

@patch("oracledb.connect")
def test_execute_raw_rechaza_dsn_libre_en_todas_las_rutas(mock_connect):
    """Fase 2: ninguna ruta de ejecución acepta ya un dsn/user libre; no se intenta conectar a nada."""
    proj_id, conn_id = _perfil("TEST")
    tc = client.post("/api/test-cases/", json={"project_id": proj_id, "name": "c", "sql_query": "SELECT 1 FROM dual", "expected_result": "1"}).json()["id"]
    suite = client.post("/api/suites/", json={"project_id": proj_id, "name": "s"}).json()["id"]
    libre = {"dsn": "servidor-externo:1521/xe", "user": "u", "password": "p", "sql_query": "SELECT 1 FROM dual"}

    assert client.post("/api/execute/raw", json=libre).status_code == 422
    assert client.post(f"/api/execute/test-case/{tc}", json={k: v for k, v in libre.items() if k != "sql_query"}).status_code == 422
    assert client.post(f"/api/execute/suite/{suite}", json={k: v for k, v in libre.items() if k != "sql_query"}).status_code == 422
    # incluso junto a un perfil válido, el campo dsn se rechaza (no se ignora en silencio)
    assert client.post("/api/execute/raw", json={**libre, "connection_profile_id": conn_id}).status_code == 422
    mock_connect.assert_not_called()


def test_execute_raw_exige_perfil_guardado():
    response = client.post("/api/execute/raw", json={"password": "x", "sql_query": "SELECT 1 FROM dual"})
    assert response.status_code == 422

def test_execute_raw_ignora_environment_type_del_cliente():
    """El ambiente sale del perfil: un cliente no puede 'bajar' PRODUCTION a TEST."""
    _, conn_id = _perfil("PRODUCTION")
    payload = {
        "connection_profile_id": conn_id,
        "password": "secret_password",
        "sql_query": "DELETE FROM users",
        "environment_type": "TEST"  # el cliente intenta evadir
    }
    response = client.post("/api/execute/raw", json=payload)
    assert response.status_code == 400
    assert "En producción solo se permiten sentencias SELECT" in response.json()["detail"]

@patch("app.api.executions.resolve_connection_credentials")
def test_execute_raw_production_profile_with_test_env_blocked(mock_resolve):
    """Verifica que si el perfil es PRODUCTION, se ignora el environment_type=TEST enviado."""
    from app.models.connection import ConnectionProfile
    mock_profile = ConnectionProfile(id=99, environment_type="PRODUCTION")
    mock_resolve.return_value = ("localhost/xe", "user", "pass", mock_profile)

    payload = {
        "connection_profile_id": 99,
        "password": "secret_password",
        "sql_query": "INSERT INTO users(id) VALUES(1)",
        "environment_type": "TEST" # Cliente intenta evadir
    }
    response = client.post("/api/execute/raw", json=payload)
    assert response.status_code == 400
    assert "En producción solo se permiten sentencias SELECT" in response.json()["detail"]

@patch("oracledb.connect")
def test_connection_test_invalid_environment_returns_400(mock_connect):
    """Verifica que un test de conexión con un ambiente inválido se rechace con 400 y sin conectar."""
    # 1. Crear proyecto
    proj_res = client.post("/api/projects/", json={"name": "Temp Project", "description": ""})
    assert proj_res.status_code == 201
    proj_id = proj_res.json()["id"]

    from app.core.database import get_db
    from app.main import app
    db_gen = app.dependency_overrides[get_db]()
    db = next(db_gen)

    from app.models.connection import ConnectionProfile
    invalid_profile = ConnectionProfile(
        project_id=proj_id, name="Invalid", host="localhost", port=1521,
        service_name="xe", username="u", environment_type="INVALID_DB"
    )
    db.add(invalid_profile)
    db.commit()
    db.refresh(invalid_profile)
    prof_id = invalid_profile.id
    db.close()

    # 3. Testear conexión
    response = client.post(f"/api/connections/{prof_id}/test", json={"password": "pwd"})
    assert response.status_code == 400
    assert "Ambiente de ejecución inválido" in response.json()["detail"]
    mock_connect.assert_not_called()
