<!-- GENERADO por scripts/docs/gen_docs.py. No editar a mano: edite el código o descripciones_datos.py y vuelva a ejecutarlo. -->


# Referencia del código

Clases, métodos y propiedades generados con *mkdocstrings* a partir de los docstrings y las anotaciones del código de `app/`. Solo se documenta Python; el frontend (JavaScript) no está incluido.

| Módulo | Descripción |
| --- | --- |
| [`app.api.analysis`](api_analysis.md) | Analizar una tabla: perfila una tabla de la base objetivo con una conexión guardada y propone reglas; después guarda las elegidas |
| [`app.api.connections`](api_connections.md) | Endpoints REST para la gestión de Perfiles de Conexión Oracle (sin persistencia de contraseñas). |
| [`app.api.demo`](api_demo.md) | Escenario de demostración: crea los casos y suites de ejemplo en un proyecto y, si se pide, los ejecuta de principio a fin. |
| [`app.api.excel`](api_excel.md) | Endpoints de la integración con Excel (.xlsx). Ver app/services/excel_io.py para las reglas y la seguridad. |
| [`app.api.executions`](api_executions.md) | Router de Ejecución de Pruebas SQL desacoplado utilizando el Servicio Centralizado de Ejecución. |
| [`app.api.history`](api_history.md) | Endpoints REST para la consulta del Historial de Ejecuciones. |
| [`app.api.projects`](api_projects.md) | Endpoints REST para la gestión de Proyectos. |
| [`app.api.rules`](api_rules.md) | Asistente de reglas: catálogo de reglas comunes y generación del SELECT correspondiente. No se conecta a Oracle ni guarda nada. |
| [`app.api.suites`](api_suites.md) | Endpoints REST para las Suites de Pruebas. |
| [`app.api.test_cases`](api_test_cases.md) | Endpoints REST para la gestión de Casos de Prueba SQL. |
| [`app.api.usage`](api_usage.md) | Dashboard de utilización: métricas de uso calculadas a partir de datos persistidos. |
| [`app.api.users`](api_users.md) | Ingreso, solicitud de cuenta y administración de usuarios. |
| [`app.cli`](cli.md) | CLI del Framework de pruebas SQL: ejecutar casos y suites desde la terminal o desde un flujo de CI y obtener un |
| [`app.core.database`](core_database.md) |  |
| [`app.core.logs`](core_logs.md) | Registro (logs) de la aplicación: una línea por evento, a la salida estándar (Docker la recoge con `docker logs`). |
| [`app.engine.executor`](engine_executor.md) | Módulo de ejecución SQL para el Framework de Pruebas. |
| [`app.engine.validator`](engine_validator.md) | Módulo de validación para el Framework de Pruebas. |
| [`app.main`](main.md) |  |
| [`app.models.connection`](models_connection.md) | Modelo de base de datos para Perfiles de Conexión Oracle (sin columna de contraseña). |
| [`app.models.history`](models_history.md) | Modelo de base de datos para registrar la trazabilidad completa de las ejecuciones. |
| [`app.models.project`](models_project.md) | Modelo de base de datos para Proyectos. |
| [`app.models.schemas`](models_schemas.md) |  |
| [`app.models.suite`](models_suite.md) | Modelo de base de datos para las Suites de Pruebas. |
| [`app.models.test_case`](models_test_case.md) | Modelo de base de datos para Casos de Prueba SQL. |
| [`app.models.usage`](models_usage.md) | Eventos de uso del producto que no son ejecuciones (p. ej. importar o exportar Excel). |
| [`app.models.user`](models_user.md) | Usuarios de la aplicación (base interna SQLite). |
| [`app.security.acceso`](security_acceso.md) | Dependencias de FastAPI para el control de acceso por usuario y rol. |
| [`app.security.auth`](security_auth.md) | Seguridad del acceso: contraseñas, sesiones y límites de intentos. |
| [`app.security.sql_policy`](security_sql_policy.md) | Módulo de políticas SQL para el Framework de Pruebas. |
| [`app.security.target_policy`](security_target_policy.md) | Política de destinos para las conexiones Oracle de la aplicación. |
| [`app.services.analisis_tabla`](services_analisis_tabla.md) | Analizar una tabla: lee la estructura de una tabla Oracle y cómo están hoy sus datos, y propone reglas de calidad listas para |
| [`app.services.comparacion`](services_comparacion.md) | Comparar con la ejecución anterior: para cada caso, qué resultado tuvo la vez anterior y si ahora empeoró («nuevo fallo») o se |
| [`app.services.demo_scenario`](services_demo_scenario.md) | Escenario de demostración: reglas de calidad de datos sobre la tabla FRAMEWORK_TEST_ITEMS. |
| [`app.services.excel_io`](services_excel_io.md) | Integración con Excel: plantilla, importación y exportación de casos, y exportación de resultados (.xlsx). |
| [`app.services.execution_service`](services_execution_service.md) | Servicio centralizado de ejecución y validación de pruebas SQL. |
| [`app.services.project_service`](services_project_service.md) | Servicio para inicializar y gestionar proyectos en la base de datos interna. |
| [`app.services.reporte_corrida`](services_reporte_corrida.md) | Reporte de una corrida: página HTML autónoma (sin JavaScript ni recursos externos) con el resultado de cada caso, la comparación |
| [`app.services.rule_templates`](services_rule_templates.md) | Asistente de reglas: convierte una regla en lenguaje común («ninguna fila con la columna X vacía») en la consulta SELECT, el tipo |
| [`app.services.usage_service`](services_usage_service.md) | Métricas de uso del producto, calculadas SOLO con datos persistidos en la base interna: |
| [`app.services.validacion_auto`](services_validacion_auto.md) | Validación automática: la persona escribe la consulta y lo que espera, y la aplicación decide cómo compararlo. |
