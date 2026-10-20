# Matriz de Trazabilidad

| ID Requisito | Funcionalidad | Componente Backend | Componente Frontend | Pruebas Automatizadas |
|--------------|---------------|--------------------|---------------------|-----------------------|
| REQ-01 | Gestión de Proyectos | `/api/projects/` | `frontend/js/modulos/proyectos.js` | `tests/test_core_models.py` |
| REQ-02 | Gestión de Conexiones | `/api/connections/` | `frontend/js/modulos/conexiones.js` | `tests/test_core_models.py` |
| REQ-03 | Gestión de Casos de Prueba | `/api/test-cases/` | `frontend/js/modulos/casos.js` | `tests/test_core_models.py` |
| REQ-04 | Agrupación de Suites | `/api/suites/` | `frontend/js/modulos/suites.js` | `tests/test_core_models.py` |
| REQ-05 | Ejecución Oracle y Rollback | `app/services/execution_service.py`, `app/engine/executor.py` | `frontend/js/modulos/ejecutor.js` | `tests/test_execution_engine.py`, `tests/test_oracle_integration.py` |
| REQ-06 | Paginación y Filtrado Historial| `/api/history/` | `frontend/js/modulos/historial.js` | `tests/test_history_pagination.py` |
| REQ-07 | Seguridad de Autenticación | Middleware (Cookie HttpOnly) | `frontend/js/core/api.js` | `tests/test_auth.py` |
| REQ-08 | Dashboard de KPIs | `/api/history/` | `frontend/js/modulos/dashboard.js` | `tests/test_revision_final_frontend.py` |
| REQ-09 | Políticas por Ambiente (TEST, STAGING, PRODUCTION) | `app/security/sql_policy.py`, `app/engine/executor.py` | `frontend/index.html` (Ayuda) | `tests/test_environment_policies.py`, `tests/test_engine.py` |
| REQ-10 | Prueba rápida de un SELECT («Inicio») | `POST /api/execute/quick` | `frontend/js/modulos/inicio.js` | `tests/test_quick_execution.py` |
| REQ-11 | Panel «Uso del producto» | `GET /api/usage/summary` | `frontend/js/modulos/uso.js` | `tests/test_phase4_usage.py` |
| REQ-12 | Excel (plantilla, importar, exportar) | `/api/excel/*`, `app/services/excel_io.py` | `frontend/js/modulos/excel.js` | `tests/test_phase4_excel.py` |
| REQ-13 | CLI con código de salida | `app/cli.py` | — | `tests/test_phase4_cli.py` |
| REQ-14 | Escenario de demostración (suites de ejemplo) | `POST /api/demo/scenario` | `frontend/js/modulos/inicio.js` | `tests/test_phase2_scalar_demo_targets.py`, `tests/test_oracle_phase2.py` (Oracle real, omitida sin variables) |
