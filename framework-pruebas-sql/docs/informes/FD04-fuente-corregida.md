# FD04 — Arquitectura de software (fuente corregida, versión 1.1 propuesta)

> Fuente editable para reemplazar textos del PDF `FD04_Informe_SAD_FrameworkSQL.pdf` (**no modificado**). Cada afirmación remite a un archivo del repositorio. Todas las figuras de esta versión salen de `docs/diagramas/*.mermaid` generados por `scripts/docs/gen_docs.py`.
> Control de versiones sugerido: 1.1 · KHC, GZP · fecha de la entrega · «Corrección de contenido ajeno y actualización al producto implementado».

## 1. Introducción

Este documento describe la arquitectura de la aplicación que permite repetir comprobaciones SQL sobre Oracle y conservar su evidencia. Hay **dos bases de datos distintas** que no deben confundirse en ningún diagrama:

| | Base interna | Base objetivo |
| --- | --- | --- |
| Motor | SQLite (`FRAMEWORK_DB_URL`) | Oracle (la que se comprueba; Oracle Free en la demostración) |
| Contenido | Proyectos, perfiles (sin contraseña), casos, suites, historial, eventos de uso | Datos del usuario; la aplicación no los posee |
| Acceso | SQLAlchemy | `python-oracledb` (modo Thin), una conexión por ejecución |
| Versionado | Alembic (`alembic/versions/`) | Solo los objetos de la demostración, con Liquibase (`infra/oracle/liquibase/`) |

### 1.1 Propósito
Dar una guía de la organización del sistema para quien desarrolle o revise. **No** se afirma que garantice aislamiento transaccional: *intenta* revertir los cambios de datos permitidos y bloquea las sentencias que Oracle confirma por sí solas; los límites están en `docs/seguridad.md`.

### 1.2 Definiciones (correcciones)
- **`ROW_COUNT`**: compara el número de filas **devueltas** (SELECT) o **afectadas** (DML) con un entero.
- **`SCALAR_VALUE`**: compara el valor de la primera columna de una **única** fila (p. ej. `COUNT(*)`). No existe en PRODUCTION.
- **`EXISTS`**: `true` si la consulta devuelve al menos una fila, `false` si ninguna.
- **DDL, TCL y PL/SQL**: se rechazan en todos los ambientes antes de abrir la conexión.
- **Rollback**: se ejecuta tras todo INSERT/UPDATE/DELETE permitido y ante un error; si falla, el resultado es ERROR.

### 1.3 Visión general
Aplicación web (HTML/JavaScript servida por FastAPI). Una persona crea o elige comprobaciones, las ejecuta contra un perfil guardado y consulta el historial. En PRODUCTION solo se permite SELECT y **se ocultan las filas devueltas** (no se enmascaran campos). Además existen una CLI y la importación/exportación Excel.

## 2. Representación arquitectónica

| Vista | Figura | Fuente |
| --- | --- | --- |
| Escenarios (casos de uso) | `docs/diagramas/casos_uso.mermaid` (a mano) | Revisar términos (§5) |
| Lógica (paquetes y clases) | `componentes.mermaid`, `clases.mermaid`, `clases_modelos.mermaid`, `clases_schemas.mermaid` | **Generadas** del código |
| Procesos (secuencia/actividad) | `secuencia.mermaid`, `actividad.mermaid` (a mano) | Revisar |
| Datos | `base_datos.mermaid` (**solo la base interna**) | **Generada** de los modelos |
| Despliegue (física) | `despliegue.mermaid` | **Generada** de `compose.yml`, Terraform y workflows; no verifica que exista en Azure |

*(La vista «Física» del PDF contenía el diagrama de clases: debe ser el despliegue.)*

## 3. Objetivos y limitaciones arquitectónicas

