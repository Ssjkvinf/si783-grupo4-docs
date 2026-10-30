"""
Comparar con la ejecución anterior: para cada caso, qué resultado tuvo la vez anterior y si ahora empeoró («nuevo fallo») o se
arregló («corregido»); y el resumen de las últimas corridas de una suite (una corrida = filas que comparten run_id).

Se calcula con el historial guardado; no ejecuta nada contra la base objetivo.
"""
from collections import OrderedDict
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.history import ExecutionHistory

CAMBIOS = {
    "primera_vez": "Primera ejecución de este caso",
    "igual": "Igual que la vez anterior",
    "nuevo_fallo": "Antes pasaba y ahora no: algo cambió",
    "corregido": "Antes fallaba y ahora pasa",
    "cambio": "Sigue sin pasar, pero con otro resultado",
}


def anterior(db: Session, test_case_id: Optional[int], antes_de_id: int) -> Optional[ExecutionHistory]:
    """Ejecución inmediatamente anterior del mismo caso (en cualquier suite o suelta)."""
    if not test_case_id:
        return None
    return (db.query(ExecutionHistory)
            .filter(ExecutionHistory.test_case_id == test_case_id, ExecutionHistory.id < antes_de_id)
            .order_by(ExecutionHistory.id.desc()).first())


def clasificar(estado_anterior: Optional[str], estado_actual: str) -> str:
    if estado_anterior is None:
        return "primera_vez"
    if estado_anterior == estado_actual:
        return "igual"
    if estado_anterior == "PASS":
        return "nuevo_fallo"
    if estado_actual == "PASS":
        return "corregido"
    return "cambio"


def corridas_de_suite(db: Session, suite_id: int, limite: int = 10) -> List[Dict[str, Any]]:
    """Últimas corridas de la suite (la más reciente primero), con sus conteos. Los registros antiguos sin run_id se omiten."""
    filas = (db.query(ExecutionHistory)
             .filter(ExecutionHistory.suite_id == suite_id, ExecutionHistory.run_id.isnot(None))
             .order_by(ExecutionHistory.id.desc()).limit(limite * 60).all())
    corridas: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    for h in filas:
        c = corridas.get(h.run_id)
        if c is None:
            if len(corridas) >= limite:
                continue
            c = corridas[h.run_id] = {"run_id": h.run_id, "fecha": h.executed_at, "passed": 0, "failed": 0, "errors": 0,
                                      "total": 0, "executed_by": h.executed_by, "duracion_ms": 0.0}
        c["total"] += 1
        c["duracion_ms"] = round(c["duracion_ms"] + (h.duration_ms or 0), 2)
        c["passed" if h.status == "PASS" else "failed" if h.status == "FAIL" else "errors"] += 1
        if h.executed_at and (c["fecha"] is None or h.executed_at < c["fecha"]):
            c["fecha"] = h.executed_at
    return list(corridas.values())
