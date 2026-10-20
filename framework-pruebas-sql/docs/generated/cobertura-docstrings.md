<!-- GENERADO por scripts/docs/gen_docs.py. No editar a mano: edite el código o descripciones_datos.py y vuelva a ejecutarlo. -->


# Cobertura de documentación del código (`app/`)

Cuenta lo que existe en cada módulo y cuánto tiene docstring. **Documentada** significa: la clase, función o método tiene docstring; una propiedad (atributo de clase, campo, `self.x` de `__init__`) la tiene si lleva un docstring de atributo o, solo en las columnas del modelo ORM, si figura en el diccionario de datos (`scripts/docs/descripciones_datos.py`, columna «Propiedades en diccionario»). Se excluyen nombres que empiezan por `_`. Es una medida **formal** (existe texto), no de calidad del texto.

| Módulo | Docstring del módulo | Clases (doc/total) | Funciones (doc/total) | Métodos (doc/total) | Propiedades con docstring (doc/total) | Propiedades en diccionario | Propiedades sin describir |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `app.api.connections` | sí | 0/0 | 6/6 | 0/0 | 0/0 | 0 | 0 |
| `app.api.demo` | sí | 0/1 | 1/1 | 0/0 | 0/2 | 0 | 2 |
| `app.api.excel` | sí | 0/0 | 2/4 | 0/0 | 0/0 | 0 | 0 |
| `app.api.executions` | sí | 0/0 | 4/4 | 0/0 | 0/0 | 0 | 0 |
| `app.api.history` | sí | 0/0 | 2/2 | 0/0 | 0/0 | 0 | 0 |
| `app.api.projects` | sí | 0/0 | 5/5 | 0/0 | 0/0 | 0 | 0 |
| `app.api.suites` | sí | 0/0 | 7/7 | 0/0 | 0/0 | 0 | 0 |
| `app.api.test_cases` | sí | 0/0 | 5/5 | 0/0 | 0/0 | 0 | 0 |
| `app.api.usage` | sí | 0/0 | 1/1 | 0/0 | 0/0 | 0 | 0 |
| `app.cli` | sí | 1/1 | 0/8 | 0/0 | 0/0 | 0 | 0 |
| `app.core.database` | **no** | 0/0 | 0/2 | 0/0 | 0/0 | 0 | 0 |
| `app.engine.executor` | sí | 1/1 | 0/0 | 3/3 | 0/6 | 0 | 6 |
| `app.engine.validator` | sí | 5/5 | 2/2 | 3/6 | 0/0 | 0 | 0 |
| `app.main` | **no** | 0/1 | 0/8 | 0/0 | 0/2 | 0 | 2 |
| `app.models.connection` | sí | 0/1 | 0/1 | 0/0 | 0/13 | 11 | 2 |
| `app.models.history` | sí | 0/1 | 0/1 | 0/0 | 0/23 | 19 | 4 |
| `app.models.project` | sí | 0/1 | 0/1 | 0/0 | 0/9 | 5 | 4 |
| `app.models.schemas` | **no** | 3/25 | 1/1 | 0/16 | 0/145 | 0 | 145 |
| `app.models.suite` | sí | 0/1 | 0/0 | 0/0 | 0/9 | 6 | 3 |
| `app.models.test_case` | sí | 0/1 | 0/0 | 0/0 | 0/11 | 9 | 2 |
| `app.models.usage` | sí | 0/1 | 0/1 | 0/0 | 0/6 | 6 | 0 |
| `app.security.sql_policy` | sí | 0/0 | 1/1 | 0/0 | 0/0 | 0 | 0 |
| `app.security.target_policy` | sí | 0/0 | 2/3 | 0/0 | 0/0 | 0 | 0 |
| `app.services.demo_scenario` | sí | 0/0 | 1/1 | 0/0 | 0/0 | 0 | 0 |
| `app.services.excel_io` | sí | 1/1 | 3/6 | 0/0 | 0/0 | 0 | 0 |
| `app.services.execution_service` | sí | 0/0 | 7/7 | 0/0 | 0/0 | 0 | 0 |
| `app.services.project_service` | sí | 0/0 | 1/1 | 0/0 | 0/0 | 0 | 0 |
| `app.services.usage_service` | sí | 0/0 | 1/2 | 0/0 | 0/0 | 0 | 0 |
| **Total** | 25/28 | 11/41 | 52/81 | 6/25 | 0/226 | 56 | 170 |

## Vacíos (sin docstring)

### Módulos sin documentar (3)

| Módulo | Nombre | Línea |
| --- | --- | --- |
| `app.core.database` | `app.core.database` | 1 |
| `app.main` | `app.main` | 1 |
| `app.models.schemas` | `app.models.schemas` | 1 |

### Clases sin documentar (30)

