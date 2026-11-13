"""
Ingreso, solicitud de cuenta y administración de usuarios.

Flujo: una persona solicita una cuenta (queda como TESTER inactiva) → un ADMIN la aprueba → la persona ingresa.
El primer ADMIN se crea con APP_ACCESS_USERNAME / APP_ACCESS_PASSWORD (ver app/security/acceso.py).
"""
import os
from datetime import datetime, timedelta, timezone
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logs import limpio, obtener
from app.models.user import User
from app.security.acceso import COOKIE_SESION, asegurar_admin_inicial, requiere_admin, usuario_actual
from app.security.auth import (MAX_FALLOS_CUENTA, MINUTOS_BLOQUEO, LimiteDeIntentos, crear_token, hash_password,
                               leer_token, limite_por_ip, problemas_de_contrasena, problemas_de_usuario,
                               verify_password)
from app.services.usage_service import record_event

router = APIRouter()

HORAS_SESION = 8
# Como máximo 10 solicitudes de cuenta por IP y por hora.
log = obtener('acceso')
limite_registro = LimiteDeIntentos(maximo=10, ventana=3600)


class LoginRequest(BaseModel):
    username: str = Field(..., max_length=50)
    password: str = Field(..., max_length=200)


class RegistroRequest(BaseModel):
    username: str = Field(..., max_length=50)
    full_name: str = Field(..., min_length=3, max_length=120)
    password: str = Field(..., max_length=200)


class CambioContrasenaRequest(BaseModel):
    actual: str = Field(..., max_length=200)
    nueva: str = Field(..., max_length=200)


class UsuarioCrear(BaseModel):
    username: str = Field(..., max_length=50)
    full_name: Optional[str] = Field(None, max_length=120)
    password: str = Field(..., max_length=200)
    role: Literal["ADMIN", "TESTER"] = "TESTER"


class UsuarioActualizar(BaseModel):
    full_name: Optional[str] = Field(None, max_length=120)
    role: Optional[Literal["ADMIN", "TESTER"]] = None
    active: Optional[bool] = None


class RestablecerRequest(BaseModel):
    nueva: str = Field(..., max_length=200)


class UsuarioResponse(BaseModel):
    id: int
    username: str
    full_name: Optional[str] = None
    role: str
    active: bool
    bloqueado: bool = False
    created_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _utc(fecha: Optional[datetime]) -> Optional[datetime]:
    # SQLite devuelve fechas sin zona horaria: se interpretan como UTC.
    if fecha is None:
        return None
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


def _bloqueado(user: User) -> bool:
    hasta = _utc(user.locked_until)
    return hasta is not None and hasta > _ahora()


def _respuesta(user: User) -> UsuarioResponse:
    r = UsuarioResponse.model_validate(user)
    r.bloqueado = _bloqueado(user)
    return r


def _ip(request: Request) -> str:
    return request.client.host if request.client else "desconocida"


def _poner_cookie(response: JSONResponse, user: User) -> None:
    response.set_cookie(
        key=COOKIE_SESION,
        value=crear_token(user.id, user.username, user.role, user.session_version, horas=HORAS_SESION),
        httponly=True,
        secure=os.getenv("ENVIRONMENT", "production").lower() == "production",
        samesite="strict",
        max_age=HORAS_SESION * 3600,
    )


def _admins_activos(db: Session) -> int:
    return db.query(User).filter(User.role == "ADMIN", User.active.is_(True)).count()


def _validar_nuevo(db: Session, username: str, password: str) -> str:
    username = (username or "").strip()
    problema = problemas_de_usuario(username) or problemas_de_contrasena(password, username)
    if problema:
        raise HTTPException(status_code=422, detail=problema)
    if db.query(User).filter(User.username.ilike(username)).first():
        raise HTTPException(status_code=409, detail="Ese nombre de usuario ya está en uso.")
    return username


