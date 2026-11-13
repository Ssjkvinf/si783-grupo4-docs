"""
Registro (logs) de la aplicación: una línea por evento, a la salida estándar (Docker la recoge con `docker logs`).

Qué se registra: peticiones HTTP, ingresos (correctos, fallidos y bloqueos) y ejecuciones de pruebas.
Qué NUNCA se registra: contraseñas, cookies, tokens, el SQL ni los resultados de las consultas.
El nivel se cambia con LOG_LEVEL (INFO por defecto).
"""
import logging
import os
import sys

NOMBRE = "framework"


def configurar_logs() -> logging.Logger:
    logger = logging.getLogger(NOMBRE)
    if logger.handlers:
        return logger
    nivel = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s", "%Y-%m-%dT%H:%M:%S%z"))
    logger.addHandler(handler)
    logger.setLevel(nivel)
    logger.propagate = False
    return logger


def obtener(sufijo: str) -> logging.Logger:
    """Logger hijo (p. ej. framework.acceso). Hereda el formato y el nivel de configurar_logs()."""
    configurar_logs()
    return logging.getLogger(f"{NOMBRE}.{sufijo}")


def limpio(valor: object, maximo: int = 60) -> str:
    """Texto seguro para una línea de log: sin saltos de línea (evita falsificar líneas) y acotado."""
    return " ".join(str(valor).split())[:maximo]
