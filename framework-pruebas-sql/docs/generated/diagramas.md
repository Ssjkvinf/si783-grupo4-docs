<!-- GENERADO por scripts/docs/gen_docs.py. No editar a mano: edite el código o descripciones_datos.py y vuelva a ejecutarlo. -->


# Diagramas generados

Todos se generan desde el código con `scripts/docs/gen_docs.py`. Los diagramas de casos de uso, actividad, secuencia, paquetes y arquitectura de `docs/diagramas/` se mantienen **a mano** y no se regeneran.

## Modelo entidad-relación de la base interna (SQLite)

```mermaid
%% Base INTERNA (SQLite): metadatos e historial. No incluye la base Oracle objetivo.
erDiagram
    projects {
        INTEGER id PK
        VARCHAR name
        VARCHAR description
        DATETIME created_at
        DATETIME updated_at
    }
    users {
        INTEGER id PK
        VARCHAR username
        VARCHAR full_name
        VARCHAR password_hash
        VARCHAR role
        BOOLEAN active
        INTEGER failed_attempts
        DATETIME locked_until
        INTEGER session_version
        DATETIME created_at
        DATETIME last_login_at
    }
    connection_profiles {
        INTEGER id PK
        INTEGER project_id FK
        VARCHAR name
        VARCHAR engine
        VARCHAR host
        INTEGER port
        VARCHAR service_name
        VARCHAR username
        VARCHAR environment_type
        DATETIME created_at
        DATETIME updated_at
    }
    test_cases {
        INTEGER id PK
        INTEGER project_id FK
        VARCHAR name
        VARCHAR description
        TEXT sql_query
        VARCHAR expected_result
        VARCHAR validation_type
        DATETIME created_at
        DATETIME updated_at
    }
    test_suites {
        INTEGER id PK
        INTEGER project_id FK
        VARCHAR name
        VARCHAR description
        DATETIME created_at
        DATETIME updated_at
    }
    usage_events {
        INTEGER id PK
        VARCHAR event_type
        INTEGER project_id FK
        VARCHAR source
        VARCHAR detail
        DATETIME created_at
    }
    execution_history {
        INTEGER id PK
        INTEGER project_id FK
        INTEGER test_case_id FK
        INTEGER suite_id FK
        INTEGER connection_profile_id FK
        VARCHAR status
        DATETIME executed_at
        FLOAT duration_ms
        VARCHAR statement_type
        TEXT executed_sql
        VARCHAR validation_type
        VARCHAR expected_result
        TEXT actual_result
        INTEGER rowcount
        BOOLEAN rollback_applied
        TEXT rollback_error
        TEXT error_message
        VARCHAR trigger_source
        VARCHAR run_id
        VARCHAR executed_by
    }
    suite_test_case {
        INTEGER suite_id PK,FK
        INTEGER test_case_id PK,FK
    }
    projects ||--o{ connection_profiles : "project_id"
    projects ||--o{ test_cases : "project_id"
    projects ||--o{ test_suites : "project_id"
    projects |o--o{ usage_events : "project_id"
    projects ||--o{ execution_history : "project_id"
    test_cases |o--o{ execution_history : "test_case_id"
    test_suites |o--o{ execution_history : "suite_id"
    connection_profiles |o--o{ execution_history : "connection_profile_id"
    test_suites ||--o{ suite_test_case : "suite_id"
    test_cases ||--o{ suite_test_case : "test_case_id"
```

## Clases ORM (base interna)

