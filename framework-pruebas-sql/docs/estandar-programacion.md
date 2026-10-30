# Estándar de programación

Para Kevin y Gerald. Cada regla es de uno de dos tipos:

- **Observada**: ya se cumple en el código (se indica dónde).
- **Propuesta**: el equipo la acuerda desde ahora. **No hay linter ni formateador configurado hoy** (no existe `pyproject.toml`, `ruff.toml` ni `.flake8`); las reglas propuestas se comprueban en revisión, salvo las que ya tienen una prueba automática (marcadas).

## 1. Estructura

| Regla | Tipo |
| --- | --- |
| `app/api/` solo contiene routers FastAPI: validan la entrada, llaman a servicios y traducen errores a HTTP. | Observada |
| `app/services/` orquesta (ejecución, uso, Excel, demostración). `app/engine/` ejecuta y valida contra la base objetivo. `app/security/` decide qué se permite. `app/models/` define tablas (ORM) y esquemas Pydantic. | Observada |
| La lógica de negocio no va en el frontend: toda regla de seguridad se aplica en el backend. | Observada (`docs/seguridad.md`) |
| Un cambio de esquema de la base interna **siempre** va con una migración Alembic; `alembic check` no debe mostrar diferencias. | Observada (prueba `tests/test_execution_engine.py` espera la cabeza de migraciones) |
| Los objetos Oracle de la demostración se versionan con Liquibase (`infra/oracle/liquibase/`), nunca a mano. | Observada |

## 2. Estilo de código Python

| Regla | Tipo |
| --- | --- |
| Python 3.12 (`Dockerfile`); sangría de 4 espacios; nombres `snake_case` para funciones y variables, `PascalCase` para clases, `MAYUSCULAS` para constantes. | Observada |
| Comentarios y docstrings en español, una línea de resumen y luego el detalle. Los docstrings alimentan la documentación técnica (`mkdocstrings`): toda clase y función pública lleva docstring. | Observada / Propuesta (cobertura) |
| Anotaciones de tipo en funciones públicas nuevas. | Propuesta |
| No usar `except:` sin tipo; los mensajes de error al usuario no incluyen contraseñas (`TargetDatabaseExecutor._sanitize_message`). | Observada |
| Mensajes para personas en español claro; sin jerga de implementación. | Observada (`explain_execution`) |
| Línea ≤ 120 caracteres. | Propuesta |
| Linter y formateador (`ruff check` y `ruff format`) en CI. | Propuesta; ver tarea T1 en `docs/tareas-gerald.md` |

## 3. Seguridad (reglas que no se negocian)

1. Nunca guardar, registrar ni devolver una contraseña (de Oracle, de acceso ni de secretos). La contraseña de Oracle llega por petición o por variable de entorno (CLI) y se descarta. **Observada.**
2. Los destinos Oracle salen solo de perfiles guardados y validados (`app/security/target_policy.py`); no se acepta un DSN libre. **Observada.**
3. Toda sentencia pasa por `validate_sql_statement` **antes** de abrir una conexión. **Observada**, con prueba (`tests/test_oracle_phase2.py` comprueba 0 conexiones).
4. En PRODUCTION no se guardan filas ni mensajes técnicos. **Observada**, con prueba.
5. Ningún secreto en el repositorio: `.env*` está en `.gitignore`; las pruebas usan valores ficticios. **Observada.**
6. En Excel y CLI, los textos que empiezan por `=`, `+`, `-` o `@` se tratan como texto (inyección de fórmulas). **Observada**, con prueba (`tests/test_phase4_excel.py`).

## 4. Pruebas

| Regla | Tipo |
| --- | --- |
| `pytest`; un archivo `tests/test_<tema>.py`; funciones `test_<comportamiento>` con nombre que dice qué se comprueba. | Observada |
| Las pruebas que necesitan un Oracle real llevan `@pytest.mark.oracle_integration` y se **omiten** sin variables de entorno (no cuentan como aprobadas). | Observada |
| Las pruebas Oracle **destructivas** (borran filas, crean cuentas o usan la clave de SYS) solo corren contra un Oracle local o de CI; con otro host se omiten sin conectar. Se autoriza un host remoto desechable con `ORACLE_TESTS_CONFIRM_DESTRUCTIVE_HOST=<host exacto>`. | Observada (`tests/oracle_guard.py`, `tests/test_oracle_guard.py`) |
| Las pruebas con Oracle simulado (`tests/fake_oracle.py`, SQLite) se rotulan como simuladas: no sustituyen a las de Oracle real. | Observada |
| Una corrección de error añade una prueba que falla sin ella. | Propuesta |
| Antes de subir: `python -m pytest -q` y `node --check` de cada `.js` de `frontend/`. | Observada (`.github/workflows/tests.yml`) |
| Antes de subir cambios de modelos, endpoints, infraestructura o `descripciones_datos.py`: `python scripts/docs/gen_docs.py` y subir lo regenerado. | Propuesta con **prueba** (`tests/test_phase5_docs.py` falla si lo generado está desactualizado) |

## 5. Git y revisión

| Regla | Tipo |
| --- | --- |
| Ramas `feature/…`, `fix/…`, `chore/…`, `docs/…` y *pull request* hacia `main`. | Observada (PR #1 a #5 en el historial) |
| Mensajes de commit al estilo `tipo: resumen` (`feat`, `fix`, `docs`, `chore`, `ci`, `refactor`). | Observada |
| Cada integrante hace commit con **su propia cuenta**; el otro revisa el PR antes de fusionar. | Propuesta (el historial actual tiene commits de una sola persona; ver la matriz de contribuciones) |
| No reescribir historial ni atribuir trabajo a quien no lo hizo. | Propuesta |
| No subir bases `.db`/`.sqlite`, `.env`, llaves, estados de Terraform ni informes generados. | Observada (`.gitignore`) |

## 6. Documentación

- Lo que se puede generar **no se edita a mano**: diccionario de datos, diagramas ER/clases/componentes/despliegue, tabla de endpoints, bloque «Resumen generado» del README y referencia del código (`scripts/docs/gen_docs.py`).
- Toda afirmación de un informe cita su evidencia (archivo, prueba o ejecución) y se rotula **Hecho / Fuente / Meta / Hipótesis / Futuro**.
- Se distingue siempre «creado / probado en local / probado con Oracle real / ejecutado en GitHub / desplegado en Azure».
- Una cifra que no se midió es una meta o una hipótesis, nunca un resultado.
- Capturas con datos sintéticos, H2 o sustitutos SQLite se rotulan «ilustrativa».

## 7. Nombres en la base de datos

Tablas en plural y `snake_case` (`test_cases`), tabla de asociación en singular (`suite_test_case`), claves foráneas `<tabla_singular>_id`, fechas `created_at`/`updated_at` en UTC. **Inconsistencia conocida:** `test_cases` y `test_suites` guardan UTC sin zona horaria y las demás tablas con zona horaria (ver diccionario de datos).
