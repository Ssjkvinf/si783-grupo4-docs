# Matriz: afirmación de FD01–FD04 → evidencia → corrección

Texto leído de los PDF del repositorio (`FD01`…`FD04` en la raíz) el 20‑oct‑2026. **Los PDF no se modificaron.** Las páginas y secciones son las del texto extraído. Los diagramas de los PDF son imágenes y **no se inspeccionaron**; tampoco el cuadro de costos de FD03 §4.2.

Veredictos: **Comprobado** (hay código o prueba) · **Parcial** (cierto con matices) · **No comprobado** (sin evidencia ni medición) · **Falso/ajeno** (contradice el proyecto o es de otra plantilla) · **Desactualizado** (era cierto antes de las Fases 1–4).

Evidencia: rutas relativas a `framework-pruebas-sql/`. «Oracle real local» = Oracle Free en Docker de un equipo, ejecución del 18‑oct‑2026 (Fase 2); no se repitió después.

## A. FD03 — Especificación de requerimientos

| # | Sección | Afirmación | Evidencia | Veredicto | Corrección |
| --- | --- | --- | --- | --- | --- |
| 3.1 | Control de versiones | Hecha por «CCC», revisada por «IME», fecha «30/09/202» | Autores reales: KHC, GZP (FD01, FD02, FD06). Fecha truncada | Falso/ajeno | Iniciales KHC/GZP, fecha completa y motivo de la v1.1 |
| 3.2 | I. Generalidades | La «Empresa» es la UPT, con visión, misión y organigrama | FD01/FD02/FD06: no existe organización cliente | Falso/ajeno | Reemplazar por «Contexto académico» (ver `FD03-fuente-corregida.md` §I) |
| 3.3 | II.1 Objetivos de negocio | «cumplimiento de regulaciones … SUNAT», «materiales y reactivos», «insumos de laboratorio», «gestión académica» | Nada en `app/` toca esos temas | Falso/ajeno | Reescrito en la fuente corregida |
| 3.4 | II.2–II.3 Diseño y alcance | Ejecución «principalmente DML»; «garantizar» ejecución segura; «evitando modificaciones permanentes» | `app/security/sql_policy.py`: PRODUCTION solo SELECT; la prueba rápida es solo SELECT (`app/api/executions.py`). Rollback tras INSERT/UPDATE/DELETE: `app/engine/executor.py` (Oracle real local) | Parcial | «Intenta revertir» en lugar de «garantiza»; el alcance principal es SELECT; DML solo en TEST/STAGING; límites del rollback |
| 3.5 | II.4.1 Viabilidad técnica | «El laboratorio cuenta con equipos … Intel i5 12.ª gen., 12 GB, SSD 256 GB, Windows» | Describe un laboratorio, no el producto (corre en un servidor y se usa con navegador) | Falso/ajeno | Resumir con lo comprobable: Python 3.12 (`Dockerfile`), FastAPI, SQLite, Oracle objetivo, navegador |
| 3.6 | II.4.2 Cuadro de costos | Figura con costos generales | Imagen no inspeccionada; FD01 §7 ya trata costos | No comprobado | Retirar y remitir a FD01 §7–§9 (escenarios) |
| 3.7 | II.5 Levantamiento de información | «realizada a través de entrevistas, encuestas, observación directa» | FD01 §11, FD02, FD06 §1: **no se hicieron** | **Falso/ajeno** | «No se realizaron entrevistas, encuestas ni observación en una organización»; listar las fuentes documentales de FD06 |
| 3.8 | III Proceso propuesto | «estandarizar la gestión de reactivos» | Texto de otra plantilla | Falso/ajeno | «repetir comprobaciones SQL y conservar su evidencia» |
| 3.9 | IV.a RF‑01 | Autenticar «con sus credenciales registradas» | `app/main.py`: **una sola** credencial por variables de entorno (`APP_ACCESS_USERNAME/PASSWORD`); cookie `session_token` HttpOnly, firma HMAC **igual para todos** | Parcial | «Acceso con una credencial de aplicación configurable; no hay usuarios individuales» |
| 3.10 | IV.a RF‑02 | Proyecto activo filtra toda la interfaz; no se elimina con dependencias | `frontend/index.html` (`select-proyecto-activo`); `app/api/projects.py` | Comprobado | Sin cambios |
| 3.11 | IV.a RF‑03 | Perfil sin contraseña; prueba con contraseña temporal; sin uso cruzado entre proyectos | `app/models/connection.py` (sin columna de contraseña); 409 en `app/api/executions.py`; `tests/test_core_models.py:155` | Comprobado | Añadir: host/service validados (`app/security/target_policy.py`) |
| 3.12 | IV.a RF‑04 | Validación `ROW_COUNT` o `EXISTS` | Ahora hay tres: `SCALAR_VALUE` (`app/engine/validator.py`) | Desactualizado | Añadir `SCALAR_VALUE` y su restricción en PRODUCTION |
| 3.13 | IV.a RF‑05 | Casos de la suite del mismo proyecto | 409 en `app/api/suites.py:56` | Comprobado | Sin cambios |
| 3.14 | IV.a RF‑06 | Una sentencia permitida; bloquear DDL/TCL; «obligar el rollback en toda operación DML» | `sql_policy.py`, `executor.py`; Oracle real local: `tests/test_oracle_phase2.py` (INSERT revertido, `DROP/TRUNCATE/ALTER` rechazados con 0 conexiones) | Comprobado, con límites | Añadir límites: secuencias, transacciones autónomas, paquetes `DBMS_*/UTL_*`; cuenta de privilegio mínimo |
| 3.15 | IV.a RF‑07 | Ejecutar caso o suite; PASS/FAIL/ERROR; resumen | `app/api/executions.py`, `SuiteExecutionSummary` | Comprobado | Sin cambios |
| 3.16 | IV.a RF‑08 | Historial con filtros y paginación; **«sin permitir su alteración posterior»** | `app/api/history.py` solo expone GET (límite 100). **Pero** la SQLite es editable directamente y no hay firma ni hash | Parcial | «La API no ofrece modificar ni borrar el historial»; no afirmar inalterabilidad |
| 3.17 | IV.a RF‑09 | Dashboard con indicadores | `frontend/js/modulos/dashboard.js` (últimas 100) y, desde la Fase 4, `GET /api/usage/summary` | Comprobado | Añadir RF‑10 (uso del producto) |
| 3.18 | IV.b RNF | Solo 2 RNF (disponibilidad, persistencia) | `/health`; `alembic/` | Parcial | Añadir RNF medibles (ver fuente corregida §IV.b); los umbrales son **metas** |
| 3.19 | — | No hay RF para: prueba rápida, Excel, CLI, origen de ejecución | `POST /api/execute/quick`; `app/api/excel.py`; `app/cli.py`; `execution_history.trigger_source` | Desactualizado | RF‑10…RF‑14 (fuente corregida) |
| 3.20 | V.1 Perfiles | Un único perfil «Usuario» | Coincide con la credencial única | Comprobado | FD04 menciona «administrador» y «tester»: unificar |
| 3.21 | V.3.a Objetos entidad | «datos persistentes, como reactivos, materiales y usuarios» | No hay tabla de usuarios (`docs/generated/diccionario-datos.md`) | Falso/ajeno | Proyectos, perfiles, casos, suites, historial, eventos de uso |
| 3.22 | Conclusiones | «garantizando en todo momento la integridad de los datos mediante rollback obligatorio» | Rollback es un control, con límites (ver 3.14) | Falso (sobreafirmación) | Reescrito |
| 3.23 | Conclusiones | «optimiza el tiempo» y «reduce de forma significativa el riesgo» | Sin medición (`protocolo-usabilidad.md` pendiente) | No comprobado | Convertir en hipótesis H1–H3 |
| 3.24 | Conclusiones | Historial «completamente trazable … auditable» | Ver 3.16; un solo usuario compartido: no hay quién ejecutó | Parcial | «Trazable por caso, suite, perfil, origen y fecha; sin identidad por persona» |
| 3.25 | Recomendaciones | Notificaciones y reportes exportables como futuro | Reportes exportables ya existen (Excel, CLI: Markdown/JUnit/JSON) | Desactualizado | Mover a lo implementado; dejar notificaciones como futuro |

