
"""Autenticación FastAPI: registro, login, refresh y logout."""

import secrets

from fastapi import APIRouter, Depends, Header, Request, Response

from app.core.config import get_settings
from app.core.dependencies import get_db
from app.core.auth import get_current_principal, Principal
from app.core.exceptions import BadRequestError, UnauthorizedError
from app.models.auth import (
    GuestRegisterIn,
    LoginIn,
    AuthResultOut,
    TokenOut,
    UserOut,
    MessageOut,
)
from app.services.auth_service import AuthService


router = APIRouter(prefix="/auth", tags=["Autenticación"])


def _service(db=Depends(get_db)):
    return AuthService(db, get_settings())


def _set_auth_cookies(response: Response, tokens: dict):
    settings = get_settings()

    max_age = settings.auth_refresh_ttl_days * 86400

    response.set_cookie(
        key=settings.auth_refresh_cookie_name,
        value=tokens["refresh_token"],
        max_age=max_age,
        httponly=True,
        secure=True,
        samesite="none",
        path="/auth",
    )

    response.set_cookie(
        key=settings.auth_csrf_cookie_name,
        value=tokens["csrf_token"],
        max_age=max_age,
        httponly=False,
        secure=True,
        samesite="none",
        path="/auth",
    )

    response.headers["Cache-Control"] = "no-store"


def _clear_auth_cookies(response: Response):
    settings = get_settings()

    response.delete_cookie(
        key=settings.auth_refresh_cookie_name,
        path="/auth",
        secure=True,
        httponly=True,
        samesite="none",
    )

    response.delete_cookie(
        key=settings.auth_csrf_cookie_name,
        path="/auth",
        secure=True,
        httponly=False,
        samesite="none",
    )

    response.headers["Cache-Control"] = "no-store"


def _validate_csrf(request: Request, csrf_header: str | None):
    settings = get_settings()

    csrf_cookie = request.cookies.get(
        settings.auth_csrf_cookie_name
    )

    if (
        not csrf_header
        or not csrf_cookie
        or not secrets.compare_digest(csrf_header, csrf_cookie)
    ):
        raise BadRequestError("Validación CSRF incorrecta")


def _user_out(user):
    if not user:
        raise UnauthorizedError("Usuario no encontrado")

    return UserOut(
        id_usuario=user["id_usuario"],
        email=user["email"],
        nombre=user["nombre"],
        roles=user["roles"],
        activo=user["activo"],
    )


@router.post(
    "/registro-invitado",
    status_code=201,
    response_model=AuthResultOut,
)
def registro_invitado(
    datos: GuestRegisterIn,
    request: Request,
    response: Response,
    service: AuthService = Depends(_service),
):
    user, tokens = service.register_guest(
        datos,
        request.headers.get("user-agent"),
    )

    _set_auth_cookies(response, tokens)

    return AuthResultOut(
        usuario=_user_out(user),
        access_token=tokens["access_token"],
        expires_in=tokens["expires_in"],
        csrf_token=tokens["csrf_token"],
    )


@router.post(
    "/login",
    response_model=AuthResultOut,
)
def login(
    datos: LoginIn,
    request: Request,
    response: Response,
    service: AuthService = Depends(_service),
):
    user, tokens = service.login(
        str(datos.email),
        datos.password,
        request.headers.get("user-agent"),
    )

    _set_auth_cookies(response, tokens)

    return AuthResultOut(
        usuario=_user_out(user),
        access_token=tokens["access_token"],
        expires_in=tokens["expires_in"],
        csrf_token=tokens["csrf_token"],
    )


@router.post(
    "/refresh",
    response_model=TokenOut,
)
def refresh(
    request: Request,
    response: Response,
    csrf_header: str | None = Header(
        default=None,
        alias="X-CSRF-Token",
    ),
    service: AuthService = Depends(_service),
):
    settings = get_settings()

    refresh_cookie = request.cookies.get(
        settings.auth_refresh_cookie_name
    )

    if not refresh_cookie:
        raise UnauthorizedError(
            "No existe una sesión de renovación"
        )

    _validate_csrf(request, csrf_header)

    _, tokens = service.refresh(
        refresh_cookie,
        request.headers.get("user-agent"),
    )

    _set_auth_cookies(response, tokens)

    return TokenOut(
        access_token=tokens["access_token"],
        expires_in=tokens["expires_in"],
        csrf_token=tokens["csrf_token"],
    )


@router.post(
    "/logout",
    response_model=MessageOut,
)
def logout(
    request: Request,
    response: Response,
    csrf_header: str | None = Header(
        default=None,
        alias="X-CSRF-Token",
    ),
    service: AuthService = Depends(_service),
):
    settings = get_settings()

    refresh_cookie = request.cookies.get(
        settings.auth_refresh_cookie_name
    )

    if refresh_cookie:
        _validate_csrf(request, csrf_header)

    service.logout(refresh_cookie)

    _clear_auth_cookies(response)

    return {
        "mensaje": "Sesión cerrada correctamente"
    }


@router.get(
    "/me",
    response_model=UserOut,
)
def me(
    response: Response,
    principal: Principal = Depends(get_current_principal),
    db=Depends(get_db),
):
    from app.repositories.auth_repository import AuthRepository

    user = AuthRepository(db).get_by_id(
        principal.id_usuario
    )

    response.headers["Cache-Control"] = "no-store"

    return _user_out(user)
