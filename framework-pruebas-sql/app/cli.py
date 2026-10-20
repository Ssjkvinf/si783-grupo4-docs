"""
CLI del Framework de pruebas SQL: ejecutar casos y suites desde la terminal o desde un flujo de CI y obtener un
código de salida útil, además de importar/exportar Excel.

Uso (desde la carpeta framework-pruebas-sql):
  python -m app.cli init-db
  python -m app.cli import-excel checks/reglas_demo.xlsx --project "Demo" --create-project --dry-run --mode update
  python -m app.cli run --project "Demo" --suite "Reglas de calidad" \
        --host 127.0.0.1 --port 1521 --service FREEPDB1 --user FRAMEWORK_TEST --env TEST \
        --junit reportes/sql.xml --markdown reportes/sql.md --json reportes/sql.json
  python -m app.cli export-excel results --project "Demo" --out resultados.xlsx

La contraseña de Oracle NUNCA se pasa por argumento: se lee de una variable de entorno (por defecto FW_ORACLE_PASSWORD,
configurable con --password-env). La base interna (SQLite) se elige con --db o con FRAMEWORK_DB_URL.

Códigos de salida de `run` (pensados para usar la CLI como compuerta en CI):
  0  todas las comprobaciones dieron PASS
  1  al menos una dio FAIL y ninguna dio ERROR
  2  al menos una dio ERROR (no se pudo ejecutar o evaluar), aunque haya FAIL
  3  uso o configuración inválidos (proyecto o suite inexistente, falta la contraseña, argumentos incorrectos…)
  4  no había casos que ejecutar
Los demás comandos devuelven 0 si salen bien, 1 si el Excel tiene errores de validación y 3 si el uso es inválido.

Cada ejecución queda en el historial con origen CLI (o GITHUB_ACTIONS cuando corre dentro de un flujo de GitHub).
"""
import argparse
import json
import os
import sys
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

EXIT_OK, EXIT_FAIL, EXIT_ERROR, EXIT_USAGE, EXIT_NO_CASES = 0, 1, 2, 3, 4
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class UsageError(Exception):
    """Argumentos o entorno inválidos (código de salida 3)."""


# ------------------------------------------------------------------------------------------ utilidades

def _out(msg: str = "") -> None:
    print(msg)


def _find_project(db, name: str, create: bool = False):
    from app.models.project import Project
    proj = db.query(Project).filter(Project.name.ilike(name)).first()
    if proj is None and create:
        proj = Project(name=name, description="Creado desde la CLI.")
        db.add(proj)
        db.commit()
        db.refresh(proj)
    if proj is None:
        raise UsageError(f"No existe el proyecto «{name}». Use --create-project al importar o revise el nombre.")
    return proj


def _resolve_profile(db, project, args):
    """Perfil existente por nombre o perfil ad hoc (host/puerto/servicio/usuario/ambiente) validado como en la API."""
    from app.models.connection import ConnectionProfile
    from app.security.target_policy import ensure_valid_target

    if args.profile:
        prof = db.query(ConnectionProfile).filter(ConnectionProfile.project_id == project.id,
                                                  ConnectionProfile.name.ilike(args.profile)).first()
        if not prof:
            raise UsageError(f"No existe el perfil de conexión «{args.profile}» en el proyecto «{project.name}».")
        return prof
    missing = [flag for flag, v in (("--host", args.host), ("--service", args.service), ("--user", args.user)) if not v]
    if missing:
        raise UsageError("Indique --profile NOMBRE o bien " + ", ".join(missing) + " (y opcionalmente --port y --env).")
    try:
        ensure_valid_target(args.host, args.service)
    except ValueError as exc:
        raise UsageError(str(exc))
    name = f"cli:{args.user}@{args.host}:{args.port}/{args.service}"
    prof = db.query(ConnectionProfile).filter(ConnectionProfile.project_id == project.id, ConnectionProfile.name == name).first()
    if prof is None:
        prof = ConnectionProfile(project_id=project.id, name=name, engine="ORACLE", host=args.host, port=args.port,
                                 service_name=args.service, username=args.user, environment_type=args.env)
        db.add(prof)
    else:
        prof.environment_type = args.env
    db.commit()
    db.refresh(prof)
    return prof


def _select_cases(db, project, args):
    from app.models.suite import TestSuite
    from app.models.test_case import TestCase
    suite = None
    if args.suite:
        suite = db.query(TestSuite).filter(TestSuite.project_id == project.id, TestSuite.name.ilike(args.suite)).first()
        if not suite:
            raise UsageError(f"No existe la suite «{args.suite}» en el proyecto «{project.name}».")
        return suite, list(suite.test_cases)
    if args.case:
        cases = []
        for n in args.case:
            c = db.query(TestCase).filter(TestCase.project_id == project.id, TestCase.name.ilike(n)).first()
            if not c:
                raise UsageError(f"No existe el caso «{n}» en el proyecto «{project.name}».")
            cases.append(c)
        return None, cases
    return None, db.query(TestCase).filter(TestCase.project_id == project.id).order_by(TestCase.id).all()


