"""Esquemas de autenticación y perfiles de la plataforma."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Role = Literal["admin", "user", "guest"]


class AuthInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class GuestRegisterIn(AuthInput):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    nombre: str = Field(min_length=2, max_length=120)

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        if not any(c.islower() for c in value) or not any(c.isupper() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("La contraseña debe incluir mayúsculas, minúsculas y números")
        return value


class LoginIn(AuthInput):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id_usuario: int
    email: EmailStr
    nombre: str
    roles: list[Role]
    activo: bool


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    csrf_token: str


class AuthResultOut(BaseModel):
    usuario: UserOut
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    csrf_token: str


class MessageOut(BaseModel):
    mensaje: str
