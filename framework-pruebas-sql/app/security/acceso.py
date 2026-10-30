"""
Dependencias de FastAPI para el control de acceso por usuario y rol.

- `usuario_actual`: devuelve el usuario de la sesión (o None si el acceso está desactivado con APP_ACCESS_ENABLED=false,
  el modo local de desarrollo y de pruebas). Rechaza con 401 un token caducado, de una cuenta desactivada o de una sesión
  anterior (versión de sesión distinta).
- `requiere_admin`: igual, pero exige el rol ADMIN (403 si es TESTER).
- `asegurar_admin_inicial`: crea el primer administrador con APP_ACCESS_USERNAME / APP_ACCESS_PASSWORD si todavía no existe.
  Si ya existe, no toca su contraseña (el administrador puede cambiarla desde la aplicación).
"""
import os
from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.security.auth import hash_password, leer_token

COOKIE_SESION = "session_token"


def acceso_activado() -> bool:
    return os.getenv("APP_ACCESS_ENABLED", "").lower() == "true"


def asegurar_admin_inicial(db: Session) -> None:
    username = os.getenv("APP_ACCESS_USERNAME", "").strip()
    password = os.getenv("APP_ACCESS_PASSWORD", "").strip()
    if not username or not password:
        return
    if db.query(User).filter(User.username == username).first():
        return
    db.add(User(username=username, full_name="Administrador", password_hash=hash_password(password), role="ADMIN", active=True))
    db.commit()


def usuario_actual(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    if not acceso_activado():
        return None
    carga = leer_token(request.cookies.get(COOKIE_SESION))
    if not carga:
        raise HTTPException(status_code=401, detail="Sesión no válida o caducada. Vuelva a ingresar.")
    user = db.query(User).filter(User.id == carga.get("uid")).first()
    if not user or not user.active or user.session_version != carga.get("v"):
        raise HTTPException(status_code=401, detail="Sesión no válida o caducada. Vuelva a ingresar.")
    return user


def requiere_admin(user: Optional[User] = Depends(usuario_actual)) -> Optional[User]:
    if user is not None and user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Solo un administrador puede hacer esto.")
    return user


def nombre_de(user) -> Optional[str]:
    """Nombre que se guarda en «ejecutado por». Sin control de acceso (modo local) devuelve None."""
    return user.username if isinstance(user, User) else None
