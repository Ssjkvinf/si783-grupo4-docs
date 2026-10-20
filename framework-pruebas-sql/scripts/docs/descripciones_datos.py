"""
Descripciones del diccionario de datos (texto escrito a mano; lo demás se genera desde el código).

Cada entrada se redactó leyendo `app/models/*.py`, `app/models/schemas.py` y `app/services/*.py`.
El generador FALLA si una columna del modelo no tiene descripción o si aquí sobra una columna que ya no existe:
así el diccionario no puede quedar desactualizado en silencio.

Clave: "tabla.columna". Todas las tablas de este archivo son de la base INTERNA (SQLite) de la aplicación.
"""

TABLAS = {
    "projects": "Proyecto: agrupa perfiles de conexión, casos, suites e historial. Es el filtro principal de la interfaz.",
    "connection_profiles": "Perfil de conexión a la base objetivo (Oracle): dónde y con qué usuario conectarse. NO guarda contraseñas.",
    "test_cases": "Caso de prueba: una sentencia SQL, el tipo de validación y el resultado esperado.",
    "test_suites": "Suite: agrupación de casos del mismo proyecto que se ejecutan juntos.",
    "suite_test_case": "Tabla de asociación muchos-a-muchos entre suites y casos.",
    "execution_history": "Historial: evidencia de cada ejecución (qué se ejecutó, qué se esperaba, qué se obtuvo, estado y duración).",
    "usage_events": "Eventos de uso que no son ejecuciones (importar o exportar Excel). Alimenta la sección «Otras acciones» del dashboard.",
}

