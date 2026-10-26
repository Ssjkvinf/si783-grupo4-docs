"""
Usuarios de la aplicación (base interna SQLite).

Dos roles:
  - ADMIN: administra usuarios, proyectos y conexiones, y puede hacer todo lo que hace un TESTER.
  - TESTER: crea y ejecuta casos y suites, usa el asistente y revisa el historial.
La contraseña nunca se guarda: solo su hash PBKDF2-SHA256 con sal (app/security/auth.py).
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.core.database import Base


def get_utc_now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    full_name = Column(String(120), nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="TESTER")
    active = Column(Boolean, nullable=False, default=True)
    failed_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    session_version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
