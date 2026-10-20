"""
Endpoints de la integración con Excel (.xlsx). Ver app/services/excel_io.py para las reglas y la seguridad.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import project as models_project
from app.services import excel_io
from app.services.usage_service import record_event

router = APIRouter()


def _xlsx(content: bytes, filename: str) -> Response:
    return Response(content=content, media_type=excel_io.XLSX_MEDIA_TYPE,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _project_or_404(db: Session, project_id: int):
    if not db.query(models_project.Project).filter(models_project.Project.id == project_id).first():
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")


@router.get("/excel/template")
def download_template(db: Session = Depends(get_db)):
    """Plantilla de casos con instrucciones, ejemplos y lista desplegable de validaciones."""
    record_event(db, "excel_template", None, "UI")
    return _xlsx(excel_io.build_template(), "plantilla_casos.xlsx")


@router.get("/excel/cases/export")
def export_cases(project_id: int = Query(...), db: Session = Depends(get_db)):
    _project_or_404(db, project_id)
    content = excel_io.export_cases(db, project_id)
    record_event(db, "excel_export_cases", project_id, "UI")
    return _xlsx(content, f"casos_proyecto_{project_id}.xlsx")


@router.get("/excel/results/export")
def export_results(
    project_id: Optional[int] = Query(None),
    suite_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    days: Optional[int] = Query(None, ge=1, le=3650),
    db: Session = Depends(get_db),
):
    if status and status.upper() not in ("PASS", "FAIL", "ERROR"):
        raise HTTPException(status_code=422, detail="Estado inválido. Use PASS, FAIL o ERROR.")
    if project_id:
        _project_or_404(db, project_id)
    content = excel_io.export_results(db, project_id, suite_id, status, days)
    record_event(db, "excel_export_results", project_id, "UI")
    return _xlsx(content, "resultados.xlsx")


@router.post("/excel/cases/import")
async def import_cases(
    request: Request,
    project_id: int = Query(...),
    mode: str = Query("skip", description="skip = omitir los que ya existen; update = actualizarlos"),
    dry_run: bool = Query(False, description="true = solo validar, sin guardar"),
    db: Session = Depends(get_db),
):
    """
    Importa casos desde un .xlsx enviado como cuerpo binario de la petición (sin multipart).
    Todo o nada: con un solo error no se guarda nada. Devuelve el informe fila por fila.
    """
    _project_or_404(db, project_id)
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > excel_io.MAX_BYTES:
        raise HTTPException(status_code=413, detail="El archivo supera el máximo permitido (2 MB).")
    body = await request.body()
    try:
        return excel_io.import_cases(db, project_id, body, mode=mode, dry_run=dry_run, source="UI")
    except excel_io.ExcelError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
