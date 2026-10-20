<!-- GENERADO por scripts/docs/gen_docs.py. No editar a mano: edite el código o descripciones_datos.py y vuelva a ejecutarlo. -->


# Endpoints de la API

Leídos del esquema OpenAPI de la aplicación FastAPI (`app.main:app`, versión 2.0.0). Total: **38** operaciones documentadas. No incluye `/ui/` (archivos estáticos), `/login` (página) ni `/` (redirección).

La documentación interactiva está en `/docs` cuando la aplicación está en marcha.

| Grupo | Método | Ruta | Resumen | Descripción (primera línea del docstring) |
| --- | --- | --- | --- | --- |
| Autenticación | POST | `/api/login` | Login |  |
| Autenticación | POST | `/api/logout` | Logout |  |
| Casos de Prueba | GET | `/api/test-cases/` | Read Test Cases | Obtiene la lista de casos de prueba guardados con paginación y filtro de proyecto. |
| Casos de Prueba | POST | `/api/test-cases/` | Create Test Case | Crea un nuevo caso de prueba asignado a un proyecto. |
| Casos de Prueba | DELETE | `/api/test-cases/{test_case_id}` | Delete Test Case | Elimina un caso de prueba de la base de datos. |
| Casos de Prueba | GET | `/api/test-cases/{test_case_id}` | Read Test Case | Obtiene un caso de prueba específico por su ID. |
| Casos de Prueba | PUT | `/api/test-cases/{test_case_id}` | Update Test Case | Actualiza la información de un caso de prueba. |
| Escenario de demostración | POST | `/api/demo/scenario` | Create Demo Scenario | Carga (de forma idempotente) las suites de demostración en el proyecto indicado. |
| Excel | GET | `/api/excel/cases/export` | Export Cases |  |
| Excel | POST | `/api/excel/cases/import` | Import Cases | Importa casos desde un .xlsx enviado como cuerpo binario de la petición (sin multipart). |
| Excel | GET | `/api/excel/results/export` | Export Results |  |
| Excel | GET | `/api/excel/template` | Download Template | Plantilla de casos con instrucciones, ejemplos y lista desplegable de validaciones. |
| Historial de Ejecuciones | GET | `/api/history/` | Get History | Obtiene el historial de ejecuciones guardadas admitiendo paginación |
| Historial de Ejecuciones | GET | `/api/history/{history_id}` | Get History Detail | Obtiene los detalles de un registro de historial específico. |
| Motor de Ejecución | POST | `/api/execute/quick` | Run Quick Check | Prueba rápida del recorrido guiado: ejecuta UN SELECT contra un perfil de |
| Motor de Ejecución | POST | `/api/execute/raw` | Execute Target Sql | Ejecuta una sentencia SQL aislada, sobre un perfil guardado, aplicando las políticas del ambiente. |
| Motor de Ejecución | POST | `/api/execute/suite/{suite_id}` | Run Test Suite | Ejecuta en ráfaga todos los casos de prueba de una Suite utilizando una conexión única. |
| Motor de Ejecución | POST | `/api/execute/test-case/{test_case_id}` | Run Test Case | Orquestador Principal: Recupera un caso de prueba guardado y lo ejecuta |
| Perfiles de Conexión | GET | `/api/connections/` | Get Connection Profiles | Obtiene la lista de perfiles de conexión filtrados opcionalmente por proyecto. |
| Perfiles de Conexión | POST | `/api/connections/` | Create Connection Profile | Crea un nuevo perfil de conexión Oracle para un proyecto (sin contraseña). |
| Perfiles de Conexión | DELETE | `/api/connections/{connection_id}` | Delete Connection Profile | Elimina un perfil de conexión. |
| Perfiles de Conexión | GET | `/api/connections/{connection_id}` | Get Connection Profile | Obtiene un perfil de conexión por su ID. |
| Perfiles de Conexión | PUT | `/api/connections/{connection_id}` | Update Connection Profile | Actualiza la información de un perfil de conexión. |
| Perfiles de Conexión | POST | `/api/connections/{connection_id}/test` | Test Connection Profile | Prueba la conectividad de un perfil Oracle usando la contraseña enviada en el cuerpo. |
| Proyectos | GET | `/api/projects/` | Get Projects | Obtiene la lista de proyectos con paginación estricta. |
| Proyectos | POST | `/api/projects/` | Create Project | Crea un nuevo proyecto. |
| Proyectos | DELETE | `/api/projects/{project_id}` | Delete Project | Elimina un proyecto únicamente si no tiene datos asociados. |
| Proyectos | GET | `/api/projects/{project_id}` | Get Project | Obtiene los detalles de un proyecto por su ID. |
| Proyectos | PUT | `/api/projects/{project_id}` | Update Project | Actualiza la información de un proyecto existente. |
| Salud | GET | `/health` | Health Check |  |
| Suites de Pruebas | GET | `/api/suites/` | Get All Suites | Obtiene todas las suites registradas con paginación y filtro de proyecto. |
| Suites de Pruebas | POST | `/api/suites/` | Create Suite | Crea una nueva Suite de Pruebas. |
| Suites de Pruebas | DELETE | `/api/suites/{suite_id}` | Delete Suite | Elimina una suite de prueba. |
| Suites de Pruebas | GET | `/api/suites/{suite_id}` | Get Suite Detail | Obtiene el detalle de una suite por su ID. |
| Suites de Pruebas | PUT | `/api/suites/{suite_id}` | Update Suite | Actualiza nombre y descripción de una suite. |
| Suites de Pruebas | DELETE | `/api/suites/{suite_id}/test-cases/{test_case_id}` | Remove Test Case From Suite | Retira un caso de una suite de forma controlada. |
| Suites de Pruebas | POST | `/api/suites/{suite_id}/test-cases/{test_case_id}` | Add Test Case To Suite | Vincula un Caso de Prueba a una Suite de Pruebas. |
| Uso del producto | GET | `/api/usage/summary` | Get Usage Summary | Resumen de uso: ejecuciones por fecha, resultados, casos y suites más usados, origen y eventos. |
