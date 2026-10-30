"""
Usuarios, roles y seguridad del acceso (APP_ACCESS_ENABLED=true).

Cubre: hash de contraseñas, token firmado con caducidad, primer administrador desde el entorno, solicitud de cuenta y
aprobación, permisos ADMIN/TESTER, bloqueo por intentos fallidos, límite por IP, cierre de sesión que anula el token,
cambio de contraseña y «ejecutado por» en el historial.
"""
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User
from app.security import auth

ADMIN = "admin"
# Contraseñas ficticias de prueba, compuestas al ejecutar.
CLAVE_ADMIN = "clave" + "-admin-ficticia"
CLAVE_TESTER = "Tester" + "2026ficticia"


@pytest.fixture(autouse=True)
def acceso_activado(monkeypatch):
    monkeypatch.setenv("APP_ACCESS_ENABLED", "true")
    monkeypatch.setenv("APP_ACCESS_USERNAME", ADMIN)
    monkeypatch.setenv("APP_ACCESS_PASSWORD", CLAVE_ADMIN)
    monkeypatch.setenv("APP_SESSION_SECRET", "secreto-de-prueba-ficticio")
    monkeypatch.setenv("ENVIRONMENT", "development")


def _ingresar(usuario=ADMIN, clave=CLAVE_ADMIN):
    c = TestClient(app)
    r = c.post("/api/login", json={"username": usuario, "password": clave})
    return c, r


def _tester_aprobado(admin_client, username="ana.qa"):
    r = TestClient(app).post("/api/register", json={"username": username, "full_name": "Ana Pérez", "password": CLAVE_TESTER})
    assert r.status_code == 201
    uid = next(u["id"] for u in admin_client.get("/api/users").json() if u["username"] == username)
    assert admin_client.patch(f"/api/users/{uid}", json={"active": True}).status_code == 200
    return uid


# ------------------------------------------------------------------------------------------- piezas de seguridad
def test_hash_con_sal_y_verificacion():
    h1, h2 = auth.hash_password("Una clave 123"), auth.hash_password("Una clave 123")
    assert h1 != h2 and h1.startswith("pbkdf2_sha256$")
    assert "Una clave 123" not in h1
    assert auth.verify_password("Una clave 123", h1)
    assert not auth.verify_password("otra", h1)
    assert not auth.verify_password("cualquiera", None)


def test_token_firmado_caduca_y_no_se_puede_alterar(monkeypatch):
    t = auth.crear_token(1, "ana", "TESTER", 1)
    assert auth.leer_token(t)["u"] == "ana"
    cuerpo, firma = t[3:].rsplit(".", 1)
    assert auth.leer_token(f"v2.{cuerpo}.{'0' * len(firma)}") is None
    vencido = auth.crear_token(1, "ana", "TESTER", 1, horas=-1)
    assert auth.leer_token(vencido) is None
    monkeypatch.setenv("APP_SESSION_SECRET", "otro-secreto-ficticio")
    assert auth.leer_token(t) is None


@pytest.mark.parametrize("clave,motivo", [("corta1", "10 caracteres"), ("solamenteletras", "letras y números"),
                                          ("ana.qa12345", "nombre de usuario")])
def test_politica_de_contrasenas(clave, motivo):
    assert motivo in auth.problemas_de_contrasena(clave, "ana.qa")
    assert auth.problemas_de_contrasena(CLAVE_TESTER, "ana.qa") is None


# ------------------------------------------------------------------------------------------- ingreso
def test_primer_admin_se_crea_desde_el_entorno_y_no_guarda_la_clave(setup_isolated_db):
    c, r = _ingresar()
    assert r.status_code == 200 and r.json()["usuario"]["role"] == "ADMIN"
    u = setup_isolated_db.query(User).filter_by(username=ADMIN).one()
    assert u.password_hash != CLAVE_ADMIN and CLAVE_ADMIN not in u.password_hash
    assert c.get("/api/me").json()["role"] == "ADMIN"


def test_cada_ingreso_tiene_un_token_distinto():
    _, r1 = _ingresar()
    _, r2 = _ingresar()
    assert r1.cookies["session_token"] != r2.cookies["session_token"]


def test_mensaje_igual_para_usuario_inexistente_y_clave_mala():
    _, r1 = _ingresar("no.existe", "lo-que-sea-123")
    _, r2 = _ingresar(ADMIN, "incorrecta-123")
    assert r1.status_code == r2.status_code == 401
    assert r1.json() == r2.json()


def test_cuenta_se_bloquea_tras_cinco_fallos():
    for _ in range(auth.MAX_FALLOS_CUENTA):
        _, r = _ingresar(ADMIN, "incorrecta-123")
        assert r.status_code == 401
    _, r = _ingresar()  # aun con la clave correcta
    assert r.status_code == 423


