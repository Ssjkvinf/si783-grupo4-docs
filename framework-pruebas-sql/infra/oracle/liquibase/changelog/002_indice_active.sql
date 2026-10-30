--liquibase formatted sql

--changeset equipo:002-indice-active context:esquema,demo labels:esquema
--comment: Índice por ACTIVE (acelera las reglas de calidad que filtran por ese campo).
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 SELECT COUNT(*) FROM user_indexes WHERE index_name = 'IX_FW_ITEMS_ACTIVE'
CREATE INDEX IX_FW_ITEMS_ACTIVE ON FRAMEWORK_TEST_ITEMS (ACTIVE);
--rollback DROP INDEX IX_FW_ITEMS_ACTIVE;