COLUMNAS = {
    # --- projects
    "projects.id": "Identificador numérico del proyecto.",
    "projects.name": "Nombre del proyecto. Único en toda la aplicación.",
    "projects.description": "Descripción libre (opcional).",
    "projects.created_at": "Fecha y hora de creación (UTC, con zona horaria).",
    "projects.updated_at": "Fecha y hora de la última modificación (UTC, con zona horaria).",
    # --- connection_profiles
    "connection_profiles.id": "Identificador del perfil.",
    "connection_profiles.project_id": "Proyecto al que pertenece el perfil. Un perfil no se usa en otro proyecto.",
    "connection_profiles.name": "Nombre visible del perfil.",
    "connection_profiles.engine": "Motor de la base objetivo. Hoy solo se acepta ORACLE.",
    "connection_profiles.host": "Servidor de la base objetivo. Solo caracteres de nombre de host (se valida); puede restringirse con ORACLE_ALLOWED_HOSTS.",
    "connection_profiles.port": "Puerto de escucha (1521 por defecto).",
    "connection_profiles.service_name": "Service name de Oracle (por ejemplo FREEPDB1).",
    "connection_profiles.username": "Usuario de Oracle con el que se conecta. La contraseña no se almacena: se pide en cada ejecución.",
    "connection_profiles.environment_type": "Ambiente del perfil: TEST, STAGING o PRODUCTION. Determina qué sentencias se permiten y si se ocultan las filas.",
    "connection_profiles.created_at": "Fecha y hora de creación (UTC, con zona horaria).",
    "connection_profiles.updated_at": "Fecha y hora de la última modificación (UTC, con zona horaria).",
    # --- test_cases
    "test_cases.id": "Identificador del caso.",
    "test_cases.project_id": "Proyecto al que pertenece el caso.",
    "test_cases.name": "Nombre del caso. En la importación desde Excel el nombre identifica al caso dentro del proyecto.",
    "test_cases.description": "Descripción libre (opcional).",
    "test_cases.sql_query": "Sentencia SQL a ejecutar contra la base objetivo (una sola sentencia; pasa por la política de SQL).",
    "test_cases.expected_result": "Resultado esperado como texto. Significado según validation_type: entero (ROW_COUNT), valor de la primera columna (SCALAR_VALUE) o true/false (EXISTS).",
    "test_cases.validation_type": "Tipo de comparación: ROW_COUNT (cantidad de filas), SCALAR_VALUE (valor de una única fila) o EXISTS (hay filas o no).",
    "test_cases.created_at": "Fecha y hora de creación (UTC, sin zona horaria: se guarda con datetime.utcnow).",
    "test_cases.updated_at": "Fecha y hora de la última modificación (UTC, sin zona horaria).",
    # --- test_suites
    "test_suites.id": "Identificador de la suite.",
    "test_suites.project_id": "Proyecto al que pertenece la suite. Sus casos deben ser del mismo proyecto.",
    "test_suites.name": "Nombre de la suite.",
    "test_suites.description": "Descripción libre (opcional).",
    "test_suites.created_at": "Fecha y hora de creación (UTC, sin zona horaria).",
    "test_suites.updated_at": "Fecha y hora de la última modificación (UTC, sin zona horaria).",
    # --- suite_test_case
    "suite_test_case.suite_id": "Suite que contiene el caso.",
    "suite_test_case.test_case_id": "Caso incluido en la suite.",
    # --- execution_history
    "execution_history.id": "Identificador del registro (crece con cada ejecución; el historial se lista de más reciente a más antiguo).",
    "execution_history.project_id": "Proyecto en el que se ejecutó.",
    "execution_history.test_case_id": "Caso ejecutado. Vacío en las pruebas rápidas de «Inicio», que no son un caso guardado.",
    "execution_history.suite_id": "Suite desde la que se ejecutó. Vacío si fue un caso suelto.",
    "execution_history.connection_profile_id": "Perfil de conexión usado (las ejecuciones exigen un perfil guardado; la CLI crea uno si se le dan host, servicio y usuario).",
    "execution_history.status": "Resultado: PASS (coincide con lo esperado), FAIL (se ejecutó pero no coincide) o ERROR (no se pudo ejecutar o evaluar).",
    "execution_history.executed_at": "Fecha y hora de la ejecución (UTC, con zona horaria).",
    "execution_history.duration_ms": "Duración de la ejecución, en milisegundos, medida por la aplicación.",
    "execution_history.statement_type": "Tipo de sentencia detectado (SELECT, INSERT, UPDATE, DELETE, o el rechazado, p. ej. DROP).",
    "execution_history.executed_sql": "SQL que se ejecutó (copia en el momento de la ejecución).",
    "execution_history.validation_type": "Tipo de validación aplicado (copia en el momento de la ejecución).",
    "execution_history.expected_result": "Resultado esperado (copia en el momento de la ejecución).",
    "execution_history.actual_result": "Evidencia del resultado obtenido, serializada como texto y truncada a 2000 caracteres. En PRODUCTION solo guarda la cantidad de filas.",
    "execution_history.rowcount": "Filas devueltas (SELECT) o afectadas (INSERT/UPDATE/DELETE).",
    "execution_history.rollback_applied": "Verdadero si, tras un INSERT/UPDATE/DELETE, el rollback se ejecutó sin error. No prueba por sí solo que Oracle no haya conservado efectos (secuencias, transacciones autónomas).",
    "execution_history.rollback_error": "Mensaje si el rollback falló (en PRODUCTION se reemplaza por un texto genérico).",
    "execution_history.error_message": "Motivo del ERROR (en PRODUCTION se oculta salvo los rechazos de política).",
    "execution_history.trigger_source": "Origen: UI (módulos Casos/Suites), INICIO (recorrido guiado), CLI o GITHUB_ACTIONS. Vacío en registros anteriores a la Fase 4.",
    "execution_history.run_id": "Identificador de corrida: todas las filas de una misma ejecución de suite o de la CLI lo comparten.",
    # --- usage_events
    "usage_events.id": "Identificador del evento.",
    "usage_events.event_type": "Tipo de evento (p. ej. importación o exportación de Excel).",
    "usage_events.project_id": "Proyecto asociado (opcional).",
    "usage_events.source": "Origen del evento: UI, CLI o API.",
    "usage_events.detail": "Detalle breve (máximo 500 caracteres). No guarda contenido de archivos ni datos personales.",
    "usage_events.created_at": "Fecha y hora del evento (UTC, con zona horaria).",
}

# Objetos Oracle de la demostración (versionados con Liquibase; NO son de la SQLite interna).
ORACLE_TABLAS = {
    "FRAMEWORK_TEST_ITEMS": "Tabla de la demostración sobre la que se ejecutan las reglas de calidad (5 productos de ejemplo).",
}
ORACLE_COLUMNAS = {
    "FRAMEWORK_TEST_ITEMS.ID": "Identificador del producto (clave primaria).",
    "FRAMEWORK_TEST_ITEMS.NAME": "Nombre del producto (obligatorio).",
    "FRAMEWORK_TEST_ITEMS.ACTIVE": "1 = activo, 0 = inactivo (por defecto 1). Una regla de la demostración comprueba que solo valga 0 o 1.",
}
ORACLE_OTROS = {
    "IX_FW_ITEMS_ACTIVE": "Índice por ACTIVE sobre FRAMEWORK_TEST_ITEMS.",
    "V_FW_ITEMS_ACTIVOS": "Vista con los productos activos (ID, NAME).",
}