```mermaid
%% Clases ORM de la base interna SQLite (app/models)
classDiagram
    class Project {
        +Integer id
        +String name
        +String description
        +DateTime created_at
        +DateTime updated_at
    }
    class ConnectionProfile {
        +Integer id
        +Integer project_id
        +String name
        +String engine
        +String host
        +Integer port
        +String service_name
        +String username
        +String environment_type
        +DateTime created_at
        +DateTime updated_at
    }
    class TestCase {
        +Integer id
        +Integer project_id
        +String name
        +String description
        +Text sql_query
        +String expected_result
        +String validation_type
        +DateTime created_at
        +DateTime updated_at
    }
    class TestSuite {
        +Integer id
        +Integer project_id
        +String name
        +String description
        +DateTime created_at
        +DateTime updated_at
    }
    class ExecutionHistory {
        +Integer id
        +Integer project_id
        +Integer test_case_id
        +Integer suite_id
        +Integer connection_profile_id
        +String status
        +DateTime executed_at
        +Float duration_ms
        +String statement_type
        +Text executed_sql
        +String validation_type
        +String expected_result
        +Text actual_result
        +Integer rowcount
        +Boolean rollback_applied
        +Text rollback_error
        +Text error_message
        +String trigger_source
        +String run_id
        +String executed_by
        +case_name()
        +suite_name()
        +connection_name()
    }
    class UsageEvent {
        +Integer id
        +String event_type
        +Integer project_id
        +String source
        +String detail
        +DateTime created_at
    }
    Project --> TestCase : test_cases
    Project --> TestSuite : test_suites
    Project --> ConnectionProfile : connection_profiles
    Project --> ExecutionHistory : execution_histories
    ConnectionProfile --> Project : project
    ConnectionProfile --> ExecutionHistory : execution_histories
    TestCase --> Project : project
    TestCase --> ExecutionHistory : execution_histories
    TestSuite --> Project : project
    TestSuite --> TestCase : test_cases
    TestSuite --> ExecutionHistory : execution_histories
    ExecutionHistory --> Project : project
    ExecutionHistory --> TestCase : test_case
    ExecutionHistory --> TestSuite : test_suite
    ExecutionHistory --> ConnectionProfile : connection_profile
```

## Clases del motor, la seguridad y los servicios

```mermaid
%% Clases del motor de ejecución, la seguridad y los servicios (app/engine, app/security, app/services, app/core)
classDiagram
    class UsageError {
    }
    class TargetDatabaseExecutor {
        +dsn
        +user
        +password
        +environment_type
        +max_rows
        +timeout_ms
        +connect()
        +execute_query(query, params, confirm_staging_dml) Dict~str~
        +disconnect()
    }
    class ValidationStrategy {
        <<abstract>>
        +evaluate(execution_data, expected_value) bool
    }
    class RowCountValidation {
        +evaluate(execution_data, expected_value) bool
    }
    class ExistenceValidation {
        +evaluate(execution_data, expected_value) bool
    }
    class ValidationContext {
        +set_strategy(strategy)
        +execute_validation(execution_data, expected_value) bool
    }
    class ScalarValueValidation {
        +evaluate(execution_data, expected_value) bool
    }
    class LimiteDeIntentos {
        +bloqueada(ip) bool
        +fallo(ip)
        +reiniciar(ip)
    }
    class AnalisisError {
    }
    class ExcelError {
    }
    class ReglaInvalida {
    }
    ValidationStrategy <|-- RowCountValidation
    ValidationStrategy <|-- ExistenceValidation
    ValidationStrategy <|-- ScalarValueValidation
```

## Clases Pydantic de la API

