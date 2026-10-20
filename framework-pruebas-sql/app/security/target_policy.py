"""
Política de destinos para las conexiones Oracle de la aplicación.

Los destinos se definen solo mediante perfiles de conexión guardados (campos validados).
Si la variable de entorno ORACLE_ALLOWED_HOSTS está definida (lista separada por comas),
únicamente esos hosts pueden usarse al crear/editar perfiles y al ejecutar. Si no está
definida se permite cualquier host (uso local y académico).
"""
import os
import re
from typing import Optional, Set

# host y service_name se insertan en el descriptor de conexión de Oracle: solo se admiten
# caracteres de nombre (sin paréntesis, '=', espacios, '/', '@', etc.) para que no puedan
# inyectar partes del descriptor.
HOST_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?$")
SERVICE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def allowed_hosts() -> Optional[Set[str]]:
    raw = os.getenv("ORACLE_ALLOWED_HOSTS", "").strip()
    if not raw:
        return None
    return {h.strip().lower() for h in raw.split(",") if h.strip()}


def ensure_host_allowed(host: str) -> None:
    """Lanza ValueError si hay una lista de hosts permitidos y `host` no figura en ella."""
    allow = allowed_hosts()
    if allow is not None and str(host).strip().lower() not in allow:
        raise ValueError(
            f"El host '{host}' no está permitido por la configuración del servidor (ORACLE_ALLOWED_HOSTS)."
        )


def ensure_valid_target(host: str, service_name: str) -> None:
    """Valida la sintaxis del destino (también de perfiles guardados antes de existir esta regla) y la lista permitida."""
    if not HOST_RE.match(str(host)) or not SERVICE_RE.match(str(service_name)):
        raise ValueError("El perfil tiene un host o service name con caracteres no permitidos; corríjalo en Conexiones.")
    ensure_host_allowed(host)
