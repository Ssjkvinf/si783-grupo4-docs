from app.security.target_policy import HOST_RE, SERVICE_RE
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator, model_validator
from typing import Optional, Any, List
from datetime import datetime
from enum import Enum
from app.services.validacion_auto import inferir_validacion


class ValidationTypeEnum(str, Enum):
    ROW_COUNT = "ROW_COUNT"          # cantidad de FILAS que devuelve la consulta
    EXISTS = "EXISTS"                # la consulta devuelve al menos una fila (true) o ninguna (false)
    SCALAR_VALUE = "SCALAR_VALUE"    # VALOR de la primera columna de la única fila (p. ej. un COUNT(*))

class EnvironmentTypeEnum(str, Enum):
    TEST = "TEST"
    STAGING = "STAGING"
    PRODUCTION = "PRODUCTION"


# --- ESQUEMAS DE PROYECTOS ---

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El nombre del proyecto no puede estar vacío ni contener solo espacios.")
        return v

class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("El nombre del proyecto no puede estar vacío.")
        return v

class ProjectResponse(ProjectCreate):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- ESQUEMAS DE PERFILES DE CONEXIÓN ---

# host y service_name se usan para construir el descriptor de conexión de Oracle:
# solo se admiten caracteres de nombre de host / servicio (sin paréntesis, '=', espacios, '/', '@', ...).
_HOST_RE = HOST_RE
_SERVICE_RE = SERVICE_RE


def _check_host(v: str) -> str:
    if not _HOST_RE.match(v):
        raise ValueError("El host solo puede contener letras, números, puntos, guiones y guiones bajos.")
    return v


def _check_service(v: str) -> str:
    if not _SERVICE_RE.match(v):
        raise ValueError("El service name solo puede contener letras, números, puntos, guiones y guiones bajos.")
    return v


class ConnectionProfileCreate(BaseModel):
    project_id: int
    name: str = Field(..., min_length=1, max_length=100)
    engine: str = Field("ORACLE", min_length=1, max_length=20)
    host: str = Field(..., min_length=1, max_length=255)
    port: int = Field(1521, ge=1, le=65535)
    service_name: str = Field(..., min_length=1, max_length=100)
    username: str = Field(..., min_length=1, max_length=100)
    environment_type: EnvironmentTypeEnum = EnvironmentTypeEnum.TEST

    @field_validator('name', 'host', 'service_name', 'username')
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El campo no puede estar vacío ni contener solo espacios.")
        return v

    @field_validator('host')
    @classmethod
    def validate_host(cls, v: str) -> str:
        return _check_host(v)

    @field_validator('service_name')
    @classmethod
    def validate_service(cls, v: str) -> str:
        return _check_service(v)

    @field_validator('engine')
    @classmethod
    def validate_engine(cls, v: str) -> str:
        v = v.strip().upper()
        if v != 'ORACLE':
            raise ValueError("El único motor soportado es ORACLE.")
        return v

class ConnectionProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    host: Optional[str] = Field(None, min_length=1, max_length=255)
    port: Optional[int] = Field(None, ge=1, le=65535)
    service_name: Optional[str] = Field(None, min_length=1, max_length=100)
    username: Optional[str] = Field(None, min_length=1, max_length=100)
    environment_type: Optional[EnvironmentTypeEnum] = None

    @field_validator('name', 'host', 'service_name', 'username')
    @classmethod
    def validate_non_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("El campo no puede estar vacío ni contener solo espacios.")
        return v

    @field_validator('host')
    @classmethod
    def validate_host(cls, v: Optional[str]) -> Optional[str]:
        return _check_host(v) if v is not None else v

    @field_validator('service_name')
    @classmethod
    def validate_service(cls, v: Optional[str]) -> Optional[str]:
        return _check_service(v) if v is not None else v

class ConnectionProfileResponse(BaseModel):
    id: int
    project_id: int
    name: str
    engine: str
    host: str
    port: int
    service_name: str
    username: str
    environment_type: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class TestConnectionRequest(BaseModel):
    password: str = Field(..., min_length=1)


# --- ESQUEMAS DE CASOS DE PRUEBA ---

