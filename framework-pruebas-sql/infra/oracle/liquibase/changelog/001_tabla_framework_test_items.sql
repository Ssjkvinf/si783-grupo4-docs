--liquibase formatted sql

--changeset equipo:001-tabla-framework-test-items context:esquema,demo labels:esquema
--comment: Tabla de la demostración. Si ya existe (creada por infra/oracle/init/001_test_schema.sh) se marca como ejecutada sin tocarla.
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 SELECT COUNT(*) FROM user_tables WHERE table_name = 'FRAMEWORK_TEST_ITEMS'
CREATE TABLE FRAMEWORK_TEST_ITEMS (
    ID     NUMBER        PRIMARY KEY,
    NAME   VARCHAR2(100) NOT NULL,
    ACTIVE NUMBER(1)     DEFAULT 1 NOT NULL
);
-- Sin rollback automático a propósito: la tabla puede haber existido antes (MARK_RAN) y borrarla destruiría datos.
