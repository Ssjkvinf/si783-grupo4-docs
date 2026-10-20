"""
Pruebas de integración de la Fase 2 contra un Oracle LOCAL DESECHABLE (nunca contra la VM de Azure).

Qué demuestran (todo verificado consultando la base desde una conexión INDEPENDIENTE):
  1. SELECT con las tres validaciones (cantidad de filas, valor escalar, existencia) y el ERROR real de Oracle.
  2. Un INSERT en ambiente TEST termina en ROLLBACK: la fila no permanece (antes = después).
     Es una comprobación de ESTE caso con ESTA cuenta; el rollback no es una garantía universal
     (ver «Limitaciones» en docs/demostracion-fase2.md: secuencias, triggers autónomos, DDL, funciones con COMMIT).
  3. DROP / TRUNCATE / ALTER / varias sentencias se rechazan ANTES de abrir una conexión y la tabla queda intacta.
     La cuenta usada solo tiene CREATE SESSION + SELECT/INSERT sobre una tabla de otro dueño: aunque la política
     fallara, esa cuenta no podría borrar la tabla. No se ejecuta ningún DROP real.
  4. La suite de demostración se configura una vez y se repite; al romper un dato aparece un FAIL con evidencia.

Requisitos (todas por variables de entorno; no se escriben en ningún archivo del repositorio):
  RUN_ORACLE_TESTS=1, FRAMEWORK_TEST_PASSWORD, ORACLE_HOST / ORACLE_PORT / ORACLE_SERVICE.
  Para las pruebas de privilegios mínimos además ORACLE_PWD (contraseña de SYS del Oracle desechable).
"""
import os
import re
import secrets
from pathlib import Path
from unittest.mock import patch

import oracledb
import pytest
from fastapi.testclient import TestClient
from oracle_guard import destructive_skip_reason

from app.main import app

run_oracle = os.getenv("RUN_ORACLE_TESTS", "0") == "1"
test_password = os.getenv("FRAMEWORK_TEST_PASSWORD", "").strip()
sys_password = os.getenv("ORACLE_PWD", "").strip()

HOST = os.getenv("ORACLE_HOST", "127.0.0.1")
# Estas pruebas borran filas, crean cuentas y usan la clave de SYS: solo corren contra un Oracle local o de CI (tests/oracle_guard.py).
_guard = destructive_skip_reason(HOST)

pytestmark = [
    pytest.mark.oracle_integration,
    pytest.mark.skipif(
        not run_oracle or not test_password,
        reason="Pruebas Oracle desactivadas. Requiere RUN_ORACLE_TESTS=1 y FRAMEWORK_TEST_PASSWORD",
    ),
    pytest.mark.skipif(_guard is not None, reason=_guard or ""),
]
PORT = int(os.getenv("ORACLE_PORT", "1521"))
SERVICE = os.getenv("ORACLE_SERVICE", "FREEPDB1")
DEMO_USER = os.getenv("ORACLE_TEST_USER", "FRAMEWORK_TEST")
DSN = f"{HOST}:{PORT}/{SERVICE}"

client = TestClient(app)
SEED = Path("infra/oracle/demo/seed_demo_data.sql")


def _connect(user, password, sysdba=False):
    kwargs = {"mode": oracledb.AUTH_MODE_SYSDBA} if sysdba else {}
    return oracledb.connect(user=user, password=password, dsn=DSN, **kwargs)


def _scalar(user, password, sql, **bind):
    """Consulta desde una conexión NUEVA e independiente de la que usa la aplicación."""
    with _connect(user, password) as conn:
        cur = conn.cursor()
        cur.execute(sql, bind)
        return cur.fetchone()[0]


def _seed_demo_data():
    """Carga los datos de demostración con las mismas sentencias del script infra/oracle/demo/seed_demo_data.sql."""
    sentencias = [m.group(1) for m in re.finditer(r"^((?:DELETE|INSERT)\b[^;]*);\s*$", SEED.read_text(encoding="utf-8"),
                                                   re.MULTILINE | re.IGNORECASE)]
    assert len(sentencias) == 6          # 1 DELETE + 5 INSERT
    with _connect(DEMO_USER, test_password) as conn:
        cur = conn.cursor()
        for s in sentencias:
            cur.execute(s)
        conn.commit()


