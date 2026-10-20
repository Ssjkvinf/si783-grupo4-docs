"""
Integración con Excel: plantilla, importación y exportación de casos, y exportación de resultados (.xlsx).

Qué lo hace una integración funcional y no solo un archivo:
  - IMPORTA casos desde un Excel con validaciones fila por fila (mismas reglas que la API y la política SQL),
    con modo de simulación (sin guardar) y todo-o-nada: si hay un solo error no se importa nada.
  - EXPORTA casos y resultados (con color por PASS/FAIL/ERROR) para revisarlos o compartirlos.
  - Es un ciclo completo: plantilla -> importar -> ejecutar (UI/CLI) -> exportar resultados.

Seguridad de los archivos:
  - Se rechazan las fórmulas (una celda con fórmula no se importa) y los archivos con macros o demasiado grandes.
  - Al exportar, el texto que empiece por = + - @ se escribe como TEXTO literal, nunca como fórmula (inyección de fórmulas).
  - No se leen enlaces externos y los archivos se procesan en memoria, sin escribir en disco.
"""
import io
import re
import unicodedata
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from sqlalchemy.orm import Session

from app.models import suite as models_suite
from app.models import test_case as models_tc
from app.models.history import ExecutionHistory
from app.models.project import Project
from app.models.schemas import normalize_expected_result
from app.security.sql_policy import validate_sql_statement
from app.services.usage_service import record_event

MAX_BYTES = 2 * 1024 * 1024            # tamaño máximo del archivo importado
MAX_UNCOMPRESSED = 25 * 1024 * 1024    # protección contra «zip bombs»
MAX_ROWS = 500                         # filas de casos por importación
MAX_CELL = 30000                       # Excel admite 32 767 caracteres por celda
SHEET_CASES = "Casos"
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

COLUMNS = [("nombre", "Nombre"), ("descripcion", "Descripción"), ("sql", "SQL"),
           ("validacion", "Validación"), ("esperado", "Esperado"), ("suites", "Suites")]
REQUIRED = ("nombre", "sql", "validacion", "esperado")
VALIDATION_ALIASES = {
    "ROW_COUNT": {"row_count", "cantidad de filas", "filas", "cantidad"},
    "SCALAR_VALUE": {"scalar_value", "valor", "valor escalar", "valor que devuelve la consulta"},
    "EXISTS": {"exists", "existencia", "existe"},
}

HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
STATUS_FILL = {"PASS": PatternFill("solid", fgColor="C6EFCE"), "FAIL": PatternFill("solid", fgColor="FFEB9C"),
               "ERROR": PatternFill("solid", fgColor="FFC7CE")}


class ExcelError(Exception):
    """Archivo inválido en su conjunto (no es un .xlsx, es demasiado grande, falta la hoja…)."""


# ---------------------------------------------------------------------------------------- utilidades

def _norm(text: Any) -> str:
    t = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", t).strip().lower()


def _put(ws, row: int, col: int, value: Any):
    """Escribe una celda. El texto que parece fórmula se guarda como texto literal."""
    cell = ws.cell(row=row, column=col)
    if isinstance(value, str):
        value = value[:MAX_CELL]
        cell.value = value
        if value[:1] in ("=", "+", "-", "@", "\t", "\r"):
            cell.data_type = "s"
    else:
        cell.value = value
    return cell


def _style_header(ws, headers: List[str], widths: List[int]):
    for i, (h, w) in enumerate(zip(headers, widths), start=1):
        c = _put(ws, 1, i, h)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = HEADER_FILL
        c.alignment = Alignment(vertical="center")
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"


def _to_bytes(wb: Workbook) -> bytes:
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ------------------------------------------------------------------------------------------ plantilla