### 3.1 Disponibilidad
Existe un mecanismo de copia consistente de la SQLite (`scripts/backup/sqlite_backup.py`, API de respaldo de SQLite) y un verificador de restauración aislada (`scripts/backup/sqlite_restore_verify.py`). **Probado en local; no ejecutado en GitHub ni Azure.** Una sola VM: no hay alta disponibilidad; RPO y RTO no están definidos.

### 3.2 Seguridad
Cookie de sesión HttpOnly (24 h) con firma HMAC **igual para todas las sesiones**; una sola credencial configurable por variables de entorno; comparación con `secrets.compare_digest`; mensaje genérico «Credenciales inválidas»; **sin límite de intentos**. La contraseña de Oracle no se persiste. Las reglas de SQL y de ambiente se aplican en el backend (`app/security/sql_policy.py`, `app/engine/executor.py`).

### 3.3 Adaptabilidad
El patrón Strategy (`ValidationStrategy` en `app/engine/validator.py`) separa la comparación, pero la elección de estrategia es un `if/elif` en `app/services/execution_service.py` y el tipo se declara en `app/models/schemas.py`. Agregar `SCALAR_VALUE` exigió cambios en validador, esquema, servicio, explicaciones, interfaz y pruebas. **El soporte de otros motores no está implementado**: `executor.py` usa `oracledb` directamente.

### 3.4 Rendimiento
Meta (no medida): carga de listas e historial ≤ 2 s con datos de prueba. Límites reales y verificados: `MAX_RESULT_ROWS` (por defecto 1000) y `ORACLE_CALL_TIMEOUT_MS` (10 000 ms).

## 4. Requerimientos
Usar las tablas RF‑01…RF‑14 y RNF‑01…RNF‑08 de `FD03-fuente-corregida.md` (misma numeración en los dos documentos). Sustituir el párrafo introductorio del PDF («creación de usuarios y configuración de metodologías… informes») por: «Los requerimientos funcionales cubren la gestión de proyectos, conexiones, casos y suites, la ejecución con reglas por ambiente, el historial, el uso del producto y las integraciones».

## 5. Vistas de casos de uso (textos corregidos)

| CU | Texto del PDF | Texto propuesto |
| --- | --- | --- |
| CU01 | «inicio de sesión para usuarios y administradores» | Una sola credencial de aplicación; no hay administradores. |
| CU02 Gestionar proyecto | «permite al administrador crear un usuario nuevo» | Crear, editar, listar y eliminar proyectos (se rechaza si tienen dependencias) y elegir el proyecto activo. |
| CU03 Gestionar perfil Oracle | «gestionar las obras» | Registrar, editar y eliminar perfiles sin guardar la contraseña, y probar la conexión. |
| CU04 Gestionar caso | «registrar una partida nueva» | Crear, editar y eliminar casos con SQL, tipo de validación y resultado esperado. |
| CU05 Gestionar suite | «el residente de obra registrar el avance físico» | Agrupar casos del mismo proyecto en una suite. |
| CU06 Validar ejecución SQL | «gestionar el catálogo de materiales» | El sistema verifica una sola sentencia permitida, bloquea DDL/TCL/PL/SQL y aplica las reglas del ambiente. |
| CU07 Ejecutar caso y suite | «el almacenero registrar compra de materiales» | Ejecutar un caso o una suite contra un perfil y clasificar PASS/FAIL/ERROR. |
| CU08 Registrar historial | «el residente de obra registrar consumo de materiales» | Guardar la evidencia de cada ejecución y permitir consultarla. |
| CU09 Visualizar dashboard | «el almacenero gestionar proveedor» | Ver los resultados recientes y el uso del producto. |
| CU10 *(nuevo)* Prueba rápida | — | Ejecutar un SELECT desde «Inicio» y ver el resultado explicado. |
| CU11 *(nuevo)* Importar/exportar Excel | — | Importar casos con validación todo-o-nada y exportar casos y resultados. |
| CU12 *(nuevo)* Ejecutar desde la CLI | — | Ejecutar casos o una suite y obtener un código de salida y un informe. |