def _perfil(user, password, environment_type="TEST", name="Perfil Oracle desechable"):
    proj = client.post("/api/projects/", json={"name": f"Proyecto {name}"}).json()
    conn = client.post("/api/connections/", json={
        "project_id": proj["id"], "name": name, "engine": "ORACLE", "host": HOST, "port": PORT,
        "service_name": SERVICE, "username": user, "environment_type": environment_type})
    assert conn.status_code == 201, conn.text
    return proj["id"], conn.json()["id"], password


def _quick(conn_id, password, sql, validation, expected):
    res = client.post("/api/execute/quick", json={
        "connection_profile_id": conn_id, "password": password, "sql_query": sql,
        "validation_type": validation, "expected_result": expected})
    assert res.status_code == 200, res.text
    return res.json()


@pytest.fixture()
def demo_data():
    _seed_demo_data()
    yield
    _seed_demo_data()        # deja la tabla de demostración como la espera la suite


@pytest.fixture(scope="module")
def cuentas_minimas():
    """
    FW_OWNER (dueño de la tabla CANARY) y FW_TEST_MIN (solo CREATE SESSION + SELECT/INSERT sobre CANARY).
    Se crean con SYS en el Oracle desechable. Idempotente. No se ejecuta ningún DROP.
    """
    if not sys_password:
        pytest.skip("Requiere ORACLE_PWD (contraseña de SYS del Oracle desechable) para crear las cuentas de prueba")
    owner_pwd = "Fo" + secrets.token_hex(8) + "9x"
    min_pwd = "Fm" + secrets.token_hex(8) + "9x"
    with _connect("SYS", sys_password, sysdba=True) as conn:
        cur = conn.cursor()
        for usuario, pwd in (("FW_OWNER", owner_pwd), ("FW_TEST_MIN", min_pwd)):
            cur.execute("SELECT COUNT(*) FROM dba_users WHERE username = :u", u=usuario)
            verbo = "ALTER" if cur.fetchone()[0] else "CREATE"
            cur.execute(f'{verbo} USER {usuario} IDENTIFIED BY "{pwd}"')
        cur.execute("GRANT CREATE SESSION TO FW_OWNER")
        cur.execute("GRANT CREATE TABLE TO FW_OWNER")
        cur.execute("ALTER USER FW_OWNER QUOTA 1M ON USERS")
        cur.execute("GRANT CREATE SESSION TO FW_TEST_MIN")
        cur.execute("SELECT COUNT(*) FROM dba_tables WHERE owner = 'FW_OWNER' AND table_name = 'CANARY'")
        existe = cur.fetchone()[0]
    with _connect("FW_OWNER", owner_pwd) as conn:
        cur = conn.cursor()
        if not existe:
            cur.execute("CREATE TABLE FW_OWNER.CANARY (ID NUMBER PRIMARY KEY, NAME VARCHAR2(50) NOT NULL)")
        cur.execute("DELETE FROM FW_OWNER.CANARY")
        for i, n in ((1, "canario-1"), (2, "canario-2"), (3, "canario-3")):
            cur.execute("INSERT INTO FW_OWNER.CANARY (ID, NAME) VALUES (:i, :n)", i=i, n=n)
        cur.execute("GRANT SELECT, INSERT ON FW_OWNER.CANARY TO FW_TEST_MIN")
        conn.commit()
    return {"owner": ("FW_OWNER", owner_pwd), "min": ("FW_TEST_MIN", min_pwd)}


# ------------------------------------------------------------------------------------ 1. SELECT

