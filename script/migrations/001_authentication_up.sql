-- M001: identidad, perfiles y sesiones. No altera ni elimina tablas existentes.
-- Aplicar primero en staging; requiere respaldo verificado de RDS.
CREATE TABLE IF NOT EXISTS auth_usuarios (
  id_usuario BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  email VARCHAR(254) NOT NULL,
  nombre VARCHAR(120) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id_usuario),
  UNIQUE KEY uq_auth_usuario_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS auth_roles (
  id_rol SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  codigo VARCHAR(20) NOT NULL,
  descripcion VARCHAR(120) NOT NULL,
  PRIMARY KEY (id_rol),
  UNIQUE KEY uq_auth_rol_codigo (codigo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS auth_usuario_roles (
  id_usuario BIGINT UNSIGNED NOT NULL,
  id_rol SMALLINT UNSIGNED NOT NULL,
  asignado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id_usuario, id_rol),
  CONSTRAINT fk_auth_ur_usuario FOREIGN KEY (id_usuario)
    REFERENCES auth_usuarios(id_usuario) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_auth_ur_rol FOREIGN KEY (id_rol)
    REFERENCES auth_roles(id_rol) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS auth_sesiones_refresh (
  id_sesion CHAR(36) NOT NULL,
  id_usuario BIGINT UNSIGNED NOT NULL,
  token_hash CHAR(64) NOT NULL,
  expira_en DATETIME NOT NULL,
  revocada_en DATETIME NULL,
  user_agent VARCHAR(255) NULL,
  creada_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id_sesion),
  UNIQUE KEY uq_auth_refresh_hash (token_hash),
  KEY ix_auth_refresh_usuario (id_usuario, revocada_en, expira_en),
  CONSTRAINT fk_auth_refresh_usuario FOREIGN KEY (id_usuario)
    REFERENCES auth_usuarios(id_usuario) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO auth_roles(codigo, descripcion) VALUES
 ('admin', 'Administrador de la empresa'),
 ('user', 'Cliente propietario'),
 ('guest', 'Invitado registrado');