## 6. Vista lógica
Regenerar el diagrama contextual con: Persona usuaria, Navegador, Aplicación (FastAPI), SQLite interna, Oracle objetivo, CLI, GitHub Actions (opcional). Diagrama de componentes: `docs/diagramas/componentes.mermaid`.

## 7. Vista de procesos
Índice y cuerpo deben decir lo mismo («7.1 Proceso actual» y «7.2 Proceso propuesto», como en el índice del PDF). Secuencia de referencia de la ejecución: Navegador → `POST /api/execute/...` → `resolve_connection_credentials` → `validate_sql_statement` → `TargetDatabaseExecutor.execute_query` → `ValidationContext` → `ExecutionHistory`.

## 8. Vista de despliegue
Figura: `despliegue.mermaid`. Descripción verificable en `infra/production/compose.yml`: tres servicios (`caddy`, `api`, `oracle_db`), puertos 80/443 solo en Caddy, volúmenes `framework_data` y `oracle_data`. Terraform (`infra/terraform/`) consulta una VM existente y puede crear almacenamiento de copias y, solo con confirmación, una VM nueva. **No se verificó en Azure.**

## 9. Vista de implementación
Figura: `componentes.mermaid` (dependencias leídas de los `import`).

## 10. Vista de datos
Figura: `base_datos.mermaid` (7 tablas de la base interna; la tabla de asociación real es `suite_test_case`). Diccionario: `docs/generated/diccionario-datos.md`. La base objetivo solo se describe para los objetos de la demostración.

## 11. Calidad (escenarios corregidos)

### 11.1 Seguridad
*Estímulo:* intentos de inicio de sesión con credenciales inválidas. *Respuesta:* respuesta 401 «Credenciales inválidas» sin cookie. *Medida:* los casos de `tests/test_auth.py` pasan; **no hay límite de intentos** (limitación declarada). Sustituir «información de las obras» por «información de proyectos, conexiones, casos e historial».

### 11.2 Usabilidad
*Fuente:* persona que prueba SQL por primera vez. *Estímulo:* quiere ver si una consulta da lo esperado. *Artefacto:* pantalla «Inicio». *Respuesta:* conectar, escribir o elegir un SELECT, indicar lo esperado y ejecutar; resultado explicado. *Medida (**meta, sin medir**):* primer resultado en ≤ 5 min y sin ayuda en ≥ 4 de 5 participantes (`docs/protocolo-usabilidad.md`).

### 11.3 Adaptabilidad
*Estímulo:* agregar un tipo de validación. *Respuesta real:* nueva clase `ValidationStrategy`, rama en `execution_service.py`, valor en `ValidationTypeEnum`, texto en `explain_execution`, opción en la interfaz y pruebas. *Medida:* retirar «una o dos clases»; registrar el número real de archivos tocados al hacerlo.

### 11.4 Disponibilidad *(faltaba en el cuerpo)*
*Estímulo:* pérdida o corrupción de la SQLite. *Respuesta:* restaurar desde una copia consistente tras verificarla en una carpeta aislada. *Medida:* la copia pasa `integrity_check` y los conteos de filas coinciden (probado en local con `tests/test_phase3_scripts.py`; **no en producción**).

### 11.5 Confidencialidad
*Estímulo:* ejecutar SQL contra un perfil PRODUCTION. *Respuesta:* se muestran y guardan solo conteos y mensajes genéricos; los rechazos de política sí se muestran. *Medida:* `tests/test_engine.py::test_production_row_count_and_exists_work_with_hidden_rows`, `tests/test_quick_execution.py::test_quick_produccion_no_muestra_filas` y, con Oracle real local, `tests/test_oracle_phase2.py::test_produccion_oculta_filas_y_no_permite_valor_escalar`.

## 12. Limitaciones de la arquitectura actual
Una credencial compartida; token de sesión único; sin límite de intentos; historial editable directamente en la SQLite; análisis SQL léxico; rollback con límites; un solo motor objetivo (Oracle ≥ 12.1); una sola VM.
