-- M001 DOWN: reversión SOLO de prueba/staging después de exportar usuarios/sesiones.
-- No toca las seis tablas IoT preexistentes. DDL MySQL realiza commits implícitos.
DROP TABLE IF EXISTS auth_sesiones_refresh;
DROP TABLE IF EXISTS auth_usuario_roles;
DROP TABLE IF EXISTS auth_roles;
DROP TABLE IF EXISTS auth_usuarios;
