"""Autorización por API key y sesión HttpOnly del dashboard.

Dos niveles:
  - control: acciones sobre el vehículo (POST de movimiento, iniciar/cancelar DEMO).
  - admin: todo lo anterior + crear/actualizar/eliminar vehículos, comandos y demos.

Las API keys viven en .env. El navegador nunca conserva la API key: la intercambia
por una cookie HttpOnly firmada, con expiración y sin incluir la clave original.
"""
import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Optional

from fastapi import Cookie, Depends, Security
from fastapi.security import APIKeyHeader
from pydantic import SecretStr

from app.core.config import Settings, get_settings
from app.core.exceptions import ForbiddenError, ServiceUnavailableError, UnauthorizedError

SESSION_COOKIE_NAME = "iot_dashboard_session"
api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="Clave de acceso. `control` para mover/DEMO; `admin` para crear, actualizar y eliminar.",
)


def _valor(clave: Optional[SecretStr]) -> str:
    return clave.get_secret_value() if clave else ""


def _coincide(recibida: str, configurada: str) -> bool:
    return bool(configurada) and secrets.compare_digest(recibida.encode(), configurada.encode())


def validar_api_key(api_key: Optional[str], settings: Settings) -> str:
    """Valida una API key y devuelve el rol; se usa también durante el login web."""
    admin, control = _valor(settings.api_key_admin), _valor(settings.api_key_control)
    if not admin and not control:
        raise ServiceUnavailableError(
            "Autenticación no configurada en el servidor (define API_KEY_ADMIN y API_KEY_CONTROL en .env)"
        )
    if not api_key:
        raise UnauthorizedError("Falta la cabecera X-API-Key")
    if _coincide(api_key, admin):
        return "admin"
    if _coincide(api_key, control):
        return "control"
    raise UnauthorizedError("API key inválida")


def _session_secret(settings: Settings) -> bytes:
    secret = _valor(settings.dashboard_session_secret)
    if len(secret) < 32:
        raise ServiceUnavailableError(
            "El dashboard requiere DASHBOARD_SESSION_SECRET de al menos 32 caracteres"
        )
    return secret.encode("utf-8")


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def crear_token_sesion(rol: str, settings: Settings) -> str:
    """Crea un token HMAC compacto. No contiene la API key ni datos del usuario."""
    if rol not in {"control", "admin"}:
        raise UnauthorizedError("Rol de sesión inválido")
    payload = json.dumps(
        {"role": rol, "exp": int(time.time()) + settings.dashboard_session_ttl_seconds},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    firma = hmac.new(_session_secret(settings), payload, hashlib.sha256).digest()
    return f"{_b64encode(payload)}.{_b64encode(firma)}"


def obtener_rol_sesion(token: Optional[str], settings: Settings) -> Optional[str]:
    """Verifica firma y expiración; devuelve None si la cookie no es válida."""
    if not token:
        return None
    try:
        payload_b64, firma_b64 = token.split(".", 1)
        payload = _b64decode(payload_b64)
        firma_recibida = _b64decode(firma_b64)
        firma_esperada = hmac.new(_session_secret(settings), payload, hashlib.sha256).digest()
        if not hmac.compare_digest(firma_recibida, firma_esperada):
            return None
        datos = json.loads(payload.decode("utf-8"))
        rol = datos.get("role")
        exp = int(datos.get("exp", 0))
        if rol not in {"control", "admin"} or exp <= int(time.time()):
            return None
        return rol
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError, ServiceUnavailableError):
        return None


def _rol(
    api_key: Optional[str],
    settings: Settings,
    session_cookie: Optional[str] = None,
) -> str:
    rol_sesion = obtener_rol_sesion(session_cookie, settings)
    if rol_sesion:
        return rol_sesion
    return validar_api_key(api_key, settings)


def requiere_control(
    api_key: Optional[str] = Security(api_key_header),
    settings: Settings = Depends(get_settings),
    session_cookie: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> str:
    """Acepta clave de control/admin o una sesión web válida."""
    return _rol(api_key, settings, session_cookie)


def requiere_admin(
    api_key: Optional[str] = Security(api_key_header),
    settings: Settings = Depends(get_settings),
    session_cookie: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> str:
    """Solo acepta clave admin o sesión web con rol admin."""
    rol = _rol(api_key, settings, session_cookie)
    if rol != "admin":
        raise ForbiddenError("Esta operación requiere permisos de administrador")
    return rol