def build_template() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_CASES
    _style_header(ws, [h for _, h in COLUMNS], [34, 38, 70, 18, 12, 34])
    ejemplos = [
        ("Hay 5 productos registrados", "Cantidad esperada de registros", "SELECT COUNT(*) FROM FRAMEWORK_TEST_ITEMS", "SCALAR_VALUE", 5, "Reglas de calidad"),
        ("No hay productos sin nombre", "Datos inválidos: 0", "SELECT COUNT(*) FROM FRAMEWORK_TEST_ITEMS WHERE TRIM(NAME) IS NULL", "SCALAR_VALUE", 0, "Reglas de calidad"),
        ("Existe el producto con ID 3", "Existencia de un registro", "SELECT ID FROM FRAMEWORK_TEST_ITEMS WHERE ID = 3", "EXISTS", "true", "Reglas de calidad"),
    ]
    for r, fila in enumerate(ejemplos, start=2):
        for c, v in enumerate(fila, start=1):
            _put(ws, r, c, v)
    dv = DataValidation(type="list", formula1='"ROW_COUNT,SCALAR_VALUE,EXISTS"', allow_blank=True, showDropDown=False)
    dv.error = "Elija ROW_COUNT, SCALAR_VALUE o EXISTS"
    dv.errorTitle = "Validación no válida"
    ws.add_data_validation(dv)
    dv.add(f"D2:D{MAX_ROWS + 1}")

    info = wb.create_sheet("Instrucciones")
    info.column_dimensions["A"].width = 120
    lineas = [
        "Plantilla de casos de prueba — Framework de pruebas SQL",
        "",
        "1. Complete una fila por caso en la hoja «Casos». Las 3 filas de ejemplo usan la tabla de demostración FRAMEWORK_TEST_ITEMS: bórrelas o cámbielas.",
        "2. Nombre (obligatorio, único en el archivo, máx. 150), SQL (obligatorio: UNA sola sentencia; se rechazan DDL como DROP/ALTER y varias sentencias).",
        "3. Validación (obligatoria): ROW_COUNT = cantidad de FILAS que devuelve la consulta; SCALAR_VALUE = VALOR de la primera columna de la única fila "
        "(p. ej. el número de un COUNT(*)); EXISTS = devuelve filas (true) o ninguna (false).",
        "4. Esperado (obligatorio): un entero >= 0 para ROW_COUNT; cualquier valor para SCALAR_VALUE (NULL = nulo); true o false para EXISTS. "
        "Lo define usted: la aplicación no lo calcula.",
        "5. Suites (opcional): nombres de suites separados por punto y coma (;). Si no existen, se crean y se vinculan los casos.",
        "6. No use fórmulas: las celdas con fórmula se rechazan. Máximo 500 casos y 2 MB por archivo.",
        "7. Importe el archivo en la pantalla «Casos de Prueba» o con la CLI (python -m app.cli import-excel). Use primero «Validar» para ver los errores sin guardar nada.",
    ]
    for i, t in enumerate(lineas, start=1):
        c = _put(info, i, 1, t)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        if i == 1:
            c.font = Font(bold=True, size=13)
    return _to_bytes(wb)


def build_cases_file(rows: List[Tuple[str, str, str, str, Any, str]]) -> bytes:
    """Libro de casos listo para importar a partir de tuplas (nombre, descripción, sql, validación, esperado, suites)."""
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_CASES
    _style_header(ws, [h for _, h in COLUMNS], [34, 38, 70, 18, 12, 34])
    for r, fila in enumerate(rows, start=2):
        for c, v in enumerate(fila, start=1):
            cell = _put(ws, r, c, v)
            if c == 3:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
    dv = DataValidation(type="list", formula1='"ROW_COUNT,SCALAR_VALUE,EXISTS"', allow_blank=True, showDropDown=False)
    ws.add_data_validation(dv)
    dv.add(f"D2:D{MAX_ROWS + 1}")
    return _to_bytes(wb)


# ------------------------------------------------------------------------------------------ exportar

def export_cases(db: Session, project_id: int) -> bytes:
    cases = db.query(models_tc.TestCase).filter(models_tc.TestCase.project_id == project_id).order_by(models_tc.TestCase.id).all()
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_CASES
    _style_header(ws, [h for _, h in COLUMNS], [34, 38, 70, 18, 12, 34])
    for r, c in enumerate(cases, start=2):
        suites = "; ".join(sorted(s.name for s in c.suites))
        for col, v in enumerate((c.name, c.description or "", c.sql_query, c.validation_type, c.expected_result, suites), start=1):
            cell = _put(ws, r, col, v)
            if col == 3:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
    ws.auto_filter.ref = f"A1:F{max(2, len(cases) + 1)}"
    return _to_bytes(wb)


