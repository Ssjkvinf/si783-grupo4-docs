"""
Endpoint del escenario de demostración: crea los casos y suites de ejemplo en un proyecto.
Solo escribe definiciones en la base interna (SQLite); no se conecta a Oracle ni guarda contraseñas.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import project as models_project
from app.services.demo_scenario import load_demo_scenario

router = APIRouter()


class DemoScenarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: int


@router.post("/demo/scenario")
def create_demo_scenario(request: DemoScenarioRequest, db: Session = Depends(get_db)):
    """Carga (de forma idempotente) las suites de demostración en el proyecto indicado."""
    if not db.query(models_project.Project).filter(models_project.Project.id == request.project_id).first():
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    return load_demo_scenario(db, request.project_id)
