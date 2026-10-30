-- Privilegios que necesita la cuenta FRAMEWORK_TEST para que Liquibase cree SUS PROPIOS objetos.
-- Ejecutar UNA vez como SYS/SYSTEM en el Oracle de demostración (los hace el workflow en el Oracle desechable de CI).
--
--   CREATE SESSION : conectarse (ya lo concede infra/oracle/init/001_test_schema.sh)
--   CREATE TABLE   : tablas del esquema y las tablas de control DATABASECHANGELOG / DATABASECHANGELOGLOCK
--   CREATE VIEW    : la vista V_FW_ITEMS_ACTIVOS
--   (los índices del propio esquema no necesitan un privilegio adicional)
--
-- Aviso: con CREATE TABLE la cuenta puede crear tablas nuevas en su esquema. Es aceptable en una base de
-- demostración desechable; para una base real use una cuenta de migración separada de la que usa la aplicación.
WHENEVER SQLERROR EXIT FAILURE ROLLBACK
ALTER SESSION SET CONTAINER = FREEPDB1;
GRANT CREATE SESSION, CREATE TABLE, CREATE VIEW TO FRAMEWORK_TEST;
ALTER USER FRAMEWORK_TEST QUOTA 10M ON USERS;
EXIT
