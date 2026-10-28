"""
scripts/deploy/deploy_remote.sh: reversión automática cuando el despliegue falla, también si `docker compose up` falla a medias.

Se prueba con un `docker` falso al principio del PATH que guarda en archivos qué imagen «corre» y simula fallos de arranque o de
salud según variables FAKE_*. No usa Docker real ni toca ninguna VM.
"""
import json
import os
import subprocess
from pathlib import Path

import pytest

from test_oracle_guard import _bash

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "deploy" / "deploy_remote.sh"
NUEVA = "ghcr.io/equipo/repo/framework-pruebas-sql:v1.0.0"
ANTERIOR_REF = "sql-qa-framework:latest"

FAKE_DOCKER = r'''#!/bin/sh
S="$FAKE_STATE_DIR"
echo "docker $*" >> "$S/llamadas.log"
case "$1" in
  compose)
    case "$*" in
      *" version"*) echo "Docker Compose version v2 (simulado)"; exit 0 ;;
      *" up "*)
        if [ "${FAKE_FAIL_UP_ALL:-0}" = "1" ]; then echo "Error: no arranca ninguna imagen (simulado)" >&2; exit 1; fi
        if [ -n "$FAKE_FAIL_UP_IMAGE" ] && [ "$API_IMAGE" = "$FAKE_FAIL_UP_IMAGE" ]; then echo "Error: puerto ocupado (simulado)" >&2; exit 1; fi
        echo "$API_IMAGE" > "$S/actual"; exit 0 ;;
    esac ;;
  inspect)
    [ -f "$S/actual" ] || [ "${FAKE_HAS_PREV:-1}" = "1" ] || { echo "Error: No such object" >&2; exit 1; }
    actual="$(cat "$S/actual" 2>/dev/null || echo "$FAKE_PREV_REF")"
    case "$*" in
      *"{{.Image}}"*) echo "sha256:0123456789abcdef0123456789abcdef" ;;
      *"{{.Config.Image}}"*) echo "$actual" ;;
      *State.Health*) if [ "$actual" = "$FAKE_UNHEALTHY_IMAGE" ]; then echo unhealthy; else echo healthy; fi ;;
    esac
    exit 0 ;;
  exec)
    actual="$(cat "$S/actual" 2>/dev/null || echo "$FAKE_PREV_REF")"
    [ "$actual" = "$FAKE_UNHEALTHY_IMAGE" ] && exit 1
    echo "health: ok version: 2.0.0"; exit 0 ;;
  logs) echo "log simulado del contenedor"; exit 0 ;;
  *) exit 0 ;;
esac
'''


def _desplegar(tmp_path, **fake):
    bash = _bash()
    if not bash:
        pytest.skip("no hay un bash utilizable en este entorno")
    estado, app_dir, reportes = tmp_path / "estado", tmp_path / "app", tmp_path / "reportes"
    for d in (estado, app_dir, reportes):
        d.mkdir()
    for f in ("compose.yml", ".env.production", "compose.release.yml"):
        (app_dir / f).write_text("# simulado\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(FAKE_DOCKER, encoding="utf-8", newline="\n")
    os.chmod(docker, 0o755)
    env = {k: v for k, v in os.environ.items() if not k.startswith("FAKE_")}
    env.update({"PATH": str(bin_dir) + os.pathsep + env.get("PATH", ""), "FAKE_STATE_DIR": str(estado), "FAKE_PREV_REF": ANTERIOR_REF,
                "APP_DIR": str(app_dir), "API_IMAGE": NUEVA, "REPORT_DIR": str(reportes), "SKIP_BACKUP": "1",
                "HEALTH_TIMEOUT": "2", "HEALTH_INTERVAL": "0"})
    env.update({k: str(v) for k, v in fake.items()})
    quien = subprocess.run([bash, "-c", "command -v docker"], env=env, capture_output=True, text=True, timeout=30).stdout.strip()
    assert "bin" in quien and tmp_path.name in quien, f"el docker falso no quedó primero en PATH: {quien!r}"
    r = subprocess.run([bash, str(SCRIPT)], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=120)
    reporte = json.loads((reportes / "last_deploy.json").read_text(encoding="utf-8")) if (reportes / "last_deploy.json").exists() else None
    actual = (estado / "actual").read_text(encoding="utf-8").strip() if (estado / "actual").exists() else None
    return r, reporte, actual


def test_despliegue_correcto(tmp_path):
    r, rep, actual = _desplegar(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert rep["resultado"] == "ok" and rep["reversion_aplicada"] == "no" and rep["imagen_nueva"] == NUEVA
    assert actual == NUEVA


def test_si_compose_up_falla_a_medias_revierte_a_la_imagen_anterior_y_lo_informa(tmp_path):
    r, rep, actual = _desplegar(tmp_path, FAKE_FAIL_UP_IMAGE=NUEVA)
    assert r.returncode == 1
    assert rep is not None, "debe quedar el reporte aunque compose up falle"
    assert rep["resultado"] == "fallo_al_iniciar" and rep["reversion_aplicada"] == "si"
    assert rep["imagen_nueva"] == NUEVA and rep["etiqueta_de_reversion"].startswith("framework-rollback:")
    assert actual == rep["etiqueta_de_reversion"], "debe quedar corriendo la imagen anterior"
    assert "REVERSIÓN automática" in r.stdout and "fallo_al_iniciar" in r.stderr


def test_si_la_imagen_nueva_no_queda_sana_revierte(tmp_path):
    r, rep, actual = _desplegar(tmp_path, FAKE_UNHEALTHY_IMAGE=NUEVA)
    assert r.returncode == 1
    assert rep["resultado"] == "fallo_de_salud" and rep["reversion_aplicada"] == "si"
    assert actual.startswith("framework-rollback:")


def test_si_tambien_falla_la_reversion_el_reporte_lo_dice(tmp_path):
    # Ni la imagen nueva ni la anterior arrancan: hay que intervenir a mano, y el reporte debe decirlo.
    r, rep, _ = _desplegar(tmp_path, FAKE_FAIL_UP_ALL=1)
    assert r.returncode == 1 and rep is not None
    assert rep["resultado"] == "fallo_al_iniciar" and rep["reversion_aplicada"] == "intentada_sin_exito"
    assert "intentada_sin_exito" in r.stderr


def test_primer_despliegue_sin_imagen_previa_no_puede_revertir(tmp_path):
    r, rep, _ = _desplegar(tmp_path, FAKE_FAIL_UP_IMAGE=NUEVA, FAKE_HAS_PREV=0)
    assert r.returncode == 1
    assert rep["reversion_aplicada"] == "imposible_sin_imagen_previa" and rep["etiqueta_de_reversion"] == ""
