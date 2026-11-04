"""Rutas para servir el dashboard y administrar sesiones de navegador."""
from pathlib import Path

from fastapi import APIRouter, Cookie, Depends, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, SecretStr

from app.core.config import Settings, get_settings
from app.core.exceptions import UnauthorizedError
from app.core.security import (
    SESSION_COOKIE_NAME,
    crear_token_sesion,
    obtener_rol_sesion,
    validar_api_key,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
STATIC_DIR = Path(__file__).resolve().parent / "static"
INDEX_FILE = STATIC_DIR / "index.html"


class LoginIn(BaseModel):
    api_key: SecretStr


@router.get("", include_in_schema=False)
@router.get("/", include_in_schema=False)
def dashboard_index():
    """Entrega la aplicación web del dashboard."""
    return FileResponse(
        INDEX_FILE,
        media_type="text/html",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@router.post("/auth/login", include_in_schema=False)
def dashboard_login(
    datos: LoginIn,
    response: Response,
    settings: Settings = Depends(get_settings),
):
    """Valida una API key y la intercambia por una cookie HttpOnly firmada."""
    rol = validar_api_key(datos.api_key.get_secret_value(), settings)
    token = crear_token_sesion(rol, settings)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.dashboard_session_ttl_seconds,
        httponly=True,
        secure=settings.dashboard_cookie_secure,
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return {"authenticated": True, "role": rol}


@router.get("/auth/me", include_in_schema=False)
def dashboard_me(
    response: Response,
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    settings: Settings = Depends(get_settings),
):
    """Devuelve el rol asociado a la cookie de sesión actual."""
    rol = obtener_rol_sesion(session_cookie, settings)
    if not rol:
        raise UnauthorizedError("La sesión no existe o ha expirado")
    response.headers["Cache-Control"] = "no-store"
    return {"authenticated": True, "role": rol}


@router.post("/auth/logout", include_in_schema=False)
def dashboard_logout(response: Response, settings: Settings = Depends(get_settings)):
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=settings.dashboard_cookie_secure,
        httponly=True,
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"
    return {"authenticated": False}
