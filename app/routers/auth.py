"""Autenticación FastAPI: registro de invitado, login, refresh y logout."""
from fastapi import APIRouter, Depends, Header, Request, Response, Cookie

from app.core.config import get_settings
from app.core.dependencies import get_db
from app.core.auth import get_current_principal, Principal
from app.core.exceptions import BadRequestError, UnauthorizedError
from app.models.auth import GuestRegisterIn, LoginIn, AuthResultOut, TokenOut, UserOut, MessageOut
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Autenticación"])


def _service(db=Depends(get_db)):
    return AuthService(db, get_settings())


def _set_refresh_cookie(response: Response, token: str):
    settings = get_settings()
    response.set_cookie(
        key=settings.auth_refresh_cookie_name, value=token,
        max_age=settings.auth_refresh_ttl_days * 86400, httponly=True,
        secure=True, samesite="none", path="/auth",
    )


def _set_csrf_cookie(response: Response, token: str):
    response.set_cookie(
        key=get_settings().auth_csrf_cookie_name, value=token,
        max_age=get_settings().auth_refresh_ttl_days * 86400,
        httponly=False, secure=True, samesite="none", path="/auth",
    )


def _user_out(user):
    return UserOut(id_usuario=user["id_usuario"], email=user["email"], nombre=user["nombre"],
                   roles=user["roles"], activo=user["activo"])


@router.post("/registro-invitado", status_code=201, response_model=AuthResultOut)
def registro_invitado(datos: GuestRegisterIn, request: Request, response: Response,
                      service: AuthService = Depends(_service)):
    user, tokens = service.register_guest(datos, request.headers.get("user-agent"))
    _set_refresh_cookie(response, tokens["refresh_token"])
    _set_csrf_cookie(response, tokens["csrf_token"])
    return AuthResultOut(usuario=_user_out(user), access_token=tokens["access_token"],
                         expires_in=tokens["expires_in"], csrf_token=tokens["csrf_token"])


@router.post("/login", response_model=AuthResultOut)
def login(datos: LoginIn, request: Request, response: Response,
          service: AuthService = Depends(_service)):
    user, tokens = service.login(str(datos.email), datos.password, request.headers.get("user-agent"))
    _set_refresh_cookie(response, tokens["refresh_token"])
    _set_csrf_cookie(response, tokens["csrf_token"])
    return AuthResultOut(usuario=_user_out(user), access_token=tokens["access_token"],
                         expires_in=tokens["expires_in"], csrf_token=tokens["csrf_token"])


@router.post("/refresh", response_model=TokenOut)
def refresh(request: Request, response: Response,
            csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
            csrf_cookie: str | None = Cookie(default=None, alias="iot_csrf"),
            refresh_cookie: str | None = Cookie(default=None, alias="iot_refresh"),
            service: AuthService = Depends(_service)):
    if not refresh_cookie:
        raise UnauthorizedError("No existe una sesión de renovación")
    if not csrf_header or not csrf_cookie or csrf_header != csrf_cookie:
        raise BadRequestError("Validación CSRF incorrecta")
    _, tokens = service.refresh(refresh_cookie, request.headers.get("user-agent"))
    _set_refresh_cookie(response, tokens["refresh_token"])
    _set_csrf_cookie(response, tokens["csrf_token"])
    return TokenOut(access_token=tokens["access_token"], expires_in=tokens["expires_in"],
                    csrf_token=tokens["csrf_token"])


@router.post("/logout", response_model=MessageOut)
def logout(response: Response, csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
           csrf_cookie: str | None = Cookie(default=None, alias="iot_csrf"),
           refresh_cookie: str | None = Cookie(default=None, alias="iot_refresh"),
           service: AuthService = Depends(_service)):
    if refresh_cookie and (not csrf_header or not csrf_cookie or csrf_header != csrf_cookie):
        raise BadRequestError("Validación CSRF incorrecta")
    service.logout(refresh_cookie)
    response.delete_cookie("iot_refresh", path="/auth", secure=True, httponly=True, samesite="none")
    response.delete_cookie("iot_csrf", path="/auth", secure=True, samesite="none")
    return {"mensaje": "Sesión cerrada"}


@router.get("/me", response_model=UserOut)
def me(principal: Principal = Depends(get_current_principal), db=Depends(get_db)):
    from app.repositories.auth_repository import AuthRepository
    user = AuthRepository(db).get_by_id(principal.id_usuario)
    return _user_out(user)
