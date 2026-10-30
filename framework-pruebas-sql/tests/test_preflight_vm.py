"""
scripts/deploy/preflight_vm.sh: revisión previa de la VM, de SOLO LECTURA y sin imprimir secretos.

Se ejecuta con `docker`, `df` y `free` falsos al principio del PATH y un .env.production con valores inventados. Comprueba lo que
informa, que nunca muestra un valor secreto y que solo usa comandos de lectura. No usa Docker real ni ninguna VM.
"""
import os
import re
import subprocess
import time
from pathlib import Path

import pytest

from test_oracle_guard import _bash

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "deploy" / "preflight_vm.sh"
SECRETO = "SecretoInventado-" + "7f3a9c"        # valores ficticios: las pruebas comprueban que NUNCA se imprimen
CLAVE_FICTICIA = "ClaveInventada" + "2026x"

FAKE_DOCKER = r'''#!/bin/sh
echo "docker $*" >> "$FAKE_LOG"
case "$1" in
  version) echo "27.3.1" ;;
  compose) echo "2.29.7" ;;
  ps)
    echo "framework_api_prod ghcr.io/x/framework-pruebas-sql:v0.9.0 Up 3 days (healthy)"
    [ "${FAKE_CADDY:-1}" = "1" ] && echo "framework_caddy_prod caddy:2-alpine Up 3 days"
    echo "framework_oracle_prod container-registry.oracle.com/database/free Up 3 days" ;;
  inspect)
    [ "${FAKE_API:-1}" = "1" ] || exit 1
    case "$*" in
      *"com.docker.compose.project.working_dir"*) echo "$FAKE_APP_DIR" ;;
      *"com.docker.compose.project.config_files"*) echo "$FAKE_APP_DIR/compose.yml" ;;
      *"com.docker.compose.project"*) echo "framework_pruebas_sql" ;;
      *"Config.Image"*) echo "ghcr.io/x/framework-pruebas-sql:v0.9.0" ;;
      *"State.Health"*) echo "healthy" ;;
      *"Mounts"*) echo "framework_pruebas_sql_framework_data en /data; " ;;
      *"Config.Env"*) cat "$FAKE_CONTAINER_ENV" ;;
      *) echo "{}" ;;
    esac ;;
  port) [ -n "${FAKE_PORTS:-}" ] && echo "$FAKE_PORTS" ;;
  exec) echo "${FAKE_ALEMBIC:-e7c3a91f5b42}" ;;
  *) echo "comando no previsto: $*" >&2; exit 9 ;;
esac
exit 0
'''
FAKE_FREE = r'''#!/bin/sh
echo "               total        used        free"
echo "Mem:            3900        2100        1800"
'''

ENV_BUENO = f"""ENVIRONMENT=production
APP_ACCESS_USERNAME=kevin.admin
APP_ACCESS_PASSWORD={CLAVE_FICTICIA}
APP_SESSION_SECRET="{SECRETO}"
APP_REGISTRATION_ENABLED=false
"""
ENV_EJEMPLO = """APP_ACCESS_USERNAME=usuario_ficticio
APP_ACCESS_PASSWORD=contrasena_ficticia
APP_SESSION_SECRET=secreto_ficticio_largo_y_complejo
APP_REGISTRATION_ENABLED=true
"""


def _preflight(tmp_path, env_archivo=ENV_BUENO, env_contenedor=None, con_copia=True, **fake):
    bash = _bash()
    if not bash:
        pytest.skip("no hay un bash utilizable en este entorno")
    app_dir, backups, bin_dir = tmp_path / "app", tmp_path / "backups", tmp_path / "bin"
    for d in (app_dir, backups, bin_dir):
        d.mkdir()
    if env_archivo is not None:
        (app_dir / ".env.production").write_text(env_archivo, encoding="utf-8", newline="\n")
    cont = tmp_path / "env_contenedor.txt"
    cont.write_text(env_contenedor if env_contenedor is not None else (env_archivo or "") + "FORWARDED_ALLOW_IPS=*\n",
                    encoding="utf-8", newline="\n")
    if con_copia:
        (backups / "framework_interno_20261027T071700Z.sqlite.gz").write_bytes(b"x")
    # `df` es el real: el bash de Git para Windows pone /usr/bin antes del PATH heredado. El umbral se fija con MIN_FREE_GB.
    for nombre, cuerpo in (("docker", FAKE_DOCKER), ("free", FAKE_FREE)):
        f = bin_dir / nombre
        f.write_text(cuerpo, encoding="utf-8", newline="\n")
        os.chmod(f, 0o755)
    log = tmp_path / "llamadas.log"
    env = {k: v for k, v in os.environ.items() if not k.startswith(("FAKE_", "APP_", "ENV_FILE"))}
    env.update({"PATH": str(bin_dir) + os.pathsep + env.get("PATH", ""), "FAKE_LOG": str(log), "FAKE_APP_DIR": str(app_dir).replace("\\", "/"),
                "FAKE_CONTAINER_ENV": str(cont), "BACKUP_DIR": str(backups).replace("\\", "/"), "MIN_FREE_GB": "0"})
    env.update({k: str(v) for k, v in fake.items()})
    quien = subprocess.run([bash, "-c", "command -v docker"], env=env, capture_output=True, text=True, timeout=30).stdout.strip()
    assert "bin" in quien and tmp_path.name in quien, f"el docker falso no quedó primero en PATH: {quien!r}"
    r = subprocess.run([bash, str(SCRIPT)], env=env, capture_output=True, text=True, encoding="utf-8", timeout=120)
    llamadas = log.read_text(encoding="utf-8") if log.exists() else ""
    return r, llamadas