# --------------------------------------------------------------------------------------------- reportes

def junit_xml(results: List[Dict[str, Any]], suite_name: str, project: str, run_id: str, source: str) -> str:
    fails = sum(1 for r in results if r["status"] == "FAIL")
    errors = sum(1 for r in results if r["status"] == "ERROR")
    ts = ET.Element("testsuite", name=suite_name, tests=str(len(results)), failures=str(fails), errors=str(errors), skipped="0",
                    time=f"{sum(r['duration_ms'] for r in results) / 1000:.3f}")
    props = ET.SubElement(ts, "properties")
    for k, v in (("run_id", run_id), ("origen", source), ("proyecto", project)):
        ET.SubElement(props, "property", name=k, value=str(v))
    for r in results:
        tc = ET.SubElement(ts, "testcase", classname=project, name=r["caso"], time=f"{r['duration_ms'] / 1000:.3f}")
        if r["status"] == "FAIL":
            ET.SubElement(tc, "failure", message=r["motivo"]).text = f"Esperado: {r['esperado']}\nObtenido: {r['obtenido']}\n{r['motivo']}"
        elif r["status"] == "ERROR":
            ET.SubElement(tc, "error", message=r["motivo"]).text = r.get("error") or r["motivo"]
    ET.indent(ts)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(ts, encoding="unicode") + "\n"


def markdown_report(results: List[Dict[str, Any]], meta: Dict[str, Any], exit_code: int) -> str:
    c = {s: sum(1 for r in results if r["status"] == s) for s in ("PASS", "FAIL", "ERROR")}
    veredicto = {EXIT_OK: "✅ TODAS LAS COMPROBACIONES PASARON", EXIT_FAIL: "⚠️ HAY COMPROBACIONES CON FAIL", EXIT_ERROR: "⛔ HAY COMPROBACIONES CON ERROR"}[exit_code]
    esc = lambda s: str(s).replace("|", "\\|").replace("\n", " ")  # noqa: E731
    filas = "\n".join(f"| {esc(r['caso'])} | {esc(r['esperado'])} | {esc(r['obtenido'])} | {r['status']} | {esc(r['motivo'])} |" for r in results)
    return f"""# Reporte de comprobaciones SQL

**{veredicto}** — {c['PASS']} PASS · {c['FAIL']} FAIL · {c['ERROR']} ERROR (de {len(results)})

| Dato | Valor |
| --- | --- |
| Fecha | {meta['fecha']} |
| Proyecto | {meta['proyecto']} |
| Suite | {meta['suite']} |
| Conexión | {meta['conexion']} ({meta['ambiente']}) |
| Origen | {meta['origen']} |
| Corrida | `{meta['run_id']}` |
| Código de salida | {exit_code} (0 = todo PASS · 1 = hay FAIL · 2 = hay ERROR) |

| Comprobación | Se esperaba | Se obtuvo | Estado | Por qué |
| --- | --- | --- | --- | --- |
{filas}

> Cada ejecución quedó registrada en el historial de la aplicación (origen {meta['origen']}). El reporte no contiene contraseñas.
"""


# ---------------------------------------------------------------------------------------------- comandos

def cmd_init_db(args, session_factory) -> int:
    from alembic import command
    from alembic.config import Config
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    command.upgrade(cfg, "head")
    _out("Base interna al día (alembic upgrade head).")
    return EXIT_OK


