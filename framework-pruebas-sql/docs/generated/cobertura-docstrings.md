<!-- GENERADO por scripts/docs/gen_docs.py. No editar a mano: edite el código o descripciones_datos.py y vuelva a ejecutarlo. -->


# Cobertura de documentación del código (`app/`)

Cuenta lo que existe en cada módulo y cuánto tiene docstring. **Documentada** significa: la clase, función o método tiene docstring; una propiedad (atributo de clase, campo, `self.x` de `__init__`) la tiene si lleva un docstring de atributo o, solo en las columnas del modelo ORM, si figura en el diccionario de datos (`scripts/docs/descripciones_datos.py`, columna «Propiedades en diccionario»). Se excluyen nombres que empiezan por `_`. Es una medida **formal** (existe texto), no de calidad del texto.

| Módulo | Docstring del módulo | Clases (doc/total) | Funciones (doc/total) | Métodos (doc/total) | Propiedades con docstring (doc/total) | Propiedades en diccionario | Propiedades sin describir |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `app.api.analysis` | sí | 0/3 | 2/2 | 0/0 | 0/12 | 0 | 12 |
| `app.api.connections` | sí | 0/0 | 6/6 | 0/0 | 0/0 | 0 | 0 |
| `app.api.demo` | sí | 0/2 | 2/2 | 0/0 | 0/5 | 0 | 5 |
| `app.api.excel` | sí | 0/0 | 2/4 | 0/0 | 0/0 | 0 | 0 |
| `app.api.executions` | sí | 0/0 | 4/4 | 0/0 | 0/0 | 0 | 0 |
| `app.api.history` | sí | 0/0 | 4/4 | 0/0 | 0/0 | 0 | 0 |
| `app.api.projects` | sí | 0/0 | 5/5 | 0/0 | 0/0 | 0 | 0 |
| `app.api.rules` | sí | 0/1 | 2/2 | 0/0 | 0/3 | 0 | 3 |
| `app.api.suites` | sí | 0/0 | 7/7 | 0/0 | 0/0 | 0 | 0 |
| `app.api.test_cases` | sí | 0/0 | 5/5 | 0/0 | 0/0 | 0 | 0 |
| `app.api.usage` | sí | 0/0 | 1/1 | 0/0 | 0/0 | 0 | 0 |
| `app.api.users` | sí | 0/7 | 10/10 | 0/0 | 0/24 | 0 | 24 |
| `app.cli` | sí | 1/1 | 0/8 | 0/0 | 0/0 | 0 | 0 |
| `app.core.database` | **no** | 0/0 | 0/2 | 0/0 | 0/0 | 0 | 0 |
| `app.engine.executor` | sí | 1/1 | 0/0 | 3/3 | 0/6 | 0 | 6 |
| `app.engine.validator` | sí | 5/5 | 2/2 | 3/6 | 0/0 | 0 | 0 |
| `app.main` | **no** | 0/0 | 1/4 | 0/0 | 0/0 | 0 | 0 |
| `app.models.connection` | sí | 0/1 | 0/1 | 0/0 | 0/13 | 11 | 2 |
| `app.models.history` | sí | 0/1 | 0/1 | 0/3 | 0/24 | 20 | 4 |
| `app.models.project` | sí | 0/1 | 0/1 | 0/0 | 0/9 | 5 | 4 |
| `app.models.schemas` | **no** | 3/25 | 1/1 | 1/20 | 0/157 | 0 | 157 |
| `app.models.suite` | sí | 0/1 | 0/0 | 0/0 | 0/9 | 6 | 3 |
| `app.models.test_case` | sí | 0/1 | 0/0 | 0/0 | 0/11 | 9 | 2 |
| `app.models.usage` | sí | 0/1 | 0/1 | 0/0 | 0/6 | 6 | 0 |
| `app.models.user` | sí | 0/1 | 0/1 | 0/0 | 0/11 | 11 | 0 |
| `app.security.acceso` | sí | 0/0 | 1/5 | 0/0 | 0/0 | 0 | 0 |
| `app.security.auth` | sí | 1/1 | 5/6 | 0/3 | 0/0 | 0 | 0 |
| `app.security.sql_policy` | sí | 0/0 | 1/1 | 0/0 | 0/0 | 0 | 0 |
| `app.security.target_policy` | sí | 0/0 | 2/3 | 0/0 | 0/0 | 0 | 0 |
| `app.services.analisis_tabla` | sí | 1/1 | 3/4 | 0/0 | 0/0 | 0 | 0 |
| `app.services.comparacion` | sí | 0/0 | 2/3 | 0/0 | 0/0 | 0 | 0 |
| `app.services.demo_scenario` | sí | 0/0 | 1/1 | 0/0 | 0/0 | 0 | 0 |
| `app.services.excel_io` | sí | 1/1 | 3/6 | 0/0 | 0/0 | 0 | 0 |
| `app.services.execution_service` | sí | 0/0 | 7/7 | 0/0 | 0/0 | 0 | 0 |
| `app.services.project_service` | sí | 0/0 | 1/1 | 0/0 | 0/0 | 0 | 0 |
| `app.services.reporte_corrida` | sí | 0/0 | 0/2 | 0/0 | 0/0 | 0 | 0 |
| `app.services.rule_templates` | sí | 1/1 | 2/2 | 0/0 | 0/0 | 0 | 0 |
| `app.services.usage_service` | sí | 0/0 | 1/2 | 0/0 | 0/0 | 0 | 0 |
| `app.services.validacion_auto` | sí | 0/0 | 2/2 | 0/0 | 0/0 | 0 | 0 |
| **Total** | 36/39 | 14/56 | 85/119 | 7/35 | 0/290 | 68 | 222 |

