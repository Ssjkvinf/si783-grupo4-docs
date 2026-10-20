# Guion de demostración (5–8 min) y preguntas del jurado

Para **Kevin y Gerald**. Cada afirmación remite a una pantalla, un comando o una evidencia. Nada de esto se ensayó con público; los tiempos son una propuesta [estimación].

## 0. Antes de empezar (30 min antes)

**Ruta A (recomendada): Oracle local desechable.** Seguir `docs/demostracion-fase2.md` §3.1–§3.3: Oracle Free en Docker (nunca la VM de Azure ni una base real), cargar los datos de demostración (5 productos, 4 activos) y levantar la aplicación en `http://127.0.0.1:8001/ui/`. Contraseñas solo en su `.env.oracle` local, que no se sube al repositorio.

**Ruta B (si falla Docker, Oracle o la red): modo simulado.**
```bash
python scripts/demo/offline_demo.py servir --puerto 8001
```
Levanta la aplicación con un **sustituto SQLite** de Oracle (proyecto «Demo simulado», conexión «SIMULADO»; cualquier contraseña salvo «mala»). **Dígalo en voz alta: «esto no es Oracle»**; muestra el flujo, no el comportamiento de Oracle. Para romper y reparar un dato:
```bash
python scripts/demo/offline_demo.py romper
python scripts/demo/offline_demo.py reparar
```
Sin internet: las páginas de la documentación y los diagramas Mermaid del sitio necesitan internet para dibujar; lleven **capturas hechas antes** (nombres sugeridos en el informe de la Fase 5) y el PDF de FD05.

**Siempre:** dejar abierta una terminal en `framework-pruebas-sql/` con el entorno activado; el último `python -m pytest -q` guardado en pantalla o en captura.

## 1. Guion

| Min | Quién | Qué se muestra | Qué se dice | Evidencia |
| --- | --- | --- | --- | --- |
| 0:00 | Kevin | Diapositiva con el problema | «Repetir una comprobación SQL y conservar su evidencia cuesta; es una necesidad potencial, no observada en una empresa». | `docs/problema-y-objetivos.md` §2 |
| 0:30 | Kevin | **Inicio**: conexión, `SELECT COUNT(*) FROM FRAMEWORK_TEST_ITEMS`, «valor que devuelve la consulta» = 5, ejecutar | PASS con la explicación «esperabas el valor 5 y la consulta devolvió 5». | Pantalla «Inicio»; `tests/test_quick_execution.py` |
| 1:15 | Kevin | Mismo SELECT con esperado 4; luego `SELECT * FROM TABLA_QUE_NO_EXISTE` | FAIL (se ejecutó y no coincide) y ERROR (no se pudo ejecutar: ORA‑00942 en Oracle). | `execution_service.explain_execution` |
| 2:00 | Gerald | **Suites**: cargar suites de demostración y ejecutar «reglas de calidad» | 5 PASS; cada regla con esperado, obtenido y motivo; «Ejecutar de nuevo» repite sin reconstruir. | `app/services/demo_scenario.py`; `tests/test_oracle_phase2.py::test_suite_de_reglas_se_configura_una_vez_y_se_repite` (Oracle real local, 18‑oct) |
| 3:00 | Gerald | Romper un dato (Ruta A: `UPDATE … SET ACTIVE = 7 WHERE ID = 4` + `COMMIT` con SQL*Plus del contenedor, `docs/demostracion-fase2.md` §3.4 paso 5; Ruta B: `offline_demo.py romper`) y repetir la suite | 4 PASS + 1 FAIL; se repara y vuelve a 5 PASS. Hay 3 corridas en **Historial**. | Pantalla «Historial» |
| 4:00 | Kevin | Caso con `INSERT INTO FRAMEWORK_TEST_ITEMS (ID, NAME, ACTIVE) VALUES (99,'Prueba',1)` en una conexión TEST; luego `SELECT COUNT(*)` | PASS con `rollback_applied`; el conteo sigue en 5. **Es un control, no una garantía** (no revierte secuencias ni transacciones autónomas). | `app/engine/executor.py`; Oracle real local: `tests/test_oracle_phase2.py` (conteo antes/después con otra conexión) |
| 4:45 | Kevin | Caso con `DROP TABLE FRAMEWORK_TEST_ITEMS` | ERROR «Rechazado por seguridad»; la tabla sigue. Aclarar: **bloquear DROP es un control, no el beneficio principal**. | `app/security/sql_policy.py`. **Precaución en Ruta A:** la cuenta de demostración es dueña de la tabla; si prefieren no arriesgarla, muestren la salida de `python -m pytest -m oracle_integration -k ddl -v -s` (cuenta de privilegio mínimo; requiere `ORACLE_PWD` del Oracle desechable) o hagan este paso en Ruta B |
| 5:30 | Gerald | **Uso del producto** | Ejecuciones por fecha, casos y suites más usados, origen (Inicio/UI/CLI/Actions); cada tarjeta explica su cálculo. «Con una demostración hay pocos datos; no es uso real». | `app/services/usage_service.py`; `tests/test_phase4_usage.py` |
| 6:15 | Gerald | Terminal: `python -m app.cli run …` (ver `docs/integraciones-fase4.md` §3) y `echo $?`; **Casos → Plantilla Excel** | Código de salida 0/1/2 según PASS/FAIL/ERROR; Excel con importación validada. | `tests/test_phase4_cli.py`, `tests/test_phase4_excel.py` |
| 7:00 | Kevin | `docs/generated/diagramas.md` o el sitio de documentación | Diagramas generados del código (ER de la base interna, clases, componentes, despliegue). | `python scripts/docs/gen_docs.py --check` |
| 7:30 | Kevin | Diapositiva de límites | Utilidad **no medida**; Azure y GitHub Actions **sin verificar**; una credencial compartida; Oracle ≥ 12.1. | `docs/informes/FD05-informe-final.md` §6.2 |

