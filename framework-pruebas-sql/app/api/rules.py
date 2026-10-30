"""
Asistente de reglas: catálogo de reglas comunes y generación del SELECT correspondiente. No se conecta a Oracle ni guarda nada.
"""
from typing import Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from app.services import rule_templates

router = APIRouter()


class RuleBuildRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rule_id: str
    params: Dict[str, str] = {}


@router.get("/rules/templates")
def list_rule_templates():
    """Lista las reglas comunes que el asistente sabe convertir en una consulta (con sus campos y ejemplos)."""
    return rule_templates.listar()


@router.post("/rules/build")
def build_rule(request: RuleBuildRequest):
    """Convierte una regla y sus datos en el SELECT, el tipo de validación y el valor esperado."""
    try:
        return rule_templates.construir(request.rule_id, request.params)
    except rule_templates.ReglaInvalida as e:
        raise HTTPException(status_code=422, detail=str(e))
