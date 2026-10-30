-- Datos de demostración para la tabla FRAMEWORK_TEST_ITEMS (creada por infra/oracle/init/001_test_schema.sh).
--
-- SOLO para un Oracle LOCAL DESECHABLE (este script BORRA las filas de FRAMEWORK_TEST_ITEMS: verifique a qué base está conectado antes de ejecutarlo). Se ejecuta como el usuario FRAMEWORK_TEST (que solo es dueño de esa
-- tabla). La aplicación NUNCA ejecuta este script: lo corre una persona con sqlplus (ver README.md).
--
-- Es idempotente: borra las filas de la tabla de demostración y vuelve a cargar siempre las mismas 5.
-- Las reglas de la suite de demostración esperan exactamente estos datos:
--   5 productos · 4 activos (ACTIVE = 1) · 0 sin nombre · 0 con ACTIVE distinto de 0 y 1 · existe el ID 3.
WHENEVER SQLERROR EXIT FAILURE ROLLBACK
SET FEEDBACK OFF
SET HEADING OFF

DELETE FROM FRAMEWORK_TEST_ITEMS;

INSERT INTO FRAMEWORK_TEST_ITEMS (ID, NAME, ACTIVE) VALUES (1, 'Cuaderno', 1);
INSERT INTO FRAMEWORK_TEST_ITEMS (ID, NAME, ACTIVE) VALUES (2, 'Lapicero', 1);
INSERT INTO FRAMEWORK_TEST_ITEMS (ID, NAME, ACTIVE) VALUES (3, 'Regla', 1);
INSERT INTO FRAMEWORK_TEST_ITEMS (ID, NAME, ACTIVE) VALUES (4, 'Borrador', 0);
INSERT INTO FRAMEWORK_TEST_ITEMS (ID, NAME, ACTIVE) VALUES (5, 'Tijera', 1);

COMMIT;

SELECT 'Datos de demostracion cargados: ' || COUNT(*) || ' productos, ' ||
       SUM(CASE WHEN ACTIVE = 1 THEN 1 ELSE 0 END) || ' activos.'
  FROM FRAMEWORK_TEST_ITEMS;
EXIT