## B. FD04 — Arquitectura de software

| # | Sección | Afirmación | Evidencia | Veredicto | Corrección |
| --- | --- | --- | --- | --- | --- |
| 4.1 | Control de versiones | «CCC, IME», «30/09/202» | Ver 3.1 | Falso/ajeno | KHC/GZP y fecha |
| 4.2 | 1 Introducción | «ninguna prueba deje datos residuales», «auditable», «modernización del proceso … en las organizaciones» | Límites del rollback; no hay organizaciones | Parcial / No comprobado | Reescrito |
| 4.3 | 1.2 Definiciones | `row_count` compara «filas afectadas» | Para SELECT son las **devueltas**; para DML, las afectadas (`validator.py`) | Parcial | Precisar |
| 4.4 | 1.2 Definiciones | `exists`: «condición evaluada resulta verdadera o falsa» | Es «la consulta devuelve al menos una fila» (`ExistenceValidation`) | Parcial | Precisar |
| 4.5 | 1.2 Definiciones | DDL bloqueado «en todos los ambientes» | `FORBIDDEN_KEYWORDS` se comprueba antes de las reglas por ambiente | Comprobado | — |
| 4.6 | 1.2 Definiciones | Rollback «obligatorio al final de cada ejecución de prueba» | Solo tras INSERT/UPDATE/DELETE o ante error; en SELECT no hay rollback | Parcial | «tras toda sentencia DML» |
| 4.7 | 1.1/1.3 | PRODUCTION «enmascara los datos sensibles» | No enmascara: **oculta todas las filas** (`executor.py`: `fetched_rows = []`) | Parcial | «oculta las filas devueltas» |
| 4.8 | 2.2/2.4/2.5 | «Vista Física» = diagrama de clases; «Vista de desarrollo» = paquetes | El diagrama de clases es de la vista lógica; la física es el despliegue | Parcial | Reordenar; usar `docs/diagramas/clases*.mermaid` y `despliegue.mermaid` generados |
| 4.9 | 3.1 Disponibilidad | «debe existir un mecanismo documentado de respaldo periódico» | `scripts/backup/sqlite_backup.py` (API de respaldo de SQLite) y `docs/respaldo-restauracion.md`; **probado en local**, no en GitHub/Azure | Parcial | Citar el mecanismo y su estado |
| 4.10 | 3.2 Seguridad | Cookie HttpOnly; `secrets.compare_digest`; credenciales Oracle no se persisten | `app/main.py` (líneas de `login`); no hay columna de contraseña | Comprobado | Añadir: la cookie vale 24 h y el token es único para todos |
| 4.11 | 3.3 Adaptabilidad | Strategy permite nuevos tipos de validación; «la separación del motor facilita soportar otros motores» | `ValidationStrategy` existe, pero **la selección es un `if/elif` en `app/services/execution_service.py`** y `executor.py`/`resolve_connection_credentials` usan `oracledb` directamente | Parcial | Reconocer que agregar `SCALAR_VALUE` tocó validador, esquema, servicio, explicaciones e interfaz |
| 4.12 | 3.4 Rendimiento | Consultas habituales ≤ 2 s con volumen representativo | **No medido** | No comprobado | Meta M‑RNF‑1 |
| 4.13 | 4 Análisis (intro) | «desde la creación de usuarios y configuración de metodologías … control de cambios y generación de informes» | Texto de otro proyecto | Falso/ajeno | Reescribir con los RF reales |
| 4.14 | 4.1 RNF (intro) | «alta disponibilidad y recuperación rápida ante fallos» | Una sola VM sin alta disponibilidad (FD01 §5); RTO/RPO no definidos | Falso (sobreafirmación) | Retirar |
| 4.15 | 5 Casos de uso (CU02–CU09) | Narrativas con «administrador crear usuario», «obras», «partida», «residente de obra», «catálogo de materiales», «almacenero» | Ver `docs/correccion-fd03-fd04.md` §1 | Falso/ajeno | Textos propuestos en `FD04-fuente-corregida.md` §5 |
| 4.16 | 7 Procesos | Índice «7.1 Proceso Actual»; el cuerpo «7.1 Proceso Propuesto» | Incoherencia interna | Falso | Alinear índice y cuerpo |
| 4.17 | 11 Calidad | Índice: 11.3 Adaptabilidad, 11.4 Disponibilidad, 11.5 Otro; cuerpo: falta Disponibilidad y «Otro» es 11.4 | Incoherencia interna | Falso | Añadir el escenario de disponibilidad |
| 4.18 | 11.1 Seguridad | Mensaje genérico «Credenciales inválidas»; sin cookie si falla | `app/main.py`; `tests/test_auth.py::test_login_failure` | Comprobado | La medida «100 %» se cumple solo para los casos probados; **no hay límite de intentos** |
| 4.19 | 11.1 | «información de las obras» | Texto ajeno | Falso/ajeno | «proyectos, conexiones, casos e historial» |
| 4.20 | 11.2 Usabilidad | «registro de avance de obra»; registrar un caso en < 2 min | Texto ajeno; no medido | Falso/ajeno + No comprobado | Escenario de primer resultado (OS‑1) como **meta** |
| 4.21 | 11.3 Adaptabilidad | Cambiar como máximo «una o dos clases de la capa de motor» | Ver 4.11 | Falso | Reformular como meta o retirarlo |
| 4.22 | 11.4 Confidencialidad | «datos financieros de una obra», «rol autorizado» | No hay roles | Falso/ajeno | «filas devueltas en PRODUCTION» |
| 4.23 | 11.4 | 100 % de ejecuciones PRODUCTION sin filas ni mensajes técnicos | `executor.py`, `execution_service.py`; `tests/test_engine.py::test_production_error_masking`, `::test_production_row_count_and_exists_work_with_hidden_rows`, `tests/test_quick_execution.py::test_quick_produccion_no_muestra_filas`, y con Oracle real local `tests/test_oracle_phase2.py::test_produccion_oculta_filas_y_no_permite_valor_escalar` | Comprobado en pruebas | Citar esas pruebas |
| 4.24 | 8 Despliegue | Diagrama de contenedor | `docs/diagramas/despliegue.mermaid` (generado de `compose.yml`) | Parcial | Regenerar la figura |
| 4.25 | 10 Datos | Diagrama ER | El ER de `docs/diagramas/` usaba `suite_test_cases`; la tabla real es `suite_test_case` | Desactualizado | Regenerar desde `base_datos.mermaid` (generado) |

