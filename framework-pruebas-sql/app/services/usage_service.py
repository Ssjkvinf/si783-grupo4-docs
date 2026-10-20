"""
Métricas de uso del producto, calculadas SOLO con datos persistidos en la base interna:
  - execution_history  (cada caso ejecutado deja una fila)
  - test_cases / test_suites / connection_profiles / projects (altas y totales)
  - usage_events       (importar/exportar Excel y otras acciones que no son ejecuciones)

No hay datos inventados ni estimaciones: si no hay registros, el resultado lo dice (`hay_datos = False`).
Las fechas están en UTC. La aplicación usa una credencial compartida, por lo que NO se mide uso por persona.
"""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.connection import ConnectionProfile
from app.models.history import ExecutionHistory
from app.models.project import Project
from app.models.suite import TestSuite
from app.models.test_case import TestCase
from app.models.usage import UsageEvent

MAX_ROWS = 100_000
ORIGENES = {
    "UI": "Módulos Casos y Suites (interfaz web)",
    "INICIO": "Recorrido guiado de Inicio",
    "CLI": "Línea de comandos (CLI)",
    "GITHUB_ACTIONS": "GitHub Actions",
    "SIN_REGISTRAR": "Origen no registrado (anterior a la Fase 4)",
}
EVENTOS = {
    "excel_import_cases": "Intentos de importar casos desde Excel (incluye los rechazados por errores)",
    "excel_validate_cases": "Validaciones de un Excel (sin importar)",
    "excel_export_cases": "Exportaciones de casos a Excel",
    "excel_export_results": "Exportaciones de resultados a Excel",
    "excel_template": "Descargas de la plantilla de Excel",
    "demo_scenario_loaded": "Cargas del escenario de demostración",
}

DEFINICIONES = {
    "total_ejecuciones": "Cantidad de registros de ejecución en el periodo. Un caso ejecutado una vez cuenta 1; una suite de 5 casos ejecutada una vez cuenta 5.",
    "corridas_de_suite": "Veces que se ejecutó una suite completa (se agrupan las filas que comparten el identificador de corrida; en registros antiguos sin identificador se agrupan por suite y minuto, de forma aproximada).",
    "tasa_pass": "Porcentaje de ejecuciones del periodo que terminaron en PASS. FAIL = se ejecutó pero no coincidió con lo esperado; ERROR = no se pudo ejecutar o evaluar.",
    "casos_distintos": "Casos guardados distintos que se ejecutaron al menos una vez en el periodo (las pruebas rápidas no se cuentan porque no son casos guardados).",
    "proyectos_activos": "Proyectos con al menos una ejecución en el periodo.",
    "por_fecha": "Ejecuciones por día (UTC), separadas por resultado. Los días sin ejecuciones aparecen en cero.",
    "top_casos": "Casos con más ejecuciones en el periodo, con su resultado más reciente.",
    "top_suites": "Suites con más corridas en el periodo.",
    "por_origen": "Desde dónde se lanzaron las ejecuciones (interfaz, recorrido guiado, CLI o GitHub Actions).",
    "altas": "Casos, suites y conexiones creados en el periodo (según su fecha de creación guardada).",
    "eventos": "Acciones que no son ejecuciones: importaciones y exportaciones de Excel, etc.",
}

LIMITACIONES = [
    "La aplicación usa una credencial compartida: no se mide el uso por persona.",
    "Las fechas y los días se calculan en UTC.",
    "Los registros anteriores a la Fase 4 no tienen origen: aparecen como «origen no registrado».",
    "Solo cuenta lo que quedó guardado en la base interna; las ejecuciones desde la CLI con otra base no aparecen aquí.",
    "El panel no distingue datos de demostración de uso real: las suites «Demo: …» y las pruebas de ejemplo cuentan igual que cualquier ejecución.",
    "«Importaciones» de Excel cuenta intentos, incluidos los archivos rechazados por errores.",
]


def _naive_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _iso(dt: Optional[datetime]) -> Optional[str]:
    dt = _naive_utc(dt)
    return dt.strftime("%Y-%m-%d %H:%M:%S") + " UTC" if dt else None