# --------------------------------------------------------------------------------------------- ingreso y salida
@router.post("/login")
def login(creds: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Ingresa con usuario y contraseña. Bloquea la cuenta tras 5 fallos seguidos y la IP tras 20 fallos en 15 minutos."""
    ip = _ip(request)
    if limite_por_ip.bloqueada(ip):
        log.warning('ingreso rechazado: ip bloqueada ip=%s', ip)
        return JSONResponse(status_code=429, content={"detail": "Demasiados intentos fallidos desde este equipo. Espere unos minutos."})
    asegurar_admin_inicial(db)

    user = db.query(User).filter(User.username == creds.username.strip()).first()
    if user and _bloqueado(user):
        log.warning('ingreso rechazado: cuenta bloqueada usuario=%s ip=%s', limpio(creds.username), ip)
        return JSONResponse(status_code=423, content={
            "detail": f"Cuenta bloqueada temporalmente por intentos fallidos. Intente de nuevo en {MINUTOS_BLOQUEO} minutos."})

    if not verify_password(creds.password, user.password_hash if user else None):
        limite_por_ip.fallo(ip)
        log.warning('ingreso fallido usuario=%s ip=%s', limpio(creds.username), ip)
        if user:
            user.failed_attempts = (user.failed_attempts or 0) + 1
            if user.failed_attempts >= MAX_FALLOS_CUENTA:
                user.failed_attempts = 0
                user.locked_until = _ahora() + timedelta(minutes=MINUTOS_BLOQUEO)
            db.commit()
        return JSONResponse(status_code=401, content={"detail": "Usuario o contraseña incorrectos."})

    if not user.active:
        return JSONResponse(status_code=403, content={"detail": "Su cuenta todavía no fue aprobada por un administrador."})

    log.info('ingreso correcto usuario=%s rol=%s ip=%s', user.username, user.role, ip)
    user.failed_attempts = 0
    user.locked_until = None
    user.last_login_at = _ahora()
    db.commit()
    db.refresh(user)

    response = JSONResponse(content={
        "detail": "Login exitoso",
        "usuario": {"username": user.username, "full_name": user.full_name, "role": user.role},
        # La contraseña inicial del administrador viene del entorno; si es débil se sugiere cambiarla.
        "cambiar_contrasena_recomendado": problemas_de_contrasena(creds.password, user.username) is not None,
    })
    _poner_cookie(response, user)
    return response


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    """Cierra la sesión: borra la cookie y anula el token (también en otros equipos donde se haya ingresado)."""
    carga = leer_token(request.cookies.get(COOKIE_SESION))
    if carga:
        user = db.query(User).filter(User.id == carga.get("uid")).first()
        if user and user.session_version == carga.get("v"):
            user.session_version += 1
            db.commit()
    response = JSONResponse(content={"detail": "Logout exitoso"})
    response.delete_cookie(COOKIE_SESION)
    return response


@router.post("/register", status_code=201)
def solicitar_cuenta(datos: RegistroRequest, request: Request, db: Session = Depends(get_db)):
    """Solicitud de cuenta: queda como TESTER inactiva hasta que un ADMIN la apruebe."""
    if os.getenv("APP_REGISTRATION_ENABLED", "true").lower() != "true":
        raise HTTPException(status_code=403, detail="La solicitud de cuentas está desactivada. Pida una cuenta al administrador.")
    ip = _ip(request)
    if limite_registro.bloqueada(ip):
        raise HTTPException(status_code=429, detail="Demasiadas solicitudes desde este equipo. Intente más tarde.")
    limite_registro.fallo(ip)
    asegurar_admin_inicial(db)
    username = _validar_nuevo(db, datos.username, datos.password)
    db.add(User(username=username, full_name=datos.full_name.strip(), password_hash=hash_password(datos.password),
                role="TESTER", active=False))
    db.commit()
    record_event(db, "account_requested", None, "UI")
    return {"detail": "Solicitud enviada. Un administrador debe aprobar su cuenta antes de que pueda ingresar."}


# --------------------------------------------------------------------------------------------- mi cuenta
@router.get("/me")
def mi_cuenta(user: Optional[User] = Depends(usuario_actual)):
    """Usuario de la sesión. Sin control de acceso (modo local) responde como administrador local."""
    if user is None:
        return {"acceso_activado": False, "username": None, "full_name": "Modo local (sin control de acceso)", "role": "ADMIN"}
    return {"acceso_activado": True, "username": user.username, "full_name": user.full_name, "role": user.role}


@router.post("/me/password")
def cambiar_mi_contrasena(datos: CambioContrasenaRequest, user: Optional[User] = Depends(usuario_actual),
                          db: Session = Depends(get_db)):
    """Cambia la contraseña propia; cierra las otras sesiones y renueva la actual."""
    if user is None:
        raise HTTPException(status_code=409, detail="El control de acceso está desactivado: no hay contraseña que cambiar.")
    if not verify_password(datos.actual, user.password_hash):
        raise HTTPException(status_code=400, detail="La contraseña actual no es correcta.")
    problema = problemas_de_contrasena(datos.nueva, user.username)
    if problema:
        raise HTTPException(status_code=422, detail=problema)
    user.password_hash = hash_password(datos.nueva)
    user.session_version += 1
    db.commit()
    db.refresh(user)
    response = JSONResponse(content={"detail": "Contraseña actualizada."})
    _poner_cookie(response, user)
    return response


# --------------------------------------------------------------------------------------------- administración
@router.get("/users", response_model=List[UsuarioResponse])
def listar_usuarios(_: Optional[User] = Depends(requiere_admin), db: Session = Depends(get_db)):
    """Todos los usuarios; primero los pendientes de aprobación."""
    usuarios = db.query(User).order_by(User.active.asc(), User.username.asc()).all()
    return [_respuesta(u) for u in usuarios]


@router.post("/users", response_model=UsuarioResponse, status_code=201)
def crear_usuario(datos: UsuarioCrear, _: Optional[User] = Depends(requiere_admin), db: Session = Depends(get_db)):
    """El administrador crea una cuenta ya activa."""
    username = _validar_nuevo(db, datos.username, datos.password)
    user = User(username=username, full_name=(datos.full_name or "").strip() or None,
                password_hash=hash_password(datos.password), role=datos.role, active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _respuesta(user)


def _usuario_o_404(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    return user


@router.patch("/users/{user_id}", response_model=UsuarioResponse)
def actualizar_usuario(user_id: int, datos: UsuarioActualizar, admin: Optional[User] = Depends(requiere_admin),
                       db: Session = Depends(get_db)):
    """Aprobar/desactivar una cuenta o cambiar su rol. No permite quitarse el rol a uno mismo ni dejar el sistema sin administradores."""
    user = _usuario_o_404(db, user_id)
    es_uno_mismo = admin is not None and admin.id == user.id
    if es_uno_mismo and ((datos.role and datos.role != user.role) or datos.active is False):
        raise HTTPException(status_code=409, detail="No puede quitarse el rol de administrador ni desactivar su propia cuenta.")
    deja_de_ser_admin = user.role == "ADMIN" and user.active and (datos.role == "TESTER" or datos.active is False)
    if deja_de_ser_admin and _admins_activos(db) <= 1:
        raise HTTPException(status_code=409, detail="Debe quedar al menos un administrador activo.")

    if datos.full_name is not None:
        user.full_name = datos.full_name.strip() or None
    cambia_permisos = (datos.role is not None and datos.role != user.role) or (datos.active is not None and datos.active != user.active)
    if datos.role is not None:
        user.role = datos.role
    if datos.active is not None:
        user.active = datos.active
        if datos.active:
            user.failed_attempts, user.locked_until = 0, None
    if cambia_permisos:
        user.session_version += 1
    db.commit()
    db.refresh(user)
    return _respuesta(user)


@router.post("/users/{user_id}/reset-password", response_model=UsuarioResponse)
def restablecer_contrasena(user_id: int, datos: RestablecerRequest, _: Optional[User] = Depends(requiere_admin),
                           db: Session = Depends(get_db)):
    """El administrador asigna una contraseña nueva (y desbloquea la cuenta). Cierra las sesiones de ese usuario."""
    user = _usuario_o_404(db, user_id)
    problema = problemas_de_contrasena(datos.nueva, user.username)
    if problema:
        raise HTTPException(status_code=422, detail=problema)
    user.password_hash = hash_password(datos.nueva)
    user.failed_attempts, user.locked_until = 0, None
    user.session_version += 1
    db.commit()
    db.refresh(user)
    return _respuesta(user)


@router.delete("/users/{user_id}", status_code=204)
def eliminar_usuario(user_id: int, admin: Optional[User] = Depends(requiere_admin), db: Session = Depends(get_db)):
    """Elimina una cuenta (por ejemplo, una solicitud rechazada). El historial conserva el nombre en «ejecutado por»."""
    user = _usuario_o_404(db, user_id)
    if admin is not None and admin.id == user.id:
        raise HTTPException(status_code=409, detail="No puede eliminar su propia cuenta.")
    if user.role == "ADMIN" and user.active and _admins_activos(db) <= 1:
        raise HTTPException(status_code=409, detail="Debe quedar al menos un administrador activo.")
    db.delete(user)
    db.commit()
