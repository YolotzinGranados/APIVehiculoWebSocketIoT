
"""Persistencia de usuarios, roles y sesiones de autenticacion."""

from datetime import datetime
import uuid


class AuthRepository:

    def __init__(self, db):
        self.db = db

    # --------------------------------------------------
    # DETECCION DE COLUMNAS REALES EN AWS RDS
    # --------------------------------------------------

    def _refresh_schema(self, conn):
        cur = conn.cursor()
        try:
            cur.execute("SHOW COLUMNS FROM auth_sesiones_refresh")
            columns = {row[0] for row in cur.fetchall()}
        finally:
            cur.close()

        def find_column(*candidates):
            for name in candidates:
                if name in columns:
                    return name
            raise RuntimeError(
                f"No se encontro ninguna de estas columnas "
                f"en auth_sesiones_refresh: {candidates}. "
                f"Columnas disponibles: {sorted(columns)}"
            )

        return {
            "session": find_column("id_sesion", "session_id"),
            "user": find_column("id_usuario", "user_id"),
            "token": find_column("token_hash"),
            "expires": find_column("expira_en", "expires_at"),
            "revoked": find_column("revocada_en", "revoked_at"),
            "agent": (
                "user_agent" if "user_agent" in columns else None
            ),
        }

    @staticmethod
    def _date(value):
        if value.tzinfo is not None:
            return value.replace(tzinfo=None)
        return value

    # --------------------------------------------------
    # USUARIOS
    # --------------------------------------------------

    @staticmethod
    def _user(row):
        if not row:
            return None

        roles_csv = row.get("roles_csv") or ""

        return {
            "id_usuario": int(row["id_usuario"]),
            "username": row.get("username"),
            "email": row.get("email"),
            "nombre": row["nombre"],
            "password_hash": row.get("password_hash"),
            "activo": bool(row["activo"]),
            "roles": roles_csv.split(",") if roles_csv else [],
        }

    def get_by_email(self, email: str):
        with self.db.connection() as conn:
            cur = conn.cursor(dictionary=True)
            try:
                cur.execute(
                    """
                    SELECT
                        u.id_usuario,
                        u.username,
                        u.email,
                        u.nombre,
                        u.password_hash,
                        u.activo,
                        GROUP_CONCAT(
                            r.codigo ORDER BY r.codigo
                        ) AS roles_csv
                    FROM auth_usuarios u
                    LEFT JOIN auth_usuario_roles ur
                        ON ur.id_usuario = u.id_usuario
                    LEFT JOIN auth_roles r
                        ON r.id_rol = ur.id_rol
                    WHERE u.email = %s
                    GROUP BY u.id_usuario
                    """,
                    (email.strip().lower(),)
                )
                return self._user(cur.fetchone())
            finally:
                cur.close()

    def get_by_id(self, user_id: int):
        with self.db.connection() as conn:
            cur = conn.cursor(dictionary=True)
            try:
                cur.execute(
                    """
                    SELECT
                        u.id_usuario,
                        u.username,
                        u.email,
                        u.nombre,
                        u.password_hash,
                        u.activo,
                        GROUP_CONCAT(
                            r.codigo ORDER BY r.codigo
                        ) AS roles_csv
                    FROM auth_usuarios u
                    LEFT JOIN auth_usuario_roles ur
                        ON ur.id_usuario = u.id_usuario
                    LEFT JOIN auth_roles r
                        ON r.id_rol = ur.id_rol
                    WHERE u.id_usuario = %s
                    GROUP BY u.id_usuario
                    """,
                    (user_id,)
                )
                return self._user(cur.fetchone())
            finally:
                cur.close()

    # --------------------------------------------------
    # REGISTRO DE INVITADOS
    # --------------------------------------------------

    def create_guest(
        self,
        *,
        email: str,
        nombre: str,
        password_hash: str,
        username: str | None = None
    ):
        username = (
            username.strip()
            if username
            else f"guest_{uuid.uuid4().hex[:12]}"
        )

        with self.db.transaction() as conn:
            cur = conn.cursor()
            try:
                cur.execute(
                    """
                    INSERT INTO auth_usuarios
                    (
                        username,
                        email,
                        nombre,
                        password_hash,
                        activo
                    )
                    VALUES (%s, %s, %s, %s, TRUE)
                    """,
                    (
                        username,
                        email.strip().lower(),
                        nombre.strip(),
                        password_hash
                    )
                )

                user_id = cur.lastrowid

                cur.execute(
                    """
                    SELECT id_rol
                    FROM auth_roles
                    WHERE codigo = 'guest'
                    """
                )

                role = cur.fetchone()

                if not role:
                    raise RuntimeError(
                        "El rol guest no existe en auth_roles."
                    )

                cur.execute(
                    """
                    INSERT INTO auth_usuario_roles
                    (id_usuario, id_rol)
                    VALUES (%s, %s)
                    """,
                    (user_id, role[0])
                )

                return int(user_id)

            finally:
                cur.close()

    # --------------------------------------------------
    # CREAR SESION REFRESH
    # --------------------------------------------------

    def create_refresh_session(
        self,
        *,
        session_id: str,
        user_id: int,
        token_hash: str,
        expires_at: datetime,
        user_agent: str | None
    ):
        with self.db.transaction() as conn:
            schema = self._refresh_schema(conn)

            fields = [
                schema["session"],
                schema["user"],
                schema["token"],
                schema["expires"],
            ]

            values = [
                session_id,
                user_id,
                token_hash,
                self._date(expires_at),
            ]

            if schema["agent"]:
                fields.append(schema["agent"])
                values.append((user_agent or "")[:255])

            columns_sql = ", ".join(
                f"`{field}`" for field in fields
            )

            placeholders = ", ".join(
                ["%s"] * len(values)
            )

            cur = conn.cursor()
            try:
                cur.execute(
                    f"""
                    INSERT INTO auth_sesiones_refresh
                    ({columns_sql})
                    VALUES ({placeholders})
                    """,
                    tuple(values)
                )
            finally:
                cur.close()

    # --------------------------------------------------
    # RENOVAR SESION REFRESH
    # --------------------------------------------------

    def rotate_refresh_session(
        self,
        *,
        old_hash: str,
        session_id: str,
        user_id: int,
        new_hash: str,
        expires_at: datetime,
        user_agent: str | None
    ):
        with self.db.transaction() as conn:
            schema = self._refresh_schema(conn)

            session_col = f"`{schema['session']}`"
            user_col = f"`{schema['user']}`"
            token_col = f"`{schema['token']}`"
            expires_col = f"`{schema['expires']}`"
            revoked_col = f"`{schema['revoked']}`"

            cur = conn.cursor()
            try:
                cur.execute(
                    f"""
                    SELECT {session_col}
                    FROM auth_sesiones_refresh
                    WHERE {token_col} = %s
                      AND {revoked_col} IS NULL
                      AND {expires_col} > UTC_TIMESTAMP()
                    FOR UPDATE
                    """,
                    (old_hash,)
                )

                if not cur.fetchone():
                    return False

                cur.execute(
                    f"""
                    UPDATE auth_sesiones_refresh
                    SET {revoked_col} = UTC_TIMESTAMP()
                    WHERE {token_col} = %s
                      AND {revoked_col} IS NULL
                    """,
                    (old_hash,)
                )

                fields = [
                    schema["session"],
                    schema["user"],
                    schema["token"],
                    schema["expires"],
                ]

                values = [
                    session_id,
                    user_id,
                    new_hash,
                    self._date(expires_at),
                ]

                if schema["agent"]:
                    fields.append(schema["agent"])
                    values.append((user_agent or "")[:255])

                columns_sql = ", ".join(
                    f"`{field}`" for field in fields
                )

                placeholders = ", ".join(
                    ["%s"] * len(values)
                )

                cur.execute(
                    f"""
                    INSERT INTO auth_sesiones_refresh
                    ({columns_sql})
                    VALUES ({placeholders})
                    """,
                    tuple(values)
                )

                return True

            finally:
                cur.close()

    # --------------------------------------------------
    # REVOCAR SESION
    # --------------------------------------------------

    def revoke_refresh_session(self, token_hash: str):
        with self.db.transaction() as conn:
            schema = self._refresh_schema(conn)

            cur = conn.cursor()
            try:
                cur.execute(
                    f"""
                    UPDATE auth_sesiones_refresh
                    SET `{schema['revoked']}` = UTC_TIMESTAMP()
                    WHERE `{schema['token']}` = %s
                      AND `{schema['revoked']}` IS NULL
                    """,
                    (token_hash,)
                )
            finally:
                cur.close()

    # --------------------------------------------------
    # CONSULTAR SESION REFRESH
    # --------------------------------------------------

    def find_refresh_session(self, token_hash: str):
        with self.db.connection() as conn:
            schema = self._refresh_schema(conn)

            cur = conn.cursor(dictionary=True)
            try:
                cur.execute(
                    f"""
                    SELECT
                        s.`{schema['user']}` AS id_usuario,
                        u.username,
                        u.email,
                        u.nombre,
                        u.activo,
                        GROUP_CONCAT(
                            r.codigo ORDER BY r.codigo
                        ) AS roles_csv

                    FROM auth_sesiones_refresh s

                    JOIN auth_usuarios u
                        ON u.id_usuario = s.`{schema['user']}`

                    LEFT JOIN auth_usuario_roles ur
                        ON ur.id_usuario = u.id_usuario

                    LEFT JOIN auth_roles r
                        ON r.id_rol = ur.id_rol

                    WHERE s.`{schema['token']}` = %s
                      AND s.`{schema['revoked']}` IS NULL
                      AND s.`{schema['expires']}` > UTC_TIMESTAMP()
                      AND u.activo = TRUE

                    GROUP BY
                        s.`{schema['session']}`,
                        s.`{schema['user']}`,
                        u.id_usuario,
                        u.username,
                        u.email,
                        u.nombre,
                        u.activo
                    """,
                    (token_hash,)
                )

                row = cur.fetchone()

                if not row:
                    return None

                roles_csv = row.get("roles_csv") or ""

                return {
                    "id_usuario": int(row["id_usuario"]),
                    "username": row.get("username"),
                    "email": row.get("email"),
                    "nombre": row["nombre"],
                    "activo": bool(row["activo"]),
                    "roles": (
                        roles_csv.split(",")
                        if roles_csv
                        else []
                    )
                }

            finally:
                cur.close()