def test_limite_por_ip_responde_429():
    for i in range(auth.MAX_FALLOS_IP):
        _ingresar(f"usuario{i}", "incorrecta-123")
    _, r = _ingresar()
    assert r.status_code == 429


def test_cerrar_sesion_anula_el_token_aunque_se_reutilice():
    c, r = _ingresar()
    token = r.cookies["session_token"]
    assert c.post("/api/logout").status_code == 200
    otro = TestClient(app)
    otro.cookies.set("session_token", token)
    assert otro.get("/api/projects/").status_code == 401


# ------------------------------------------------------------------------------------------- solicitud de cuenta y roles
def test_solicitud_queda_pendiente_hasta_que_el_admin_la_aprueba():
    admin, _ = _ingresar()
    r = TestClient(app).post("/api/register", json={"username": "ana.qa", "full_name": "Ana Pérez", "password": CLAVE_TESTER})
    assert r.status_code == 201
    _, r = _ingresar("ana.qa", CLAVE_TESTER)
    assert r.status_code == 403 and "aprobada" in r.json()["detail"]
    _tester = next(u for u in admin.get("/api/users").json() if u["username"] == "ana.qa")
    assert _tester["role"] == "TESTER" and _tester["active"] is False
    admin.patch(f"/api/users/{_tester['id']}", json={"active": True})
    _, r = _ingresar("ana.qa", CLAVE_TESTER)
    assert r.status_code == 200 and r.json()["usuario"]["role"] == "TESTER"


def test_solicitud_rechaza_clave_debil_y_usuario_repetido():
    c = TestClient(app)
    assert c.post("/api/register", json={"username": "ana.qa", "full_name": "Ana", "password": "corta"}).status_code == 422
    assert c.post("/api/register", json={"username": "ana.qa", "full_name": "Ana", "password": CLAVE_TESTER}).status_code == 201
    assert c.post("/api/register", json={"username": "ANA.QA", "full_name": "Ana", "password": CLAVE_TESTER}).status_code == 409


def test_solicitud_se_puede_desactivar(monkeypatch):
    monkeypatch.setenv("APP_REGISTRATION_ENABLED", "false")
    r = TestClient(app).post("/api/register", json={"username": "ana.qa", "full_name": "Ana", "password": CLAVE_TESTER})
    assert r.status_code == 403


def test_tester_no_administra_pero_si_trabaja_con_casos():
    admin, _ = _ingresar()
    pid = admin.post("/api/projects/", json={"name": "Proyecto QA"}).json()["id"]
    _tester_aprobado(admin)
    tester, _ = _ingresar("ana.qa", CLAVE_TESTER)
    assert tester.get("/api/users").status_code == 403
    assert tester.post("/api/projects/", json={"name": "Otro"}).status_code == 403
    assert tester.post("/api/connections/", json={"project_id": pid, "name": "x", "host": "db.example.com", "port": 1521,
                                                 "service_name": "FREEPDB1", "username": "u"}).status_code == 403
    assert tester.get("/api/projects/").status_code == 200
    r = tester.post("/api/test-cases/", json={"project_id": pid, "name": "Hay clientes", "sql_query": "SELECT * FROM clientes",
                                              "expected_result": "3"})
    assert r.status_code == 201, r.text


def test_cambiar_el_rol_cierra_la_sesion_de_ese_usuario():
    admin, _ = _ingresar()
    uid = _tester_aprobado(admin)
    tester, _ = _ingresar("ana.qa", CLAVE_TESTER)
    assert tester.get("/api/me").status_code == 200
    admin.patch(f"/api/users/{uid}", json={"role": "ADMIN"})
    assert tester.get("/api/me").status_code == 401


def test_no_se_puede_quitar_el_ultimo_admin_ni_degradarse_a_si_mismo():
    admin, _ = _ingresar()
    yo = next(u for u in admin.get("/api/users").json() if u["username"] == ADMIN)
    assert admin.patch(f"/api/users/{yo['id']}", json={"role": "TESTER"}).status_code == 409
    assert admin.patch(f"/api/users/{yo['id']}", json={"active": False}).status_code == 409
    assert admin.delete(f"/api/users/{yo['id']}").status_code == 409


def test_admin_crea_restablece_y_elimina():
    admin, _ = _ingresar()
    r = admin.post("/api/users", json={"username": "luis", "full_name": "Luis", "password": CLAVE_TESTER, "role": "TESTER"})
    assert r.status_code == 201 and r.json()["active"] is True
    uid = r.json()["id"]
    nueva = "Restablecida" + "77ficticia"
    assert admin.post(f"/api/users/{uid}/reset-password", json={"nueva": nueva}).status_code == 200
    assert _ingresar("luis", CLAVE_TESTER)[1].status_code == 401
    assert _ingresar("luis", nueva)[1].status_code == 200
    assert admin.delete(f"/api/users/{uid}").status_code == 204