def test_select_con_las_tres_validaciones_y_errores_reales(demo_data):
    _, conn_id, pwd = _perfil(DEMO_USER, test_password)

    # cantidad de filas
    r = _quick(conn_id, pwd, "SELECT ID, NAME FROM FRAMEWORK_TEST_ITEMS", "ROW_COUNT", "5")
    assert (r["status"], r["rowcount"]) == ("PASS", 5)
    assert r["columns"] == ["ID", "NAME"] and len(r["rows"]) == 5

    # valor escalar: el número que calcula COUNT(*) (5), no el número de filas (1)
    r = _quick(conn_id, pwd, "SELECT COUNT(*) FROM FRAMEWORK_TEST_ITEMS", "SCALAR_VALUE", "5")
    assert r["status"] == "PASS" and r["obtained_text"] == "La consulta devolvió el valor 5" and r["rowcount"] == 1
    r = _quick(conn_id, pwd, "SELECT COUNT(*) FROM FRAMEWORK_TEST_ITEMS", "SCALAR_VALUE", "4")
    assert r["status"] == "FAIL" and "esperabas 4 y devolvió 5" in r["reason"]
    # la confusión original: ROW_COUNT=1 sobre un COUNT(*) pasa siempre; la explicación lo avisa
    r = _quick(conn_id, pwd, "SELECT COUNT(*) FROM FRAMEWORK_TEST_ITEMS", "ROW_COUNT", "1")
    assert r["status"] == "PASS" and "no el número que calcula" in r["reason"]

    # existencia
    assert _quick(conn_id, pwd, "SELECT ID FROM FRAMEWORK_TEST_ITEMS WHERE ID = 3", "EXISTS", "true")["status"] == "PASS"
    assert _quick(conn_id, pwd, "SELECT ID FROM FRAMEWORK_TEST_ITEMS WHERE ID = 99", "EXISTS", "true")["status"] == "FAIL"

    # ERROR real de Oracle (tabla inexistente) y contraseña incorrecta
    r = _quick(conn_id, pwd, "SELECT COUNT(*) FROM TABLA_QUE_NO_EXISTE", "SCALAR_VALUE", "0")
    assert r["status"] == "ERROR" and "ORA-00942" in r["error_message"]
    r = _quick(conn_id, "contrasena-incorrecta", "SELECT 1 FROM DUAL", "ROW_COUNT", "1")
    assert r["status"] == "ERROR" and "contrasena-incorrecta" not in str(r)


def test_produccion_oculta_filas_y_no_permite_valor_escalar(demo_data):
    _, conn_id, pwd = _perfil(DEMO_USER, test_password, "PRODUCTION", "Perfil PRODUCTION")
    r = _quick(conn_id, pwd, "SELECT ID, NAME FROM FRAMEWORK_TEST_ITEMS", "ROW_COUNT", "5")
    assert r["status"] == "PASS" and r["rows_hidden"] is True and r["rows"] == []
    r = _quick(conn_id, pwd, "SELECT COUNT(*) FROM FRAMEWORK_TEST_ITEMS", "SCALAR_VALUE", "5")
    assert r["status"] == "ERROR" and "PRODUCTION" in r["error_message"]


# ---------------------------------------------------------------- 2. INSERT con ROLLBACK (TEST)

def test_insert_en_test_termina_en_rollback_antes_y_despues(cuentas_minimas):
    owner, minimo = cuentas_minimas["owner"], cuentas_minimas["min"]
    proj, conn_id, pwd = _perfil(*minimo, name="Cuenta de privilegios mínimos")

    antes = _scalar(*owner, "SELECT COUNT(*) FROM FW_OWNER.CANARY")
    assert antes == 3

    tc = client.post("/api/test-cases/", json={
        "project_id": proj, "name": "INSERT con rollback",
        "sql_query": "INSERT INTO FW_OWNER.CANARY (ID, NAME) VALUES (900, 'fila-temporal')",
        "validation_type": "ROW_COUNT", "expected_result": "1"}).json()["id"]
    res = client.post(f"/api/execute/test-case/{tc}", json={"connection_profile_id": conn_id, "password": pwd})
    assert res.status_code == 200
    hist = res.json()
    assert hist["status"] == "PASS" and hist["statement_type"] == "INSERT" and hist["rowcount"] == 1
    assert hist["rollback_applied"] is True

    # conexión INDEPENDIENTE: la fila insertada no permanece
    despues = _scalar(*owner, "SELECT COUNT(*) FROM FW_OWNER.CANARY")
    assert despues == antes
    assert _scalar(*owner, "SELECT COUNT(*) FROM FW_OWNER.CANARY WHERE ID = 900") == 0
    print(f"\n[EVIDENCIA INSERT] filas antes={antes} · INSERT dentro de la app: rowcount=1, rollback_applied=True "
          f"· filas después={despues} · filas con ID=900: 0")


