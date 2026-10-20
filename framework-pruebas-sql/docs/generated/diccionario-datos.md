<!-- GENERADO por scripts/docs/gen_docs.py. No editar a mano: edite el código o descripciones_datos.py y vuelva a ejecutarlo. -->


# Diccionario de datos

Este diccionario se genera desde los modelos SQLAlchemy (`app/models/*.py`) y el changelog de Liquibase (`infra/oracle/liquibase/changelog/`). Hay **dos bases distintas**:

| Base | Motor | Qué guarda | Versionada con | Sección |
| --- | --- | --- | --- | --- |
| **Interna de la aplicación** | SQLite (`FRAMEWORK_DB_URL`) | Metadatos: proyectos, perfiles de conexión (sin contraseña), casos, suites, historial, eventos de uso | Alembic (`alembic/versions/`) | 1 |
| **Objetivo** | Oracle (la que se comprueba) | Los datos del usuario sobre los que se ejecutan los casos. La aplicación **no** es dueña de esos datos; solo se versiona con Liquibase el objeto de la **demostración** | Liquibase (`infra/oracle/liquibase/`) | 2 |

## 1. Base interna (SQLite)

Las fechas `created_at/updated_at` de `test_cases` y `test_suites` se guardan en UTC **sin** zona horaria; las demás tablas usan UTC con zona horaria. Es una inconsistencia real del código, no un error de este documento.

### `projects`

Proyecto: agrupa perfiles de conexión, casos, suites e historial. Es el filtro principal de la interfaz.

| Columna | Tipo | Nulo | Clave | Por defecto (en la aplicación) | Índice | Descripción |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | INTEGER | no | PK |  |  | Identificador numérico del proyecto. |
| `name` | VARCHAR | no | único |  | sí | Nombre del proyecto. Único en toda la aplicación. |
| `description` | VARCHAR | sí |  |  |  | Descripción libre (opcional). |
| `created_at` | DATETIME | sí |  | (función de la aplicación: fecha y hora actual UTC) |  | Fecha y hora de creación (UTC, con zona horaria). |
| `updated_at` | DATETIME | sí |  | (función de la aplicación: fecha y hora actual UTC) |  | Fecha y hora de la última modificación (UTC, con zona horaria). |

### `connection_profiles`

Perfil de conexión a la base objetivo (Oracle): dónde y con qué usuario conectarse. NO guarda contraseñas.

| Columna | Tipo | Nulo | Clave | Por defecto (en la aplicación) | Índice | Descripción |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | INTEGER | no | PK |  |  | Identificador del perfil. |
| `project_id` | INTEGER | no | FK → projects.id |  |  | Proyecto al que pertenece el perfil. Un perfil no se usa en otro proyecto. |
| `name` | VARCHAR | no |  |  | sí | Nombre visible del perfil. |
| `engine` | VARCHAR | no |  | 'ORACLE' |  | Motor de la base objetivo. Hoy solo se acepta ORACLE. |
| `host` | VARCHAR | no |  |  |  | Servidor de la base objetivo. Solo caracteres de nombre de host (se valida); puede restringirse con ORACLE_ALLOWED_HOSTS. |
| `port` | INTEGER | no |  | 1521 |  | Puerto de escucha (1521 por defecto). |
| `service_name` | VARCHAR | no |  |  |  | Service name de Oracle (por ejemplo FREEPDB1). |
| `username` | VARCHAR | no |  |  |  | Usuario de Oracle con el que se conecta. La contraseña no se almacena: se pide en cada ejecución. |
| `environment_type` | VARCHAR | no |  | 'TEST' |  | Ambiente del perfil: TEST, STAGING o PRODUCTION. Determina qué sentencias se permiten y si se ocultan las filas. |
| `created_at` | DATETIME | sí |  | (función de la aplicación: fecha y hora actual UTC) |  | Fecha y hora de creación (UTC, con zona horaria). |
| `updated_at` | DATETIME | sí |  | (función de la aplicación: fecha y hora actual UTC) |  | Fecha y hora de la última modificación (UTC, con zona horaria). |

### `test_cases`

Caso de prueba: una sentencia SQL, el tipo de validación y el resultado esperado.

| Columna | Tipo | Nulo | Clave | Por defecto (en la aplicación) | Índice | Descripción |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | INTEGER | no | PK |  |  | Identificador del caso. |
| `project_id` | INTEGER | no | FK → projects.id | 1 |  | Proyecto al que pertenece el caso. |
| `name` | VARCHAR | no |  |  | sí | Nombre del caso. En la importación desde Excel el nombre identifica al caso dentro del proyecto. |
| `description` | VARCHAR | sí |  |  |  | Descripción libre (opcional). |
| `sql_query` | TEXT | no |  |  |  | Sentencia SQL a ejecutar contra la base objetivo (una sola sentencia; pasa por la política de SQL). |
| `expected_result` | VARCHAR | no |  |  |  | Resultado esperado como texto. Significado según validation_type: entero (ROW_COUNT), valor de la primera columna (SCALAR_VALUE) o true/false (EXISTS). |
| `validation_type` | VARCHAR | no |  | 'ROW_COUNT' |  | Tipo de comparación: ROW_COUNT (cantidad de filas), SCALAR_VALUE (valor de una única fila) o EXISTS (hay filas o no). |
| `created_at` | DATETIME | sí |  | (función de la aplicación: fecha y hora actual UTC) |  | Fecha y hora de creación (UTC, sin zona horaria: se guarda con datetime.utcnow). |
| `updated_at` | DATETIME | sí |  | (función de la aplicación: fecha y hora actual UTC) |  | Fecha y hora de la última modificación (UTC, sin zona horaria). |

