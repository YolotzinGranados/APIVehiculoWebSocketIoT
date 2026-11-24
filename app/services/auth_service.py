"""Casos de uso de registro de invitados, login y sesiones."""
from datetime import datetime, timedelta, timezone
import secrets
import uuid

from app.core.auth_crypto import (
    create_access_token, hash_password, hash_refresh_token, verify_password,
)
from app.core.exceptions import ConflictError, UnauthorizedError, ServiceUnavailableError
from app.repositories.auth_repository import AuthRepository


class AuthService:
    def __init__(self, db, settings):
        self.repo = AuthRepository(db)
        self.settings = settings
        if not settings.auth_secret_key or len(settings.auth_secret_key.get_secret_value()) < 32:
            raise ServiceUnavailableError(
                "Autenticación no configurada: AUTH_SECRET_KEY debe tener al menos 32 caracteres"
            )

    def _issue(self, user, user_agent: str | None):
        access_ttl = self.settings.auth_access_ttl_minutes * 60
        access = create_access_token(
            user_id=user["id_usuario"], email=user["email"], roles=user["roles"],
            secret=self.settings.auth_secret_key.get_secret_value(), ttl_seconds=access_ttl,
        )
        refresh = secrets.token_urlsafe(48)
        csrf = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(days=self.settings.auth_refresh_ttl_days)
        self.repo.create_refresh_session(
            session_id=str(uuid.uuid4()), user_id=user["id_usuario"],
            token_hash=hash_refresh_token(refresh), expires_at=expires, user_agent=user_agent,
        )
        return {"access_token": access, "expires_in": access_ttl, "refresh_token": refresh,
                "csrf_token": csrf}

    def register_guest(self, datos, user_agent: str | None):
        if self.repo.get_by_email(str(datos.email)):
            raise ConflictError("Ya existe una cuenta con ese correo")
        try:
            user_id = self.repo.create_guest(
                email=str(datos.email), nombre=datos.nombre, password_hash=hash_password(datos.password),
            )
        except Exception as exc:
            # UNIQUE(email) resuelve también dos registros simultáneos.
            if getattr(exc, "errno", None) == 1062:
                raise ConflictError("Ya existe una cuenta con ese correo") from exc
            raise
        user = self.repo.get_by_id(user_id)
        return user, self._issue(user, user_agent)

    def login(self, email: str, password: str, user_agent: str | None):
        user = self.repo.get_by_email(email)
        if not user or not user["activo"] or not verify_password(password, user["password_hash"]):
            raise UnauthorizedError("Correo o contraseña incorrectos")
        return user, self._issue(user, user_agent)

    def refresh(self, refresh_token: str, user_agent: str | None):
        from app.core.auth_crypto import hash_refresh_token
        old_hash = hash_refresh_token(refresh_token)
        user = self.repo.find_refresh_session(old_hash)
        if not user:
            raise UnauthorizedError("Sesión inválida, expirada o revocada")
        access_ttl = self.settings.auth_access_ttl_minutes * 60
        access = create_access_token(
            user_id=user["id_usuario"], email=user["email"], roles=user["roles"],
            secret=self.settings.auth_secret_key.get_secret_value(), ttl_seconds=access_ttl,
        )
        new_refresh = secrets.token_urlsafe(48)
        csrf = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(days=self.settings.auth_refresh_ttl_days)
        ok = self.repo.rotate_refresh_session(
            old_hash=old_hash, session_id=str(uuid.uuid4()), user_id=user["id_usuario"],
            new_hash=hash_refresh_token(new_refresh), expires_at=expires, user_agent=user_agent,
        )
        if not ok:
            raise UnauthorizedError("La sesión ya fue utilizada o revocada")
        return user, {"access_token": access, "expires_in": access_ttl,
                      "refresh_token": new_refresh, "csrf_token": csrf}

    def logout(self, refresh_token: str | None):
        if refresh_token:
            self.repo.revoke_refresh_session(hash_refresh_token(refresh_token))