def test_control_negativo_un_commit_si_haria_visible_la_fila(cuentas_minimas):
    """Demuestra que la verificación 'antes = después' NO es vacía: un INSERT con COMMIT (fuera de la app) sí se ve."""
    owner, minimo = cuentas_minimas["owner"], cuentas_minimas["min"]
    antes = _scalar(*owner, "SELECT COUNT(*) FROM FW_OWNER.CANARY")
    with _connect(*minimo) as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO FW_OWNER.CANARY (ID, NAME) VALUES (901, 'control-negativo')")
        conn.commit()
    try:
        assert _scalar(*owner, "SELECT COUNT(*) FROM FW_OWNER.CANARY") == antes + 1
    finally:
        with _connect(*owner) as conn:                      # limpieza con la cuenta dueña (la mínima no puede borrar)
            conn.cursor().execute("DELETE FROM FW_OWNER.CANARY WHERE ID = 901")
            conn.commit()
    assert _scalar(*owner, "SELECT COUNT(*) FROM FW_OWNER.CANARY") == antes


# ------------------------------------------------------------------------ 3. DROP rechazado

@pytest.mark.parametrize("sql", [
    "DROP TABLE FW_OWNER.CANARY",
    "TRUNCATE TABLE FW_OWNER.CANARY",
    "ALTER TABLE FW_OWNER.CANARY ADD (EXTRA NUMBER)",
    "SELECT 1 FROM DUAL; DROP TABLE FW_OWNER.CANARY",
])
def test_ddl_se_rechaza_antes_de_conectar_y_la_tabla_queda_intacta(cuentas_minimas, sql):
    owner, minimo = cuentas_minimas["owner"], cuentas_minimas["min"]
    proj, conn_id, pwd = _perfil(*minimo, name="Cuenta mínima DDL")
    antes = _scalar(*owner, "SELECT COUNT(*) FROM FW_OWNER.CANARY")
    tc = client.post("/api/test-cases/", json={
        "project_id": proj, "name": "DDL", "sql_query": sql,
        "validation_type": "ROW_COUNT", "expected_result": "0"}).json()["id"]

    with patch("oracledb.connect", wraps=oracledb.connect) as espia:
        res = client.post(f"/api/execute/test-case/{tc}", json={"connection_profile_id": conn_id, "password": pwd})
        conexiones_abiertas = espia.call_count

    assert res.status_code == 200
    hist = res.json()
    assert hist["status"] == "ERROR"
    assert "Rechazado" in hist["error_message"]
    assert conexiones_abiertas == 0, "la política debe rechazar la sentencia antes de abrir una conexión a Oracle"

    # tabla intacta, vista desde otra conexión y desde el diccionario de datos
    assert _scalar(*owner, "SELECT COUNT(*) FROM user_tables WHERE table_name = 'CANARY'") == 1
    assert _scalar(*owner, "SELECT COUNT(*) FROM FW_OWNER.CANARY") == antes
    assert _scalar(*owner, "SELECT COUNT(*) FROM user_tab_columns WHERE table_name = 'CANARY' AND column_name = 'EXTRA'") == 0
    print(f"\n[EVIDENCIA DDL] '{sql}' -> {hist['status']} ({hist['error_message']}) · conexiones a Oracle: 0 "
          f"· CANARY existe, filas={antes}")


def test_la_cuenta_minima_solo_tiene_los_privilegios_esperados(cuentas_minimas):
    """Evidencia de privilegios mínimos sin ejecutar ningún DROP: lo que ve el diccionario de datos."""
    with _connect("SYS", sys_password, sysdba=True) as conn:
        cur = conn.cursor()
        cur.execute("SELECT privilege FROM dba_sys_privs WHERE grantee = 'FW_TEST_MIN'")
        assert sorted(r[0] for r in cur.fetchall()) == ["CREATE SESSION"]
        cur.execute("SELECT privilege FROM dba_tab_privs WHERE grantee = 'FW_TEST_MIN' AND table_name = 'CANARY' "
                    "AND owner = 'FW_OWNER'")
        assert sorted(r[0] for r in cur.fetchall()) == ["INSERT", "SELECT"]
        cur.execute("SELECT COUNT(*) FROM dba_role_privs WHERE grantee = 'FW_TEST_MIN'")
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT COUNT(*) FROM dba_tab_privs WHERE grantee = 'FW_TEST_MIN' AND privilege IN ('DELETE','UPDATE','ALTER')")
        assert cur.fetchone()[0] == 0