| Módulo | Nombre | Línea |
| --- | --- | --- |
| `app.api.demo` | `DemoScenarioRequest` | 15 |
| `app.main` | `LoginRequest` | 90 |
| `app.models.connection` | `ConnectionProfile` | 12 |
| `app.models.history` | `ExecutionHistory` | 12 |
| `app.models.project` | `Project` | 12 |
| `app.models.schemas` | `ValidationTypeEnum` | 8 |
| `app.models.schemas` | `EnvironmentTypeEnum` | 13 |
| `app.models.schemas` | `ProjectCreate` | 21 |
| `app.models.schemas` | `ProjectUpdate` | 33 |
| `app.models.schemas` | `ProjectResponse` | 46 |
| `app.models.schemas` | `ConnectionProfileCreate` | 73 |
| `app.models.schemas` | `ConnectionProfileUpdate` | 109 |
| `app.models.schemas` | `ConnectionProfileResponse` | 136 |
| `app.models.schemas` | `TestConnectionRequest` | 150 |
| `app.models.schemas` | `TestCaseCreate` | 178 |
| `app.models.schemas` | `TestCaseUpdate` | 201 |
| `app.models.schemas` | `TestCaseResponse` | 217 |
| `app.models.schemas` | `TestSuiteCreate` | 225 |
| `app.models.schemas` | `TestSuiteUpdate` | 238 |
| `app.models.schemas` | `TestSuiteResponse` | 251 |
| `app.models.schemas` | `ExecutionRequest` | 273 |
| `app.models.schemas` | `TestCaseExecutionRequest` | 276 |
| `app.models.schemas` | `SuiteExecutionRequest` | 279 |
| `app.models.schemas` | `ExecutionResponse` | 282 |
| `app.models.schemas` | `QuickExecutionResponse` | 321 |
| `app.models.schemas` | `HistoryResponse` | 345 |
| `app.models.schemas` | `SuiteExecutionSummary` | 382 |
| `app.models.suite` | `TestSuite` | 17 |
| `app.models.test_case` | `TestCase` | 9 |
| `app.models.usage` | `UsageEvent` | 15 |

### Funciones sin documentar (29)

| Módulo | Nombre | Línea |
| --- | --- | --- |
| `app.api.excel` | `export_cases` | 35 |
| `app.api.excel` | `export_results` | 43 |
| `app.cli` | `junit_xml` | 116 |
| `app.cli` | `markdown_report` | 134 |
| `app.cli` | `cmd_init_db` | 163 |
| `app.cli` | `cmd_import_excel` | 173 |
| `app.cli` | `cmd_export_excel` | 228 |
| `app.cli` | `cmd_run` | 257 |
| `app.cli` | `build_parser` | 324 |
| `app.cli` | `main` | 372 |
| `app.core.database` | `set_sqlite_pragma` | 16 |
| `app.core.database` | `get_db` | 29 |
| `app.main` | `create_session_token` | 42 |
| `app.main` | `verify_session_token` | 48 |
| `app.main` | `cookie_auth_middleware` | 60 |
| `app.main` | `login` | 95 |
| `app.main` | `logout` | 117 |
| `app.main` | `get_login_page` | 123 |
| `app.main` | `health_check` | 131 |
| `app.main` | `read_root` | 151 |
| `app.models.connection` | `get_utc_now` | 9 |
| `app.models.history` | `get_utc_now` | 9 |
| `app.models.project` | `get_utc_now` | 9 |
| `app.models.usage` | `get_utc_now` | 11 |
| `app.security.target_policy` | `allowed_hosts` | 20 |
| `app.services.excel_io` | `build_template` | 99 |
| `app.services.excel_io` | `export_cases` | 160 |
| `app.services.excel_io` | `export_results` | 176 |
| `app.services.usage_service` | `build_summary` | 77 |

### Métodos sin documentar (19)

| Módulo | Nombre | Línea |
| --- | --- | --- |
| `app.engine.validator` | `RowCountValidation.evaluate` | 32 |
| `app.engine.validator` | `ExistenceValidation.evaluate` | 63 |
| `app.engine.validator` | `ScalarValueValidation.evaluate` | 141 |
| `app.models.schemas` | `ProjectCreate.validate_name` | 27 |
| `app.models.schemas` | `ProjectUpdate.validate_name` | 39 |
| `app.models.schemas` | `ConnectionProfileCreate.validate_non_empty` | 85 |
| `app.models.schemas` | `ConnectionProfileCreate.validate_host` | 93 |
| `app.models.schemas` | `ConnectionProfileCreate.validate_service` | 98 |
| `app.models.schemas` | `ConnectionProfileCreate.validate_engine` | 103 |
| `app.models.schemas` | `ConnectionProfileUpdate.validate_non_empty` | 119 |
| `app.models.schemas` | `ConnectionProfileUpdate.validate_host` | 128 |
| `app.models.schemas` | `ConnectionProfileUpdate.validate_service` | 133 |
| `app.models.schemas` | `TestCaseCreate.validate_text` | 188 |
| `app.models.schemas` | `TestCaseCreate.validate_expected` | 196 |
| `app.models.schemas` | `TestCaseUpdate.validate_text` | 210 |
| `app.models.schemas` | `TestSuiteCreate.validate_name` | 232 |
| `app.models.schemas` | `TestSuiteUpdate.validate_name` | 244 |
| `app.models.schemas` | `QuickExecutionRequest.validate_text` | 310 |
| `app.models.schemas` | `QuickExecutionRequest.validate_expected_for_type` | 317 |

