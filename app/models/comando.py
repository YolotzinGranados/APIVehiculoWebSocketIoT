from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models.common import ActualizacionBase, EntradaBase


class ComandoIn(EntradaBase):
    nombre: str = Field(..., min_length=1, max_length=60, examples=["AVANZAR"])
    codigo: int = Field(..., ge=0, le=9999, description="Código numérico único dentro del vehículo", examples=[1])
    descripcion: Optional[str] = Field(None, max_length=255)


class ComandoUpdateIn(ActualizacionBase):
    nombre: Optional[str] = Field(None, min_length=1, max_length=60)
    codigo: Optional[int] = Field(None, ge=0, le=9999)
    descripcion: Optional[str] = Field(None, max_length=255)
    activo: Optional[bool] = None

    @field_validator("nombre", "codigo", "activo")
    @classmethod
    def _no_nulo(cls, v):
        if v is None:
            raise ValueError("este campo no puede ser nulo")
        return v


class ComandoOut(BaseModel):
    id_comando: int
    id_vehiculo: int
    nombre: str
    codigo: int
    descripcion: Optional[str] = None
    activo: bool