```mermaid
%% Clases Pydantic de entrada y salida de la API (app/models/schemas.py)
classDiagram
    class ValidationTypeEnum {
    }
    class EnvironmentTypeEnum {
    }
    class ProjectCreate {
        +str name
        +Optional~str~ description
        +validate_name(v) str
    }
    class ProjectUpdate {
        +Optional~str~ name
        +Optional~str~ description
        +validate_name(v) Optional~str~
    }
    class ProjectResponse {
        +int id
        +datetime created_at
        +datetime updated_at
    }
    class ConnectionProfileCreate {
        +int project_id
        +str name
        +str engine
        +str host
        +int port
        +str service_name
        +str username
        +EnvironmentTypeEnum environment_type
        +validate_non_empty(v) str
        +validate_host(v) str
        +validate_service(v) str
        +validate_engine(v) str
    }
    class ConnectionProfileUpdate {
        +Optional~str~ name
        +Optional~str~ host
        +Optional~int~ port
        +Optional~str~ service_name
        +Optional~str~ username
        +Optional~EnvironmentTypeEnum~ environment_type
        +validate_non_empty(v) Optional~str~
        +validate_host(v) Optional~str~
        +validate_service(v) Optional~str~
    }
    class ConnectionProfileResponse {
        +int id
        +int project_id
        +str name
        +str engine
        +str host
        +int port
        +str service_name
        +str username
        +str environment_type
        +datetime created_at
        +datetime updated_at
    }
    class TestConnectionRequest {
        +str password
    }
    class TestCaseCreate {
        +Optional~int~ project_id
        +str name
        +Optional~str~ description
        +str sql_query
        +Optional~ValidationTypeEnum~ validation_type
        +str expected_result
        +validacion_automatica(data) Any
        +validate_text(v) str
        +validate_expected(v, info) str
    }
    class TestCaseUpdate {
        +Optional~str~ name
        +Optional~str~ description
        +Optional~str~ sql_query
        +Optional~ValidationTypeEnum~ validation_type
        +Optional~str~ expected_result
        +validacion_automatica(data) Any
        +validate_text(v) Optional~str~
    }
    class TestCaseResponse {
        +int id
        +int project_id
    }
    class TestSuiteCreate {
        +Optional~int~ project_id
        +str name
        +Optional~str~ description
        +validate_name(v) str
    }
    class TestSuiteUpdate {
        +Optional~str~ name
        +Optional~str~ description
        +validate_name(v) Optional~str~
    }
    class TestSuiteResponse {
        +int id
        +int project_id
        +List~TestCaseResponse~ test_cases
    }
    class DBCredentials {
        +str password
        +int connection_profile_id
        +Optional~EnvironmentTypeEnum~ environment_type
        +bool confirm_staging_dml
    }
    class ExecutionRequest {
        +str sql_query
    }
    class TestCaseExecutionRequest {
    }
    class SuiteExecutionRequest {
    }
    class ExecutionResponse {
        +bool success
        +str statement_type
        +List~Any~ rows
        +int rowcount
        +List~Any~ data
        +str message
        +Optional~str~ error_message
        +bool rollback_applied
        +Optional~str~ rollback_error
    }
    class QuickExecutionRequest {
        +int connection_profile_id
        +str password
        +str sql_query
        +Optional~ValidationTypeEnum~ validation_type
        +str expected_result
        +Optional~str~ _motivo_auto
        +aceptar_auto(data) Any
        +validate_text(v) str
        +validate_expected_for_type()
        +motivo_validacion_automatica() Optional~str~
    }
    class QuickExecutionResponse {
        +int history_id
        +str status
        +str environment_type
        +str connection_name
        +str sql_query
        +str validation_type
        +str expected_result
        +str expected_text
        +str obtained_text
        +str reason
        +bool validation_auto
        +Optional~str~ validation_reason
        +List~str~ columns
        +Optional~str~ obtained_value
        +List rows
        +int rows_shown
        +bool rows_truncated
        +bool rows_hidden
        +int rowcount
        +float duration_ms
        +Optional~str~ error_message
    }
    class HistoryResponse {
        +int id
        +int project_id
        +Optional~int~ test_case_id
        +Optional~int~ suite_id
        +Optional~int~ connection_profile_id
        +str status
        +datetime executed_at
        +float duration_ms
        +Optional~str~ statement_type
        +str executed_sql
        +Optional~str~ validation_type
        +Optional~str~ expected_result
        +Optional~str~ actual_result
        +int rowcount
        +bool rollback_applied
        +Optional~str~ rollback_error
        +Optional~str~ error_message
        +Optional~str~ trigger_source
        +Optional~str~ run_id
        +Optional~str~ executed_by
        +Optional~str~ case_name
        +Optional~str~ suite_name
        +Optional~str~ connection_name
    }
    class SuiteCaseResult {
        +int history_id
        +int test_case_id
        +str case_name
        +str status
        +Optional~str~ validation_type
        +Optional~str~ expected_result
        +str expected_text
        +str obtained_text
        +str reason
        +float duration_ms
        +Optional~str~ error_message
        +Optional~str~ previous_status
        +Optional~datetime~ previous_executed_at
        +Optional~str~ change
        +Optional~str~ change_text
    }
    class SuiteExecutionSummary {
        +int suite_id
        +str suite_name
        +int total_tests
        +int passed
        +int failed
        +int errors
        +float total_duration_ms
        +Optional~str~ run_id
        +List~HistoryResponse~ details
        +List~SuiteCaseResult~ case_results
        +int new_failures
        +int fixed
    }
    ProjectCreate <|-- ProjectResponse
    TestCaseCreate <|-- TestCaseResponse
    TestSuiteCreate <|-- TestSuiteResponse
    DBCredentials <|-- ExecutionRequest
    DBCredentials <|-- TestCaseExecutionRequest
    DBCredentials <|-- SuiteExecutionRequest
```

## Componentes y dependencias entre paquetes