## Vacíos (sin docstring)

### Módulos sin documentar (3)

| Módulo | Nombre | Línea |
| --- | --- | --- |
| `app.core.database` | `app.core.database` | 1 |
| `app.main` | `app.main` | 1 |
| `app.models.schemas` | `app.models.schemas` | 1 |

### Clases sin documentar (42)

| Módulo | Nombre | Línea |
| --- | --- | --- |
| `app.api.analysis` | `AnalisisRequest` | 21 |
| `app.api.analysis` | `PropuestaElegida` | 28 |
| `app.api.analysis` | `GuardarSuiteRequest` | 34 |
| `app.api.demo` | `DemoScenarioRequest` | 24 |
| `app.api.demo` | `GuidedDemoRequest` | 29 |
| `app.api.rules` | `RuleBuildRequest` | 14 |
| `app.api.users` | `LoginRequest` | 31 |
| `app.api.users` | `RegistroRequest` | 36 |
| `app.api.users` | `CambioContrasenaRequest` | 42 |
| `app.api.users` | `UsuarioCrear` | 47 |
| `app.api.users` | `UsuarioActualizar` | 54 |
| `app.api.users` | `RestablecerRequest` | 60 |
| `app.api.users` | `UsuarioResponse` | 64 |
| `app.models.connection` | `ConnectionProfile` | 12 |
| `app.models.history` | `ExecutionHistory` | 12 |
| `app.models.project` | `Project` | 12 |
| `app.models.schemas` | `ValidationTypeEnum` | 9 |
| `app.models.schemas` | `EnvironmentTypeEnum` | 14 |
| `app.models.schemas` | `ProjectCreate` | 22 |
| `app.models.schemas` | `ProjectUpdate` | 34 |
| `app.models.schemas` | `ProjectResponse` | 47 |
| `app.models.schemas` | `ConnectionProfileCreate` | 74 |
| `app.models.schemas` | `ConnectionProfileUpdate` | 110 |
| `app.models.schemas` | `ConnectionProfileResponse` | 137 |
| `app.models.schemas` | `TestConnectionRequest` | 151 |
| `app.models.schemas` | `TestCaseCreate` | 179 |
| `app.models.schemas` | `TestCaseUpdate` | 212 |
| `app.models.schemas` | `TestCaseResponse` | 241 |
| `app.models.schemas` | `TestSuiteCreate` | 249 |
| `app.models.schemas` | `TestSuiteUpdate` | 262 |
| `app.models.schemas` | `TestSuiteResponse` | 275 |
| `app.models.schemas` | `ExecutionRequest` | 297 |
| `app.models.schemas` | `TestCaseExecutionRequest` | 300 |
| `app.models.schemas` | `SuiteExecutionRequest` | 303 |
| `app.models.schemas` | `ExecutionResponse` | 306 |
| `app.models.schemas` | `QuickExecutionResponse` | 361 |
| `app.models.schemas` | `HistoryResponse` | 387 |
| `app.models.schemas` | `SuiteExecutionSummary` | 433 |
| `app.models.suite` | `TestSuite` | 17 |
| `app.models.test_case` | `TestCase` | 9 |
| `app.models.usage` | `UsageEvent` | 15 |
| `app.models.user` | `User` | 20 |

