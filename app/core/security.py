"""Autorización por API key (cabecera X-API-Key).

Dos niveles:
  - control: acciones sobre el vehículo (POST de movimiento, iniciar/cancelar DEMO).
  - admin:   todo lo anterior + crear/actualizar/eliminar vehículos, comandos y demos.

Las claves viven en .env (API_KEY_ADMIN / API_KEY_CONTROL), nunca en el código.
Si no hay ninguna configurada, las operaciones protegidas se rechazan (falla cerrada).
"""
import secrets
from typing import Optional

from fastapi import Depends, Security
from fastapi.security import APIKeyHeader
from pydantic import SecretStr

from app.core.config import Settings, get_settings
from app.core.exceptions import ForbiddenError, ServiceUnavailableError, UnauthorizedError

api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="Clave de acceso. `control` para mover/DEMO; `admin` para crear, actualizar y eliminar.",
)


def _valor(clave: Optional[SecretStr]) -> str:
    return clave.get_secret_value() if clave else ""


def _coincide(recibida: str, configurada: str) -> bool:
    return bool(configurada) and secrets.compare_digest(recibida.encode(), configurada.encode())


def _rol(api_key: Optional[str], settings: Settings) -> str:
    admin, control = _valor(settings.api_key_admin), _valor(settings.api_key_control)
    if not admin and not control:
        raise ServiceUnavailableError(
            "Autenticación no configurada en el servidor (define API_KEY_ADMIN y API_KEY_CONTROL en .env)")
    if not api_key:
        raise UnauthorizedError("Falta la cabecera X-API-Key")
    if _coincide(api_key, admin):
        return "admin"
    if _coincide(api_key, control):
        return "control"
    raise UnauthorizedError("API key inválida")


def requiere_control(
    api_key: Optional[str] = Security(api_key_header),
    settings: Settings = Depends(get_settings),
) -> str:
    """Acepta clave de control o de administrador."""
    return _rol(api_key, settings)


def requiere_admin(
    api_key: Optional[str] = Security(api_key_header),
    settings: Settings = Depends(get_settings),
) -> str:
    """Solo clave de administrador."""
    rol = _rol(api_key, settings)
    if rol != "admin":
        raise ForbiddenError("Esta operación requiere permisos de administrador")
    return rol