def test_configuracion_correcta_no_pide_revisar_nada(tmp_path):
    r, _ = _preflight(tmp_path)
    s = r.stdout
    assert r.returncode == 0, r.stderr
    assert "Versión del motor: 27.3.1" in s and "Compose: 2.29.7" in s
    assert "framework_api_prod" in s and "Caddy: SÍ (framework_caddy_prod)" in s
    assert "Proyecto compose: framework_pruebas_sql" in s and "Puertos publicados por la API: NO" in s
    assert "Volúmenes montados en la API: framework_pruebas_sql_framework_data en /data;" in s
    assert "Existe: SÍ" in s and "Mem:" in s
    assert "APP_SESSION_SECRET (archivo): usa un valor de ejemplo bloqueado: NO" in s
    assert "APP_ACCESS_PASSWORD (contenedor): usa un valor de ejemplo bloqueado: NO" in s
    assert "APP_REGISTRATION_ENABLED (archivo): false" in s and "FORWARDED_ALLOW_IPS en el contenedor: SÍ" in s
    assert "Versión de Alembic: e7c3a91f5b42" in s and "aplicará migraciones" in s
    assert "copias: 1" in s and "Todo en orden para continuar." in s


def test_valores_de_ejemplo_se_detectan_sin_mostrar_ningun_valor(tmp_path):
    r, _ = _preflight(tmp_path, env_archivo=ENV_EJEMPLO)
    s = r.stdout + r.stderr
    assert "APP_SESSION_SECRET (archivo): usa un valor de ejemplo BLOQUEADO por la app: SÍ" in s
    assert "APP_ACCESS_PASSWORD (contenedor): usa un valor de ejemplo BLOQUEADO por la app: SÍ" in s
    assert "APP_ACCESS_USERNAME (archivo): usa el valor del archivo de ejemplo: SÍ" in s
    assert "REVISAR antes de desplegar" in s and "responderá 503" in s
    for valor in ("contrasena_ficticia", "secreto_ficticio_largo_y_complejo", "usuario_ficticio"):
        assert valor not in s, f"se imprimió un valor: {valor}"


def test_nunca_imprime_los_valores_reales(tmp_path):
    r, _ = _preflight(tmp_path)
    s = r.stdout + r.stderr
    assert SECRETO not in s and CLAVE_FICTICIA not in s and "kevin.admin" not in s


def test_avisa_lo_que_falta(tmp_path):
    r, _ = _preflight(tmp_path, env_archivo=None, env_contenedor="APP_SESSION_SECRET=x\n", con_copia=False, FAKE_CADDY=0,
                      FAKE_PORTS="8000/tcp -> 0.0.0.0:8000", MIN_FREE_GB=100000000)
    s = r.stdout
    assert r.returncode == 0
    assert "Existe: NO" in s and "Caddy: NO" in s and "Puertos publicados por la API: SÍ" in s
    assert "FORWARDED_ALLOW_IPS en el contenedor: NO" in s
    for aviso in ("No se encontró .env.production", "No se ve Caddy", "publica puertos", "menos de 100000000 GB", "APP_REGISTRATION_ENABLED=false",
                  "Sin FORWARDED_ALLOW_IPS", "copias de los últimos"):
        assert aviso in s, aviso


def test_sin_contenedor_de_la_api_lo_dice_y_no_falla(tmp_path):
    r, _ = _preflight(tmp_path, FAKE_API=0)
    assert r.returncode == 0 and "No hay un contenedor llamado framework_api_prod" in r.stdout


def test_solo_usa_comandos_de_lectura(tmp_path):
    _, llamadas = _preflight(tmp_path)
    usados = {linea.split()[1] for linea in llamadas.splitlines() if len(linea.split()) > 1}
    assert usados <= {"version", "compose", "ps", "inspect", "port", "exec"}, usados
    assert "compose up" not in llamadas and "compose down" not in llamadas
    execs = [linea for linea in llamadas.splitlines() if linea.startswith("docker exec")]
    assert all("mode=ro" in e for e in execs), "docker exec solo puede abrir la base en solo lectura"


def test_el_script_no_contiene_operaciones_que_cambien_algo():
    texto = SCRIPT.read_text(encoding="utf-8")
    assert b"\r\n" not in SCRIPT.read_bytes()
    codigo = "\n".join(l for l in texto.splitlines() if not l.lstrip().startswith("#"))
    for prohibido in ("docker run", "docker rm", "docker stop", "docker start", "docker pull", "docker restart", "compose up",
                      "compose down", "docker volume", "docker system", "rm -", "mv ", "sed -i", "tee ", "chmod", "systemctl"):
        assert prohibido not in codigo, prohibido
    redirecciones = re.findall(r">>?\s*([^\s|&;)]+)", codigo)
    assert all(d == "/dev/null" or d.startswith("&") for d in redirecciones), redirecciones


def test_sintaxis_bash():
    bash = _bash()
    if not bash:
        pytest.skip("no hay un bash utilizable en este entorno")
    r = subprocess.run([bash, "-n", str(SCRIPT)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
