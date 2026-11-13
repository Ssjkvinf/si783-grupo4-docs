"""
Logs de la aplicación: registran ingresos y peticiones, y NUNCA contraseñas ni datos sensibles.
"""
import logging

import pytest
from fastapi.testclient import TestClient

from app.core.logs import limpio, obtener
from app.main import app

ADMIN = "admin"
CLAVE_ADMIN = "clave" + "-admin-ficticia"
CLAVE_MALA = "otra" + "-clave-ficticia"


class _Captura(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lineas = []

    def emit(self, record):
        self.lineas.append(self.format(record))


@pytest.fixture
def lineas(monkeypatch):
    monkeypatch.setenv("APP_ACCESS_ENABLED", "true")
    monkeypatch.setenv("APP_ACCESS_USERNAME", ADMIN)
    monkeypatch.setenv("APP_ACCESS_PASSWORD", CLAVE_ADMIN)
    monkeypatch.setenv("APP_SESSION_SECRET", "secreto-de-prueba-ficticio")
    monkeypatch.setenv("ENVIRONMENT", "development")
    obtener("prueba")                      # asegura que el logger «framework» está configurado
    logger = logging.getLogger("framework")
    h = _Captura()
    h.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
    logger.addHandler(h)
    yield h.lineas
    logger.removeHandler(h)


def test_ingreso_correcto_y_fallido_quedan_registrados_sin_la_contrasena(lineas):
    c = TestClient(app)
    assert c.post("/api/login", json={"username": ADMIN, "password": CLAVE_MALA}).status_code == 401
    assert c.post("/api/login", json={"username": ADMIN, "password": CLAVE_ADMIN}).status_code == 200
    texto = "\n".join(lineas)
    assert "WARNING framework.acceso ingreso fallido usuario=admin" in texto
    assert "INFO framework.acceso ingreso correcto usuario=admin rol=ADMIN" in texto
    assert "POST /api/login 401" in texto and "POST /api/login 200" in texto
    assert CLAVE_ADMIN not in texto and CLAVE_MALA not in texto


def test_el_usuario_con_saltos_de_linea_no_puede_falsificar_lineas(lineas):
    TestClient(app).post("/api/login", json={"username": "x\nINFO falso", "password": CLAVE_MALA})
    assert not any(l.startswith("INFO falso") for l in "\n".join(lineas).splitlines())
    assert "\n" not in limpio("a\nb\r\nc") and len(limpio("z" * 500)) == 60
