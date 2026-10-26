"""
Analizar una tabla: perfila una tabla de la base objetivo con una conexión guardada y propone reglas; después guarda las elegidas
como casos agrupados en una suite. La contraseña llega en la petición, se usa para conectar y no se guarda.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.engine.executor import TargetDatabaseExecutor
from app.models import project as models_project
from app.services import analisis_tabla
from app.services.execution_service import resolve_connection_credentials
from app.services.usage_service import record_event

router = APIRouter()


class AnalisisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connection_profile_id: int
    password: str = Field(..., min_length=1, max_length=200)
    tabla: str = Field(..., min_length=1, max_length=61)


class PropuestaElegida(BaseModel):
    model_config = ConfigDict(extra="ignore")
    regla: str
    params: Dict[str, Any]


class GuardarSuiteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: int
    nombre_suite: str = Field(..., min_length=1, max_length=120)
    descripcion: Optional[str] = Field(None, max_length=500)
    propuestas: List[PropuestaElegida] = Field(..., min_length=1, max_length=60)


@router.post("/analysis/table")
def analizar_tabla(request: AnalisisRequest, db: Session = Depends(get_db)):
    """Lee la estructura y el estado actual de la tabla (solo SELECT) y propone reglas de calidad. No disponible en PRODUCTION."""
    try:
        dsn, user, password, profile = resolve_connection_credentials(db, request.connection_profile_id, request.password)
    except ValueError as e:
        raise HTTPException(status_code=404 if "no encontrado" in str(e) else 400, detail=str(e))
    env = str(getattr(profile.environment_type, "value", profile.environment_type)).upper()
    if env == "PRODUCTION":
        raise HTTPException(status_code=409, detail="El análisis no está disponible en PRODUCTION: allí las filas se ocultan. Use una conexión TEST o STAGING.")
    try:
        executor = TargetDatabaseExecutor(dsn=dsn, user=user, password=password, environment_type=env)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        resultado = analisis_tabla.analizar(executor, request.tabla)
    except analisis_tabla.AnalisisError as e:
        raise HTTPException(status_code=422, detail=str(e))
    finally:
        executor.disconnect()
    record_event(db, "table_analyzed", profile.project_id, "UI", f"propuestas={len(resultado['propuestas'])}")
    return {"conexion": profile.name, "ambiente": env, "project_id": profile.project_id, **resultado}


@router.post("/analysis/save-suite", status_code=201)
def guardar_suite(request: GuardarSuiteRequest, db: Session = Depends(get_db)):
    """Crea un caso por cada regla elegida (el SQL se vuelve a generar aquí) y una suite que los agrupa."""
    if not db.query(models_project.Project).filter(models_project.Project.id == request.project_id).first():
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    try:
        suite = analisis_tabla.guardar_como_suite(db, request.project_id, request.nombre_suite, request.descripcion,
                                                  [p.model_dump() for p in request.propuestas])
    except analisis_tabla.AnalisisError as e:
        raise HTTPException(status_code=422, detail=str(e))
    record_event(db, "table_analysis_saved", request.project_id, "UI", f"casos={len(suite.test_cases)}")
    return {"suite_id": suite.id, "suite_name": suite.name, "casos": [{"id": c.id, "name": c.name} for c in suite.test_cases]}