### Funciones sin documentar (34)

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
| `app.cli` | `build_parser` | 325 |
| `app.cli` | `main` | 373 |
| `app.core.database` | `set_sqlite_pragma` | 16 |
| `app.core.database` | `get_db` | 29 |
| `app.main` | `get_login_page` | 96 |
| `app.main` | `health_check` | 104 |
| `app.main` | `read_root` | 130 |
| `app.models.connection` | `get_utc_now` | 9 |
| `app.models.history` | `get_utc_now` | 9 |
| `app.models.project` | `get_utc_now` | 9 |
| `app.models.usage` | `get_utc_now` | 11 |
| `app.models.user` | `get_utc_now` | 16 |
| `app.security.acceso` | `acceso_activado` | 24 |
| `app.security.acceso` | `asegurar_admin_inicial` | 28 |
| `app.security.acceso` | `usuario_actual` | 39 |
| `app.security.acceso` | `requiere_admin` | 51 |
| `app.security.auth` | `problemas_de_usuario` | 73 |
| `app.security.target_policy` | `allowed_hosts` | 20 |
| `app.services.analisis_tabla` | `nombre_de_caso` | 140 |
| `app.services.comparacion` | `clasificar` | 32 |
| `app.services.excel_io` | `build_template` | 99 |
| `app.services.excel_io` | `export_cases` | 160 |
| `app.services.excel_io` | `export_results` | 176 |
| `app.services.reporte_corrida` | `filas_de_corrida` | 44 |
| `app.services.reporte_corrida` | `generar_html` | 48 |
| `app.services.usage_service` | `build_summary` | 82 |

### Métodos sin documentar (28)

| Módulo | Nombre | Línea |
| --- | --- | --- |
| `app.engine.validator` | `RowCountValidation.evaluate` | 32 |
| `app.engine.validator` | `ExistenceValidation.evaluate` | 63 |
| `app.engine.validator` | `ScalarValueValidation.evaluate` | 141 |
| `app.models.history` | `ExecutionHistory.case_name` | 50 |
| `app.models.history` | `ExecutionHistory.suite_name` | 54 |
| `app.models.history` | `ExecutionHistory.connection_name` | 58 |
| `app.models.schemas` | `ProjectCreate.validate_name` | 28 |
| `app.models.schemas` | `ProjectUpdate.validate_name` | 40 |
| `app.models.schemas` | `ConnectionProfileCreate.validate_non_empty` | 86 |
| `app.models.schemas` | `ConnectionProfileCreate.validate_host` | 94 |
| `app.models.schemas` | `ConnectionProfileCreate.validate_service` | 99 |
| `app.models.schemas` | `ConnectionProfileCreate.validate_engine` | 104 |
| `app.models.schemas` | `ConnectionProfileUpdate.validate_non_empty` | 120 |
| `app.models.schemas` | `ConnectionProfileUpdate.validate_host` | 129 |
| `app.models.schemas` | `ConnectionProfileUpdate.validate_service` | 134 |
| `app.models.schemas` | `TestCaseCreate.validacion_automatica` | 189 |
| `app.models.schemas` | `TestCaseCreate.validate_text` | 199 |
| `app.models.schemas` | `TestCaseCreate.validate_expected` | 207 |
| `app.models.schemas` | `TestCaseUpdate.validacion_automatica` | 221 |
| `app.models.schemas` | `TestCaseUpdate.validate_text` | 234 |
| `app.models.schemas` | `TestSuiteCreate.validate_name` | 256 |
| `app.models.schemas` | `TestSuiteUpdate.validate_name` | 268 |
| `app.models.schemas` | `QuickExecutionRequest.aceptar_auto` | 335 |
| `app.models.schemas` | `QuickExecutionRequest.validate_text` | 342 |
| `app.models.schemas` | `QuickExecutionRequest.validate_expected_for_type` | 349 |
| `app.security.auth` | `LimiteDeIntentos.bloqueada` | 132 |
| `app.security.auth` | `LimiteDeIntentos.fallo` | 136 |
| `app.security.auth` | `LimiteDeIntentos.reiniciar` | 140 |

