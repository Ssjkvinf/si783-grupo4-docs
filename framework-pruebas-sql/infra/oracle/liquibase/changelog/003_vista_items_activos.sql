--liquibase formatted sql

--changeset equipo:003-vista-items-activos context:esquema,demo labels:esquema runOnChange:true
--comment: Vista de los productos activos. runOnChange: si cambia la definición, Liquibase la vuelve a aplicar (CREATE OR REPLACE).
CREATE OR REPLACE VIEW V_FW_ITEMS_ACTIVOS AS
    SELECT ID, NAME FROM FRAMEWORK_TEST_ITEMS WHERE ACTIVE = 1;
--rollback DROP VIEW V_FW_ITEMS_ACTIVOS;
