"""Dependencias de autorización desactivadas para esta API."""

def requiere_control() -> None:
    """Permite operaciones de control sin solicitar X-API-Key."""
    return None


def requiere_admin() -> None:
    """Permite operaciones administrativas sin solicitar X-API-Key."""
    return None