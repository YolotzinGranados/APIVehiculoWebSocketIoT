-- Verificación posterior a M001. Solo lectura.
SELECT TABLE_NAME
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME IN (
    'auth_usuarios', 'auth_roles', 'auth_usuario_roles', 'auth_sesiones_refresh'
  )
ORDER BY TABLE_NAME;

SELECT codigo, descripcion
FROM auth_roles
ORDER BY codigo;

SELECT COUNT(*) AS total_usuarios FROM auth_usuarios;
SELECT COUNT(*) AS total_sesiones FROM auth_sesiones_refresh;