```mermaid
%% Dependencias entre paquetes, leídas de los import de app/ y alembic/env.py (se omiten FastAPI y, salvo en app.core y alembic, SQLAlchemy por legibilidad).
flowchart LR
    nav["Navegador: frontend/ (17 archivos JS)"]
    subgraph APP["Aplicación Python (app/)"]
        app_api["app.api"]
        app_cli["app.cli"]
        app_core["app.core"]
        app_engine["app.engine"]
        app_main["app.main"]
        app_models["app.models"]
        app_security["app.security"]
        app_services["app.services"]
    end
    alembic["alembic/ (migraciones)"]
    ext_openpyxl[("openpyxl (Excel)")]
    ext_oracle[("Oracle objetivo (python-oracledb)")]
    ext_sqlite[("SQLite interna (SQLAlchemy)")]
    ext_sqlparse[("sqlparse")]
    nav -->|"HTTP /api"| app_main
    app_main -->|"sirve /ui"| nav
    alembic --> app_core
    alembic --> app_models
    app_api --> app_core
    app_api --> app_engine
    app_api --> app_models
    app_api --> app_security
    app_api --> app_services
    app_cli --> app_core
    app_cli --> app_engine
    app_cli --> app_models
    app_cli --> app_security
    app_cli --> app_services
    app_engine --> app_security
    app_main --> app_api
    app_main --> app_core
    app_main --> app_models
    app_main --> app_security
    app_models --> app_core
    app_models --> app_security
    app_models --> app_services
    app_security --> app_core
    app_security --> app_models
    app_services --> app_core
    app_services --> app_engine
    app_services --> app_models
    app_services --> app_security
    alembic -.-> ext_sqlite
    app_api -.-> ext_oracle
    app_cli -.-> ext_oracle
    app_core -.-> ext_sqlite
    app_engine -.-> ext_oracle
    app_engine -.-> ext_sqlparse
    app_security -.-> ext_sqlparse
    app_services -.-> ext_openpyxl
    app_services -.-> ext_oracle
```

## Despliegue (compose, Terraform y workflows)

```mermaid
%% Leído de infra/production/compose.yml, infra/terraform/*.tf y .github/workflows/*.yml (no verifica que exista en Azure).
flowchart TB
    user(["Persona usuaria (navegador)"])
    subgraph VM["Máquina virtual Linux (Docker Compose: infra/production/compose.yml)"]
        api["api<br/>sql-qa-framework:latest"]
        caddy["caddy<br/>caddy:2-alpine<br/>puertos 80:80, 443:443"]
        oracle_db["oracle_db<br/>container-registry.oracle.com/database/free"]
    end
    vol_framework_data[("volumen framework_data")]
    api --- vol_framework_data
    vol_oracle_data[("volumen oracle_data")]
    oracle_db --- vol_oracle_data
    user -->|"HTTPS 443"| caddy
    caddy -->|"proxy a api:8000"| api
    api -->|"oracledb"| oracle_db
    api -->|"SQLAlchemy"| vol_framework_data
    subgraph TF["Terraform (infra/terraform/)"]
        tf_budget_tf["budget.tf<br/>resource azurerm_consumption_budget_resource_group.monthly"]
        tf_main_tf["main.tf<br/>data azurerm_resource_group.existing<br/>data azurerm_virtual_machine.existing"]
        tf_storage_tf["storage.tf<br/>resource azurerm_storage_account.backups<br/>resource azurerm_storage_container.backups<br/>resource azurerm_storage_management_policy.backups"]
        tf_vm_new_tf["vm_new.tf<br/>resource azurerm_resource_group.new<br/>resource azurerm_virtual_network.new<br/>resource azurerm_subnet.new<br/>resource azurerm_public_ip.new<br/>resource azurerm_network_security_group.new<br/>resource azurerm_subnet_network_security_group_association.new<br/>resource azurerm_network_interface.new<br/>resource azurerm_linux_virtual_machine.new"]
    end
    subgraph GH["GitHub Actions (.github/workflows/)"]
        wf_backup_yml["backup.yml<br/>schedule,workflow_dispatch"]
        wf_db_objects_yml["db-objects.yml<br/>pull_request,push,workflow_dispatch"]
        wf_deploy_yml["deploy.yml<br/>workflow_call,workflow_dispatch"]
        wf_docs_generate_yml["docs-generate.yml<br/>pull_request,push,workflow_dispatch"]
        wf_docs_yml["docs.yml<br/>pull_request,push"]
        wf_infra_yml["infra.yml<br/>pull_request,push,workflow_dispatch"]
        wf_pages_yml["pages.yml<br/>pull_request,push,workflow_dispatch"]
        wf_release_yml["release.yml<br/>workflow_dispatch"]
        wf_sql_checks_yml["sql-checks.yml<br/>pull_request,workflow_call,workflow_dispatch"]
        wf_tests_yml["tests.yml<br/>pull_request,push"]
    end
    TF -.->|"gestiona/consulta"| VM
    GH -.->|"construye, prueba, despliega"| VM
```