def cmd_import_excel(args, session_factory) -> int:
    from app.services import excel_io
    path = Path(args.file)
    if not path.is_file():
        raise UsageError(f"No existe el archivo {path}")
    db = session_factory()
    try:
        existe = _project_exists(db, args.project)
        if not existe and not args.create_project:
            raise UsageError(f"No existe el proyecto «{args.project}». Use --create-project para crearlo al importar.")
        try:
            if not existe and args.dry_run:
                _out(f"(simulación) el proyecto «{args.project}» se crearía al importar de verdad.")
                res = _dry_run_unknown_project(path)
            else:
                res = None
                if not existe:
                    # Proyecto nuevo: se valida el archivo ANTES de crearlo, para que un archivo rechazado no deje un proyecto vacío.
                    previa = _dry_run_unknown_project(path)
                    if not previa["ok"]:
                        previa["simulacion"] = False
                        previa["mensaje"] = f"No se importó nada: hay {len(previa['errores'])} error(es). Corrija el archivo y vuelva a intentarlo."
                        res = previa
                if res is None:
                    project = _find_project(db, args.project, create=args.create_project)
                    res = excel_io.import_cases(db, project.id, path.read_bytes(), mode=args.mode, dry_run=args.dry_run, source="CLI")
        except excel_io.ExcelError as exc:
            raise UsageError(str(exc))
    finally:
        db.close()
    if args.json:
        _out(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        _out(res["mensaje"])
        for e in res["errores"]:
            _out(f"  fila {e['fila']} · {e['campo']}: {e['mensaje']}")
        if res["ok"]:
            _out(f"  a crear: {res['n_crear']} · a actualizar: {res['n_actualizar']} · omitidos (ya existen): {res['n_omitidos']}")
    return EXIT_OK if res["ok"] else EXIT_FAIL


def _project_exists(db, name: str) -> bool:
    from app.models.project import Project
    return db.query(Project).filter(Project.name.ilike(name)).first() is not None


def _dry_run_unknown_project(path: Path) -> Dict[str, Any]:
    """Simulación para un proyecto que aún no existe: solo se valida el archivo."""
    from app.services import excel_io
    rows, errors = excel_io.parse_cases(path.read_bytes())
    return {"ok": not errors, "simulacion": True, "errores": errors, "n_crear": len(rows), "n_actualizar": 0, "n_omitidos": 0,
            "mensaje": "Validación correcta. No se guardó nada (simulación)." if not errors else
            f"No se importó nada: hay {len(errors)} error(es)."}


def cmd_export_excel(args, session_factory) -> int:
    from app.services import excel_io
    out = Path(args.out)
    if out.exists() and not args.force:
        raise UsageError(f"{out} ya existe; use --force para sobrescribirlo.")
    db = session_factory()
    try:
        project = _find_project(db, args.project)
        if args.what == "cases":
            content = excel_io.export_cases(db, project.id)
            excel_io.record_event(db, "excel_export_cases", project.id, "CLI")
        else:
            suite_id = None
            if args.suite:
                from app.models.suite import TestSuite
                s = db.query(TestSuite).filter(TestSuite.project_id == project.id, TestSuite.name.ilike(args.suite)).first()
                if not s:
                    raise UsageError(f"No existe la suite «{args.suite}».")
                suite_id = s.id
            content = excel_io.export_results(db, project.id, suite_id, args.status, args.days)
            excel_io.record_event(db, "excel_export_results", project.id, "CLI")
    finally:
        db.close()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(content)
    _out(f"Archivo generado: {out} ({len(content)} bytes)")
    return EXIT_OK


def cmd_run(args, session_factory) -> int:
    import oracledb
    from app.engine.executor import TargetDatabaseExecutor
    from app.services.execution_service import explain_execution, run_single_test_case_execution

    password = os.environ.get(args.password_env, "")
    if not password:
        raise UsageError(f"Falta la contraseña de Oracle: defina la variable de entorno {args.password_env} "
                         "(la contraseña no se acepta como argumento para que no quede en el historial del shell ni en los registros).")
    db = session_factory()
    try:
        project = _find_project(db, args.project)
        suite, cases = _select_cases(db, project, args)
        if not cases:
            _out("No hay casos que ejecutar (la suite o el proyecto no tienen casos).")
            return EXIT_NO_CASES
        profile = _resolve_profile(db, project, args)

        from app.security.target_policy import ensure_valid_target
        try:
            ensure_valid_target(profile.host, profile.service_name)
        except ValueError as exc:
            raise UsageError(str(exc))
        dsn = oracledb.makedsn(profile.host, profile.port, service_name=profile.service_name)
        executor = TargetDatabaseExecutor(dsn=dsn, user=profile.username, password=password, environment_type=profile.environment_type)

        source = "GITHUB_ACTIONS" if os.environ.get("GITHUB_ACTIONS", "").lower() == "true" else "CLI"
        run_id = str(uuid.uuid4())
        results: List[Dict[str, Any]] = []
        try:
            for tc in cases:
                details: Dict[str, Any] = {}
                rec = run_single_test_case_execution(
                    db=db, tc=tc, executor=executor, suite_id=suite.id if suite else None, connection_profile_id=profile.id,
                    confirm_staging_dml=args.confirm_staging_dml, details=details, trigger_source=source, run_id=run_id)
                rows = [] if executor.environment_type == "PRODUCTION" else list(details.get("rows", []))
                ex = explain_execution(rec.status, rec.validation_type, rec.expected_result, rec.rowcount or 0,
                                       rec.error_message, rows=rows, sql=rec.executed_sql)
                results.append({"caso": tc.name, "status": rec.status, "esperado": ex["expected_text"], "obtenido": ex["obtained_text"],
                                "motivo": ex["reason"], "duration_ms": rec.duration_ms, "history_id": rec.id, "error": rec.error_message})
                _out(f"[{rec.status:<5}] {tc.name}\n          esperado: {ex['expected_text']}\n          obtenido: {ex['obtained_text']}\n          por qué:  {ex['reason']}")
        finally:
            executor.disconnect()
        meta = {"fecha": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "proyecto": project.name,
                "suite": suite.name if suite else ("casos indicados" if args.case else "todos los casos del proyecto"),
                "conexion": profile.name, "ambiente": profile.environment_type, "origen": source, "run_id": run_id}
    finally:
        db.close()

    errors = sum(1 for r in results if r["status"] == "ERROR")
    fails = sum(1 for r in results if r["status"] == "FAIL")
    code = EXIT_ERROR if errors else (EXIT_FAIL if fails else EXIT_OK)
    _out(f"\nResumen: {len(results) - fails - errors} PASS · {fails} FAIL · {errors} ERROR — código de salida {code}")

    for opt, content_fn in ((args.junit, lambda: junit_xml(results, meta["suite"], meta["proyecto"], run_id, source)),
                            (args.markdown, lambda: markdown_report(results, meta, code)),
                            (args.json, lambda: json.dumps({"meta": meta, "codigo_salida": code, "resultados": results}, ensure_ascii=False, indent=2))):
        if opt:
            p = Path(opt)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content_fn(), encoding="utf-8")
            _out(f"Reporte escrito: {p}")
    return code