## C. FD01 — Factibilidad

| # | Sección | Afirmación | Evidencia | Veredicto | Corrección |
| --- | --- | --- | --- | --- | --- |
| 1.1 | Resumen | Origen académico, sin empresa, entrevistas ni medición | Coherente con FD02 y FD06 | Comprobado | — |
| 1.2 | Resumen | «La demostración se desplegó en una VM de Azure» | El repositorio no contiene la VM ni su evidencia; solo documentos | No comprobado | «informado por el equipo; evidencia pendiente (OS‑7)» |
| 1.3 | Tabla 02 | «aproximadamente cuatro semanas calendario» | `git log`: commits del 14‑sep al 06‑oct‑2026 (≈ 3 semanas), todos de Kevin | Parcial | Citar el rango de commits |
| 1.4 | §3 | «116 funciones `test_` (13 de Oracle)» | Al 20‑oct‑2026: 22 archivos, **292** funciones `def test_`; colectadas 353 (330 pasan + 23 omitidas sin Oracle) con `python -m pytest -q` | Desactualizado | Actualizar con el comando y la fecha |
| 1.5 | §3 | Imagen del API con Python 3.12 y Alembic | `Dockerfile` (`python:3.12-slim`) | Comprobado | — |
| 1.6 | §3 | Tres servicios, 80/443 publicados, API y Oracle en red interna | `infra/production/compose.yml` | Comprobado | — |
| 1.7 | §3 | Cubre `ROW_COUNT` y `EXISTS` | Ahora también `SCALAR_VALUE` | Desactualizado | Añadir |
| 1.8 | §3/§5 | «El procedimiento actual usa una copia directa del archivo» | `scripts/backup/sqlite_backup.py` ya usa la API de respaldo; `scripts/backup/sqlite_restore_verify.py` verifica; **probado solo en local** | Desactualizado | «implementado y probado en local; no en GitHub/Azure» |
| 1.9 | §3 | Autenticación configurable, no usuarios individuales | `app/main.py` | Comprobado | — |
| 1.10 | §5/§7 | Precios de DigitalOcean, SBS y Punto.pe (1‑oct‑2026) | **No reverificados** en esta fase | No comprobado | Reverificar antes de entregar; mantener como escenario |
| 1.11 | §8–§9 | 8 min por repetición; VAN S/ 2 455,59; umbral 6,98 min | Aritmética de FD01; las entradas son supuestos | Hipótesis (bien rotulada) | Mantener rótulo «escenario» y no repetir cifras en FD05 como resultado |
| 1.12 | §10.1 | «PASS no es garantía de que los datos completos sean correctos» | Coincide con el producto | Comprobado | Reutilizar en problema y objetivos |
| 1.13 | §10.2 | «No hay archivo LICENSE» | `ls` del repositorio: no hay `LICENSE` | Comprobado | Decisión pendiente del equipo |
| 1.14 | §11 | El SRS describe entrevistas y trata a la UPT como empresa | Confirmado en FD03 | Comprobado | Corregir FD03 (sección A) |
| 1.15 | Referencias | URL de Oracle (23ai, SQL Developer), sqlparse | Abiertas el 20‑oct‑2026 y coherentes con lo citado | Comprobado | — |

