"""
Eventos de uso del producto que no son ejecuciones (p. ej. importar o exportar Excel).
Las ejecuciones se miden con execution_history; aquí solo lo que no deja ese rastro.
No se guardan datos personales ni contenido de los archivos: solo tipo, proyecto, origen y un detalle breve.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from datetime import datetime, timezone
from app.core.database import Base


def get_utc_now():
    return datetime.now(timezone.utc)


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    source = Column(String, nullable=True)          # UI | CLI | API
    detail = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, index=True)
