# FD03 — Especificación de requerimientos (fuente corregida, versión 1.1 propuesta)

> Fuente editable para reemplazar los textos del PDF `FD03_Informe_SRS_FrameworkSQL.pdf`, que **no se modificó**. Pegar cada sección en la plantilla Word del curso conservando estilos, numeración y «Fuente: Elaboración Propia». Las figuras se regeneran (ver `LEEME.md`).
> Control de versiones sugerido: 1.1 · Hecha por KHC, GZP · Revisada por GZP, KHC · Fecha: la de la entrega · Motivo: «Corrección de contenido ajeno al proyecto y actualización al producto implementado».

## Introducción

Este documento especifica los requisitos de una aplicación web que permite **repetir comprobaciones SQL sobre una base Oracle y conservar la evidencia de cada ejecución**. Una persona registra una conexión (sin contraseña), define casos con una sentencia SQL y un resultado esperado, los agrupa en suites, los ejecuta y consulta el historial. La aplicación aplica reglas distintas según el ambiente de la conexión (TEST, STAGING, PRODUCTION) y **procura** que los cambios de datos permitidos no queden confirmados; no sustituye los permisos mínimos de la cuenta Oracle.

Se distinguen siempre dos bases de datos: la **base interna** (SQLite, guarda proyectos, perfiles, casos, suites, historial y eventos de uso) y la **base objetivo** (Oracle, la que se comprueba).

## I. Contexto académico del proyecto

| Elemento | Contenido |
| --- | --- |
| Tipo | Proyecto del curso Calidad y Pruebas de Software, Universidad Privada de Tacna, EPIS |
| Docente | Ing. Patrick Cuadros Quiroga |
| Integrantes | Kevin Elvis Hinojosa Calloapaza (2023078335), Gerald Deybi Zevallos Pinto (2023078691) |
| Origen | Proyecto elegido entre los propuestos en clase |
| Organización cliente | **No existe** (FD01, FD02, FD06) |

*(Se eliminan «Nombre de la Empresa», «Visión», «Misión» y «Organigrama» de la UPT.)*

## II. Visionamiento

### 1. Descripción del problema

Quien modifica una consulta o una operación sobre datos Oracle necesita comprobar que sigue dando lo esperado. Si la comprobación queda aislada, es difícil repetirla, compararla con ejecuciones anteriores y conservar qué se ejecutó. Es una **necesidad potencial**; no se observó en una organización (ver `docs/problema-y-objetivos.md`).

### 2. Objetivos de negocio (de la solución)

- Facilitar que una persona repita comprobaciones SQL sobre Oracle y conserve la evidencia de cada ejecución. *[Meta]*
- Reducir el esfuerzo de repetir y comparar comprobaciones. *[Hipótesis; no medida]*
- Aplicar reglas distintas según el ambiente de conexión.

### 3. Objetivos de diseño

- Registrar casos de prueba SQL y ejecutarlos contra un perfil de conexión guardado.
- Comparar lo obtenido con lo esperado con tres validaciones (`ROW_COUNT`, `SCALAR_VALUE`, `EXISTS`) y clasificar PASS, FAIL o ERROR.
- Rechazar antes de conectar las sentencias no permitidas (DDL, TCL, PL/SQL, varias sentencias) y aplicar las reglas del ambiente.
- Intentar revertir (`ROLLBACK`) los INSERT/UPDATE/DELETE permitidos en TEST y STAGING.
- Conservar un historial consultable y mostrar el uso del producto.
- Ofrecer integraciones: Excel (importar/exportar casos y resultados) y línea de comandos con código de salida.

### 4. Alcance

**Incluido (verificable en el repositorio):** proyectos; perfiles de conexión Oracle sin contraseña; casos y suites; ejecución individual, de suite y rápida (solo SELECT); historial con origen de ejecución; panel «Uso del producto»; Excel; CLI; migraciones de la base interna.
**Excluido:** otros motores, Oracle anterior a 12.1 (modo Thick no implementado ni probado), usuarios individuales con roles, pruebas de carga o de vulnerabilidades, auditoría general de calidad de datos, alta disponibilidad, certificación de seguridad.
**Condición:** una cuenta Oracle de privilegio mínimo; el análisis de la sentencia es léxico (`sqlparse` es no validador) y el rollback no cubre secuencias, transacciones autónomas ni efectos fuera de la transacción.

