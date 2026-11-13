---
name: comprobaciones-sql
description: Ejecuta, importa y exporta comprobaciones SQL del Framework de pruebas SQL con su CLI (suites contra Oracle, casos desde Excel, resultados a Excel). Úsalo cuando pidan correr una suite, validar reglas de calidad de una tabla Oracle o sacar el reporte de PASS/FAIL/ERROR.
---

# Comprobaciones SQL (Framework de pruebas SQL)

Todo se hace con la CLI, desde la carpeta `framework-pruebas-sql`. No hace falta abrir la web.

## Reglas de seguridad (obligatorias)
- **Nunca** pidas, muestres ni escribas la contraseña de Oracle en un comando, archivo o mensaje. Pídele a la persona que la defina en su terminal: `export FW_ORACLE_PASSWORD='...'` (PowerShell: `$env:FW_ORACLE_PASSWORD='...'`).
- Solo el ambiente **TEST** (`--env TEST`). No uses STAGING ni PRODUCTION salvo que la persona lo pida expresamente.
- La herramienta solo admite SELECT (y INSERT/UPDATE/DELETE en TEST, que siempre se revierten). Rechaza DROP, TRUNCATE, ALTER, etc. antes de llegar a Oracle: no intentes saltarte eso.

## Flujo
1. Preparar la base interna (una vez): `python -m app.cli init-db`
2. Validar un Excel de casos sin guardar: `python -m app.cli import-excel checks/reglas_demo.xlsx --project "Demo" --create-project --dry-run`
3. Importarlo: mismo comando sin `--dry-run` (añade `--mode update` para actualizar casos existentes).
4. Ejecutar una suite:
   `python -m app.cli run --project "Demo" --suite "Reglas de calidad (demo)" --host <host> --port 1521 --service FREEPDB1 --user FRAMEWORK_TEST --env TEST --markdown reportes/ultima.md --json reportes/ultima.json --junit reportes/ultima.xml`
5. Exportar resultados: `python -m app.cli export-excel results --project "Demo" --out reportes/resultados.xlsx --force`

## Cómo leer el resultado (código de salida de `run`)
| Código | Significa |
|---|---|
| 0 | Todo PASS |
| 1 | Hay FAIL (se ejecutó pero no coincide con lo esperado: revisar los datos) |
| 2 | Hay ERROR (no se pudo ejecutar: tabla inexistente, contraseña mala, sentencia prohibida) |
| 3 | Uso inválido (proyecto o suite inexistente, falta la contraseña) |
| 4 | No había casos que ejecutar |

Resume al usuario cuántos casos dieron PASS/FAIL/ERROR usando `reportes/ultima.md`, y explica cada FAIL con «esperado» frente a «obtenido».
Cada ejecución queda también en el historial de la aplicación web (origen CLI).
