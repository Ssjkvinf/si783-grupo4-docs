"""
scripts/ci/wait_for_oracle.sh (espera de Oracle en db-objects.yml y sql-checks.yml).

Se prueba con un `docker` falso (un script de shell con permiso de ejecución al principio del PATH) que simula un Oracle que tarda en
aceptar conexiones, uno que nunca lo hace y un contenedor detenido. No usa Oracle ni Docker reales.
"""
import os
import re
import subprocess
from pathlib import Path

import pytest

from test_oracle_guard import _bash

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
SCRIPT = ROOT / "scripts" / "ci" / "wait_for_oracle.sh"
CLAVE = "Ap0123456789abcdef9a"   # valor ficticio; las pruebas comprueban que NUNCA se imprime

FAKE_DOCKER = r'''#!/bin/sh
case "$1" in
  inspect)
    case "$*" in
      *State.Status*) echo "${FAKE_STATE:-running}" ;;
      *) echo "Estado=${FAKE_STATE:-running} Código=0 SinMemoria=false Salud=sin-healthcheck" ;;
    esac ;;
  logs)
    [ "${FAKE_READY:-0}" = "1" ] && echo "DATABASE IS READY TO USE!"
    echo "linea de log con la clave $FRAMEWORK_TEST_PASSWORD"
    echo "WARNING: aviso de escrituras lentas del redo log" ;;
  exec)
    cat > /dev/null
    n=$(cat "$FAKE_COUNT" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "$FAKE_COUNT"
    if [ "$n" -ge "${FAKE_OK_AT:-3}" ]; then printf '         1\n'; else echo "ERROR: ORA-01017: invalid credential para $FRAMEWORK_TEST_PASSWORD"; fi ;;
  *) echo "docker $1 simulado" ;;
esac
'''


def _ejecutar(tmp_path, extra_env=None, args=("fw_ci_oracle",), con_clave=True):
    bash = _bash()
    if not bash:
        pytest.skip("no hay un bash utilizable en este entorno")
    fake = tmp_path / "docker"
    fake.write_text(FAKE_DOCKER, encoding="utf-8", newline="\n")
    os.chmod(fake, 0o755)
    env = {k: v for k, v in os.environ.items() if k not in ("FRAMEWORK_TEST_PASSWORD", "ORACLE_WAIT_MAX_SECONDS", "ORACLE_WAIT_INTERVAL")}
    env.update({"PATH": str(tmp_path) + os.pathsep + env.get("PATH", ""), "FAKE_COUNT": str(tmp_path / "n.txt"),
                "ORACLE_WAIT_INTERVAL": "0", "ORACLE_WAIT_MAX_SECONDS": "30"})
    if con_clave:
        env["FRAMEWORK_TEST_PASSWORD"] = CLAVE
    env.update(extra_env or {})
    quien = subprocess.run([bash, "-c", "command -v docker"], env=env, capture_output=True, text=True, timeout=30).stdout.strip()
    assert tmp_path.name in quien, f"el docker falso no quedó primero en PATH: {quien!r}"
    return subprocess.run([bash, str(SCRIPT), *args], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=120)


def test_espera_y_termina_con_0_cuando_el_usuario_ya_puede_iniciar_sesion(tmp_path):
    r = _ejecutar(tmp_path, {"FAKE_OK_AT": "3"})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "Oracle listo" in r.stdout and "sondeo 3" in r.stdout
    assert r.stdout.count("aún no acepta conexiones") == 2           # los dos primeros sondeos fallaron y se reintentó


def test_si_el_log_ya_dice_ready_lo_registra_pero_confirma_con_un_inicio_de_sesion(tmp_path):
    r = _ejecutar(tmp_path, {"FAKE_OK_AT": "2", "FAKE_READY": "1"})
    assert r.returncode == 0
    assert "DATABASE IS READY TO USE" in r.stdout and "se confirma con un inicio de sesión" in r.stdout


def test_si_nunca_acepta_conexiones_falla_con_diagnostico_y_sin_imprimir_la_clave(tmp_path):
    r = _ejecutar(tmp_path, {"FAKE_OK_AT": "9999", "FAKE_READY": "1", "ORACLE_WAIT_MAX_SECONDS": "2", "ORACLE_WAIT_INTERVAL": "1"})
    salida = r.stdout + r.stderr
    assert r.returncode == 1
    assert "Diagnóstico de Oracle (tiempo agotado)" in salida
    assert "Último error del sondeo" in salida and "ORA-01017" in salida
    assert "estado del contenedor" in salida and "últimas 80 líneas del log" in salida and "aviso de escrituras lentas" in salida
    assert "::error::Oracle no estuvo listo" in salida
    assert "pero el inicio de sesión de sondeo no funcionó" in salida     # READY visto, sesión imposible: se distingue de «no está listo»
    assert CLAVE not in salida, "la contraseña no debe aparecer en la salida"
    assert "***" in salida


def test_un_contenedor_detenido_falla_de_inmediato(tmp_path):
    r = _ejecutar(tmp_path, {"FAKE_STATE": "exited", "ORACLE_WAIT_MAX_SECONDS": "600"})
    assert r.returncode == 1
    assert "contenedor detenido" in r.stdout + r.stderr and "estado: exited" in r.stdout + r.stderr
    assert not (tmp_path / "n.txt").exists(), "no debe sondear con sqlplus si el contenedor no corre"


def test_sin_contrasena_o_sin_contenedor_es_un_error_de_uso(tmp_path):
    assert _ejecutar(tmp_path, con_clave=False).returncode == 2
    assert _ejecutar(tmp_path, args=()).returncode == 2


def test_el_script_tiene_finales_lf_y_sintaxis_valida():
    assert b"\r\n" not in SCRIPT.read_bytes()
    bash = _bash()
    if not bash:
        pytest.skip("no hay un bash utilizable en este entorno")
    r = subprocess.run([bash, "-n", str(SCRIPT)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("flujo, contenedor, ruta", [("db-objects.yml", "fw_ci_oracle", "bash scripts/ci/wait_for_oracle.sh"),
                                                      ("sql-checks.yml", "fw_chk_oracle", "bash framework-pruebas-sql/scripts/ci/wait_for_oracle.sh")])
def test_los_dos_flujos_usan_el_mismo_script_y_no_el_estado_de_salud_inexistente(flujo, contenedor, ruta):
    texto = (REPO / ".github" / "workflows" / flujo).read_text(encoding="utf-8")
    assert f"{ruta} {contenedor}" in texto
    assert ".State.Health.Status" not in texto and "seq 1 90" not in texto
    assert "scripts/ci/**" in texto            # un cambio en el script vuelve a disparar el flujo
