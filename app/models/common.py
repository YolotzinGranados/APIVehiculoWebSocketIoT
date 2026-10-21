from typing import List

from pydantic import BaseModel, ConfigDict, model_validator


class ErrorDetalle(BaseModel):
    codigo: str
    mensaje: str


class ErrorResponse(BaseModel):
    """Formato uniforme de error de la API."""
    error: ErrorDetalle


class ErrorCampo(BaseModel):
    campo: str
    mensaje: str


class ErrorValidacionDetalle(ErrorDetalle):
    detalles: List[ErrorCampo]


class ErrorValidacionResponse(BaseModel):
    error: ErrorValidacionDetalle


class MensajeOut(BaseModel):
    mensaje: str
    id: int


class EntradaBase(BaseModel):
    """Base de los cuerpos de entrada: sin campos desconocidos y con espacios recortados."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ActualizacionBase(EntradaBase):
    """Actualización parcial: solo se modifican los campos enviados."""

    @model_validator(mode="after")
    def _al_menos_un_campo(self):
        if not self.model_fields_set:
            raise ValueError("Envía al menos un campo para actualizar")
        return self
