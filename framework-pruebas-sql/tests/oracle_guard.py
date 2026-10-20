"""
Guardia de las pruebas Oracle DESTRUCTIVAS (las que borran filas, crean cuentas o usan la clave de SYS).

Regla: solo corren contra un Oracle LOCAL o de CI. Cualquier otro host se OMITE con un mensaje claro y no se abre ninguna conexión.
  - Siempre permitidos: localhost y cualquier IP de loopback (127.0.0.0/8, ::1).
  - Solo dentro de GitHub Actions (GITHUB_ACTIONS=true): además `oracle`, `fw_ci_oracle` y `fw_chk_oracle`
    (nombres de los contenedores efímeros que levantan los workflows).
  - Cualquier otro host exige la variable ORACLE_TESTS_CONFIRM_DESTRUCTIVE_HOST con el NOMBRE EXACTO de ese host
    (confirmación explícita de que es un Oracle desechable). No existe un valor comodín.

La misma regla la aplica scripts/db/liquibase_demo.sh cuando se pide el contexto «demo» (que borra y recarga FRAMEWORK_TEST_ITEMS).
Documentación: docs/demostracion-fase2.md §4 y docs/estandar-programacion.md §4.
"""
import ipaddress
import os
from typing import Mapping, Optional

CONFIRM_VAR = "ORACLE_TESTS_CONFIRM_DESTRUCTIVE_HOST"
CI_HOSTS = {"oracle", "fw_ci_oracle", "fw_chk_oracle"}


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def destructive_skip_reason(host: str, environ: Optional[Mapping[str, str]] = None) -> Optional[str]:
    """Devuelve None si las pruebas destructivas pueden correr contra `host`, o el motivo (texto) por el que deben omitirse."""
    env = os.environ if environ is None else environ
    h = (host or "").strip().lower()
    if not h:
        return "ORACLE_HOST vacío: se omiten las pruebas Oracle destructivas."
    if _is_loopback(h):
        return None
    if env.get("GITHUB_ACTIONS", "").lower() == "true" and h in CI_HOSTS:
        return None
    if env.get(CONFIRM_VAR, "").strip().lower() == h:
        return None
    return (f"ORACLE_HOST='{host}' no es local: estas pruebas BORRAN datos y crean cuentas, así que se omiten sin conectar. "
            f"Si es un Oracle desechable, defina {CONFIRM_VAR}={host} (nombre exacto) para autorizarlas.")
