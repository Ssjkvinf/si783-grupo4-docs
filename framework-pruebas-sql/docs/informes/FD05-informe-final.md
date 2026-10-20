# FD05 — Informe final (borrador editable)

> Sigue el índice de la plantilla oficial `FD05-EPIS-Informe ProyectoFinal.docx` (Antecedentes, Planteamiento del problema, Marco teórico, Desarrollo de la solución, Presupuesto, Conclusiones, Recomendaciones, Bibliografía, Anexos). Es **texto para pegar en esa plantilla**; no se generó el `.docx`.
> Datos de portada: Universidad Privada de Tacna · Facultad de Ingeniería · EPIS · Curso: Calidad y Pruebas de Software · Docente: Ing. Patrick Cuadros Quiroga · Integrantes: Kevin Elvis Hinojosa Calloapaza (2023078335), Gerald Deybi Zevallos Pinto (2023078691) · Tacna – Perú · 2026. Control de versiones: 1.0, KHC/GZP, fecha de la entrega (**borrar** el ejemplo «MPV/ELV/ARV 10/10/2020» de la plantilla).
> Convención: **[Hecho]** verificado en el repositorio · **[Fuente]** respaldado por una fuente leída · **[Meta]**/**[Hipótesis]** sin medir · **[Futuro]** no implementado. Las capturas con datos sintéticos, H2 o sustitutos SQLite se rotulan «ilustrativa».

## 1. Antecedentes

El proyecto nace en el curso Calidad y Pruebas de Software: el docente propuso proyectos y los dos integrantes eligieron este (FD01 §resumen, FD06 §1). **No hubo organización cliente, entrevistas, convenio ni medición** de beneficios. Dos exigencias reales de entidades peruanas muestran por qué se documentan pruebas sobre bases de datos: el TdR de la Contraloría General de la República (2024) pide, en sus anexos 04.1 a 04.3, pruebas funcionales con casos de prueba, un plan de pruebas que incluye «pruebas de datos e integridad de Base de Datos» y un informe de pruebas con evidencias, y el TdR del Ministerio del Ambiente (s. f.) pide, en su apartado V, un «Documento de Pruebas de Base de Datos» aprobado por el administrador de la base, con Oracle 11g como motor (anexo 1). **Este producto no serviría para esa entidad tal como está**: exige Oracle 12.1 o posterior (modo Thin). Estos documentos son ejemplos; no prueban que esas entidades tengan el problema ni que usarían este producto.

## 2. Planteamiento del problema

### 2.1 Problema
Quien modifica una consulta u operación sobre datos Oracle debe comprobar que sigue dando lo esperado. Si la comprobación queda aislada, cuesta repetirla, compararla y conservar qué se ejecutó. Es una **necesidad potencial**, no observada en una organización. Detalle y fuentes: `docs/problema-y-objetivos.md`.

### 2.2 Justificación
Reunir en un lugar la sentencia, la conexión, lo esperado y cada resultado permite repetir y revisar. Oracle SQL Developer ya ofrece suites de pruebas unitarias y línea de comandos [Fuente]; por eso no se afirma novedad ni superioridad. El aporte es una alternativa web con prueba rápida guiada, reglas por ambiente, Excel, CLI y un panel de uso, cuya utilidad **no se midió** (hipótesis H1–H3).

### 2.3 Alcance
Implementado, demostración académica y trabajo futuro: ver la tabla de tres capas en `docs/problema-y-objetivos.md` §3 y §6 de este informe. Fuera de alcance: otros motores, Oracle anterior a 12.1 (el modo Thick con cliente Oracle 19 alcanzaría la 11.2 según la documentación del controlador; **no verificado, no implementado**), usuarios individuales, carga, vulnerabilidades, alta disponibilidad.

### 2.4 Objetivos
Los de investigación (OI‑1…3) y los de solución (OS‑1…9) con su estado están en `docs/problema-y-objetivos.md` §4. Resumen del estado: OI‑1…3 hechos (documentales); OS‑3…6, 8 y 9 verificados en local (OS‑3…6 también con Oracle real local en la Fase 2); **OS‑1, OS‑2 y OS‑7 sin medir/verificar**.

## 3. Marco teórico

### 3.1 Transacciones y reversión en Oracle
Mientras no se confirma, un cambio de datos solo es visible para su sesión y puede deshacerse con `ROLLBACK`; Oracle emite un `COMMIT` implícito antes y después de cualquier sentencia DDL (Oracle, s. f.-a). De aquí salen dos decisiones: se bloquean las sentencias que confirman solas, y el DML permitido se ejecuta con `autocommit` desactivado y se revierte. El rollback **no** deshace secuencias, transacciones autónomas ni llamadas a paquetes que escriben fuera de la transacción: por eso se exige una cuenta de privilegio mínimo.

### 3.2 Análisis de sentencias
`sqlparse` se declara «intencionalmente no validador» (sqlparse, s. f.). Se usa para separar sentencias, ignorar comentarios y literales y reconocer palabras clave; no demuestra que una sentencia sea inocua.

### 3.3 Pruebas de base de datos y comparación de resultados
Una comprobación consiste en una sentencia, una regla de comparación y un resultado esperado. El patrón Strategy (Gamma et al., 1994) desacopla la regla: `RowCountValidation`, `ScalarValueValidation` y `ExistenceValidation`.

### 3.4 Herramienta existente: Oracle SQL Developer (comparación documental)
Según la página leída (Oracle, s. f.-b): agrupa pruebas en suites (incluso anidadas, con startup/teardown), las ejecuta sobre una conexión, muestra resultados y reportes, y tiene línea de comandos (`sdcli`). No hubo pruebas de uso de ninguna de las dos herramientas; la tabla compara **funciones declaradas**, no desempeño.

| Criterio | SQL Developer (documentación) | Este producto (repositorio) |
| --- | --- | --- |
| Casos / pruebas | Pruebas unitarias sobre objetos y consultas | Casos SQL con `ROW_COUNT`, `SCALAR_VALUE`, `EXISTS` |
| Grupos | Suites (anidables, startup/teardown) | Suites planas, sin startup/teardown |
| Reportes | Reportes del repositorio de pruebas | Historial, panel de uso, Markdown/JUnit/JSON, Excel |
| Historial | Resultados en tablas del repositorio de pruebas | `execution_history` en SQLite |
| Ambientes | No se leyó una política por ambiente | TEST / STAGING / PRODUCTION con reglas distintas |
| Línea de comandos | `sdcli` | `python -m app.cli` (código de salida 0/1/2/3/4) |
| Interfaz | Aplicación de escritorio | Web |
| Instalación | Cliente + repositorio en la base | Servicio web + SQLite; sin esquema propio en la Oracle objetivo |

## 4. Desarrollo de la solución

### 4.1 Análisis de factibilidad
Técnica, económica, operativa, legal y ambiental: ver FD01 (Anexo 01). Las cifras económicas son **escenarios de planificación**. Operativa y legal: el historial guarda SQL y resultados esperados (puede contener datos sensibles) y no existe archivo `LICENSE`.

### 4.2 Tecnología de desarrollo [Hecho: `requirements.txt`, `Dockerfile`]
Python 3.12 · FastAPI/Uvicorn · SQLAlchemy y Alembic (SQLite interna) · `python-oracledb` Thin · `sqlparse` · `openpyxl` · HTML/JavaScript con Bootstrap · pytest · Docker/Compose y Caddy · Terraform (azurerm) · Liquibase (objetos Oracle de la demostración) · GitHub Actions · MkDocs (documentación). Arquitectura: ver FD04 y los diagramas generados (`docs/generated/diagramas.md`).

### 4.3 Metodología de implementación
Se trabajó por **fases** sobre el repositorio: base funcional (14‑sep a 06‑oct‑2026, según los commits), y las fases 1–5 (18 a 20‑oct‑2026, trabajo local sin commit): recorrido guiado, reglas sobre datos con Oracle desechable, automatizaciones de infraestructura/base/copias/release, dashboard e integraciones, y documentación generada. Cada fase cerró con pruebas ejecutadas y un informe que separa lo creado, lo probado en local, lo probado con Oracle real, lo ejecutado en GitHub y lo desplegado en Azure. No se declara una metodología formal (Scrum, etc.) porque no hay registros que la respalden.

### 4.4 Documentos de visión, SRS y SAD
Anexos 02, 03 y 04. Versiones corregidas propuestas: `docs/informes/`.

### 4.5 Cronograma
| Periodo | Hecho | Fuente |
| --- | --- | --- |
| 14‑sep a 06‑oct‑2026 | Aplicación base, FD01–FD04 y FD06 en PDF | `git log` (35 commits) |
| 18 a 20‑oct‑2026 | Fases 1–5 (local) | Informes de fase |
| Pendiente → 13‑nov‑2026 | Ejecutar en GitHub/Azure lo preparado, medir usabilidad, regenerar PDF/Word, presentación | Propuesta del plan de la Fase 0; **fecha límite de entrega: 15‑nov‑2026 00:00** (consigna) |

## 5. Presupuesto
Los costos de un escenario de implantación (VM de nube, copias, dominio, soporte) están en FD01 §7–§9 y son **estimaciones** con precios consultados el 1‑oct‑2026 (no reverificados). No se registraron horas ni desembolsos del prototipo; la demostración usó créditos educativos informados por el equipo. El estimador de costos de Terraform (`scripts/costs/estimate_costs.py`) distingue estimado de real y no inventa cifras si falla la API de precios; **no se ejecutó con un plan real**.

## 6. Resultados y estado de verificación

### 6.1 Qué hace hoy la aplicación [Hecho]
Proyectos, perfiles sin contraseña, casos y suites (`ROW_COUNT`, `SCALAR_VALUE`, `EXISTS`), ejecución individual/de suite/rápida, política SQL por ambiente, historial con origen y corrida, «Inicio» con resultado explicado, panel «Uso del producto» (cifras desde datos guardados), Excel (plantilla, importar todo-o-nada, exportar), CLI con informes y códigos de salida. Endpoints: `docs/generated/api-endpoints.md`. Datos: `docs/generated/diccionario-datos.md`.

### 6.2 Estado por componente
«Probado local» incluye el uso de Oracle **simulado** (sustituto SQLite de las pruebas) o H2: no es Oracle real. Fecha de las pruebas con Oracle real: 18‑oct‑2026, Oracle Free en Docker local desechable, antes de que Docker Desktop dejara de arrancar contenedores; **no se repitieron** tras los cambios de las Fases 3 a 5.

| Componente | Creado | Probado local | Probado con Oracle real | Ejecutado en GitHub | Desplegado en Azure |
| --- | --- | --- | --- | --- | --- |
| API, motor y política SQL | Sí | Sí (suite pytest) | Sí (Fase 2: SELECT, INSERT revertido, `DROP`/`TRUNCATE`/`ALTER` rechazados, suite 5 PASS→FAIL→5 PASS) | No verificado | No verificado |
| Inicio / prueba rápida | Sí | Sí (Oracle simulado) | Sin prueba automática | No | No |
| Dashboard de uso | Sí | Sí (reloj fijo; datos sembrados) | No aplica (usa solo la SQLite interna) | No | No |
| Excel | Sí | Sí (openpyxl real) | No aplica a importar; exportar resultados usa el historial | No | No |
| CLI | Sí | Sí (sustituto SQLite de Oracle; subproceso) | **No** | No | No |
| Workflow `sql-checks.yml` | Sí | Solo análisis estático del YAML | No | **No** | No |
| Terraform | Sí | `fmt`, `validate`, reglas de variables | No aplica | No | **No** (sin plan real) |
| Liquibase | Sí | `update-sql` y 2 ejecuciones sobre **H2 en modo Oracle**; idempotente | **No** (no es prueba contra Oracle) | No | No |
| Copias de la SQLite y restauración aislada | Sí | Sí (pytest) | No aplica | No | No |
| Release / despliegue con reversa | Sí | `docker build`; `bash -n` | No | No | No |
| Documentación generada (Fase 5) | Sí | Generadores, validación de Mermaid y construcción del sitio MkDocs | No aplica | **No** (workflows creados, no ejecutados) | Pages **no publicado** |
| Usabilidad (OS‑1/OS‑2) | Protocolo | **No medido** | — | — | — |

### 6.3 Pruebas ejecutadas (comando y resultado)
Ejecutadas el 20‑oct‑2026 en un equipo Windows con Python 3.11.9 (el `Dockerfile` y GitHub Actions usan 3.12: **no se probó con 3.12**), desde `framework-pruebas-sql/`:

| Comando | Resultado |
| --- | --- |
| `python -m pytest -q` (sin variables Oracle) | **330 superadas, 23 omitidas, 0 fallidas** (48 s; Fase 7). Las 23 omitidas son las pruebas Oracle y no cuentan como aprobadas. `--collect-only`: 353 pruebas |
| `python -m pytest -q tests/test_phase5_docs.py` | 24 superadas (más 21 de `tests/test_oracle_guard.py`) |
| `python scripts/docs/gen_docs.py --check` | «OK: 40 archivos generados al día» |
| `python -m mkdocs build --strict` | Sitio construido sin avisos (1,6 s) |
| `node --check` de cada `.js` de `frontend/` | 15 archivos, sin errores |
| Validación de Mermaid (Mermaid 10.9.1 en Edge sin cabeza, necesita internet) | 6 diagramas generados: análisis y dibujo correctos |
| `git diff --check` | 0 errores de espacios (solo avisos de fin de línea CRLF/LF) |

Con Oracle real (Oracle Free en Docker local desechable, 18‑oct‑2026, Fase 2): `python -m pytest -m oracle_integration -v -s` → 23 superadas; suite completa con Oracle → 198 superadas. **No se repitió el 20‑oct‑2026** (en las Fases 3 y 4 Docker Desktop dejó de arrancar contenedores en ese equipo; en la Fase 5 no se reintentó ni se reinició) y desde entonces cambió el código de las Fases 3 a 5.

Cobertura de la documentación del código (Fase 6, `docs/generated/cobertura-docstrings.md`, generada): módulos con docstring 25/28; clases 11/41; funciones públicas 52/81; métodos públicos 6/25; propiedades con docstring 0/226, de las que 56 columnas ORM se describen en el diccionario de datos y 170 (145 de ellas campos Pydantic de `schemas.py`) no tienen descripción. El sitio muestra clases, métodos y propiedades, pero **muchos sin texto explicativo**: es una brecha de contenido, no de herramienta.

Hallazgos corregidos en la Fase 6: un Excel rechazado importado con `--create-project` dejaba un proyecto vacío (ahora se valida antes de crearlo, con prueba); el panel contaba los intentos de importar Excel rechazados como «importaciones» (la etiqueta y las limitaciones ahora lo dicen).

Falla real encontrada por estas pruebas en la Fase 5: `pages.yml` tenía un nombre de paso con dos puntos que lo hacía YAML inválido; se corrigió.

## 7. Conclusiones
1. Existe una aplicación que permite definir, ejecutar, repetir y registrar comprobaciones SQL sobre Oracle con reglas por ambiente; su comportamiento central se verificó con pruebas automáticas y, en un Oracle local desechable, con SELECT, INSERT revertido y rechazo de DDL.
2. El rollback y el bloqueo de DDL son **controles**, con límites declarados; no garantizan inocuidad. Un PASS solo significa coincidencia con la regla configurada.
3. La utilidad (tiempo al primer resultado, ahorro) **no está medida**; son metas e hipótesis con un protocolo listo.
4. La automatización de infraestructura, copias, release y documentación está preparada y probada en local; **falta ejecutarla en GitHub y Azure**.
5. No hubo cliente ni entrevistas; los documentos deben decirlo siempre.

## 8. Recomendaciones
Ejecutar el protocolo de usabilidad con compañeros; repetir las pruebas con Oracle real tras los cambios recientes; ejecutar los workflows en GitHub y guardar sus artefactos; definir usuarios individuales; decidir la licencia; verificar los antecedentes que se citen por número de anexo.

## 9. Bibliografía (fuentes abiertas y leídas el 20‑oct‑2026)
- Contraloría General de la República (2024). *Términos de referencia para el servicio de mejora para el software de gestión de la línea de producción de microformas digitales*. https://doc.contraloria.gob.pe/BID/2024/BID_SCC635/TDR.pdf
- Ministerio del Ambiente (s. f.). *Servicio de consultoría para el fortalecimiento del enfoque de economía circular en la Huella de Carbono Perú…* https://www.minam.gob.pe/wp-content/uploads/2022/01/TdR-Actualizaci%C3%B3n-HC-Per%C3%BA.pdf
- Oracle (s. f.-a). *About DML statements and transactions*. https://docs.oracle.com/en/database/oracle/oracle-database/23/tdddg/dml-and-transactions.html
- Oracle (s. f.-b). *SQL Developer: Unit testing*. https://docs.oracle.com/database/sql-developer-17.4/RPTUG/sql-developer-unit-testing.htm
- sqlparse (s. f.). *Introduction*. https://sqlparse.readthedocs.io/en/stable/intro.html
- python-oracledb (s. f.). *Introduction* (versiones soportadas en modo Thin). https://python-oracledb.readthedocs.io/en/latest/user_guide/introduction.html
- Gamma, E., Helm, R., Johnson, R. y Vlissides, J. (1994). *Design Patterns: Elements of Reusable Object-Oriented Software*. Addison-Wesley.
- Citadas en FD01/FD02/FD06 y **no reabiertas** en la Fase 5: DigitalOcean, SQLite (API de respaldo), SBS, Punto.pe, ANPD, Docker, Presidencia del Consejo de Ministros.

## Anexos
- **Anexo 01**: Informe de factibilidad (FD01, con `FD01-parche.md`).
- **Anexo 02**: Documento de visión (FD02, con `FD02-parche.md`).
- **Anexo 03**: SRS (FD03, con `FD03-fuente-corregida.md`).
- **Anexo 04**: SAD (FD04, con `FD04-fuente-corregida.md`).
- **Anexo 05**: Manuales y otros documentos: `docs/manual-usuario.md`, `docs/manual-tecnico.md`, `docs/operacion-fase3.md`, `docs/integraciones-fase4.md`, diccionario y diagramas generados, estándar de programación, guion de demostración.

### Anexo A — Sentencias, reversibilidad y política (derivada de `app/security/sql_policy.py`)

| Sentencia | Según Oracle (23ai) | TEST | STAGING | PRODUCTION |
| --- | --- | --- | --- | --- |
| `SELECT` | No cambia datos | Permitida | Permitida | Permitida, **filas ocultas**; `FOR UPDATE` rechazado |
| `INSERT`/`UPDATE`/`DELETE` | Reversible con `ROLLBACK` mientras no haya `COMMIT` | Permitida; rollback | Permitida **con confirmación**; rollback | **Rechazada** |
| `CREATE`/`ALTER`/`DROP`/`TRUNCATE`/`GRANT`/`REVOKE` | DDL: `COMMIT` implícito (no reversible) | **Rechazada** | **Rechazada** | **Rechazada** |
| `COMMIT`/`ROLLBACK` | Control transaccional | Rechazada | Rechazada | Rechazada |
| `CALL`/`EXECUTE`/`BEGIN`/`DECLARE` (PL/SQL) | Pueden hacer cualquier cosa | Rechazada | Rechazada | Rechazada |
| `MERGE` | DML | Rechazada | Rechazada | Rechazada |
| Varias sentencias | — | Rechazada | Rechazada | Rechazada |
| `WITH` | Según su sentencia final | Permitida si `sqlparse` la clasifica como SELECT/INSERT/UPDATE/DELETE | Ídem | Solo si es SELECT |
| SELECT que invoca funciones con transacción autónoma, `DBMS_*`, `UTL_*` o enlaces | Efectos fuera del rollback | **No detectado** (análisis léxico) | **No detectado** | **No detectado** |

La política se evalúa **antes** de conectar: una sentencia rechazada no abre conexión (comprobado con Oracle real local: 0 conexiones y tabla intacta).

### Anexo B — Trazabilidad de columnas con los requisitos
| Tabla | Columnas | Requisito |
| --- | --- | --- |
| `projects` | id, name, description, created_at, updated_at | RF‑02 |
| `connection_profiles` | project_id, name, engine, host, port, service_name, username, environment_type | RF‑03, RF‑06 (ambiente), RNF‑03/04 |
| `test_cases` | project_id, name, description, sql_query, expected_result, validation_type | RF‑04, RF‑12 |
| `test_suites`, `suite_test_case` | project_id, name, description; suite_id, test_case_id | RF‑05 |
| `execution_history` | status, executed_at, duration_ms, statement_type, executed_sql, validation_type, expected_result, actual_result, rowcount, rollback_applied, rollback_error, error_message | RF‑07, RF‑08, RF‑06 |
| `execution_history` | project_id, test_case_id, suite_id, connection_profile_id, trigger_source, run_id | RF‑08, RF‑11 |
| `usage_events` | event_type, project_id, source, detail, created_at | RF‑11, RF‑12 |

Cobertura: las 7 tablas y todas sus columnas tienen descripción en el diccionario generado (el generador falla si falta alguna).
