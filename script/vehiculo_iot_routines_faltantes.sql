-- =====================================================================
-- vehiculo_iot_routines.sql contiene 19 de los 21 Stored Procedures.
-- Este script crea los 2 que faltan, con la definicion exacta del
-- documento de la practica (mismos nombres y parametros):
--     sp_actualizar_demo
--     sp_agregar_movimiento_demo
--
-- EJECUTAR UNA SOLA VEZ en la base vehiculo_iot de Amazon RDS
-- (MySQL Workbench o cliente mysql). Es seguro repetirlo: usa DROP IF EXISTS.
--
-- Verificacion posterior (deben salir 21):
--   SELECT COUNT(*) FROM information_schema.ROUTINES
--    WHERE ROUTINE_SCHEMA='vehiculo_iot' AND ROUTINE_TYPE='PROCEDURE';
-- =====================================================================
USE vehiculo_iot;

DROP PROCEDURE IF EXISTS sp_actualizar_demo;
DROP PROCEDURE IF EXISTS sp_agregar_movimiento_demo;

DELIMITER $$

CREATE PROCEDURE sp_actualizar_demo(
    IN p_id_demo INT,
    IN p_nombre VARCHAR(80),
    IN p_descripcion VARCHAR(255),
    IN p_activo BOOLEAN
)
BEGIN
    UPDATE demos
       SET nombre=p_nombre, descripcion=p_descripcion, activo=p_activo
     WHERE id_demo=p_id_demo;
END$$

CREATE PROCEDURE sp_agregar_movimiento_demo(
    IN p_id_demo INT,
    IN p_id_comando INT,
    IN p_orden INT,
    IN p_duracion_ms INT,
    IN p_pausa_ms INT
)
BEGIN
    INSERT INTO demo_movimientos
      (id_demo,id_comando,orden,duracion_ms,pausa_ms)
    VALUES
      (p_id_demo,p_id_comando,p_orden,p_duracion_ms,p_pausa_ms);
END$$

DELIMITER ;
