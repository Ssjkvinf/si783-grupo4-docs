"""
Dashboard de utilización: métricas de uso calculadas a partir de datos persistidos.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import project as models_project
from app.services.usage_service import build_summary

router = APIRouter()


@router.get("/usage/summary")
def get_usage_summary(
    days: int = Query(30, ge=1, le=365, description="Días del periodo (incluye hoy, en UTC)"),
    project_id: Optional[int] = Query(None, description="Limitar a un proyecto; sin valor = todos"),
    db: Session = Depends(get_db),
):
    """Resumen de uso: ejecuciones por fecha, resultados, casos y suites más usados, origen y eventos."""
    if project_id and not db.query(models_project.Project).filter(models_project.Project.id == project_id).first():
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    return build_summary(db, days=days, project_id=project_id)
