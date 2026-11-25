
"""Crea el primer administrador de forma interactiva."""
from getpass import getpass
import re

from app.core.auth_crypto import hash_password
from app.core.config import get_settings
from app.core.database import Database


def main():
    settings = get_settings()

    if (
        not settings.auth_secret_key
        or len(settings.auth_secret_key.get_secret_value()) < 32
    ):
        raise SystemExit(
            "ERROR: Configura AUTH_SECRET_KEY con al menos 32 caracteres en .env"
        )

    email = input("Correo del administrador: ").strip().lower()
    nombre = input("Nombre completo: ").strip()

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or not nombre:
        raise SystemExit("ERROR: El correo electrónico no es válido.")

    if len(nombre) < 2 or len(nombre) > 120:
        raise SystemExit("ERROR: El nombre debe tener entre 2 y 120 caracteres.")

    password = getpass("Contraseña (mínimo 12 caracteres): ")
    confirm = getpass("Confirma la contraseña: ")

    if password != confirm:
        raise SystemExit("ERROR: Las contraseñas no coinciden.")

    if len(password) < 12:
        raise SystemExit("ERROR: La contraseña debe tener al menos 12 caracteres.")

    if (
        not any(c.islower() for c in password)
        or not any(c.isupper() for c in password)
        or not any(c.isdigit() for c in password)
    ):
        raise SystemExit(
            "ERROR: Utiliza mayúsculas, minúsculas y números."
        )

    db = Database(settings)

    try:
        with db.transaction() as conn:
            cur = conn.cursor()

            cur.execute(
                "SELECT id_usuario FROM auth_usuarios WHERE email=%s",
                (email,),
            )
            if cur.fetchone():
                raise SystemExit("Ya existe una cuenta con ese correo.")

            cur.execute(
                """
                SELECT COUNT(*)
                FROM auth_usuario_roles ur
                JOIN auth_roles r ON r.id_rol = ur.id_rol
                WHERE r.codigo = 'admin'
                """
            )

            if int(cur.fetchone()[0]) > 0:
                raise SystemExit(
                    "Ya existe un administrador. "
                    "Las cuentas posteriores deben crearse desde Administración."
                )

            cur.execute(
                "SELECT id_rol FROM auth_roles WHERE codigo='admin' FOR UPDATE"
            )
            role = cur.fetchone()

            if not role:
                raise SystemExit(
                    "No existe el rol admin. "
                    "Primero debes aplicar la migración M001."
                )

            cur.execute(
                """
                INSERT INTO auth_usuarios
                    (email, nombre, password_hash, activo)
                VALUES (%s, %s, %s, TRUE)
                """,
                (email, nombre, hash_password(password)),
            )

            user_id = cur.lastrowid

            cur.execute(
                """
                INSERT INTO auth_usuario_roles (id_usuario, id_rol)
                VALUES (%s, %s)
                """,
                (user_id, role[0]),
            )

            cur.close()

        print("\nADMINISTRADOR CREADO CORRECTAMENTE.")
        print(f"Correo: {email}")
        print(f"ID de usuario: {user_id}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
