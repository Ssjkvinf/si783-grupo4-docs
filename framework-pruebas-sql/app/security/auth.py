"""
Seguridad del acceso: contraseñas, sesiones y límites de intentos.

- Contraseñas: PBKDF2-HMAC-SHA256 con sal aleatoria de 16 bytes (`pbkdf2_sha256$iteraciones$sal$hash`). Se comparan en tiempo constante.
- Sesión: cookie HttpOnly con un token firmado (HMAC-SHA256 con APP_SESSION_SECRET) que lleva el id de usuario, su rol, su
  «versión de sesión» y la fecha de caducidad. Cambiar la contraseña, el rol, desactivar la cuenta o cerrar sesión incrementa la
  versión y anula los tokens anteriores (lo comprueba la dependencia `usuario_actual` contra la base).
- Fuerza bruta: 5 fallos seguidos bloquean la cuenta 15 minutos; además, 20 fallos desde una misma IP en 15 minutos devuelven 429.
- Política de contraseñas: al menos 10 caracteres, con letras y números, y sin contener el nombre de usuario.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from typing import Any, Dict, Optional

PREFIJO_TOKEN = "v2."
ITERACIONES_POR_DEFECTO = 260_000
MAX_FALLOS_CUENTA = 5
MINUTOS_BLOQUEO = 15
MAX_FALLOS_IP = 20
VENTANA_IP_SEGUNDOS = 15 * 60
ROLES = ("ADMIN", "TESTER")


def _iteraciones() -> int:
    try:
        n = int(os.getenv("PASSWORD_HASH_ITERATIONS", ITERACIONES_POR_DEFECTO))
    except ValueError:
        n = ITERACIONES_POR_DEFECTO
    return max(1000, n)


def hash_password(password: str) -> str:
    """Devuelve el hash con sal para guardar en la base (nunca la contraseña)."""
    sal = secrets.token_bytes(16)
    n = _iteraciones()
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), sal, n)
    return "pbkdf2_sha256${}${}${}".format(n, base64.b64encode(sal).decode(), base64.b64encode(h).decode())


_HASH_DE_RELLENO: Dict[int, str] = {}


def _hash_de_relleno() -> str:
    """Hash con las MISMAS iteraciones que los reales: si el usuario no existe, verificar tarda lo mismo (no se puede adivinar por el tiempo)."""
    n = _iteraciones()
    if n not in _HASH_DE_RELLENO:
        _HASH_DE_RELLENO[n] = hash_password(secrets.token_urlsafe(16))
    return _HASH_DE_RELLENO[n]


def verify_password(password: str, guardado: Optional[str]) -> bool:
    """Compara en tiempo constante. Con `guardado=None` hace el mismo trabajo para no revelar si el usuario existe."""
    try:
        algoritmo, n, sal_b64, h_b64 = (guardado or _hash_de_relleno()).split("$")
        if algoritmo != "pbkdf2_sha256":
            return False
        calculado = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), base64.b64decode(sal_b64), int(n))
        return hmac.compare_digest(calculado, base64.b64decode(h_b64)) and guardado is not None
    except Exception:
        return False


def problemas_de_contrasena(password: str, username: str = "") -> Optional[str]:
    """Devuelve un mensaje si la contraseña no cumple la política; None si la cumple."""
    if len(password or "") < 10:
        return "La contraseña debe tener al menos 10 caracteres."
    if not re.search(r"[A-Za-zÁÉÍÓÚáéíóúÑñ]", password) or not re.search(r"\d", password):
        return "La contraseña debe combinar letras y números."
    if username and username.strip().lower() in password.lower():
        return "La contraseña no puede contener el nombre de usuario."
    return None


USUARIO_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{2,49}$")


def problemas_de_usuario(username: str) -> Optional[str]:
    if not USUARIO_RE.match((username or "").strip()):
        return "El usuario debe empezar con una letra y tener de 3 a 50 caracteres (letras, números, punto, guion o guion bajo)."
    return None


# Valores de ejemplo que este repositorio PUBLICA en .env.example e infra/production/.env.production.example.
# Si alguien los usa tal cual, cualquiera podría entrar o falsificar sesiones: la aplicación se niega a atender.
SECRETOS_DE_EJEMPLO = {"default_insecure_secret_replace_in_prod", "secreto_ficticio_largo_y_complejo"}
CLAVES_DE_EJEMPLO = {"contrasena_ficticia"}


def configuracion_insegura(session_secret: str, admin_password: str) -> Optional[str]:
    """Motivo (sin revelar valores) si el secreto de sesión o la clave del primer administrador son valores de ejemplo."""
    if session_secret.strip().lower() in SECRETOS_DE_EJEMPLO:
        return "APP_SESSION_SECRET usa un valor de ejemplo: genere uno largo y aleatorio."
    if admin_password.strip().lower() in CLAVES_DE_EJEMPLO:
        return "APP_ACCESS_PASSWORD usa un valor de ejemplo: defina una contraseña propia para el primer administrador."
    return None


# ------------------------------------------------------------------------------------------- tokens de sesión
def _secreto() -> bytes:
    return os.getenv("APP_SESSION_SECRET", "").encode()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def crear_token(user_id: int, username: str, role: str, session_version: int, horas: float = 8) -> str:
    """Token firmado con caducidad. Cada usuario y cada inicio de sesión tienen un token distinto (incluye un nonce)."""
    carga = {"uid": user_id, "u": username, "r": role, "v": session_version, "exp": int(time.time() + horas * 3600),
             "n": secrets.token_hex(8)}
    cuerpo = _b64(json.dumps(carga, separators=(",", ":")).encode())
    firma = hmac.new(_secreto(), cuerpo.encode(), hashlib.sha256).hexdigest()
    return f"{PREFIJO_TOKEN}{cuerpo}.{firma}"


def leer_token(token: Optional[str]) -> Optional[Dict[str, Any]]:
    """Devuelve la carga si la firma es válida y no caducó; si no, None."""
    if not token or not token.startswith(PREFIJO_TOKEN) or not _secreto():
        return None
    try:
        cuerpo, firma = token[len(PREFIJO_TOKEN):].rsplit(".", 1)
        esperada = hmac.new(_secreto(), cuerpo.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(firma, esperada):
            return None
        carga = json.loads(_unb64(cuerpo))
        if int(carga.get("exp", 0)) < time.time():
            return None
        return carga
    except Exception:
        return None


# ------------------------------------------------------------------------------------------- límite por IP
class LimiteDeIntentos:
    """Cuenta fallos de inicio de sesión por IP en una ventana deslizante (en memoria; se reinicia con el proceso)."""

    def __init__(self, maximo: int = MAX_FALLOS_IP, ventana: int = VENTANA_IP_SEGUNDOS):
        self.maximo, self.ventana = maximo, ventana
        self._fallos: Dict[str, list] = {}
        self._lock = threading.Lock()

    def _limpiar(self, ip: str, ahora: float) -> list:
        lista = [t for t in self._fallos.get(ip, []) if ahora - t < self.ventana]
        self._fallos[ip] = lista
        return lista

    def bloqueada(self, ip: str) -> bool:
        with self._lock:
            return len(self._limpiar(ip, time.time())) >= self.maximo

    def fallo(self, ip: str) -> None:
        with self._lock:
            self._limpiar(ip, time.time()).append(time.time())

    def reiniciar(self, ip: Optional[str] = None) -> None:
        with self._lock:
            if ip is None:
                self._fallos.clear()
            else:
                self._fallos.pop(ip, None)


limite_por_ip = LimiteDeIntentos()