### `test_suites`

Suite: agrupación de casos del mismo proyecto que se ejecutan juntos.

| Columna | Tipo | Nulo | Clave | Por defecto (en la aplicación) | Índice | Descripción |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | INTEGER | no | PK |  |  | Identificador de la suite. |
| `project_id` | INTEGER | no | FK → projects.id | 1 |  | Proyecto al que pertenece la suite. Sus casos deben ser del mismo proyecto. |
| `name` | VARCHAR | no |  |  | sí | Nombre de la suite. |
| `description` | VARCHAR | sí |  |  |  | Descripción libre (opcional). |
| `created_at` | DATETIME | sí |  | (función de la aplicación: fecha y hora actual UTC) |  | Fecha y hora de creación (UTC, sin zona horaria). |
| `updated_at` | DATETIME | sí |  | (función de la aplicación: fecha y hora actual UTC) |  | Fecha y hora de la última modificación (UTC, sin zona horaria). |

### `usage_events`

Eventos de uso que no son ejecuciones (importar o exportar Excel). Alimenta la sección «Otras acciones» del dashboard.

| Columna | Tipo | Nulo | Clave | Por defecto (en la aplicación) | Índice | Descripción |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | INTEGER | no | PK |  |  | Identificador del evento. |
| `event_type` | VARCHAR | no |  |  | sí | Tipo de evento (p. ej. importación o exportación de Excel). |
| `project_id` | INTEGER | sí | FK → projects.id |  |  | Proyecto asociado (opcional). |
| `source` | VARCHAR | sí |  |  |  | Origen del evento: UI, CLI o API. |
| `detail` | VARCHAR(500) | sí |  |  |  | Detalle breve (máximo 500 caracteres). No guarda contenido de archivos ni datos personales. |
| `created_at` | DATETIME | sí |  | (función de la aplicación: fecha y hora actual UTC) | sí | Fecha y hora del evento (UTC, con zona horaria). |

### `execution_history`

Historial: evidencia de cada ejecución (qué se ejecutó, qué se esperaba, qué se obtuvo, estado y duración).

| Columna | Tipo | Nulo | Clave | Por defecto (en la aplicación) | Índice | Descripción |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | INTEGER | no | PK |  |  | Identificador del registro (crece con cada ejecución; el historial se lista de más reciente a más antiguo). |
| `project_id` | INTEGER | no | FK → projects.id | 1 |  | Proyecto en el que se ejecutó. |
| `test_case_id` | INTEGER | sí | FK → test_cases.id |  |  | Caso ejecutado. Vacío en las pruebas rápidas de «Inicio», que no son un caso guardado. |
| `suite_id` | INTEGER | sí | FK → test_suites.id |  |  | Suite desde la que se ejecutó. Vacío si fue un caso suelto. |
| `connection_profile_id` | INTEGER | sí | FK → connection_profiles.id |  |  | Perfil de conexión usado (las ejecuciones exigen un perfil guardado; la CLI crea uno si se le dan host, servicio y usuario). |
| `status` | VARCHAR | no |  |  | sí | Resultado: PASS (coincide con lo esperado), FAIL (se ejecutó pero no coincide) o ERROR (no se pudo ejecutar o evaluar). |
| `executed_at` | DATETIME | sí |  | (función de la aplicación: fecha y hora actual UTC) | sí | Fecha y hora de la ejecución (UTC, con zona horaria). |
| `duration_ms` | FLOAT | no |  |  |  | Duración de la ejecución, en milisegundos, medida por la aplicación. |
| `statement_type` | VARCHAR | sí |  |  |  | Tipo de sentencia detectado (SELECT, INSERT, UPDATE, DELETE, o el rechazado, p. ej. DROP). |
| `executed_sql` | TEXT | no |  |  |  | SQL que se ejecutó (copia en el momento de la ejecución). |
| `validation_type` | VARCHAR | sí |  |  |  | Tipo de validación aplicado (copia en el momento de la ejecución). |
| `expected_result` | VARCHAR | sí |  |  |  | Resultado esperado (copia en el momento de la ejecución). |
| `actual_result` | TEXT | sí |  |  |  | Evidencia del resultado obtenido, serializada como texto y truncada a 2000 caracteres. En PRODUCTION solo guarda la cantidad de filas. |
| `rowcount` | INTEGER | sí |  | 0 |  | Filas devueltas (SELECT) o afectadas (INSERT/UPDATE/DELETE). |
| `rollback_applied` | BOOLEAN | sí |  | False |  | Verdadero si, tras un INSERT/UPDATE/DELETE, el rollback se ejecutó sin error. No prueba por sí solo que Oracle no haya conservado efectos (secuencias, transacciones autónomas). |
| `rollback_error` | TEXT | sí |  |  |  | Mensaje si el rollback falló (en PRODUCTION se reemplaza por un texto genérico). |
| `error_message` | TEXT | sí |  |  |  | Motivo del ERROR (en PRODUCTION se oculta salvo los rechazos de política). |
| `trigger_source` | VARCHAR | sí |  |  | sí | Origen: UI (módulos Casos/Suites), INICIO (recorrido guiado), CLI o GITHUB_ACTIONS. Vacío en registros anteriores a la Fase 4. |
| `run_id` | VARCHAR | sí |  |  | sí | Identificador de corrida: todas las filas de una misma ejecución de suite o de la CLI lo comparten. |

