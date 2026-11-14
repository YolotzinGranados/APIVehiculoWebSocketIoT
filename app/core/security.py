"""Acceso a la API sin autenticación por API key."""


def requiere_control() -> None:
    """Permite operaciones de control sin solicitar una clave."""
    return None


def requiere_admin() -> None:
    """Permite operaciones administrativas sin solicitar una clave."""
    return None