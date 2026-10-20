"""
Servicio centralizado de ejecución y validación de pruebas SQL.
Garantiza que la ejecución individual y la de suites compartan la misma lógica de orquestación y trazabilidad.
"""
import re
import time
import json
from decimal import Decimal
from datetime import datetime, date
from typing import Any, Dict, Optional, Tuple
from sqlalchemy.orm import Session
import oracledb

from app.engine.executor import TargetDatabaseExecutor
from app.engine.validator import (
    ValidationContext, RowCountValidation, ExistenceValidation, ScalarValueValidation, format_scalar
)
from app.security.target_policy import ensure_valid_target
from app.models import test_case as models_tc
from app.models import history as models_history
from app.models import connection as models_conn


def json_serial_helper(obj: Any) -> Any:
    """Helper para convertir objetos no JSON nativos habituales en Oracle."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, bytes):
        return obj.decode('utf-8', errors='replace')
    return str(obj)


def format_actual_result(rows: Any, max_chars: int = 2000) -> str:
    """Serializa y limita el tamaño del resultado real devuelto como evidencia."""
    try:
        serialized = json.dumps(rows, default=json_serial_helper, ensure_ascii=False)
        if len(serialized) > max_chars:
            return serialized[:max_chars] + " ... [TRUNCADO]"
        return serialized
    except Exception as e:
        return f"[Error serializando resultado: {str(e)}]"


def resolve_connection_credentials(
    db: Session,
    connection_profile_id: Optional[int] = None,
    password: Optional[str] = None
) -> Tuple[str, str, str, models_conn.ConnectionProfile]:
    """
    Resuelve el DSN, el usuario y el perfil a partir de un connection_profile_id GUARDADO.
    No existe una vía para conectarse a un destino libre enviado por el cliente: el host debe
    estar permitido por `ORACLE_ALLOWED_HOSTS` (si la variable está definida).
    """
    if not password:
        raise ValueError("Se requiere una contraseña para ejecutar la prueba.")
    if not connection_profile_id:
        raise ValueError("Debe indicar un connection_profile_id (perfil de conexión guardado).")

    profile = db.query(models_conn.ConnectionProfile).filter(models_conn.ConnectionProfile.id == connection_profile_id).first()
    if not profile:
        raise ValueError(f"Perfil de conexión ID {connection_profile_id} no encontrado.")
    ensure_valid_target(profile.host, profile.service_name)
    resolved_dsn = oracledb.makedsn(profile.host, profile.port, service_name=profile.service_name)
    return resolved_dsn, profile.username, password, profile


def run_single_test_case_execution(
    db: Session,
    tc: models_tc.TestCase,
    executor: TargetDatabaseExecutor,
    suite_id: Optional[int] = None,
    connection_profile_id: Optional[int] = None,
    confirm_staging_dml: bool = False,
    details: Optional[Dict[str, Any]] = None,
    trigger_source: Optional[str] = None,
    run_id: Optional[str] = None
) -> models_history.ExecutionHistory:
    """
    Servicio central que ejecuta un caso de prueba contra la BD objetivo,
    evalúa el resultado según la estrategia elegida y persiste la evidencia.

    Si se pasa `details` (diccionario), se rellena con `rows` y `columns` del
    SELECT ejecutado para que la interfaz pueda mostrarlos; no se persisten.
    """
    start_time = time.time()
    status = "ERROR"
    error_msg = None

    val_type_requested = (tc.validation_type or "ROW_COUNT").upper()
    is_production = getattr(executor, 'environment_type', 'TEST') == "PRODUCTION"

    # 1. Ejecución del SQL contra la BD objetivo
    if val_type_requested == "SCALAR_VALUE" and is_production:
        # En PRODUCTION las filas se ocultan; comparar un valor obligaría a leerlas. No se ejecuta nada.
        res = {
            "success": False, "statement_type": "SELECT", "rows": [], "rowcount": 0,
            "message": "Rechazado por seguridad: la validación por valor no está disponible en PRODUCTION (las filas se ocultan). Use cantidad de filas o existencia.",
            "error_message": "Rechazado por seguridad: la validación por valor no está disponible en PRODUCTION (las filas se ocultan). Use cantidad de filas o existencia.",
            "rollback_applied": False, "rollback_error": None
        }
    else:
        res = executor.execute_query(tc.sql_query, confirm_staging_dml=confirm_staging_dml)
    duration_ms = round((time.time() - start_time) * 1000, 2)

    stmt_type = res.get("statement_type", "UNKNOWN")
    rowcount = res.get("rowcount", 0)
    rows = res.get("rows", [])
    rollback_applied = res.get("rollback_applied", False)
    rollback_error = res.get("rollback_error")

    if details is not None:
        details["rows"] = rows
        details["columns"] = res.get("columns", [])

    if getattr(executor, 'environment_type', 'TEST') == "PRODUCTION":
        actual_result_str = format_actual_result(f"Operación exitosa. {rowcount} filas leídas.") if stmt_type == "SELECT" else format_actual_result(f"Filas afectadas: {rowcount}")
    else:
        actual_result_str = format_actual_result(rows if stmt_type == "SELECT" else f"Filas afectadas: {rowcount}")

    if val_type_requested == "SCALAR_VALUE" and not is_production and res.get("success", False) and stmt_type == "SELECT":
        actual_result_str = format_actual_result(f"valor: {describe_scalar(rows)[1]}")

    # 2. Evaluación del resultado
    if not res.get("success", False):
        status = "ERROR"
        err = res.get("error_message") or res.get("message")
        if getattr(executor, 'environment_type', 'TEST') == "PRODUCTION" and err and "Rechazado" not in err:
            err = "Error oculto por políticas de seguridad (PRODUCTION)."
        error_msg = err
    elif stmt_type in {"INSERT", "UPDATE", "DELETE"} and not rollback_applied:
        # Falso rollback en DML produce ERROR
        status = "ERROR"
        error_msg = res.get("error_message") or "El rollback transaccional falló o no fue verificado."
    else:
        # Selección de estrategia
        val_type = (tc.validation_type or "ROW_COUNT").upper()
        if val_type == "EXISTS":
            strategy = ExistenceValidation()
        elif val_type == "SCALAR_VALUE":
            strategy = ScalarValueValidation()
        else:
            strategy = RowCountValidation()

        validator = ValidationContext(strategy)
        is_valid = validator.execute_validation(res, tc.expected_result)
        status = "PASS" if is_valid else "FAIL"

    # Sanitización defensiva extra en el nivel de servicio para persistencia
    env_type = getattr(executor, 'environment_type', 'TEST')
    if env_type == "PRODUCTION":
        if error_msg and "Rechazado" not in error_msg:
            error_msg = "Error oculto por políticas de seguridad (PRODUCTION)."
        if rollback_error:
            rollback_error = "Error de rollback oculto por políticas de seguridad (PRODUCTION)."

    # 3. Persistir evidencia en ExecutionHistory
    history_record = models_history.ExecutionHistory(
        project_id=tc.project_id,
        test_case_id=tc.id,
        suite_id=suite_id,
        connection_profile_id=connection_profile_id,
        status=status,
        duration_ms=duration_ms,
        statement_type=stmt_type,
        executed_sql=tc.sql_query,
        validation_type=tc.validation_type,
        expected_result=tc.expected_result,
        actual_result=actual_result_str,
        rowcount=rowcount,
        rollback_applied=rollback_applied,
        rollback_error=rollback_error,
        error_message=error_msg,
        trigger_source=trigger_source,
        run_id=run_id
    )

    db.add(history_record)
    db.commit()
    db.refresh(history_record)

    return history_record


def _plural_filas(n: int) -> str:
    return f"{n} fila" if n == 1 else f"{n} filas"


def describe_scalar(rows: Any) -> Tuple[str, str]:
    """
    Resume lo que devolvió un SELECT para la validación por valor.
    Devuelve (tipo, texto): tipo = 'sin_filas' | 'varias_filas' | 'valor'.
    """
    rows = rows or []
    if len(rows) == 0:
        return "sin_filas", "sin filas"
    if len(rows) > 1:
        return "varias_filas", f"{len(rows)} filas"
    first = rows[0]
    if not first:
        return "sin_filas", "sin columnas"
    return "valor", format_scalar(first[0])


def explain_execution(
    status: str,
    validation_type: str,
    expected_result: str,
    rowcount: int,
    error_message: Optional[str] = None,
    rows: Optional[list] = None,
    sql: Optional[str] = None
) -> Dict[str, str]:
    """
    Redacta en lenguaje natural qué se esperaba, qué se obtuvo y por qué el
    resultado fue PASS, FAIL o ERROR. Distingue tres comprobaciones:
      - ROW_COUNT: cuántas FILAS devuelve la consulta.
      - SCALAR_VALUE: el VALOR de la primera columna de la única fila (p. ej. un COUNT(*)).
      - EXISTS: si devuelve al menos una fila o ninguna.
    Es texto de apoyo; la evidencia técnica sigue en el historial.
    """
    val_type = (validation_type or "ROW_COUNT").upper()
    expected = str(expected_result).strip()

    if val_type == "EXISTS":
        wants_rows = expected.lower() == "true"
        expected_text = ("Que la consulta devuelva al menos una fila" if wants_rows
                         else "Que la consulta no devuelva ninguna fila")
    elif val_type == "SCALAR_VALUE":
        expected_text = f"Que el valor que devuelve la consulta sea {expected}"
    else:
        count_text = _plural_filas(int(expected)) if expected.isdigit() else expected
        expected_text = f"Que la consulta devuelva exactamente {count_text} (cantidad de filas)"

    if status == "ERROR":
        rejected = bool(error_message) and (
            error_message.startswith("Rechazado") or error_message.startswith("Tipo de sentencia")
        )
        if rejected:
            reason = ("La consulta fue rechazada por una regla de seguridad antes de llegar a Oracle, "
                      "así que no se pudo comparar con lo esperado.")
        else:
            reason = ("La consulta no pudo completarse (por ejemplo: SQL inválido, tabla inexistente, "
                      "contraseña incorrecta o conexión no disponible). No es un fallo de los datos: "
                      "no hubo resultado que comparar.")
        return {"expected_text": expected_text, "obtained_text": "No se obtuvo resultado", "reason": reason}

    if val_type == "SCALAR_VALUE":
        kind, text = describe_scalar(rows)
        if kind == "valor":
            obtained_text = f"La consulta devolvió el valor {text}"
            if status == "PASS":
                reason = f"Coincide: esperabas el valor {expected} y la consulta devolvió {text}."
            else:
                reason = (f"La consulta se ejecutó bien, pero el valor no coincide: esperabas {expected} y devolvió {text}. "
                          "Revisa si los datos cambiaron o si el valor esperado es correcto.")
        elif kind == "sin_filas":
            obtained_text = "La consulta no devolvió ninguna fila, así que no hay un valor que comparar"
            reason = "La validación por valor necesita exactamente una fila y la consulta no devolvió ninguna. Revisa la consulta."
        else:
            obtained_text = f"La consulta devolvió {text}; se necesita una sola fila con el valor"
            reason = ("La validación por valor compara una única fila y la consulta devolvió varias. "
                      "Use un agregado (por ejemplo COUNT(*)) o filtre hasta obtener una fila.")
        return {"expected_text": expected_text, "obtained_text": obtained_text, "reason": reason}

    obtained_text = f"La consulta devolvió {_plural_filas(rowcount)}"
    if val_type == "EXISTS":
        has_rows = rowcount > 0
        if status == "PASS":
            reason = "Coincide: " + ("la consulta devolvió filas, como esperabas." if has_rows
                                     else "la consulta no devolvió filas, como esperabas.")
        else:
            detail = ("esperabas filas y no devolvió ninguna." if not has_rows
                      else "esperabas que no hubiera filas y devolvió " + _plural_filas(rowcount) + ".")
            reason = ("La consulta se ejecutó bien, pero el resultado no coincide: " + detail +
                      " Revisa si los datos cambiaron o si lo esperado está bien definido.")
    else:
        if status == "PASS":
            reason = f"Coincide: esperabas {_plural_filas(int(expected))} y la consulta devolvió {_plural_filas(rowcount)}."
        else:
            reason = (f"La consulta se ejecutó bien, pero el resultado no coincide: esperabas {expected} "
                      f"y devolvió {rowcount}. Revisa si los datos cambiaron o si el valor esperado es correcto.")
        if sql and re.search(r"\bCOUNT\s*\(", sql, re.IGNORECASE):
            reason += (" Nota: la consulta usa COUNT(...), que siempre devuelve una fila; esto comprobó cuántas filas "
                       "devuelve la consulta, no el número que calcula. Para comparar ese número use «Valor que devuelve la consulta».")
    return {"expected_text": expected_text, "obtained_text": obtained_text, "reason": reason}


def serialize_cell(value: Any) -> Any:
    """Convierte un valor de celda Oracle a algo mostrable en JSON."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return json_serial_helper(value)