def test_cambiar_mi_contrasena_renueva_mi_sesion_y_cierra_las_otras():
    admin, _ = _ingresar()
    _tester_aprobado(admin)
    sesion_1, _ = _ingresar("ana.qa", CLAVE_TESTER)
    sesion_2, _ = _ingresar("ana.qa", CLAVE_TESTER)
    nueva = "Cambiada" + "2026ficticia"
    assert sesion_1.post("/api/me/password", json={"actual": "mala-123", "nueva": nueva}).status_code == 400
    assert sesion_1.post("/api/me/password", json={"actual": CLAVE_TESTER, "nueva": "corta"}).status_code == 422
    assert sesion_1.post("/api/me/password", json={"actual": CLAVE_TESTER, "nueva": nueva}).status_code == 200
    assert sesion_1.get("/api/me").status_code == 200
    assert sesion_2.get("/api/me").status_code == 401


def test_cabeceras_de_seguridad():
    r = TestClient(app).get("/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"


@pytest.mark.parametrize("variable,valor", [("APP_SESSION_SECRET", "default_insecure_secret_replace_in_prod"),
                                            ("APP_SESSION_SECRET", "secreto_ficticio_largo_y_complejo"),
                                            ("APP_ACCESS_PASSWORD", "contrasena_ficticia")])
def test_los_valores_de_ejemplo_publicados_no_sirven_en_serio(monkeypatch, variable, valor):
    monkeypatch.setenv(variable, valor)
    r = TestClient(app).get("/health")
    assert r.status_code == 503 and variable in r.json()["detail"]
    assert valor not in r.text
    assert TestClient(app).post("/api/login", json={"username": ADMIN, "password": CLAVE_ADMIN}).status_code == 503


def test_usuario_inexistente_cuesta_lo_mismo_que_uno_real(monkeypatch):
    iteraciones = []
    original = auth.hashlib.pbkdf2_hmac

    def espia(alg, clave, sal, n, *a):
        iteraciones.append(n)
        return original(alg, clave, sal, n, *a)

    monkeypatch.setattr(auth.hashlib, "pbkdf2_hmac", espia)
    real = auth.hash_password("Una clave 123")
    iteraciones.clear()
    auth.verify_password("otra", real)
    auth.verify_password("otra", None)
    assert iteraciones[0] == iteraciones[-1] == auth._iteraciones()


def test_produccion_confia_solo_en_caddy_para_la_ip_del_visitante():
    import yaml
    from pathlib import Path
    compose = yaml.safe_load(Path("infra/production/compose.yml").read_text(encoding="utf-8"))
    api = compose["services"]["api"]
    assert "ports" not in api, "la API no debe publicar puertos: solo Caddy la alcanza"
    assert any(e.startswith("FORWARDED_ALLOW_IPS=") for e in api["environment"])
    assert "--proxy-headers" in Path("scripts/start_production.sh").read_text(encoding="utf-8")


def test_la_interfaz_se_revalida_para_no_quedarse_con_js_viejo():
    c, _ = _ingresar()
    assert c.get("/ui/app.js").headers.get("cache-control") == "no-cache"
    assert TestClient(app).get("/login").headers.get("cache-control") == "no-cache"


def test_cookie_de_sesion_httponly_y_samesite():
    _, r = _ingresar()
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "max-age=28800" in cookie


# ------------------------------------------------------------------------------------------- ejecutado por
def test_historial_registra_quien_ejecuto(setup_isolated_db, monkeypatch):
    from app.api import executions

    class EjecutorFalso:
        environment_type = "TEST"

        def __init__(self, **kw):
            pass

        def execute_query(self, sql, confirm_staging_dml=False):
            return {"success": True, "statement_type": "SELECT", "rows": [(1,), (2,)], "columns": ["ID"], "rowcount": 2,
                    "rollback_applied": False, "rollback_error": None}

        def disconnect(self):
            pass

    monkeypatch.setattr(executions, "TargetDatabaseExecutor", EjecutorFalso)
    admin, _ = _ingresar()
    pid = admin.post("/api/projects/", json={"name": "Proyecto QA"}).json()["id"]
    perfil = admin.post("/api/connections/", json={"project_id": pid, "name": "Demo", "host": "db.example.com", "port": 1521,
                                                  "service_name": "FREEPDB1", "username": "demo",
                                                  "environment_type": "TEST"}).json()
    _tester_aprobado(admin)
    tester, _ = _ingresar("ana.qa", CLAVE_TESTER)
    r = tester.post("/api/execute/quick", json={"connection_profile_id": perfil["id"], "password": "x" + "ficticia",
                                                "sql_query": "SELECT id FROM clientes", "expected_result": "2"})
    assert r.status_code == 200, r.text
    from app.models.history import ExecutionHistory
    assert setup_isolated_db.query(ExecutionHistory).one().executed_by == "ana.qa"
    resumen = admin.get("/api/usage/summary").json()
    assert resumen["por_usuario"] == [{"usuario": "ana.qa", "ejecuciones": 1}]