# -------------------------------------------------------------------------------------------------- main

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m app.cli", description="CLI del Framework de pruebas SQL",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--db", help="archivo SQLite de la base interna (por defecto FRAMEWORK_DB_URL o framework_interno.db)")
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="aplica las migraciones de Alembic a la base interna")

    p = sub.add_parser("import-excel", help="importa casos desde un .xlsx (con validaciones)")
    p.add_argument("file")
    p.add_argument("--project", required=True)
    p.add_argument("--create-project", action="store_true", help="crear el proyecto si no existe")
    p.add_argument("--mode", choices=["skip", "update"], default="skip")
    p.add_argument("--dry-run", action="store_true", help="solo validar; no guardar")
    p.add_argument("--json", action="store_true", help="imprimir el informe en JSON")

    p = sub.add_parser("export-excel", help="exporta casos o resultados a .xlsx")
    p.add_argument("what", choices=["cases", "results"])
    p.add_argument("--project", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--suite")
    p.add_argument("--status", choices=["PASS", "FAIL", "ERROR"])
    p.add_argument("--days", type=int)
    p.add_argument("--force", action="store_true")

    p = sub.add_parser("run", help="ejecuta casos o una suite y devuelve un código de salida")
    p.add_argument("--project", required=True)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--suite", help="nombre de la suite")
    g.add_argument("--case", action="append", help="nombre de un caso (repetible)")
    g.add_argument("--all", action="store_true", help="todos los casos del proyecto (por defecto si no se indica otra cosa)")
    p.add_argument("--profile", help="perfil de conexión guardado en el proyecto")
    p.add_argument("--host")
    p.add_argument("--port", type=int, default=1521)
    p.add_argument("--service")
    p.add_argument("--user")
    p.add_argument("--env", choices=["TEST", "STAGING", "PRODUCTION"], default="TEST")
    p.add_argument("--password-env", default="FW_ORACLE_PASSWORD", help="variable de entorno con la contraseña (nunca como argumento)")
    p.add_argument("--confirm-staging-dml", action="store_true")
    p.add_argument("--junit")
    p.add_argument("--markdown")
    p.add_argument("--json")
    return ap


COMMANDS: Dict[str, Callable] = {"init-db": cmd_init_db, "import-excel": cmd_import_excel, "export-excel": cmd_export_excel, "run": cmd_run}


def main(argv: Optional[List[str]] = None, session_factory=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:                      # argparse ya imprimió el error
        return EXIT_OK if exc.code in (0, None) else EXIT_USAGE
    if args.db:
        os.environ["FRAMEWORK_DB_URL"] = f"sqlite:///{Path(args.db).resolve().as_posix()}"
    if session_factory is None:
        from app.core.database import SessionLocal            # se importa después de fijar FRAMEWORK_DB_URL
        session_factory = SessionLocal
    # Registra TODOS los modelos antes de la primera consulta: sus relaciones se resuelven por nombre y, si falta alguno
    # (p. ej. al consultar solo Project), SQLAlchemy no puede configurar los mapeos.
    from app.models import project, connection, test_case, suite, history, usage  # noqa: F401
    try:
        return COMMANDS[args.command](args, session_factory)
    except UsageError as exc:
        print(f"ERROR de uso: {exc}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
