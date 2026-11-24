"""Dependencias de identidad, sesión y RBAC para FastAPI."""
from dataclasses import dataclass
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth_crypto import decode_access_token
from app.core.config import get_settings
from app.core.dependencies import get_db
from app.core.exceptions import UnauthorizedError
from app.repositories.auth_repository import AuthRepository

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    id_usuario: int
    email: str
    roles: tuple[str, ...]


def get_current_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db=Depends(get_db),
) -> Principal:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError("Se requiere un token Bearer")
    settings = get_settings()
    try:
        claims = decode_access_token(credentials.credentials, settings.auth_secret_key.get_secret_value())
        user_id = int(claims["sub"])
    except Exception as exc:
        raise UnauthorizedError("Token inválido o expirado") from exc
    user = AuthRepository(db).get_by_id(user_id)
    if not user or not user["activo"]:
        raise UnauthorizedError("La cuenta está inactiva o no existe")
    # Los roles se vuelven a leer de BD: nunca se confía en los roles enviados por el cliente/token.
    return Principal(user["id_usuario"], user["email"], tuple(user["roles"]))


def require_roles(*allowed: str):
    def dependency(principal: Principal = Depends(get_current_principal)) -> Principal:
        if not set(principal.roles).intersection(allowed):
            raise HTTPException(status_code=403, detail="El perfil no tiene permiso para esta operación")
        return principal
    return dependency