Si falta tiempo: omitir los minutos 2:00–3:00 (suite rota) o 6:15 (CLI/Excel). **No** omitir el 7:30.

## 2. Preguntas del jurado (respuestas breves)

| Pregunta | Respuesta | Evidencia |
| --- | --- | --- |
| ¿Cuál es el problema? | Repetir comprobaciones SQL sobre Oracle y conservar su evidencia está disperso; es una necesidad potencial, no observada en una organización. | `docs/problema-y-objetivos.md` §2 |
| ¿Para quién? | Personas que desarrollan o prueban sobre Oracle y quien autoriza la conexión (DBA). No existe empresa cliente. | FD02 §3; FD06 §1 |
| ¿Qué beneficio tiene? | Poder repetir, ver por qué pasó o falló y conservar la evidencia. El ahorro de tiempo **no se midió**; las cifras de FD01 son escenarios. | `docs/problema-y-objetivos.md` §4.3 |
| ¿En qué se diferencia de escribir SQL a mano? | A mano se pierde lo esperado y el registro; aquí cada ejecución guarda SQL, esperado, obtenido, estado, duración y origen, y se repite con un clic o con la CLI. | Pantalla Historial; `docs/generated/diccionario-datos.md` |
| ¿Y de SQL Developer u otras herramientas? | SQL Developer ya tiene suites y línea de comandos; no afirmamos ser mejores. Aportamos una vía web, política por ambiente, Excel, panel de uso y CLI; **no se comparó con usuarios**. | `docs/informes/FD05-informe-final.md` §3.4 |
| ¿Cuál es el alcance? | Oracle ≥ 12.1; tres validaciones; SELECT en todos los ambientes y DML en TEST/STAGING; sin usuarios individuales, sin carga, sin certificación de seguridad. | `docs/problema-y-objetivos.md` §3 |
| ¿Cuál es la arquitectura y por qué? | FastAPI sirve la interfaz y la API; SQLite guarda metadatos e historial; Oracle es la base que se comprueba, con una conexión por ejecución. Capas api / services / engine / security / models para que la política de SQL esté en un solo lugar. SQLite porque es una sola instancia y no requiere un servidor aparte (límite: un escritor a la vez). | `docs/generated/diagramas.md` (componentes, despliegue) |
| ¿Cómo se evalúa un caso? | 1) política de SQL antes de conectar; 2) conexión con el perfil guardado; 3) ejecución; 4) rollback si fue DML; 5) estrategia de comparación (`ROW_COUNT`, `SCALAR_VALUE`, `EXISTS`); 6) estado PASS/FAIL/ERROR y registro en el historial. | `app/services/execution_service.py::run_single_test_case_execution` |
| ¿Por qué FastAPI? | Genera la documentación OpenAPI (`/docs`) y valida la entrada con Pydantic; con un solo servicio se sirve también la interfaz. No se comparó con otros marcos. | `app/main.py`; `docs/generated/api-endpoints.md` |
| ¿Por qué SQLite y Oracle? | SQLite: base **interna** de la aplicación. Oracle: base **objetivo** que se comprueba; la aplicación no la posee. Son dos cosas distintas. | `docs/generated/diccionario-datos.md` §1 y §2 |
| ¿Qué son PASS, FAIL y ERROR? | PASS: coincide con lo esperado. FAIL: se ejecutó y no coincide. ERROR: no se pudo ejecutar o evaluar (SQL inválido, conexión, rechazo de política). PASS no significa que toda la base sea correcta. | `explain_execution`; FD01 §10.1 |
| ¿Qué es una suite? | Un grupo de casos del mismo proyecto que se ejecutan juntos y comparten una corrida en el historial. | `app/api/suites.py`; `run_id` |
| ¿Cómo se prueba un SELECT? | `ROW_COUNT` cuenta filas; `SCALAR_VALUE` compara el valor de una sola fila (p. ej. `COUNT(*)`); `EXISTS` comprueba si hay filas. Un `COUNT(*)` con `ROW_COUNT=1` pasa siempre: por eso existe `SCALAR_VALUE`. | `docs/demostracion-fase2.md` §1 |
| ¿Cómo funciona el INSERT con rollback? | En TEST se ejecuta con `autocommit` desactivado y se hace `ROLLBACK`; se comprobó con Oracle local contando filas antes y después con **otra** conexión. Límites: secuencias, transacciones autónomas y paquetes que escriben fuera. | `tests/test_oracle_phase2.py`; `docs/demostracion-fase2.md` §5 |
| ¿Por qué se rechaza el DROP? | Oracle confirma el DDL por sí solo (no se podría revertir), y el rechazo ocurre antes de abrir la conexión (0 conexiones; la tabla sigue intacta). Es un **control**, no el beneficio; además hace falta una cuenta Oracle de privilegio mínimo. | `app/security/sql_policy.py`; Oracle (23ai) |
| ¿Está desplegado en Azure? | El equipo informa que sí; la evidencia de acceso desde otra red está pendiente y Terraform/despliegue **no se ejecutaron**. | `docs/informes/FD05-informe-final.md` §6.2 |
| ¿Quién es el cliente? | No existe: es un proyecto académico. | FD01, FD02, FD06 |
| ¿Quién hizo qué? | Mostrar el historial de Git y los PR de cada integrante; no atribuir trabajo que no esté en el historial. | `git shortlog -sn`; `docs/tareas-gerald.md` |