### 5. Viabilidad

**5.1 Técnica.** La aplicación es Python 3.12 + FastAPI, con SQLite interna (SQLAlchemy y Alembic), `python-oracledb` en modo Thin (Oracle 12.1 o posterior) y una interfaz HTML/JavaScript servida por la misma aplicación. Se usa desde un navegador. El despliegue demostrativo descrito en FD01 usa Docker Compose (Caddy, API, Oracle Free). Los requisitos de hardware de un «laboratorio» no forman parte del sistema.
**5.2 Económica.** Ver FD01 §7–§9. Son escenarios de planificación, no resultados.

### 6. Fuentes consultadas *(reemplaza «Información obtenida del levantamiento de información»)*

No se realizaron entrevistas, encuestas ni observación en una organización. Se consultaron: términos de referencia de la Contraloría General de la República (2024) y del Ministerio del Ambiente (s. f.); la documentación de Oracle sobre transacciones y sobre pruebas unitarias de SQL Developer; la documentación de sqlparse y de python-oracledb; y el código del repositorio.

## III. Análisis de procesos

Proceso actual (hipotético): localizar la consulta → ejecutarla → comparar a mano → guardar la evidencia aparte → repetir cuando cambia algo.
Proceso propuesto: «Inicio» (conectar, escribir o elegir un SELECT, indicar lo esperado, ejecutar) → resultado explicado → guardar como caso → agrupar en suite → repetir → revisar historial y panel de uso. *(Rehacer el diagrama de actividades con estos pasos; el actual habla de «reactivos».)*

## IV. Requerimientos

### a) Funcionales

| Código | Requerimiento | Descripción | Evidencia |
| --- | --- | --- | --- |
| RF‑01 | Acceso | El sistema exige una credencial de aplicación (configurable por variables de entorno) antes de dar acceso a la interfaz y a la API. No hay usuarios individuales. | `app/main.py`, `tests/test_auth.py` |
| RF‑02 | Gestionar proyecto | Crear, editar, listar y eliminar proyectos (se rechaza eliminar con dependencias) y elegir un proyecto activo que filtra la interfaz. | `app/api/projects.py` |
| RF‑03 | Gestionar perfil Oracle | Crear, editar, listar y eliminar perfiles sin almacenar la contraseña; probar la conexión con una contraseña temporal; validar host y service name; impedir el uso de un perfil en otro proyecto. | `app/api/connections.py`, `app/security/target_policy.py`, `tests/test_core_models.py` |
| RF‑04 | Gestionar caso | Crear, editar, listar y eliminar casos con SQL, tipo de validación (`ROW_COUNT`, `SCALAR_VALUE`, `EXISTS`) y resultado esperado coherente con el tipo. | `app/api/test_cases.py`, `app/models/schemas.py` |
| RF‑05 | Gestionar suite | Crear, editar, listar y eliminar suites; asociar y desasociar casos del mismo proyecto. | `app/api/suites.py` |
| RF‑06 | Validar ejecución SQL | Aceptar una sola sentencia; rechazar DDL, TCL y PL/SQL en todos los ambientes; en PRODUCTION solo SELECT sin `FOR UPDATE`; en STAGING pedir confirmación para DML; ejecutar el DML permitido con `autocommit` desactivado y `ROLLBACK`. | `app/security/sql_policy.py`, `app/engine/executor.py` |
| RF‑07 | Ejecutar y validar | Ejecutar un caso o una suite contra un perfil guardado, clasificar PASS/FAIL/ERROR y devolver un resumen. `SCALAR_VALUE` no está disponible en PRODUCTION. | `app/api/executions.py`, `app/services/execution_service.py` |
| RF‑08 | Registrar historial | Guardar la evidencia de cada ejecución (SQL, esperado, obtenido, estado, duración, origen, corrida) y consultarla con filtros y paginación; la API no ofrece modificarla ni borrarla. | `app/api/history.py` |
| RF‑09 | Panel de resultados | Mostrar cifras de los últimos resultados del proyecto activo. | `frontend/js/modulos/dashboard.js` |
| RF‑10 | Prueba rápida | Ejecutar un SELECT sobre un perfil guardado, indicar lo esperado y ver el resultado explicado, guardándolo en el historial. No acepta DSN libre. | `POST /api/execute/quick`, `tests/test_quick_execution.py` |
| RF‑11 | Uso del producto | Calcular desde datos guardados ejecuciones por fecha, casos y suites más usados, resultados y origen, con definición de cada métrica. | `app/services/usage_service.py`, `tests/test_phase4_usage.py` |
| RF‑12 | Excel | Descargar plantilla, importar casos (todo o nada, con validación) y exportar casos y resultados. | `app/services/excel_io.py`, `tests/test_phase4_excel.py` |
| RF‑13 | CLI | Importar/exportar y ejecutar casos o una suite con código de salida 0/1/2/3/4 e informes Markdown, JUnit y JSON; la contraseña solo por variable de entorno. | `app/cli.py`, `tests/test_phase4_cli.py` |
| RF‑14 | Escenario de demostración | Cargar de forma idempotente las suites de ejemplo en un proyecto. | `app/api/demo.py` |