### Propiedades sin documentar (222)

| Módulo | Clase | Propiedades |
| --- | --- | --- |
| `app.api.analysis` | `AnalisisRequest` | `connection_profile_id`, `model_config`, `password`, `tabla` |
| `app.api.analysis` | `GuardarSuiteRequest` | `descripcion`, `model_config`, `nombre_suite`, `project_id`, `propuestas` |
| `app.api.analysis` | `PropuestaElegida` | `model_config`, `params`, `regla` |
| `app.api.demo` | `DemoScenarioRequest` | `model_config`, `project_id` |
| `app.api.demo` | `GuidedDemoRequest` | `connection_profile_id`, `model_config`, `password` |
| `app.api.rules` | `RuleBuildRequest` | `model_config`, `params`, `rule_id` |
| `app.api.users` | `CambioContrasenaRequest` | `actual`, `nueva` |
| `app.api.users` | `LoginRequest` | `password`, `username` |
| `app.api.users` | `RegistroRequest` | `full_name`, `password`, `username` |
| `app.api.users` | `RestablecerRequest` | `nueva` |
| `app.api.users` | `UsuarioActualizar` | `active`, `full_name`, `role` |
| `app.api.users` | `UsuarioCrear` | `full_name`, `password`, `role`, `username` |
| `app.api.users` | `UsuarioResponse` | `active`, `bloqueado`, `created_at`, `full_name`, `id`, `last_login_at`, `model_config`, `role`, `username` |
| `app.engine.executor` | `TargetDatabaseExecutor` | `dsn`, `environment_type`, `max_rows`, `password`, `timeout_ms`, `user` |
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
| `app.models.schemas` | `HistoryResponse` | `actual_result`, `case_name`, `connection_name`, `connection_profile_id`, `duration_ms`, `error_message`, `executed_at`, `executed_by`, `executed_sql`, `expected_result`, `id`, `model_config`, `project_id`, `rollback_applied`, `rollback_error`, `rowcount`, `run_id`, `statement_type`, `status`, `suite_id`, `suite_name`, `test_case_id`, `trigger_source`, `validation_type` |
| `app.models.schemas` | `ProjectCreate` | `description`, `name` |
| `app.models.schemas` | `ProjectResponse` | `created_at`, `id`, `model_config`, `updated_at` |
| `app.models.schemas` | `ProjectUpdate` | `description`, `name` |
| `app.models.schemas` | `QuickExecutionRequest` | `connection_profile_id`, `expected_result`, `model_config`, `password`, `sql_query`, `validation_type` |
| `app.models.schemas` | `QuickExecutionResponse` | `columns`, `connection_name`, `duration_ms`, `environment_type`, `error_message`, `expected_result`, `expected_text`, `history_id`, `obtained_text`, `obtained_value`, `reason`, `rowcount`, `rows`, `rows_hidden`, `rows_shown`, `rows_truncated`, `sql_query`, `status`, `validation_auto`, `validation_reason`, `validation_type` |
| `app.models.schemas` | `SuiteCaseResult` | `case_name`, `change`, `change_text`, `duration_ms`, `error_message`, `expected_result`, `expected_text`, `history_id`, `obtained_text`, `previous_executed_at`, `previous_status`, `reason`, `status`, `test_case_id`, `validation_type` |
| `app.models.schemas` | `SuiteExecutionSummary` | `case_results`, `details`, `errors`, `failed`, `fixed`, `new_failures`, `passed`, `run_id`, `suite_id`, `suite_name`, `total_duration_ms`, `total_tests` |
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
