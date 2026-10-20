# Fase 4: dashboard de uso e integraciones

Estado: implementado y probado **en local**. Lo que depende de GitHub o Azure está marcado como **pendiente de verificar**.

## 1. Dashboard «Uso del producto»

Se calcula en el servidor (`GET /api/usage/summary?days=30&project_id=`) con datos guardados: `execution_history`, `test_cases`, `test_suites`, `connection_profiles` y `usage_events`. Las fechas están en UTC.

| Métrica | Qué cuenta | Límite |
|---|---|---|
| Ejecuciones | Filas de historial del periodo. Un caso ejecutado una vez cuenta 1. | Una suite de 5 casos suma 5. |
| Corridas de suite | Ejecuciones agrupadas por `run_id`. En registros antiguos sin `run_id` se agrupa por suite y minuto. | Para registros antiguos es aproximado. |
| Tasa de PASS | PASS / total del periodo. | FAIL = se ejecutó pero no coincide. ERROR = no se pudo ejecutar o evaluar. |
| Casos distintos | Casos guardados ejecutados al menos una vez. | Las pruebas rápidas no cuentan como caso. |
| Proyectos activos | Proyectos con al menos una ejecución. | — |
| Duración media | Media de `duration_ms` medido por la aplicación. | No incluye la latencia del navegador. |
| Por fecha | Ejecuciones por día y resultado, con días vacíos en cero. | — |
| Origen | Interfaz web, recorrido «Inicio», CLI o GitHub Actions. | Los registros anteriores a la Fase 4 quedan sin origen. |
| Altas | Casos, suites y conexiones creados en el periodo. | — |
| Otras acciones | Importaciones y exportaciones de Excel (`usage_events`). | Solo desde la Fase 4. |

Estados vacíos: sin ejecuciones, el panel explica qué hacer (ejecutar un caso o una suite) en vez de mostrar ceros sin contexto. Si la API falla, hay un botón para reintentar.

No se mide uso por persona: la aplicación tiene un solo usuario compartido.

## 2. Excel (importar y exportar)

Interfaz: sección **Casos** → «Plantilla Excel», «Importar Excel», «Exportar casos», «Exportar resultados».

- Plantilla `.xlsx` con hoja «Casos» y columnas Nombre, Descripción, SQL, Validación (lista desplegable), Esperado y Suites (separadas por `;`).
- Importación **todo o nada**: primero se valida sin guardar y se informa fila por fila. Solo se guarda si no hay errores y la persona confirma.
- Validaciones: SQL con la misma política que la ejecución (DDL/DML prohibido, una sola sentencia), esperado coherente con el tipo, nombres no repetidos, fórmulas rechazadas, máximo 2 MB y 500 filas, rechazo de macros y de archivos comprimidos sospechosos.
- Exportación: los textos que empiezan por `=`, `+`, `-` o `@` se escriben como texto literal (evita inyección de fórmulas). Los resultados salen con PASS/FAIL/ERROR coloreado.
- Las mismas operaciones existen en la CLI (`import-excel`, `export-excel`).

## 3. CLI

```bash
python -m app.cli init-db --db checks.sqlite
python -m app.cli import-excel checks/reglas_demo.xlsx --project Demo --create-project --db checks.sqlite
export FW_ORACLE_PASSWORD='<clave-ficticia-reemplace-por-la-de-su-cuenta-de-prueba>'   # nunca como argumento
python -m app.cli run --project Demo --suite "Reglas de calidad (demo)" \
    --host 127.0.0.1 --port 1521 --service FREEPDB1 --user FRAMEWORK_TEST --env TEST \
    --junit reporte.xml --markdown reporte.md --json reporte.json --db checks.sqlite
```

Códigos de salida: `0` todo PASS · `1` hay FAIL · `2` hay ERROR (incluye no poder conectar) · `3` uso incorrecto · `4` no hay casos que ejecutar.
Si `GITHUB_ACTIONS=true`, el origen guardado es `GITHUB_ACTIONS`; si no, `CLI`.

## 4. GitHub Actions (`.github/workflows/sql-checks.yml`)

Se ejecuta en `pull_request` (por rutas), `workflow_dispatch` y `workflow_call`. Levanta un Oracle desechable (gvenzl), aplica Liquibase con `scripts/db/liquibase_demo.sh`, importa `checks/reglas_demo.xlsx`, ejecuta la suite con la CLI y publica Markdown en el resumen del job, más un artefacto `reporte-sql-checks` (Markdown, JUnit, JSON y Excel de resultados). El job falla con el código de la CLI. Las claves se generan en la ejecución y se enmascaran; no usa secretos del repositorio ni toca Azure.
Para ver el fallo a propósito: ejecutar manualmente con `provocar_dato_invalido = true`.

## 5. Evaluación crítica frente a la consigna

| Integración | Qué sí demuestra | Qué no demuestra / riesgo |
|---|---|---|
| CLI | Ejecuta casos/suites con el mismo motor y política, devuelve código útil y reportes. Sirve como compuerta de CI. | Es otro cliente de la misma aplicación: si el ingeniero exige una herramienta externa, por sí sola es débil. |
| GitHub Actions | Ejecuta el producto (no solo sus pruebas) contra un Oracle desechable y conserva el informe. | **Nunca se ejecutó en GitHub**: solo hay pruebas estáticas del YAML. No corre contra la base de Azure. |
| Excel | Flujo de ida y vuelta con validaciones. | Es una integración por formato de archivo, no con un servicio. Preguntar al ingeniero si cuenta como integración. |

## 6. Aclaración sobre Liquibase (Fase 3)

Ver el informe de Fase 4 en la conversación: la ejecución con H2 en modo Oracle solo valida la sintaxis y el orden de los changesets contra un motor distinto; **no es prueba contra Oracle real**. La verificación real queda para el workflow `db-objects.yml`/`sql-checks.yml` en GitHub.

## 7. Qué se probó y qué falta

Probado en local: migración (subida, bajada, `alembic check`), métricas con reloj fijo, API, Excel con openpyxl real, CLI en proceso y como subproceso, interfaz con navegador sin cabeza. El objetivo de los casos de CLI/API fue un **sustituto SQLite de Oracle** (`tests/fake_oracle.py`), no Oracle.
Pendiente: ejecutar `sql-checks.yml` en GitHub; repetir la demostración contra un Oracle real desechable; capturas reales (las generadas usan historial sintético).

## 8. Demostración corta (Kevin y Gerald, ~5 min)

1. Kevin: «Casos» → «Plantilla Excel», completar 2 filas, «Importar Excel» → confirmar. Mostrar también un Excel con errores (rechazo fila por fila).
2. Gerald: en terminal, `run` de la suite con la CLI; mostrar `reporte.md` y `echo $?`.
3. Kevin: «Uso del producto» → ver las corridas con origen CLI; abrir «Cómo leer estas cifras».
4. Gerald: en GitHub, ejecutar `SQL checks` manualmente con `provocar_dato_invalido` y mostrar el resumen y el artefacto.

## 9. Capturas que deben tomar

Dashboard sin datos; dashboard con datos reales; importación con errores; importación correcta; terminal con `run` y código de salida; resumen del job y artefacto en GitHub; Excel de resultados abierto.