# ---------------------------------------------------------------- 4. Suite repetible con evidencia

def test_suite_de_reglas_se_configura_una_vez_y_se_repite(demo_data):
    proj, conn_id, pwd = _perfil(DEMO_USER, test_password, name="Perfil suite demo")
    ids = client.post("/api/demo/scenario", json={"project_id": proj}).json()
    rules, examples = ids["rules_suite"]["suite_id"], ids["examples_suite"]["suite_id"]
    cred = {"connection_profile_id": conn_id, "password": pwd}

    def ejecutar(suite_id):
        res = client.post(f"/api/execute/suite/{suite_id}", json=cred)
        assert res.status_code == 200, res.text
        return res.json()

    # 1ª ejecución: las 5 reglas pasan
    primera = ejecutar(rules)
    assert (primera["passed"], primera["failed"], primera["errors"]) == (5, 0, 0)
    assert all(r["reason"].startswith("Coincide") for r in primera["case_results"])

    # los ejemplos didácticos muestran FAIL y ERROR reales
    ej = ejecutar(examples)
    assert (ej["passed"], ej["failed"], ej["errors"]) == (0, 1, 1)
    assert any("ORA-00942" in (r["error_message"] or "") for r in ej["case_results"] if r["status"] == "ERROR")

    # alguien introduce un dato inválido (ACTIVE = 7); la MISMA suite, sin reconstruir nada, detecta el problema
    with _connect(DEMO_USER, test_password) as conn:
        conn.cursor().execute("UPDATE FRAMEWORK_TEST_ITEMS SET ACTIVE = 7 WHERE ID = 4")
        conn.commit()
    segunda = ejecutar(rules)
    estados = {r["case_name"]: r for r in segunda["case_results"]}
    assert (segunda["passed"], segunda["failed"], segunda["errors"]) == (4, 1, 0)
    fallo = estados["ACTIVE solo vale 0 o 1"]
    assert fallo["status"] == "FAIL" and "esperabas 0 y devolvió 1" in fallo["reason"]

    # se corrige el dato y la suite vuelve a pasar; el historial conserva las 3 ejecuciones de reglas
    _seed_demo_data()
    tercera = ejecutar(rules)
    assert (tercera["passed"], tercera["failed"]) == (5, 0)
    hist = client.get(f"/api/history/?suite_id={rules}&limit=100").json()
    assert len(hist) == 15
    assert sorted({h["status"] for h in hist}) == ["FAIL", "PASS"]
    print(f"\n[EVIDENCIA SUITE] ejecución 1: {primera['passed']} PASS · ejecución 2 (dato roto): "
          f"{segunda['passed']} PASS, {segunda['failed']} FAIL · ejecución 3 (corregido): {tercera['passed']} PASS · "
          f"historial de la suite: {len(hist)} registros")


# --------------------------------------------------- 5. Ejecución directa: solo con perfil guardado

def test_execute_raw_en_produccion_usa_el_perfil_guardado(demo_data):
    """Sustituye al uso con dsn libre: el mismo comportamiento de PRODUCTION, pero con un perfil registrado."""
    _, conn_id, pwd = _perfil(DEMO_USER, test_password, "PRODUCTION", "Perfil PRODUCTION raw")
    cred = {"connection_profile_id": conn_id, "password": pwd}

    borrado = client.post("/api/execute/raw", json={**cred, "sql_query": "DELETE FROM FRAMEWORK_TEST_ITEMS WHERE ID = 1"})
    assert borrado.status_code == 400
    assert "En producción solo se permiten sentencias SELECT" in borrado.json()["detail"]

    lectura = client.post("/api/execute/raw", json={**cred, "sql_query": "SELECT * FROM FRAMEWORK_TEST_ITEMS"})
    assert lectura.status_code == 200 and lectura.json()["data"] == []

    error = client.post("/api/execute/raw", json={**cred, "sql_query": "SELECT * FROM TABLA_INEXISTENTE_PROD"})
    assert error.status_code == 400
    assert "ORA-" not in error.json()["detail"]
    assert _scalar(DEMO_USER, test_password, "SELECT COUNT(*) FROM FRAMEWORK_TEST_ITEMS") == 5