def export_results(db: Session, project_id: Optional[int] = None, suite_id: Optional[int] = None,
                   status: Optional[str] = None, days: Optional[int] = None, limit: int = 5000) -> bytes:
    q = db.query(ExecutionHistory)
    if project_id:
        q = q.filter(ExecutionHistory.project_id == project_id)
    if suite_id:
        q = q.filter(ExecutionHistory.suite_id == suite_id)
    if status:
        q = q.filter(ExecutionHistory.status == status.upper())
    if days:
        q = q.filter(ExecutionHistory.executed_at >= datetime.utcnow() - timedelta(days=days))
    rows = q.order_by(ExecutionHistory.id.desc()).limit(limit).all()

    cases = {c.id: c.name for c in db.query(models_tc.TestCase.id, models_tc.TestCase.name).all()}
    suites = {s.id: s.name for s in db.query(models_suite.TestSuite.id, models_suite.TestSuite.name).all()}
    projects = {p.id: p.name for p in db.query(Project.id, Project.name).all()}

    wb = Workbook()
    ws = wb.active
    ws.title = "Resultados"
    headers = ["ID", "Fecha (UTC)", "Proyecto", "Caso", "Suite", "Estado", "Validación", "Esperado", "Obtenido", "Filas",
               "Duración (ms)", "Origen", "Rollback aplicado", "Error", "Corrida"]
    _style_header(ws, headers, [8, 20, 22, 36, 30, 10, 14, 14, 40, 8, 13, 16, 12, 40, 38])
    for r, h in enumerate(rows, start=2):
        fecha = h.executed_at.astimezone(timezone.utc).replace(tzinfo=None) if h.executed_at and h.executed_at.tzinfo else h.executed_at
        valores = [h.id, fecha.strftime("%Y-%m-%d %H:%M:%S") if fecha else "", projects.get(h.project_id, ""),
                   cases.get(h.test_case_id, "Prueba rápida") if h.test_case_id else "Prueba rápida",
                   suites.get(h.suite_id, "") if h.suite_id else "", h.status, h.validation_type or "", h.expected_result or "",
                   h.actual_result or "", h.rowcount, h.duration_ms, h.trigger_source or "sin registrar",
                   "sí" if h.rollback_applied else "no", h.error_message or "", h.run_id or ""]
        for c, v in enumerate(valores, start=1):
            cell = _put(ws, r, c, v)
            if c == 6 and v in STATUS_FILL:
                cell.fill = STATUS_FILL[v]
                cell.font = Font(bold=True)
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{max(2, len(rows) + 1)}"

    resumen = wb.create_sheet("Resumen")
    resumen.column_dimensions["A"].width = 34
    resumen.column_dimensions["B"].width = 14
    estados = {s: sum(1 for h in rows if h.status == s) for s in ("PASS", "FAIL", "ERROR")}
    filas = [("Exportado (UTC)", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")), ("Filas exportadas", len(rows)),
             ("PASS", estados["PASS"]), ("FAIL", estados["FAIL"]), ("ERROR", estados["ERROR"])]
    if len(rows) == limit:
        filas.append(("Aviso", f"Se alcanzó el límite de {limit} filas"))
    for i, (k, v) in enumerate(filas, start=1):
        _put(resumen, i, 1, k).font = Font(bold=True)
        _put(resumen, i, 2, v)
    return _to_bytes(wb)


# ------------------------------------------------------------------------------------------ importar

def _check_file(content: bytes):
    if not content:
        raise ExcelError("El archivo está vacío.")
    if len(content) > MAX_BYTES:
        raise ExcelError(f"El archivo supera el máximo de {MAX_BYTES // (1024 * 1024)} MB.")
    if content[:2] != b"PK":
        raise ExcelError("No es un archivo .xlsx válido (se esperaba un libro de Excel moderno, no .xls ni CSV).")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            names = z.namelist()
            if any(n.lower().endswith("vbaproject.bin") for n in names):
                raise ExcelError("El archivo contiene macros: no se aceptan libros con macros.")
            if sum(i.file_size for i in z.infolist()) > MAX_UNCOMPRESSED:
                raise ExcelError("El contenido descomprimido del archivo es demasiado grande.")
    except zipfile.BadZipFile:
        raise ExcelError("El archivo está dañado o no es un .xlsx válido.")


def _cell_text(cell) -> Tuple[Optional[str], Optional[str]]:
    """Devuelve (texto, error). Rechaza fórmulas; convierte números y booleanos a texto estable."""
    v = cell.value
    if v is None:
        return None, None
    if cell.data_type == "f" or (isinstance(v, str) and v.lstrip().startswith("=")):
        return None, "las fórmulas no se aceptan; escriba el valor como texto"
    if isinstance(v, bool):
        return ("true" if v else "false"), None
    if isinstance(v, float) and v.is_integer():
        return str(int(v)), None
    if isinstance(v, (datetime,)):
        return None, "las fechas no se aceptan en esta plantilla; escriba el valor como texto"
    text = str(v).strip()
    return (text if text else None), None


def parse_cases(content: bytes) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Lee y valida el Excel. Devuelve (filas_validas, errores). No toca la base de datos."""
    _check_file(content)
    try:
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=False)
    except Exception:
        raise ExcelError("No se pudo leer el libro de Excel (¿está dañado o protegido con contraseña?).")
    if SHEET_CASES not in wb.sheetnames:
        raise ExcelError(f"Falta la hoja «{SHEET_CASES}». Descargue la plantilla y use esa hoja.")
    ws = wb[SHEET_CASES]
    it = ws.iter_rows(values_only=False)
    try:
        header_cells = next(it)
    except StopIteration:
        raise ExcelError("La hoja «Casos» está vacía.")

    col_of: Dict[str, int] = {}
    for idx, c in enumerate(header_cells):
        key = _norm(c.value)
        for k, label in COLUMNS:
            if key in (k, _norm(label)):
                col_of.setdefault(k, idx)
    faltan = [label for k, label in COLUMNS if k in REQUIRED and k not in col_of]
    if faltan:
        raise ExcelError("Faltan columnas obligatorias en la fila 1: " + ", ".join(faltan) + ".")

    rows: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    seen: Dict[str, int] = {}

    def err(fila: int, campo: str, msg: str):
        errors.append({"fila": fila, "campo": campo, "mensaje": msg})

    n_data = 0
    for fila, cells in enumerate(it, start=2):
        raw: Dict[str, Optional[str]] = {}
        row_errors_before = len(errors)
        for k, _label in COLUMNS:
            if k in col_of and col_of[k] < len(cells):
                text, problem = _cell_text(cells[col_of[k]])
                if problem:
                    err(fila, dict(COLUMNS)[k], problem)
                raw[k] = text
            else:
                raw[k] = None
        if not any(raw.values()) and len(errors) == row_errors_before:
            continue                                   # fila vacía
        n_data += 1
        if n_data > MAX_ROWS:
            err(fila, "—", f"Se superó el máximo de {MAX_ROWS} casos por archivo.")
            break

        nombre, sql, esperado = raw["nombre"], raw["sql"], raw["esperado"]
        desc = raw["descripcion"]
        if not nombre:
            err(fila, "Nombre", "es obligatorio")
        elif len(nombre) > 150:
            err(fila, "Nombre", "supera los 150 caracteres")
        elif nombre.lower() in seen:
            err(fila, "Nombre", f"repetido en el archivo (también en la fila {seen[nombre.lower()]})")
        else:
            seen[nombre.lower()] = fila
        if desc and len(desc) > 500:
            err(fila, "Descripción", "supera los 500 caracteres")

        validacion = None
        if not raw["validacion"]:
            err(fila, "Validación", "es obligatoria (ROW_COUNT, SCALAR_VALUE o EXISTS)")
        else:
            key = _norm(raw["validacion"])
            validacion = next((k for k, aliases in VALIDATION_ALIASES.items() if key in aliases), None)
            if not validacion:
                err(fila, "Validación", f"«{raw['validacion']}» no es válida; use ROW_COUNT, SCALAR_VALUE o EXISTS")

        stmt_type = None
        if not sql:
            err(fila, "SQL", "es obligatorio")
        else:
            ok, stmt_type, msg = validate_sql_statement(sql, "TEST")
            if not ok:
                err(fila, "SQL", msg)
            elif validacion == "SCALAR_VALUE" and stmt_type != "SELECT":
                err(fila, "Validación", "SCALAR_VALUE solo se puede usar con una consulta SELECT")

        if esperado is None or esperado == "":
            err(fila, "Esperado", "es obligatorio: usted define lo que debe devolver la consulta")
        elif validacion:
            try:
                esperado = normalize_expected_result(esperado, validacion)
            except ValueError as exc:
                err(fila, "Esperado", str(exc))

        suites: List[str] = []
        if raw["suites"]:
            suites = [s.strip() for s in raw["suites"].split(";") if s.strip()]
            if len(suites) > 5:
                err(fila, "Suites", "máximo 5 suites por caso")
            if any(len(s) > 100 for s in suites):
                err(fila, "Suites", "cada nombre de suite admite hasta 100 caracteres")

        if len(errors) == row_errors_before:
            rows.append({"fila": fila, "nombre": nombre, "descripcion": desc, "sql": sql, "validacion": validacion,
                         "esperado": esperado, "suites": suites})
    wb.close()
    if n_data == 0 and not errors:
        raise ExcelError("La hoja «Casos» no tiene filas con datos.")
    return rows, errors


def import_cases(db: Session, project_id: int, content: bytes, mode: str = "skip", dry_run: bool = False,
                 source: str = "UI") -> Dict[str, Any]:
    """
    Importa casos. mode = 'skip' (omite los que ya existen por nombre) o 'update' (los actualiza).
    Todo o nada: si hay algún error de validación no se guarda nada.
    """
    if mode not in ("skip", "update"):
        raise ExcelError("mode debe ser 'skip' o 'update'.")
    rows, errors = parse_cases(content)

    existing = {c.name.lower(): c for c in db.query(models_tc.TestCase).filter(models_tc.TestCase.project_id == project_id).all()}
    crear = [r for r in rows if r["nombre"].lower() not in existing]
    ya = [r for r in rows if r["nombre"].lower() in existing]
    actualizar = ya if mode == "update" else []
    omitidos = ya if mode == "skip" else []

    resultado: Dict[str, Any] = {
        "ok": not errors, "simulacion": dry_run, "modo": mode, "filas_validas": len(rows), "errores": errors,
        "a_crear": [r["nombre"] for r in crear][:100], "n_crear": len(crear),
        "a_actualizar": [r["nombre"] for r in actualizar][:100], "n_actualizar": len(actualizar),
        "omitidos_existentes": [r["nombre"] for r in omitidos][:100], "n_omitidos": len(omitidos),
        "importado": False,
    }
    if errors:
        resultado["mensaje"] = f"No se importó nada: hay {len(errors)} error(es). Corrija el archivo y vuelva a intentarlo."
        record_event(db, "excel_validate_cases" if dry_run else "excel_import_cases", project_id, source, f"rechazado: {len(errors)} errores")
        return resultado
    if dry_run:
        resultado["mensaje"] = "Validación correcta. No se guardó nada (simulación)."
        record_event(db, "excel_validate_cases", project_id, source, f"validas={len(rows)}")
        return resultado

    suites_cache: Dict[str, models_suite.TestSuite] = {
        s.name.lower(): s for s in db.query(models_suite.TestSuite).filter(models_suite.TestSuite.project_id == project_id).all()}
    suites_creadas = 0
    try:
        for r in crear + actualizar:
            tc = existing.get(r["nombre"].lower())
            if tc is None:
                tc = models_tc.TestCase(project_id=project_id, name=r["nombre"], description=r["descripcion"], sql_query=r["sql"],
                                        validation_type=r["validacion"], expected_result=r["esperado"])
                db.add(tc)
            else:
                tc.description, tc.sql_query = r["descripcion"], r["sql"]
                tc.validation_type, tc.expected_result = r["validacion"], r["esperado"]
            db.flush()
            for nombre_suite in r["suites"]:
                suite = suites_cache.get(nombre_suite.lower())
                if suite is None:
                    suite = models_suite.TestSuite(project_id=project_id, name=nombre_suite, description="Creada al importar desde Excel.")
                    db.add(suite)
                    db.flush()
                    suites_cache[nombre_suite.lower()] = suite
                    suites_creadas += 1
                if tc not in suite.test_cases:
                    suite.test_cases.append(tc)
        db.commit()
    except Exception:
        db.rollback()
        raise
    resultado.update({"importado": True, "suites_creadas": suites_creadas,
                      "mensaje": f"Importación correcta: {len(crear)} creados, {len(actualizar)} actualizados, {len(omitidos)} omitidos (ya existían)."})
    record_event(db, "excel_import_cases", project_id, source,
                 f"creados={len(crear)} actualizados={len(actualizar)} omitidos={len(omitidos)} suites_nuevas={suites_creadas}")
    return resultado
