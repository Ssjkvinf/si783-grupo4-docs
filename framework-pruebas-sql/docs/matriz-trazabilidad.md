# Matriz de Trazabilidad

| ID Requisito | Funcionalidad | Componente Backend | Componente Frontend | Pruebas Automatizadas |
|--------------|---------------|--------------------|---------------------|-----------------------|
| REQ-01 | Gestión de Proyectos (escritura solo ADMIN) | `/api/projects/` | `frontend/js/modulos/proyectos.js` | `tests/test_core_models.py`, `tests/test_usuarios.py` |
| REQ-02 | Gestión de Conexiones (escritura solo ADMIN; probar al guardar) | `/api/connections/` | `frontend/js/modulos/conexiones.js` | `tests/test_core_models.py`, `tests/test_usuarios.py` |
| REQ-03 | Gestión de Casos de Prueba | `/api/test-cases/` | `frontend/js/modulos/casos.js` | `tests/test_core_models.py` |
| REQ-04 | Agrupación de Suites | `/api/suites/` | `frontend/js/modulos/suites.js` | `tests/test_core_models.py` |
| REQ-05 | Ejecución Oracle y Rollback | `app/services/execution_service.py`, `app/engine/executor.py` | `frontend/js/modulos/ejecutor.js` | `tests/test_execution_engine.py`, `tests/test_oracle_integration.py` |
| REQ-06 | Historial legible: nombres, filtros (incluido «quién ejecutó») y detalle | `/api/history/` | `frontend/js/modulos/historial.js` | `tests/test_history_pagination.py`, `tests/test_historial_legible.py` |
| REQ-07 | Ingreso, sesión firmada con caducidad, límite de intentos | `app/api/users.py`, `app/security/auth.py`, middleware de `app/main.py` | `frontend/login.html`, `frontend/js/core/api.js` | `tests/test_auth.py`, `tests/test_usuarios.py` |
| REQ-08 | Dashboard de KPIs (tarjetas antiguas, ocultas) | `/api/history/` | `frontend/js/modulos/dashboard.js` | `tests/test_revision_final_frontend.py` |
| REQ-09 | Políticas por Ambiente (TEST, STAGING, PRODUCTION) | `app/security/sql_policy.py`, `app/engine/executor.py` | `frontend/index.html` (Ayuda) | `tests/test_environment_policies.py`, `tests/test_engine.py` |
| REQ-10 | Prueba rápida de un SELECT («Inicio») | `POST /api/execute/quick` | `frontend/js/modulos/inicio.js` | `tests/test_quick_execution.py` |
| REQ-11 | Panel «Uso del producto» (incluye uso por persona y origen) | `GET /api/usage/summary` | `frontend/js/modulos/uso.js` | `tests/test_phase4_usage.py`, `tests/test_usuarios.py` |
| REQ-12 | Excel (plantilla, importar, exportar; exportar por corrida) | `/api/excel/*`, `app/services/excel_io.py` | `frontend/js/modulos/excel.js` | `tests/test_phase4_excel.py`, `tests/test_comparacion_reporte.py` |
| REQ-13 | CLI con código de salida | `app/cli.py` | — | `tests/test_phase4_cli.py` |
| REQ-14 | Escenario de demostración (suites de ejemplo) | `POST /api/demo/scenario` | `frontend/js/modulos/inicio.js` | `tests/test_phase2_scalar_demo_targets.py`, `tests/test_oracle_phase2.py` (Oracle real, omitida sin variables) |
| REQ-15 | Usuarios y roles (ADMIN/TESTER), solicitud de cuenta con aprobación | `app/api/users.py`, `app/security/acceso.py`, `app/models/user.py` | `frontend/login.html`, `frontend/js/modulos/usuarios.js` | `tests/test_usuarios.py` |
| REQ-16 | «Ejecutado por» en cada ejecución | `execution_history.executed_by`, `app/api/executions.py` | `frontend/js/modulos/historial.js` | `tests/test_usuarios.py`, `tests/test_oracle_fase_c.py` (Oracle real) |
| REQ-17 | Comparación automática (sin elegir ROW_COUNT/valor) | `app/services/validacion_auto.py`, `app/models/schemas.py` | `frontend/js/modulos/inicio.js`, `frontend/js/modulos/casos.js` | `tests/test_validacion_auto.py`, `tests/test_oracle_fase_c.py` (Oracle real) |
| REQ-18 | Asistente de reglas | `/api/rules/*`, `app/services/rule_templates.py` | `frontend/js/modulos/inicio.js` | `tests/test_rule_templates.py` |
| REQ-19 | Demostración guiada | `POST /api/demo/guided` | `frontend/js/modulos/inicio.js` | `tests/test_guided_demo.py`, `tests/test_oracle_fase_c.py` (Oracle real) |
| REQ-20 | Analizar una tabla y guardar las reglas como suite | `/api/analysis/*`, `app/services/analisis_tabla.py` | `frontend/js/modulos/analisis.js` | `tests/test_analisis_tabla.py`, `tests/test_oracle_fase_c.py` (Oracle real) |
| REQ-21 | Comparar con la ejecución anterior y corridas de una suite | `app/services/comparacion.py`, `GET /api/history/runs` | `frontend/js/modulos/ejecutor.js`, `frontend/js/modulos/suites.js` | `tests/test_comparacion_reporte.py`, `tests/test_oracle_fase_c.py` (Oracle real) |
| REQ-22 | Reporte descargable de una corrida (HTML) | `GET /api/history/runs/{run_id}/report`, `app/services/reporte_corrida.py` | `frontend/js/modulos/ejecutor.js`, `frontend/js/modulos/historial.js` | `tests/test_comparacion_reporte.py` |
| REQ-23 | Migraciones de la base interna (ida y vuelta) | `alembic/versions/` | — | `tests/test_migraciones_ida_vuelta.py`, `tests/test_phase4_usage.py` |