### Propiedades sin documentar (170)

| Módulo | Clase | Propiedades |
| --- | --- | --- |
| `app.api.demo` | `DemoScenarioRequest` | `model_config`, `project_id` |
| `app.engine.executor` | `TargetDatabaseExecutor` | `dsn`, `environment_type`, `max_rows`, `password`, `timeout_ms`, `user` |
| `app.main` | `LoginRequest` | `password`, `username` |
| `app.models.connection` | `ConnectionProfile` | `execution_histories`, `project` |
| `app.models.history` | `ExecutionHistory` | `connection_profile`, `project`, `test_case`, `test_suite` |
| `app.models.project` | `Project` | `connection_profiles`, `execution_histories`, `test_cases`, `test_suites` |
| `app.models.schemas` | `ConnectionProfileCreate` | `engine`, `environment_type`, `host`, `name`, `port`, `project_id`, `service_name`, `username` |
| `app.models.schemas` | `ConnectionProfileResponse` | `created_at`, `engine`, `environment_type`, `host`, `id`, `model_config`, `name`, `port`, `project_id`, `service_name`, `updated_at`, `username` |
| `app.models.schemas` | `ConnectionProfileUpdate` | `environment_type`, `host`, `name`, `port`, `service_name`, `username` |
| `app.models.schemas` | `DBCredentials` | `confirm_staging_dml`, `connection_profile_id`, `environment_type`, `model_config`, `password` |
| `app.models.schemas` | `EnvironmentTypeEnum` | `PRODUCTION`, `STAGING`, `TEST` |
| `app.models.schemas` | `ExecutionRequest` | `sql_query` |
| `app.models.schemas` | `ExecutionResponse` | `data`, `error_message`, `message`, `rollback_applied`, `rollback_error`, `rowcount`, `rows`, `statement_type`, `success` |
| `app.models.schemas` | `HistoryResponse` | `actual_result`, `connection_profile_id`, `duration_ms`, `error_message`, `executed_at`, `executed_sql`, `expected_result`, `id`, `model_config`, `project_id`, `rollback_applied`, `rollback_error`, `rowcount`, `run_id`, `statement_type`, `status`, `suite_id`, `test_case_id`, `trigger_source`, `validation_type` |
| `app.models.schemas` | `ProjectCreate` | `description`, `name` |
| `app.models.schemas` | `ProjectResponse` | `created_at`, `id`, `model_config`, `updated_at` |
| `app.models.schemas` | `ProjectUpdate` | `description`, `name` |
| `app.models.schemas` | `QuickExecutionRequest` | `connection_profile_id`, `expected_result`, `model_config`, `password`, `sql_query`, `validation_type` |
| `app.models.schemas` | `QuickExecutionResponse` | `columns`, `connection_name`, `duration_ms`, `environment_type`, `error_message`, `expected_result`, `expected_text`, `history_id`, `obtained_text`, `obtained_value`, `reason`, `rowcount`, `rows`, `rows_hidden`, `rows_shown`, `rows_truncated`, `sql_query`, `status`, `validation_type` |
| `app.models.schemas` | `SuiteCaseResult` | `case_name`, `duration_ms`, `error_message`, `expected_result`, `expected_text`, `history_id`, `obtained_text`, `reason`, `status`, `test_case_id`, `validation_type` |
| `app.models.schemas` | `SuiteExecutionSummary` | `case_results`, `details`, `errors`, `failed`, `passed`, `run_id`, `suite_id`, `suite_name`, `total_duration_ms`, `total_tests` |
| `app.models.schemas` | `TestCaseCreate` | `description`, `expected_result`, `name`, `project_id`, `sql_query`, `validation_type` |
| `app.models.schemas` | `TestCaseResponse` | `id`, `model_config`, `project_id` |
| `app.models.schemas` | `TestCaseUpdate` | `description`, `expected_result`, `name`, `sql_query`, `validation_type` |
| `app.models.schemas` | `TestConnectionRequest` | `password` |
| `app.models.schemas` | `TestSuiteCreate` | `description`, `name`, `project_id` |
| `app.models.schemas` | `TestSuiteResponse` | `id`, `model_config`, `project_id`, `test_cases` |
| `app.models.schemas` | `TestSuiteUpdate` | `description`, `name` |
| `app.models.schemas` | `ValidationTypeEnum` | `EXISTS`, `ROW_COUNT`, `SCALAR_VALUE` |
| `app.models.suite` | `TestSuite` | `execution_histories`, `project`, `test_cases` |
| `app.models.test_case` | `TestCase` | `execution_histories`, `project` |
