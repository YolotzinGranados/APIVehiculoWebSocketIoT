"""Persistencia de identidades y sesiones. No duplica datos de los vehículos."""
from datetime import datetime, timezone


class AuthRepository:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def _user(row):
        if not row:
            return None
        return {
            "id_usuario": int(row["id_usuario"]),
            "email": row["email"],
            "nombre": row["nombre"],
            "password_hash": row.get("password_hash"),
            "activo": bool(row["activo"]),
            "roles": list(row.get("roles") or []),
        }

    def get_by_email(self, email: str):
        with self.db.connection() as conn:
            cur = conn.cursor(dictionary=True)
            try:
                cur.execute(
                    """SELECT u.id_usuario, u.email, u.nombre, u.password_hash, u.activo,
                              GROUP_CONCAT(r.codigo ORDER BY r.codigo) AS roles_csv
                       FROM auth_usuarios u
                       LEFT JOIN auth_usuario_roles ur ON ur.id_usuario=u.id_usuario
                       LEFT JOIN auth_roles r ON r.id_rol=ur.id_rol
                       WHERE u.email=%s GROUP BY u.id_usuario""", (email.lower(),)
                )
                row = cur.fetchone()
                if row:
                    row["roles"] = (row.pop("roles_csv") or "").split(",") if row.get("roles_csv") else []
                return self._user(row)
            finally:
                cur.close()

    def get_by_id(self, user_id: int):
        with self.db.connection() as conn:
            cur = conn.cursor(dictionary=True)
            try:
                cur.execute(
                    """SELECT u.id_usuario, u.email, u.nombre, u.password_hash, u.activo,
                              GROUP_CONCAT(r.codigo ORDER BY r.codigo) AS roles_csv
                       FROM auth_usuarios u
                       LEFT JOIN auth_usuario_roles ur ON ur.id_usuario=u.id_usuario
                       LEFT JOIN auth_roles r ON r.id_rol=ur.id_rol
                       WHERE u.id_usuario=%s GROUP BY u.id_usuario""", (user_id,)
                )
                row = cur.fetchone()
                if row:
                    row["roles"] = (row.pop("roles_csv") or "").split(",") if row.get("roles_csv") else []
                return self._user(row)
            finally:
                cur.close()

    def create_guest(self, *, email: str, nombre: str, password_hash: str):
        with self.db.transaction() as conn:
            cur = conn.cursor()
            try:
                cur.execute(
                    "INSERT INTO auth_usuarios(email,nombre,password_hash,activo) VALUES(%s,%s,%s,TRUE)",
                    (email.lower(), nombre, password_hash),
                )
                user_id = cur.lastrowid
                cur.execute("SELECT id_rol FROM auth_roles WHERE codigo='guest'")
                role = cur.fetchone()
                if not role:
                    raise RuntimeError("Rol guest no inicializado; aplica migración M001")
                cur.execute("INSERT INTO auth_usuario_roles(id_usuario,id_rol) VALUES(%s,%s)", (user_id, role[0]))
                return int(user_id)
            finally:
                cur.close()

    def create_refresh_session(self, *, session_id: str, user_id: int, token_hash: str,
                               expires_at: datetime, user_agent: str | None):
        with self.db.transaction() as conn:
            cur = conn.cursor()
            try:
                cur.execute(
                    """INSERT INTO auth_sesiones_refresh
                       (id_sesion,id_usuario,token_hash,expira_en,user_agent)
                       VALUES(%s,%s,%s,%s,%s)""",
                    (session_id, user_id, token_hash, expires_at.replace(tzinfo=None), (user_agent or "")[:255]),
                )
            finally:
                cur.close()

    def rotate_refresh_session(self, *, old_hash: str, session_id: str, user_id: int,
                               new_hash: str, expires_at: datetime, user_agent: str | None):
        with self.db.transaction() as conn:
            cur = conn.cursor()
            try:
                cur.execute(
                    """SELECT id_sesion FROM auth_sesiones_refresh
                       WHERE token_hash=%s AND revocada_en IS NULL AND expira_en > UTC_TIMESTAMP()
                       FOR UPDATE""", (old_hash,)
                )
                if not cur.fetchone():
                    return False
                cur.execute(
                    "UPDATE auth_sesiones_refresh SET revocada_en=UTC_TIMESTAMP() WHERE token_hash=%s",
                    (old_hash,),
                )
                cur.execute(
                    """INSERT INTO auth_sesiones_refresh
                       (id_sesion,id_usuario,token_hash,expira_en,user_agent)
                       VALUES(%s,%s,%s,%s,%s)""",
                    (session_id, user_id, new_hash, expires_at.replace(tzinfo=None), (user_agent or "")[:255]),
                )
                return True
            finally:
                cur.close()

    def revoke_refresh_session(self, token_hash: str):
        with self.db.transaction() as conn:
            cur = conn.cursor()
            try:
                cur.execute(
                    """UPDATE auth_sesiones_refresh SET revocada_en=UTC_TIMESTAMP()
                       WHERE token_hash=%s AND revocada_en IS NULL""", (token_hash,)
                )
            finally:
                cur.close()

    def find_refresh_session(self, token_hash: str):
        with self.db.connection() as conn:
            cur = conn.cursor(dictionary=True)
            try:
                cur.execute(
                    """SELECT s.id_usuario, u.email, u.nombre, u.activo,
                              GROUP_CONCAT(r.codigo ORDER BY r.codigo) AS roles_csv
                       FROM auth_sesiones_refresh s
                       JOIN auth_usuarios u ON u.id_usuario=s.id_usuario
                       LEFT JOIN auth_usuario_roles ur ON ur.id_usuario=u.id_usuario
                       LEFT JOIN auth_roles r ON r.id_rol=ur.id_rol
                       WHERE s.token_hash=%s AND s.revocada_en IS NULL
                         AND s.expira_en > UTC_TIMESTAMP() AND u.activo=TRUE
                       GROUP BY s.id_sesion, u.id_usuario, u.email, u.nombre, u.activo""", (token_hash,)
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {"id_usuario": int(row["id_usuario"]), "email": row["email"],
                        "nombre": row["nombre"], "activo": bool(row["activo"]),
                        "roles": (row.get("roles_csv") or "").split(",") if row.get("roles_csv") else []}
            finally:
                cur.close()