def build_summary(db: Session, days: int = 30, project_id: Optional[int] = None, now: Optional[datetime] = None) -> Dict[str, Any]:
    now = _naive_utc(now) if now else datetime.utcnow()
    first_day = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)

    q = db.query(ExecutionHistory).filter(ExecutionHistory.executed_at >= first_day)
    if project_id:
        q = q.filter(ExecutionHistory.project_id == project_id)
    rows: List[ExecutionHistory] = q.order_by(ExecutionHistory.executed_at.asc()).limit(MAX_ROWS + 1).all()
    truncado = len(rows) > MAX_ROWS
    rows = rows[:MAX_ROWS]

    # nombres para las tablas
    case_names = {c.id: c.name for c in db.query(TestCase.id, TestCase.name).all()}
    suite_names = {s.id: s.name for s in db.query(TestSuite.id, TestSuite.name).all()}
    project_names = {p.id: p.name for p in db.query(Project.id, Project.name).all()}

    estados = Counter(r.status for r in rows)
    total = len(rows)

    # --- por fecha (con ceros)
    por_dia: Dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        por_dia[_naive_utc(r.executed_at).strftime("%Y-%m-%d")][r.status] += 1
    por_fecha = []
    for i in range(days):
        d = (first_day + timedelta(days=i)).strftime("%Y-%m-%d")
        c = por_dia.get(d, Counter())
        por_fecha.append({"fecha": d, "total": sum(c.values()), "pass": c.get("PASS", 0), "fail": c.get("FAIL", 0), "error": c.get("ERROR", 0)})

    # --- casos más ejecutados
    por_caso: Dict[Optional[int], List[ExecutionHistory]] = defaultdict(list)
    for r in rows:
        por_caso[r.test_case_id].append(r)
    top_casos = []
    for cid, lst in por_caso.items():
        c = Counter(x.status for x in lst)
        ultimo = max(lst, key=lambda x: _naive_utc(x.executed_at))
        top_casos.append({
            "id": cid,
            "nombre": case_names.get(cid, "Pruebas rápidas (sin caso guardado)") if cid is not None else "Pruebas rápidas (sin caso guardado)",
            "ejecuciones": len(lst), "pass": c.get("PASS", 0), "fail": c.get("FAIL", 0), "error": c.get("ERROR", 0),
            "ultimo_estado": ultimo.status, "ultima_fecha": _iso(ultimo.executed_at),
        })
    top_casos.sort(key=lambda x: (-x["ejecuciones"], x["nombre"]))

    # --- suites (corridas)
    corridas: Dict[int, Dict[str, List[ExecutionHistory]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r.suite_id is not None:
            clave = r.run_id or f"{r.suite_id}|{_naive_utc(r.executed_at).strftime('%Y%m%d%H%M')}"
            corridas[r.suite_id][clave].append(r)
    top_suites = []
    for sid, runs in corridas.items():
        filas = [x for lst in runs.values() for x in lst]
        c = Counter(x.status for x in filas)
        ultimo = max(filas, key=lambda x: _naive_utc(x.executed_at))
        top_suites.append({
            "id": sid, "nombre": suite_names.get(sid, f"Suite #{sid} (eliminada)"), "corridas": len(runs), "ejecuciones": len(filas),
            "pct_pass": round(100.0 * c.get("PASS", 0) / len(filas), 1), "ultima_fecha": _iso(ultimo.executed_at),
        })
    top_suites.sort(key=lambda x: (-x["corridas"], x["nombre"]))

    # --- proyectos
    por_proyecto = Counter(r.project_id for r in rows)
    proyectos = [{"id": pid, "nombre": project_names.get(pid, f"Proyecto #{pid}"), "ejecuciones": n}
                 for pid, n in sorted(por_proyecto.items(), key=lambda kv: -kv[1])]

    # --- origen
    origen = Counter((r.trigger_source or "SIN_REGISTRAR") for r in rows)
    por_origen = [{"origen": k, "descripcion": ORIGENES.get(k, k), "ejecuciones": n} for k, n in sorted(origen.items(), key=lambda kv: -kv[1])]

    # --- altas en el periodo y totales actuales
    def count_since(model, col, extra=None):
        qq = db.query(model).filter(col >= first_day)
        if extra is not None:
            qq = qq.filter(extra)
        return qq.count()

    ev_q = db.query(UsageEvent).filter(UsageEvent.created_at >= first_day)
    if project_id:
        ev_q = ev_q.filter(UsageEvent.project_id == project_id)
    eventos_c = Counter(e.event_type for e in ev_q.all())
    eventos = [{"tipo": k, "descripcion": EVENTOS.get(k, k), "cantidad": n} for k, n in sorted(eventos_c.items(), key=lambda kv: -kv[1])]

    def scoped(model):
        qq = db.query(model)
        return qq.filter(model.project_id == project_id) if project_id and hasattr(model, "project_id") else qq

    altas = {
        "casos": count_since(TestCase, TestCase.created_at, TestCase.project_id == project_id if project_id else None),
        "suites": count_since(TestSuite, TestSuite.created_at, TestSuite.project_id == project_id if project_id else None),
        "conexiones": count_since(ConnectionProfile, ConnectionProfile.created_at, ConnectionProfile.project_id == project_id if project_id else None),
    }
    totales_actuales = {
        "proyectos": db.query(Project).count() if not project_id else 1,
        "casos": scoped(TestCase).count(), "suites": scoped(TestSuite).count(), "conexiones": scoped(ConnectionProfile).count(),
    }

    # --- primera y última ejecución de siempre (en el alcance)
    all_q = db.query(ExecutionHistory)
    if project_id:
        all_q = all_q.filter(ExecutionHistory.project_id == project_id)
    primera = all_q.order_by(ExecutionHistory.executed_at.asc()).first()
    ultima = all_q.order_by(ExecutionHistory.executed_at.desc()).first()
    total_historico = all_q.count()

    hay_datos = total > 0
    if hay_datos:
        mensaje_vacio = None
    elif total_historico > 0:
        mensaje_vacio = (f"No hay ejecuciones en los últimos {days} días. Hay {total_historico} ejecuciones anteriores "
                         f"(la última: {_iso(ultima.executed_at)}). Amplíe el periodo o ejecute una comprobación.")
    else:
        mensaje_vacio = "Todavía no hay ejecuciones registradas. Haga su primera comprobación desde Inicio y vuelva aquí."

    return {
        "periodo": {"dias": days, "desde": first_day.strftime("%Y-%m-%d"), "hasta": now.strftime("%Y-%m-%d"), "zona": "UTC"},
        "alcance": {"project_id": project_id, "proyecto": project_names.get(project_id) if project_id else "Todos los proyectos"},
        "hay_datos": hay_datos,
        "mensaje_vacio": mensaje_vacio,
        "truncado": truncado,
        "tarjetas": {
            "total_ejecuciones": total,
            "corridas_de_suite": sum(s["corridas"] for s in top_suites),
            "pass": estados.get("PASS", 0), "fail": estados.get("FAIL", 0), "error": estados.get("ERROR", 0),
            "tasa_pass": round(100.0 * estados.get("PASS", 0) / total, 1) if total else None,
            "casos_distintos": len({r.test_case_id for r in rows if r.test_case_id is not None}),
            "proyectos_activos": len(por_proyecto),
            "duracion_media_ms": round(sum(r.duration_ms or 0 for r in rows) / total, 2) if total else None,
        },
        "por_fecha": por_fecha,
        "top_casos": top_casos[:5],
        "top_suites": top_suites[:5],
        "proyectos": proyectos,
        "por_origen": por_origen,
        "altas": altas,
        "totales_actuales": totales_actuales,
        "eventos": eventos,
        "historico": {"total": total_historico, "primera_ejecucion": _iso(primera.executed_at) if primera else None,
                      "ultima_ejecucion": _iso(ultima.executed_at) if ultima else None},
        "definiciones": DEFINICIONES,
        "limitaciones": LIMITACIONES,
    }


def record_event(db: Session, event_type: str, project_id: Optional[int] = None, source: str = "API", detail: Optional[str] = None) -> None:
    """Registra un evento de uso (sin datos personales ni contenido de archivos)."""
    db.add(UsageEvent(event_type=event_type, project_id=project_id, source=source, detail=(detail or "")[:500] or None))
    db.commit()