### `suite_test_case`

Tabla de asociación muchos-a-muchos entre suites y casos.

| Columna | Tipo | Nulo | Clave | Por defecto (en la aplicación) | Índice | Descripción |
| --- | --- | --- | --- | --- | --- | --- |
| `suite_id` | INTEGER | no | PK, FK → test_suites.id |  |  | Suite que contiene el caso. |
| `test_case_id` | INTEGER | no | PK, FK → test_cases.id |  |  | Caso incluido en la suite. |

### Relaciones y borrado en cascada

| Desde | Hacia | Cascada de borrado (ORM) |
| --- | --- | --- |
| ConnectionProfile | ExecutionHistory | no (se rechaza o queda dependiente) |
| Project | ConnectionProfile | sí |
| Project | ExecutionHistory | no (se rechaza o queda dependiente) |
| Project | TestCase | sí |
| Project | TestSuite | sí |
| TestCase | ExecutionHistory | no (se rechaza o queda dependiente) |
| TestSuite | ExecutionHistory | no (se rechaza o queda dependiente) |

El borrado en cascada solo lo hace el ORM al eliminar un proyecto; los endpoints de borrado rechazan eliminar proyectos, suites o casos con dependencias (ver `docs/seguridad.md`).

### Dominios de valores

| Campo | Valores | Fuente |
| --- | --- | --- |
| `test_cases.validation_type` | `ROW_COUNT`, `EXISTS`, `SCALAR_VALUE` | `ValidationTypeEnum` en `app/models/schemas.py` |
| `connection_profiles.environment_type` | `TEST`, `STAGING`, `PRODUCTION` | `EnvironmentTypeEnum` en `app/models/schemas.py` |
| `execution_history.status` | `PASS`, `FAIL`, `ERROR` | `app/api/history.py` (filtro) y `execution_service.py` |
| `execution_history.trigger_source` | `CLI`, `GITHUB_ACTIONS`, `INICIO`, `SIN_REGISTRAR`, `UI` (vacío = anterior a la Fase 4) | `ORIGENES` en `app/services/usage_service.py` |
| `usage_events.event_type` | `excel_export_cases`, `excel_export_results`, `excel_import_cases`, `excel_template`, `excel_validate_cases` | llamadas a `record_event` en `app/` |

## 2. Objetos Oracle de la demostración (esquema `FRAMEWORK_TEST`)

Solo lo que versiona Liquibase. Son datos de **ejemplo** para las reglas de calidad de la demostración; la aplicación puede apuntar a cualquier otra base Oracle y no conoce su esquema.

### `FRAMEWORK_TEST_ITEMS`

Tabla de la demostración sobre la que se ejecutan las reglas de calidad (5 productos de ejemplo).

| Columna | Definición Oracle | Descripción |
| --- | --- | --- |
| `ID` | `NUMBER PRIMARY KEY` | Identificador del producto (clave primaria). |
| `NAME` | `VARCHAR2(100) NOT NULL` | Nombre del producto (obligatorio). |
| `ACTIVE` | `NUMBER(1) DEFAULT 1 NOT NULL` | 1 = activo, 0 = inactivo (por defecto 1). Una regla de la demostración comprueba que solo valga 0 o 1. |

| Objeto | Tipo | Definición | Changeset (archivo) | Descripción |
| --- | --- | --- | --- | --- |
| `IX_FW_ITEMS_ACTIVE` | INDEX | `ON FRAMEWORK_TEST_ITEMS (ACTIVE)` | `002_indice_active.sql` | Índice por ACTIVE sobre FRAMEWORK_TEST_ITEMS. |
| `V_FW_ITEMS_ACTIVOS` | VIEW | `AS SELECT ID, NAME FROM FRAMEWORK_TEST_ITEMS WHERE ACTIVE = 1` | `003_vista_items_activos.sql` | Vista con los productos activos (ID, NAME). |

La prueba `test_oracle_phase2.py` crea además, solo en un Oracle desechable, la tabla `FW_OWNER.CANARY` para comprobar el rechazo de `DROP`; no forma parte del esquema versionado.
