"""
Router de Ejecución de Pruebas SQL desacoplado utilizando el Servicio Centralizado de Ejecución.

Todas las rutas de ejecución exigen un perfil de conexión GUARDADO (`connection_profile_id`).
Ya no se acepta un `dsn` ni un `user` libres enviados por el cliente: el destino lo definen los
perfiles (campos validados) y, opcionalmente, la lista `ORACLE_ALLOWED_HOSTS`.
"""
import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import schemas
from app.models import test_case as models_tc
from app.models import suite as models_suite
from app.models import connection as models_conn
from app.engine.executor import TargetDatabaseExecutor
from app.security.sql_policy import validate_sql_statement
from app.services.execution_service import (
    resolve_connection_credentials,
    run_single_test_case_execution,
    explain_execution,
    serialize_cell,
    describe_scalar
)
from app.models.user import User
from app.security.acceso import nombre_de, usuario_actual
from app.services import comparacion

router = APIRouter()

QUICK_MAX_ROWS_SHOWN = 20


def _environment_of(profile) -> str:
    return getattr(profile.environment_type, "value", profile.environment_type)


@router.post("/execute/raw", response_model=schemas.ExecutionResponse)
def execute_target_sql(request: schemas.ExecutionRequest, db: Session = Depends(get_db)):
    """Ejecuta una sentencia SQL aislada, sobre un perfil guardado, aplicando las políticas del ambiente."""
    try:
        dsn, user, password, profile = resolve_connection_credentials(
            db,
            connection_profile_id=request.connection_profile_id,
            password=request.password
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # El ambiente siempre sale del perfil guardado, nunca de la petición.
    env_type = _environment_of(profile)
    try:
        executor = TargetDatabaseExecutor(dsn=dsn, user=user, password=password, environment_type=env_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        res = executor.execute_query(request.sql_query, confirm_staging_dml=request.confirm_staging_dml)
        if not res["success"]:
            detail_msg = res.get("message") or res.get("error_message") or "Error en ejecución SQL."
            if executor.environment_type == "PRODUCTION" and "Rechazado" not in detail_msg:
                detail_msg = "Error oculto por políticas de seguridad (PRODUCTION)."
            raise HTTPException(status_code=400, detail=detail_msg)
        return schemas.ExecutionResponse(
            success=res["success"],
            statement_type=res["statement_type"],
            rows=res["rows"],
            rowcount=res["rowcount"],
            data=res["rows"],
            message=res["message"],
            error_message=res.get("error_message"),
            rollback_applied=res.get("rollback_applied", False),
            rollback_error=res.get("rollback_error")
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Error interno no controlado durante la ejecución SQL.")
    finally:
        executor.disconnect()


@router.post("/execute/quick", response_model=schemas.QuickExecutionResponse)
def run_quick_check(request: schemas.QuickExecutionRequest, db: Session = Depends(get_db),
                    usuario: Optional[User] = Depends(usuario_actual)):
    """
    Prueba rápida del recorrido guiado: ejecuta UN SELECT contra un perfil de
    conexión guardado, lo compara con lo que el usuario indicó y registra la
    evidencia en el historial. Reutiliza la política SQL y el servicio de
    ejecución existentes. No acepta dsn/host libres.
    """
    profile = db.query(models_conn.ConnectionProfile).filter(
        models_conn.ConnectionProfile.id == request.connection_profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil de conexión no encontrado.")

    env_type = _environment_of(profile)

    # El recorrido rápido es solo de lectura: el DML sigue disponible desde Casos de prueba.
    is_valid, stmt_type, _ = validate_sql_statement(request.sql_query, env_type)
    if is_valid and stmt_type != "SELECT":
        raise HTTPException(
            status_code=422,
            detail="La prueba rápida solo admite consultas SELECT. Para INSERT, UPDATE o DELETE cree un caso de prueba."
        )

    try:
        dsn, user, password, _ = resolve_connection_credentials(
            db, connection_profile_id=profile.id, password=request.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        executor = TargetDatabaseExecutor(dsn=dsn, user=user, password=password, environment_type=env_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Caso transitorio: no se guarda en test_cases (test_case_id queda en NULL en el historial).
    transient_case = models_tc.TestCase(
        project_id=profile.project_id,
        name="Prueba rápida",
        sql_query=request.sql_query,
        expected_result=request.expected_result,
        validation_type=request.validation_type.value,
    )
    details: dict = {}
    try:
        record = run_single_test_case_execution(
            db=db, tc=transient_case, executor=executor, suite_id=None,
            connection_profile_id=profile.id, confirm_staging_dml=False, details=details,
            trigger_source="INICIO", run_id=str(uuid.uuid4()), executed_by=nombre_de(usuario))
    finally:
        executor.disconnect()

    rows_hidden = executor.environment_type == "PRODUCTION"
    raw_rows = [] if rows_hidden else list(details.get("rows", []))

    explanation = explain_execution(
        status=record.status, validation_type=record.validation_type,
        expected_result=record.expected_result, rowcount=record.rowcount or 0,
        error_message=record.error_message, rows=raw_rows, sql=record.executed_sql)

    shown = raw_rows[:QUICK_MAX_ROWS_SHOWN]
    _, obtained_value = describe_scalar(raw_rows)

    return schemas.QuickExecutionResponse(
        history_id=record.id,
        status=record.status,
        environment_type=executor.environment_type,
        connection_name=profile.name,
        sql_query=record.executed_sql,
        validation_type=record.validation_type,
        expected_result=record.expected_result,
        expected_text=explanation["expected_text"],
        obtained_text=explanation["obtained_text"],
        reason=explanation["reason"],
        validation_auto=request.motivo_validacion_automatica is not None,
        validation_reason=request.motivo_validacion_automatica,
        obtained_value=obtained_value if (record.status != "ERROR" and not rows_hidden) else None,
        columns=[] if rows_hidden else list(details.get("columns", [])),
        rows=[[serialize_cell(c) for c in row] for row in shown],
        rows_shown=len(shown),
        rows_truncated=len(raw_rows) > len(shown),
        rows_hidden=rows_hidden,
        rowcount=record.rowcount or 0,
        duration_ms=record.duration_ms,
        error_message=record.error_message,
    )


@router.post("/execute/test-case/{test_case_id}", response_model=schemas.HistoryResponse)
def run_test_case(test_case_id: int, db_credentials: schemas.TestCaseExecutionRequest, db: Session = Depends(get_db),
                  usuario: Optional[User] = Depends(usuario_actual)):
    """
    Orquestador Principal: Recupera un caso de prueba guardado y lo ejecuta
    utilizando el servicio centralizado de ejecución.
    """
    tc = db.query(models_tc.TestCase).filter(models_tc.TestCase.id == test_case_id).first()
    if not tc:
        raise HTTPException(status_code=404, detail="Caso de prueba no encontrado.")

    profile = db.query(models_conn.ConnectionProfile).filter(models_conn.ConnectionProfile.id == db_credentials.connection_profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil de conexión no encontrado.")
    if profile.project_id != tc.project_id:
        raise HTTPException(status_code=409, detail="El perfil de conexión no pertenece al proyecto del caso de prueba.")

    try:
        dsn, user, password, profile = resolve_connection_credentials(
            db,
            connection_profile_id=db_credentials.connection_profile_id,
            password=db_credentials.password
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    profile_id = profile.id if profile else db_credentials.connection_profile_id
    env_type = _environment_of(profile)
    try:
        executor = TargetDatabaseExecutor(dsn=dsn, user=user, password=password, environment_type=env_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        history_record = run_single_test_case_execution(
            db=db,
            tc=tc,
            executor=executor,
            suite_id=None,
            connection_profile_id=profile_id,
            confirm_staging_dml=db_credentials.confirm_staging_dml,
            trigger_source="UI",
            run_id=str(uuid.uuid4()),
            executed_by=nombre_de(usuario)
        )
        return history_record
    finally:
        executor.disconnect()


@router.post("/execute/suite/{suite_id}", response_model=schemas.SuiteExecutionSummary)
def run_test_suite(suite_id: int, db_credentials: schemas.SuiteExecutionRequest, db: Session = Depends(get_db),
                   usuario: Optional[User] = Depends(usuario_actual)):
    """
    Ejecuta en ráfaga todos los casos de prueba de una Suite utilizando una conexión única.
    Además del detalle de historial, devuelve `case_results` con una explicación legible por caso.
    """
    suite = db.query(models_suite.TestSuite).filter(models_suite.TestSuite.id == suite_id).first()
    if not suite:
        raise HTTPException(status_code=404, detail="Suite no encontrada.")

    profile = db.query(models_conn.ConnectionProfile).filter(models_conn.ConnectionProfile.id == db_credentials.connection_profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil de conexión no encontrado.")
    if profile.project_id != suite.project_id:
        raise HTTPException(status_code=409, detail="El perfil de conexión no pertenece al proyecto de la suite.")

    # Verificación de integridad: todos los casos de la suite deben pertenecer al mismo proyecto
    for tc in suite.test_cases:
        if tc.project_id != suite.project_id:
            raise HTTPException(status_code=409, detail=f"Inconsistencia: el caso de prueba {tc.id} no pertenece al proyecto {suite.project_id}.")

    summary = schemas.SuiteExecutionSummary(
        suite_id=suite.id,
        suite_name=suite.name,
        total_tests=len(suite.test_cases),
        passed=0, failed=0, errors=0, total_duration_ms=0.0, run_id=str(uuid.uuid4())
    )

    if summary.total_tests == 0:
        return summary

    try:
        dsn, user, password, profile = resolve_connection_credentials(
            db,
            connection_profile_id=db_credentials.connection_profile_id,
            password=db_credentials.password
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    profile_id = profile.id if profile else db_credentials.connection_profile_id
    env_type = _environment_of(profile)
    try:
        executor = TargetDatabaseExecutor(dsn=dsn, user=user, password=password, environment_type=env_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        for tc in suite.test_cases:
            case_details: dict = {}
            history_record = run_single_test_case_execution(
                db=db,
                tc=tc,
                executor=executor,
                suite_id=suite.id,
                connection_profile_id=profile_id,
                confirm_staging_dml=db_credentials.confirm_staging_dml,
                details=case_details,
                trigger_source="UI",
                run_id=summary.run_id,
                executed_by=nombre_de(usuario)
            )

            summary.total_duration_ms += history_record.duration_ms
            if history_record.status == "PASS":
                summary.passed += 1
            elif history_record.status == "FAIL":
                summary.failed += 1
            else:
                summary.errors += 1

            # model_validate: si se agrega el objeto ORM tal cual, la respuesta serializa cada detalle como {} (defecto previo)
            summary.details.append(schemas.HistoryResponse.model_validate(history_record))

            explanation = explain_execution(
                status=history_record.status, validation_type=history_record.validation_type,
                expected_result=history_record.expected_result, rowcount=history_record.rowcount or 0,
                error_message=history_record.error_message,
                rows=[] if executor.environment_type == "PRODUCTION" else list(case_details.get("rows", [])),
                sql=history_record.executed_sql)
            previo = comparacion.anterior(db, tc.id, history_record.id)
            cambio = comparacion.clasificar(previo.status if previo else None, history_record.status)
            summary.new_failures += cambio == "nuevo_fallo"
            summary.fixed += cambio == "corregido"
            summary.case_results.append(schemas.SuiteCaseResult(
                history_id=history_record.id,
                test_case_id=tc.id,
                case_name=tc.name,
                status=history_record.status,
                validation_type=history_record.validation_type,
                expected_result=history_record.expected_result,
                expected_text=explanation["expected_text"],
                obtained_text=explanation["obtained_text"],
                reason=explanation["reason"],
                duration_ms=history_record.duration_ms,
                error_message=history_record.error_message,
                previous_status=previo.status if previo else None,
                previous_executed_at=previo.executed_at if previo else None,
                change=cambio,
                change_text=comparacion.CAMBIOS[cambio],
            ))

    finally:
        executor.disconnect()

    summary.total_duration_ms = round(summary.total_duration_ms, 2)
    return summary
