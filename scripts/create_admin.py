"""Crea el primer administrador de forma interactiva. No acepta contraseñas por CLI."""
from getpass import getpass
import re

from app.core.auth_crypto import hash_password
from app.core.config import get_settings
from app.core.database import Database


def main():
    settings = get_settings()
    if not settings.auth_secret_key or len(settings.auth_secret_key.get_secret_value()) < 32:
        raise SystemExit("Configura AUTH_SECRET_KEY (mínimo 32 caracteres) antes de continuar.")
    email = input("Correo del administrador: ").strip().lower()
    nombre = input("Nombre: ").strip()
    if not re.fullmatch(r"[^@\\s]+@[^@\\s]+\\.[^@\\s]+", email) or not nombre:
        raise SystemExit("Correo o nombre inválido.")
    password = getpass("Contraseña (mínimo 12 caracteres): ")
    confirm = getpass("Confirma la contraseña: ")
    if password != confirm or len(password) < 12:
        raise SystemExit("Las contraseñas no coinciden o son demasiado cortas.")
    if not any(c.islower() for c in password) or not any(c.isupper() for c in password) or not any(c.isdigit() for c in password):
        raise SystemExit("La contraseña debe incluir mayúsculas, minúsculas y números.")

    db = Database(settings)
    try:
        with db.transaction() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id_usuario FROM auth_usuarios WHERE email=%s", (email,))
            if cur.fetchone():
                raise SystemExit("Ya existe una cuenta con ese correo.")
            cur.execute(
                """SELECT COUNT(*) FROM auth_usuario_roles ur
                   JOIN auth_roles r ON r.id_rol=ur.id_rol WHERE r.codigo='admin'"""
            )
            if int(cur.fetchone()[0]) > 0:
                raise RuntimeError("Ya existe un administrador. Las altas posteriores deben gestionarse desde Administración.")
            cur.execute("SELECT id_rol FROM auth_roles WHERE codigo='admin' FOR UPDATE")
            role = cur.fetchone()
            if not role:
                raise RuntimeError("No existe el rol admin. Aplica primero M001.")
            cur.execute(
                "INSERT INTO auth_usuarios(email,nombre,password_hash,activo) VALUES(%s,%s,%s,TRUE)",
                (email, nombre, hash_password(password)),
            )
            cur.execute("INSERT INTO auth_usuario_roles(id_usuario,id_rol) VALUES(%s,%s)",
                        (cur.lastrowid, role[0]))
            cur.close()
        print("Administrador creado correctamente.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