### b) No funcionales

Los umbrales son **metas**, salvo los marcados «verificado».

| Código | Atributo | Requisito | Estado |
| --- | --- | --- | --- |
| RNF‑01 | Disponibilidad | Exponer `/health`, la interfaz y `/docs`. | Verificado en pruebas (`tests/test_auth.py::test_healthcheck_always_available`) |
| RNF‑02 | Persistencia | Esquema interno versionado con migraciones reproducibles; `alembic check` sin diferencias. | Verificado en local (Fase 3) |
| RNF‑03 | Seguridad | La contraseña de Oracle no se persiste; en PRODUCTION no se guardan filas ni mensajes técnicos de Oracle. | Verificado en pruebas y con Oracle real local |
| RNF‑04 | Seguridad | Los destinos Oracle solo salen de perfiles guardados validados; `ORACLE_ALLOWED_HOSTS` restringe hosts. | Verificado en pruebas |
| RNF‑05 | Usabilidad | Una persona nueva obtiene su primer resultado en ≤ 5 min sin ayuda (≥ 4 de 5). | **Meta, sin medir** |
| RNF‑06 | Rendimiento | La carga de listas e historial responde en ≤ 2 s con datos de prueba. | **Meta, sin medir** |
| RNF‑07 | Recuperación | Copia consistente de la SQLite y restauración aislada verificable. | Verificado en local; no en GitHub/Azure |
| RNF‑08 | Límites | `MAX_RESULT_ROWS` y `ORACLE_CALL_TIMEOUT_MS` acotan filas y tiempo. | Verificado en pruebas |

### c) Reglas de negocio

Las reglas son las de RF‑01…RF‑14 más estas: el PASS solo significa coincidencia con la regla configurada; ningún resultado se presenta como garantía sobre toda la base; el borrado de un proyecto con dependencias se rechaza; el historial no se modifica desde la API.

## V. Fases de desarrollo

### 1. Perfiles de usuario
Un único perfil, «Usuario», que gestiona proyectos, conexiones, casos y suites, ejecuta y revisa el historial. (Quien autoriza la conexión Oracle es el DBA, fuera del sistema.)

### 2. Modelo conceptual y lógico
Regenerar las figuras desde `docs/diagramas/`: paquetes (`componentes.mermaid`), clases (`clases*.mermaid`), ER (`base_datos.mermaid`, solo base interna). Casos de uso, actividades y secuencias se mantienen a mano y deben revisarse para quitar términos ajenos (ver `FD04-fuente-corregida.md` §5).

## Conclusiones *(sustituye al texto del PDF)*

La aplicación permite definir comprobaciones SQL sobre Oracle, ejecutarlas, repetirlas y conservar su evidencia, con reglas por ambiente y un intento de revertir los cambios de datos permitidos. Se verificó con pruebas automáticas y, en un Oracle Free local desechable, la ejecución de SELECT, el INSERT revertido (medido con una conexión independiente) y el rechazo de `DROP`. No se midió el ahorro de tiempo ni la facilidad de uso con personas; no hay organización cliente.

## Recomendaciones

Medir el tiempo al primer resultado con compañeros (protocolo); usar cuentas Oracle de privilegio mínimo; definir usuarios individuales antes de cualquier uso compartido; ampliar el motor de validación solo con nuevos requisitos; considerar notificaciones ante FAIL/ERROR como trabajo futuro.
