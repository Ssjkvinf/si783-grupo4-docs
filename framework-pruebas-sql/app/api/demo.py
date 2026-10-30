"""
Escenario de demostración: crea los casos y suites de ejemplo en un proyecto y, si se pide, los ejecuta de principio a fin.
Cargar el escenario solo escribe definiciones en la base interna (SQLite). La demostración guiada ejecuta esas suites contra un
perfil de conexión TEST guardado (la contraseña llega en la petición y no se guarda).
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api import executions as api_executions
from app.models import connection as models_conn
from app.models import project as models_project
from app.models import schemas
from app.services.demo_scenario import ESTADO_ESPERADO_POR_CASO, load_demo_scenario
from app.services.usage_service import record_event
from app.models.user import User
from app.security.acceso import usuario_actual

router = APIRouter()


class DemoScenarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: int


class GuidedDemoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connection_profile_id: int
    password: str


@router.post("/demo/scenario")
def create_demo_scenario(request: DemoScenarioRequest, db: Session = Depends(get_db)):
    """Carga (de forma idempotente) las suites de demostración en el proyecto indicado."""
    if not db.query(models_project.Project).filter(models_project.Project.id == request.project_id).first():
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    escenario = load_demo_scenario(db, request.project_id)
    record_event(db, "demo_scenario_loaded", request.project_id, "UI")
    return escenario


PASOS_GUIADOS = (
    ("rules_suite", "1. Reglas de calidad sobre los datos",
     "Cinco reglas sobre la tabla de demostración. Con los datos de ejemplo las cinco deben dar PASS."),
    ("examples_suite", "2. Así se ven un FAIL y un ERROR",
     "Una regla que se ejecuta bien pero no coincide (FAIL) y una consulta sobre una tabla que no existe (ERROR)."),
    ("control_suite", "3. Control de cambios",
     "Un INSERT se ejecuta y se revierte (el conteo sigue igual) y un DROP TABLE se rechaza antes de llegar a Oracle (ERROR esperado; la tabla sigue existiendo). "
     "El rollback es un control, no una garantía universal: no cubre secuencias, transacciones autónomas ni DDL."),
)


@router.post("/demo/guided")
def run_guided_demo(request: GuidedDemoRequest, db: Session = Depends(get_db), usuario: Optional[User] = Depends(usuario_actual)):
    """Ejecuta la demostración completa (reglas, FAIL/ERROR y control de cambios) y dice si cada caso dio lo que el guion espera."""
    profile = db.query(models_conn.ConnectionProfile).filter(models_conn.ConnectionProfile.id == request.connection_profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil de conexión no encontrado.")
    if str(getattr(profile.environment_type, "value", profile.environment_type)).upper() != "TEST":
        raise HTTPException(status_code=409, detail="La demostración guiada incluye un INSERT (que se revierte): use una conexión de ambiente TEST.")
    escenario = load_demo_scenario(db, profile.project_id)
    pasos = []
    for clave, titulo, descripcion in PASOS_GUIADOS:
        suite_id = escenario[clave]["suite_id"]
        res = api_executions.run_test_suite(suite_id, schemas.SuiteExecutionRequest(
            connection_profile_id=profile.id, password=request.password), db, usuario)
        casos = []
        for c in res.case_results:
            esperado = ESTADO_ESPERADO_POR_CASO.get(c.case_name)
            casos.append({**c.model_dump(), "estado_esperado_por_el_guion": esperado, "como_se_esperaba": esperado == c.status})
        pasos.append({"titulo": titulo, "descripcion": descripcion, "suite_id": suite_id, "suite_name": res.suite_name,
                      "passed": res.passed, "failed": res.failed, "errors": res.errors, "total_duration_ms": res.total_duration_ms,
                      "casos": casos, "todo_como_se_esperaba": all(x["como_se_esperaba"] for x in casos)})
    record_event(db, "demo_guided_run", profile.project_id, "UI", f"todo_como_se_esperaba={all(p['todo_como_se_esperaba'] for p in pasos)}")
    return {"conexion": profile.name, "ambiente": "TEST", "pasos": pasos, "todo_como_se_esperaba": all(p["todo_como_se_esperaba"] for p in pasos)}
