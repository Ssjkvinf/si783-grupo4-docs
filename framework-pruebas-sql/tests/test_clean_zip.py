"""
scripts/build_clean_zip.py es el chequeo de secretos del flujo «Docs Check». Estas pruebas lo ejecutan en pytest para que un
texto que parezca una asignación de contraseña en un documento falle aquí (en el flujo «Tests») y no solo en «Docs Check», y comprueban que el
detector SIGUE rechazando una contraseña con aspecto real (no se debilitó para que pase).
"""
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_clean_zip  # noqa: E402


def _zip(tmp_path, contenido, nombre="docs/ejemplo.md"):
    z = tmp_path / "t.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr(nombre, contenido)
    return z


def test_el_repositorio_actual_pasa_el_chequeo_de_secretos(tmp_path):
    r = subprocess.run([sys.executable, "scripts/build_clean_zip.py", "--output", str(tmp_path / "limpio.zip")], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "Verified" in r.stdout


# Las líneas se componen en tiempo de ejecución: si estuvieran escritas completas, el propio detector marcaría este archivo.
@pytest.mark.parametrize("nombre, valor", [
    ("APP_ACCESS_" + "PASSWORD", "Sup3rSecreto123"),
    ("export FW_ORACLE_" + "PASSWORD", "'Clave-Real-9876'"),
    ("FRAMEWORK_TEST_" + "PASSWORD", "abc123XYZ789"),
    ("ORACLE_" + "PWD", "OtraClaveReal1"),
])
def test_el_detector_sigue_rechazando_contrasenas_con_aspecto_real(tmp_path, nombre, valor):
    with pytest.raises(SystemExit) as e:
        build_clean_zip.verify_zip(_zip(tmp_path, "\n".join(["texto", nombre + "=" + valor, "más texto"])))
    assert e.value.code == 1


@pytest.mark.parametrize("linea", [
    "export FW_ORACLE_PASSWORD='<clave-ficticia-reemplace-por-la-de-su-cuenta-de-prueba>'",
    'export LIQUIBASE_COMMAND_PASSWORD="${LB_PASSWORD}"',
    "FRAMEWORK_TEST_PASSWORD=contraseña_ficticia_test",
])
def test_los_marcadores_de_posicion_y_referencias_a_variables_no_se_toman_por_secretos(tmp_path, linea):
    build_clean_zip.verify_zip(_zip(tmp_path, linea))