def normalize_expected_result(value: str, validation_type: Any) -> str:
    """Valida y normaliza el resultado esperado según el tipo de validación."""
    val_type_str = str(getattr(validation_type, 'value', validation_type)).upper()
    clean_v = value.strip()

    if val_type_str == "ROW_COUNT":
        try:
            val = int(clean_v)
            if val < 0:
                raise ValueError("Para ROW_COUNT el resultado esperado debe ser un número entero mayor o igual a 0.")
        except ValueError:
            raise ValueError("Para ROW_COUNT el resultado esperado debe ser un número entero válido (>= 0).")
    elif val_type_str == "EXISTS":
        if clean_v.upper() not in {"TRUE", "FALSE"}:
            raise ValueError("Para EXISTS el resultado esperado debe ser 'true' o 'false'.")
        clean_v = clean_v.lower()
    elif val_type_str == "SCALAR_VALUE":
        if not clean_v or len(clean_v) > 100:
            raise ValueError("Para SCALAR_VALUE indique el valor esperado (hasta 100 caracteres; use NULL para un valor nulo).")
    return clean_v


class TestCaseCreate(BaseModel):
    project_id: Optional[int] = 1
    name: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = Field(None, max_length=500)
    sql_query: str = Field(..., min_length=1)
    validation_type: Optional[ValidationTypeEnum] = None     # sin valor o "AUTO": la aplicación lo decide (validacion_auto.py)
    expected_result: str = Field(..., min_length=1)

    @model_validator(mode='before')
    @classmethod
    def validacion_automatica(cls, data: Any) -> Any:
        if isinstance(data, dict) and str(data.get('validation_type') or 'AUTO').upper() == 'AUTO':
            sql, esperado = data.get('sql_query'), data.get('expected_result')
            if isinstance(sql, str) and isinstance(esperado, str) and esperado.strip():
                tipo, normalizado, _ = inferir_validacion(sql, esperado)
                data = {**data, 'validation_type': tipo, 'expected_result': normalizado}
        return data

    @field_validator('name', 'sql_query', 'expected_result')
    @classmethod
    def validate_text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El campo no puede estar vacío ni contener solo espacios.")
        return v

    @field_validator('expected_result')
    @classmethod
    def validate_expected(cls, v: str, info) -> str:
        raw_val_type = info.data.get('validation_type', ValidationTypeEnum.ROW_COUNT)
        return normalize_expected_result(v, raw_val_type)


class TestCaseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    description: Optional[str] = Field(None, max_length=500)
    sql_query: Optional[str] = Field(None, min_length=1)
    validation_type: Optional[ValidationTypeEnum] = None
    expected_result: Optional[str] = Field(None, min_length=1)

    @model_validator(mode='before')
    @classmethod
    def validacion_automatica(cls, data: Any) -> Any:
        # Al editar, «AUTO» solo se puede resolver si llegan la consulta y el esperado.
        if isinstance(data, dict) and str(data.get('validation_type') or '').upper() == 'AUTO':
            sql, esperado = data.get('sql_query'), data.get('expected_result')
            if isinstance(sql, str) and isinstance(esperado, str) and esperado.strip():
                tipo, normalizado, _ = inferir_validacion(sql, esperado)
                data = {**data, 'validation_type': tipo, 'expected_result': normalizado}
            else:
                data = {**data, 'validation_type': None}
        return data

    @field_validator('name', 'sql_query')
    @classmethod
    def validate_text(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("El campo no puede estar vacío ni contener solo espacios.")
        return v

class TestCaseResponse(TestCaseCreate):
    id: int
    project_id: int
    model_config = ConfigDict(from_attributes=True)


# --- ESQUEMAS DE SUITES DE PRUEBAS ---

class TestSuiteCreate(BaseModel):
    project_id: Optional[int] = 1
    name: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = Field(None, max_length=500)

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El nombre de la suite no puede estar vacío.")
        return v

class TestSuiteUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    description: Optional[str] = Field(None, max_length=500)

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("El nombre de la suite no puede estar vacío.")
        return v

class TestSuiteResponse(TestSuiteCreate):
    id: int
    project_id: int
    test_cases: List[TestCaseResponse] = []
    model_config = ConfigDict(from_attributes=True)


# --- ESQUEMAS DEL MOTOR DE EJECUCIÓN ---

class DBCredentials(BaseModel):
    """
    Credenciales de ejecución. Solo se admite un perfil de conexión GUARDADO: no hay campos
    `dsn`/`user`/`host` y cualquier campo desconocido se rechaza (422). `environment_type` se
    acepta por compatibilidad pero se ignora: el ambiente siempre sale del perfil.
    """
    model_config = ConfigDict(extra="forbid")

    password: str
    connection_profile_id: int
    environment_type: Optional[EnvironmentTypeEnum] = None
    confirm_staging_dml: bool = False

class ExecutionRequest(DBCredentials):
    sql_query: str

class TestCaseExecutionRequest(DBCredentials):
    pass

class SuiteExecutionRequest(DBCredentials):
    pass

class ExecutionResponse(BaseModel):
    success: bool
    statement_type: str = "UNKNOWN"
    rows: List[Any] = []
    rowcount: int = 0
    data: List[Any] = []
    message: str
    error_message: Optional[str] = None
    rollback_applied: bool = False
    rollback_error: Optional[str] = None


class QuickExecutionRequest(BaseModel):
    """
    Prueba rápida: SOLO admite un perfil de conexión guardado. No existe
    ningún campo `dsn`/`user`/`host`: el servidor nunca se conecta a un
    destino elegido libremente por el navegador.
    """
    model_config = ConfigDict(extra="forbid")

    connection_profile_id: int
    password: str = Field(..., min_length=1)
    sql_query: str = Field(..., min_length=1)
    validation_type: Optional[ValidationTypeEnum] = None     # sin valor o "AUTO": la aplicación lo decide (validacion_auto.py)
    expected_result: str = Field(..., min_length=1)
    _motivo_auto: Optional[str] = PrivateAttr(default=None)

    @model_validator(mode='before')
    @classmethod
    def aceptar_auto(cls, data: Any) -> Any:
        if isinstance(data, dict) and str(data.get('validation_type') or '').upper() == 'AUTO':
            data = {**data, 'validation_type': None}
        return data

    @field_validator('sql_query', 'expected_result')
    @classmethod
    def validate_text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El campo no puede estar vacío ni contener solo espacios.")
        return v

    @model_validator(mode='after')
    def validate_expected_for_type(self):
        if self.validation_type is None:
            tipo, self.expected_result, self._motivo_auto = inferir_validacion(self.sql_query, self.expected_result)
            self.validation_type = ValidationTypeEnum(tipo)
        self.expected_result = normalize_expected_result(self.expected_result, self.validation_type)
        return self

    @property
    def motivo_validacion_automatica(self) -> Optional[str]:
        """Explicación de por qué se eligió el tipo de validación (None si la persona lo eligió a mano)."""
        return self._motivo_auto

class QuickExecutionResponse(BaseModel):
    history_id: int
    status: str
    environment_type: str
    connection_name: str
    sql_query: str
    validation_type: str
    expected_result: str
    expected_text: str
    obtained_text: str
    reason: str
    validation_auto: bool = False                 # True si la aplicación eligió el tipo de comparación
    validation_reason: Optional[str] = None       # por qué lo eligió
    columns: List[str] = []
    obtained_value: Optional[str] = None
    rows: List[List[Any]] = []
    rows_shown: int = 0
    rows_truncated: bool = False
    rows_hidden: bool = False
    rowcount: int = 0
    duration_ms: float = 0.0
    error_message: Optional[str] = None


# --- ESQUEMAS DEL HISTORIAL DE EJECUCIONES ---

class HistoryResponse(BaseModel):
    id: int
    project_id: int
    test_case_id: Optional[int] = None
    suite_id: Optional[int] = None
    connection_profile_id: Optional[int] = None
    status: str
    executed_at: datetime
    duration_ms: float
    statement_type: Optional[str] = None
    executed_sql: str
    validation_type: Optional[str] = None
    expected_result: Optional[str] = None
    actual_result: Optional[str] = None
    rowcount: int = 0
    rollback_applied: bool = False
    rollback_error: Optional[str] = None
    error_message: Optional[str] = None
    trigger_source: Optional[str] = None
    run_id: Optional[str] = None
    executed_by: Optional[str] = None
    case_name: Optional[str] = None
    suite_name: Optional[str] = None
    connection_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class SuiteCaseResult(BaseModel):
    """Resultado legible de un caso dentro de la ejecución de una suite."""
    history_id: int
    test_case_id: int
    case_name: str
    status: str
    validation_type: Optional[str] = None
    expected_result: Optional[str] = None
    expected_text: str
    obtained_text: str
    reason: str
    duration_ms: float = 0.0
    error_message: Optional[str] = None
    # Comparación con la ejecución anterior del mismo caso (app/services/comparacion.py)
    previous_status: Optional[str] = None
    previous_executed_at: Optional[datetime] = None
    change: Optional[str] = None
    change_text: Optional[str] = None

class SuiteExecutionSummary(BaseModel):
    suite_id: int
    suite_name: str
    total_tests: int
    passed: int
    failed: int
    errors: int
    total_duration_ms: float
    run_id: Optional[str] = None
    details: List[HistoryResponse] = []
    case_results: List[SuiteCaseResult] = []
    new_failures: int = 0
    fixed: int = 0
