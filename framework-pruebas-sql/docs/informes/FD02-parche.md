# FD02 — Documento de visión: parche a la versión 1.1

> El PDF **no se modificó**. Filas de referencia: `matriz-afirmaciones.md` §D.

| Dónde | Cambio |
| --- | --- |
| 1.2 Alcance | Añadir al alcance implementado: validación `SCALAR_VALUE`; pantalla «Inicio» con prueba rápida de un SELECT (resultado explicado); panel «Uso del producto»; importación y exportación Excel; CLI con códigos de salida; origen de cada ejecución (UI, Inicio, CLI, GitHub Actions). |
| 1.3 Tabla 01 | Añadir términos: `SCALAR_VALUE`, prueba rápida, origen de ejecución. |
| 2.1 | Añadir: SQL Developer también ofrece ejecución por línea de comandos (`sdcli`), no solo suites. Este producto no se presenta como mejor sino como una alternativa web con Excel, CLI y panel de uso, **sin comparación medida**. |
| 4.1/4.2 | Distinguir siempre la **base interna (SQLite)** de la **base objetivo (Oracle)**; añadir que `python-oracledb` en modo Thin requiere Oracle 12.1 o posterior; con Thick y un cliente Oracle 19 se alcanzaría 11.2 según la documentación del controlador, **no verificado ni implementado**. |
| 5 Tabla 05 | Añadir V‑08 Inicio guiado, V‑09 Excel, V‑10 CLI, V‑11 Uso del producto. Cambiar «Comparación ROW_COUNT o EXISTS» por las tres validaciones. |
| 6 Tabla 06 | Añadir restricciones: Oracle anterior a 12.1 no soportado; una credencial compartida y token de sesión único; sin límite de intentos de acceso. |
| 7 Tabla 07 | Añadir la prueba de usabilidad (OS‑1/OS‑2) como **meta**, con el protocolo de `docs/protocolo-usabilidad.md`. |
| 9 Tabla 09 | FD03/FD04 quedan alineados con esta visión cuando se regeneren con las fuentes `FD03-fuente-corregida.md` y `FD04-fuente-corregida.md`. |
| Referencias | Unificar la cita de Oracle sobre transacciones (23ai). |

**Sin cambios:** la declaración de que no hay cliente, entrevistas, contrato ni medición; las condiciones de piloto; la advertencia sobre `ROLLBACK` y sqlparse.
