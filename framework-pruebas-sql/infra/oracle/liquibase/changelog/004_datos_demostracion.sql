--liquibase formatted sql

--changeset equipo:004-datos-demostracion context:demo labels:demo runOnChange:true
--comment: Datos de ejemplo de la demostración (5 productos, 4 activos). SOLO en un Oracle desechable: borra y recarga la tabla.
--comment: Debe coincidir con infra/oracle/demo/seed_demo_data.sql (lo comprueba una prueba automática).
DELETE FROM FRAMEWORK_TEST_ITEMS;
INSERT INTO FRAMEWORK_TEST_ITEMS (ID, NAME, ACTIVE) VALUES (1, 'Cuaderno', 1);
INSERT INTO FRAMEWORK_TEST_ITEMS (ID, NAME, ACTIVE) VALUES (2, 'Lapicero', 1);
INSERT INTO FRAMEWORK_TEST_ITEMS (ID, NAME, ACTIVE) VALUES (3, 'Regla', 1);
INSERT INTO FRAMEWORK_TEST_ITEMS (ID, NAME, ACTIVE) VALUES (4, 'Borrador', 0);
INSERT INTO FRAMEWORK_TEST_ITEMS (ID, NAME, ACTIVE) VALUES (5, 'Tijera', 1);
--rollback DELETE FROM FRAMEWORK_TEST_ITEMS;