## D. FD02 — Visión

| # | Sección | Afirmación | Evidencia | Veredicto | Corrección |
| --- | --- | --- | --- | --- | --- |
| 2.1 | 1.2 Alcance | Funciones: proyectos, perfiles, casos, suites, ejecución, validaciones `ROW_COUNT`/`EXISTS`, historial | Falta `SCALAR_VALUE`, prueba rápida, Excel, CLI, dashboard de uso | Desactualizado | Ampliar alcance (ver `FD02-parche.md`) |
| 2.2 | 1.2 | «No incluye … usuarios individuales, alta disponibilidad, garantía de ahorro» | Cierto | Comprobado | — |
| 2.3 | 2.1 | SQL Developer ya ofrece suites | Confirmado en la página de Oracle; también tiene `sdcli` | Comprobado | Añadir la línea de comandos |
| 2.4 | 4.2 | Perfil sin contraseña; PRODUCTION solo SELECT y filas ocultas; DML con reversión; STAGING confirma | `models`, `sql_policy.py` | Comprobado | Sin cambios |
| 2.5 | 4.2 | `ROLLBACK` no garantiza inocuidad; sqlparse no valida | Fuentes abiertas | Comprobado | — |
| 2.6 | 5 V‑01…V‑07 | Características de la v1 | Ver 2.1 | Desactualizado | V‑08 Inicio guiado, V‑09 Excel, V‑10 CLI, V‑11 Uso del producto |
| 2.7 | 7 | Aceptación como «condiciones propuestas» | Bien rotulado | Comprobado | — |
| 2.8 | Referencias | Oracle (s. f.-a) *Transactions* (19c) | FD06 cita otra página (23ai) | Parcial | Unificar la versión citada |

## E. Qué hay que regenerar (porque los PDF no se tocaron)

1. FD03 y FD04: reemplazar los textos de las secciones A y B; **regenerar las figuras** (paquetes, ER, clases, componentes, despliegue) desde `docs/diagramas/*.mermaid` generados; actualizar índices y numeración.
2. FD01: parche de las filas 1.2, 1.4, 1.7, 1.8, 1.10 (ver `FD01-parche.md`).
3. FD02: alcance y características (ver `FD02-parche.md`).
4. FD05: documento nuevo (ver `FD05-informe-final.md`) sobre la plantilla oficial de FD05.
5. Los `.docx` editables fueron eliminados del repositorio (commits del 06‑oct‑2026). Hay plantillas `.docx` de FD01–FD06 en `Downloads/proyecto-group-4-trabajo/` (copia del 21‑sep‑2026 **no abierta** salvo FD05, que sí es la plantilla del curso) y los `.docx` del primer commit (`bfeac77`); ver `LEEME.md`.
