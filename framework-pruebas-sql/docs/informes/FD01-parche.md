# FD01 — Informe de factibilidad: parche a la versión 1.1

> FD01 es el más honesto de los cuatro (origen académico, sin cliente, cifras rotuladas como escenarios). Solo requiere los cambios de abajo. El PDF **no se modificó**. Filas de referencia: `matriz-afirmaciones.md` §C.

| Dónde | Texto actual (resumen) | Texto propuesto |
| --- | --- | --- |
| Resumen, Tabla 01 «Cliente real / Despliegue» | «La demostración se desplegó en una máquina virtual de Azure» | «El equipo informa que la demostración se desplegó en una máquina virtual de Azure; la evidencia de acceso desde otra red está pendiente.» |
| Tabla 02 «Hecho comprobado» | «aproximadamente cuatro semanas calendario» | «El historial de Git del repositorio va del 14‑sep al 06‑oct‑2026 (35 commits hasta esa fecha).» |
| §2 | «Su evaluación automática cubre principalmente ROW_COUNT y EXISTS» | «…cubre `ROW_COUNT`, `SCALAR_VALUE` (valor de una única fila, p. ej. `COUNT(*)`) y `EXISTS`.» |
| §3, párrafo final | «116 funciones con prefijo test_ … incluidas 13 de integración Oracle» | «A la fecha de revisión hay 22 archivos de prueba y 292 funciones `def test_` (recuento estático; el README lo regenera). La ejecución `python -m pytest -q` sin Oracle dio 330 superadas, 23 omitidas y 0 fallidas el 20‑oct‑2026 (Fase 7); las 23 pruebas Oracle pasaron una vez contra un Oracle Free local desechable (18‑oct‑2026).» *(Volver a medir justo antes de entregar.)* |
| §3 / §5 | «El procedimiento actual del repositorio usa una copia directa del archivo» | «La copia usa la API de respaldo de SQLite (`scripts/backup/sqlite_backup.py`) con verificación de integridad y restauración aislada; probada en local, aún no ejecutada en GitHub ni Azure.» |
| §5 | «la automatización y las pruebas aún no están implementadas» | «Están implementadas y probadas en local; falta ejecutarlas en GitHub y Azure.» |
| §5/§7 | Precios de DigitalOcean, SBS, Punto.pe del 1‑oct‑2026 | Reverificar la fecha de consulta antes de entregar (no se reabrieron en la Fase 5). |
| §10.2 | «No aparece un archivo LICENSE» | Se mantiene: sigue sin existir. Decidir licencia o dejar constancia. |
| §11 Tabla 15 | SRS y SAD «Actualizar» | Cambiar a «Corregido en FD03/FD04 v1.1» una vez regenerados los PDF. |
| §1/§3 (alcance técnico) | No menciona la versión de Oracle soportada | «La aplicación usa `python-oracledb` en modo Thin, que requiere Oracle Database 12.1 o posterior. Oracle 11g (p. ej. el que indica el TdR del MINAM) **no está soportado**: la documentación del controlador indica que el modo Thick con un cliente Oracle 19 alcanzaría la 11.2, pero la aplicación no lo activa, la imagen no incluye cliente Oracle y no se probó (**no verificado**).» |
| Referencias | Oracle (s. f.-a) *Oracle Database Free FAQ* y FD02 cita *Transactions* 19c; FD06 cita 23ai | Unificar la versión de la documentación de transacciones citada (23ai). |

**Sin cambios:** cifras de VAN, TIR y sensibilidad (siguen siendo escenarios derivados de supuestos); `FD05` no debe repetirlas como resultados.
