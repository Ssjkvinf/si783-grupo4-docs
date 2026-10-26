"""
Endpoints REST para la consulta del Historial de Ejecuciones.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.models import history as models_history
from app.models import schemas
from app.models import suite as models_suite
from app.services import comparacion, reporte_corrida

router = APIRouter()

@router.get("/history/", response_model=list[schemas.HistoryResponse])
def get_history(
    project_id: Optional[int] = Query(None),
    test_case_id: Optional[int] = Query(None),
    suite_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    executed_by: Optional[str] = Query(None, max_length=50),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Obtiene el historial de ejecuciones guardadas admitiendo paginación
    y filtros opcionales por project_id, test_case_id, suite_id, status y executed_by (quién ejecutó).
    Cada registro incluye los nombres del caso, la suite y la conexión.
    """
    H = models_history.ExecutionHistory
    query = db.query(H).options(joinedload(H.test_case), joinedload(H.test_suite), joinedload(H.connection_profile))
    
    if project_id:
        query = query.filter(models_history.ExecutionHistory.project_id == project_id)
    if test_case_id:
        query = query.filter(models_history.ExecutionHistory.test_case_id == test_case_id)
    if suite_id:
        query = query.filter(models_history.ExecutionHistory.suite_id == suite_id)
    if status:
        status = status.upper()
        if status not in ["PASS", "FAIL", "ERROR"]:
            raise HTTPException(status_code=422, detail="Estado inválido. Use PASS, FAIL o ERROR.")
        query = query.filter(models_history.ExecutionHistory.status == status)
    if executed_by:
        query = query.filter(models_history.ExecutionHistory.executed_by == executed_by.strip())

    histories = query.order_by(models_history.ExecutionHistory.id.desc()).offset(skip).limit(limit).all()
    return histories

@router.get("/history/runs")
def get_suite_runs(suite_id: int = Query(...), limit: int = Query(10, ge=1, le=50), db: Session = Depends(get_db)):
    """Últimas corridas de una suite (la más reciente primero) con sus conteos, para ver la tendencia y comparar."""
    if not db.query(models_suite.TestSuite).filter(models_suite.TestSuite.id == suite_id).first():
        raise HTTPException(status_code=404, detail="Suite no encontrada.")
    return comparacion.corridas_de_suite(db, suite_id, limit)


@router.get("/history/runs/{run_id}/report", response_class=HTMLResponse)
def get_run_report(run_id: str, db: Session = Depends(get_db)):
    """Reporte HTML descargable de una corrida (se puede imprimir o guardar como PDF desde el navegador)."""
    if len(run_id) > 64:
        raise HTTPException(status_code=422, detail="Identificador de corrida inválido.")
    html = reporte_corrida.generar_html(db, run_id)
    if html is None:
        raise HTTPException(status_code=404, detail="No hay ejecuciones con ese identificador de corrida.")
    return HTMLResponse(html, headers={"Content-Disposition": f'attachment; filename="reporte-corrida-{run_id[:8]}.html"',
                                       "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})


@router.get("/history/{history_id}", response_model=schemas.HistoryResponse)
def get_history_detail(history_id: int, db: Session = Depends(get_db)):
    """Obtiene los detalles de un registro de historial específico."""
    record = db.query(models_history.ExecutionHistory).filter(models_history.ExecutionHistory.id == history_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Registro de historial no encontrado.")
    return record
