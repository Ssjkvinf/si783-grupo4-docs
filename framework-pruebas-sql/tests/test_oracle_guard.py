"""
Fase 7 — Guardia de las pruebas y scripts Oracle destructivos (tests/oracle_guard.py y scripts/db/liquibase_demo.sh).

Demuestran que con un host remoto las pruebas se OMITEN y NO se abre ninguna conexión: un plugin de pytest (en un
subproceso) reemplaza `oracledb.connect` por una función que deja una marca en un archivo y lanza una excepción.
No usan Oracle ni red.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from oracle_guard import CONFIRM_VAR, destructive_skip_reason

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"


# --------------------------------------------------------------------------------------------- la regla
@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "LOCALHOST", "::1", "127.0.0.5"])
def test_los_hosts_locales_estan_permitidos(host):
    assert destructive_skip_reason(host, {}) is None


@pytest.mark.parametrize("host", ["db.example.com", "10.0.0.5", "frameworksql.sytes.net", "oracle", "fw_ci_oracle", "localhost.example.com", "127.0.0.1.evil.net", ""])
def test_los_hosts_remotos_se_omiten_con_un_mensaje_claro(host):
    motivo = destructive_skip_reason(host, {})
    assert motivo and ("no es local" in motivo or "vacío" in motivo)
    if host:
        assert CONFIRM_VAR in motivo


def test_los_nombres_de_ci_solo_valen_dentro_de_github_actions():
    for h in ("oracle", "fw_ci_oracle", "fw_chk_oracle"):
        assert destructive_skip_reason(h, {"GITHUB_ACTIONS": "true"}) is None
        assert destructive_skip_reason(h, {"GITHUB_ACTIONS": "false"}) is not None
    assert destructive_skip_reason("db.example.com", {"GITHUB_ACTIONS": "true"}) is not None


def test_la_confirmacion_debe_nombrar_exactamente_el_host():
    assert destructive_skip_reason("db.example.com", {CONFIRM_VAR: "db.example.com"}) is None
    assert destructive_skip_reason("DB.Example.com", {CONFIRM_VAR: "db.example.com"}) is None
    assert destructive_skip_reason("db.example.com", {CONFIRM_VAR: "otro.example.com"}) is not None
    assert destructive_skip_reason("db.example.com", {CONFIRM_VAR: "*"}) is not None
    assert destructive_skip_reason("db.example.com", {CONFIRM_VAR: "true"}) is not None


# --------------------------------------------------------------------------------------------- las pruebas reales, con un host remoto
SPY = '''
import os
import oracledb

def _no_conectar(*args, **kwargs):
    with open(os.environ["SPY_LOG"], "a", encoding="utf-8") as f:
        f.write("connect\\n")
    raise RuntimeError("conexión bloqueada por la prueba")

oracledb.connect = _no_conectar
'''


def _pytest_oracle(tmp_path, extra_env):
    (tmp_path / "oracle_spy.py").write_text(SPY, encoding="utf-8")
    log = tmp_path / "conexiones.log"
    env = {k: v for k, v in os.environ.items() if k not in ("ORACLE_HOST", CONFIRM_VAR, "GITHUB_ACTIONS")}
    env.update({"RUN_ORACLE_TESTS": "1", "FRAMEWORK_TEST_PASSWORD": "valor_ficticio_de_prueba", "ORACLE_PWD": "valor_ficticio_de_prueba",
                "SPY_LOG": str(log), "PYTHONPATH": str(tmp_path), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"})
    env.update(extra_env)
    r = subprocess.run([sys.executable, "-m", "pytest", "-p", "oracle_spy", "-p", "no:cacheprovider", "-q", "-rs",
                        "tests/test_oracle_integration.py", "tests/test_oracle_phase2.py"],
                       cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=300)
    return r, log


def test_con_un_host_remoto_las_pruebas_oracle_se_omiten_y_no_se_conecta(tmp_path):
    r, log = _pytest_oracle(tmp_path, {"ORACLE_HOST": "db.example.com"})
    salida = r.stdout + r.stderr
    assert r.returncode == 0, salida[-1500:]
    assert " failed" not in salida and " error" not in salida.lower().replace("errors", "")
    assert "skipped" in salida and "no es local" in salida and "db.example.com" in salida
    assert not log.exists(), "se intentó abrir una conexión Oracle con un host remoto"


def test_con_la_confirmacion_explicita_la_guardia_deja_pasar_y_el_espia_bloquea_la_conexion(tmp_path):
    r, log = _pytest_oracle(tmp_path, {"ORACLE_HOST": "db.example.com", CONFIRM_VAR: "db.example.com"})
    salida = r.stdout + r.stderr
    assert r.returncode != 0                       # ya no se omiten: intentan conectar y el espía lo impide
    assert log.exists() and "connect" in log.read_text(encoding="utf-8")
    assert "no es local" not in salida


def test_con_localhost_la_guardia_no_omite(tmp_path):
    r, log = _pytest_oracle(tmp_path, {"ORACLE_HOST": "127.0.0.1"})
    assert log.exists(), "con un host local las pruebas deben intentar conectar (aquí el espía lo bloquea)"
    assert "no es local" not in (r.stdout + r.stderr)


# --------------------------------------------------------------------------------------------- el script de Liquibase
def _bash():
    candidatos = [Path("C:/Program Files/Git/bin/bash.exe"), Path("C:/Program Files/Git/usr/bin/bash.exe")]
    import shutil
    candidatos.append(Path(shutil.which("bash") or "/nonexistent"))
    for c in candidatos:
        if c.exists():
            try:
                r = subprocess.run([str(c), "-c", "echo ok"], capture_output=True, text=True, timeout=20)
            except (OSError, subprocess.SubprocessError):
                continue
            if r.returncode == 0 and r.stdout.strip() == "ok":
                return str(c)
    return None


def _liquibase(tmp_path, jdbc, extra_env):
    bash = _bash()
    if not bash:
        pytest.skip("no hay un bash utilizable en este entorno")
    env = {k: v for k, v in os.environ.items() if k not in (CONFIRM_VAR, "GITHUB_ACTIONS", "LB_CONTEXTS")}
    env.update({"LB_NETWORK": "red_inexistente", "LB_JDBC_URL": jdbc, "LB_USER": "u", "LB_PASSWORD": "valor_ficticio", "PATH": str(tmp_path) + os.pathsep + env.get("PATH", "")})
    # un «docker» falso que deja marca: si el script llega a usarlo, la guardia falló
    fake = tmp_path / "docker"
    fake.write_text('#!/bin/sh\necho llamado >> "$DOCKER_LOG"\nexit 9\n', encoding="utf-8", newline="\n")
    os.chmod(fake, 0o755)    # en Linux un archivo sin permiso de ejecución se ignora y bash usaría el docker REAL del ejecutor de CI
    env["DOCKER_LOG"] = str(tmp_path / "docker.log")
    env.update(extra_env)
    # diagnóstico: el «docker» que verá el script tiene que ser el falso; si no, las pruebas no demostrarían nada
    quien = subprocess.run([bash, "-c", "command -v docker"], env=env, capture_output=True, text=True, timeout=30).stdout.strip()
    assert tmp_path.name in quien, f"el docker falso no quedó primero en PATH (se usaría otro): {quien!r}"
    r = subprocess.run([bash, "scripts/db/liquibase_demo.sh", str(tmp_path / "salida")], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)
    return r, tmp_path / "docker.log"


def test_liquibase_con_contexto_demo_rechaza_un_host_remoto_sin_usar_docker(tmp_path):
    r, dlog = _liquibase(tmp_path, "jdbc:oracle:thin:@//db.example.com:1521/FREEPDB1", {})
    assert r.returncode == 3, r.stdout + r.stderr
    assert "no es local ni de CI" in r.stderr and "db.example.com" in r.stderr
    assert not dlog.exists()


def test_liquibase_solo_esquema_no_borra_datos_y_no_exige_guardia(tmp_path):
    r, dlog = _liquibase(tmp_path, "jdbc:oracle:thin:@//db.example.com:1521/FREEPDB1", {"LB_CONTEXTS": "esquema"})
    assert "no es local ni de CI" not in r.stderr
    assert dlog.exists()                              # pasó la guardia y llegó al (falso) docker


def test_liquibase_permite_loopback_ci_y_confirmacion_explicita(tmp_path):
    for jdbc, extra in (("jdbc:oracle:thin:@//localhost:1521/X", {}),
                        ("jdbc:oracle:thin:@//127.0.0.1:1521/X", {}),
                        ("jdbc:oracle:thin:@//fw_ci_oracle:1521/X", {"GITHUB_ACTIONS": "true"}),
                        ("jdbc:oracle:thin:@//db.example.com:1521/X", {CONFIRM_VAR: "db.example.com"})):
        d = tmp_path / str(abs(hash(jdbc + str(extra))))
        d.mkdir()
        r, dlog = _liquibase(d, jdbc, extra)
        assert "no es local ni de CI" not in r.stderr, (jdbc, r.stderr)
        assert dlog.exists(), jdbc
    r, _ = _liquibase(tmp_path, "jdbc:oracle:thin:@//fw_ci_oracle:1521/X", {})   # nombre de CI fuera de GitHub Actions
    assert r.returncode == 3
