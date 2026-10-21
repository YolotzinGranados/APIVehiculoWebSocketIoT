from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models.common import ActualizacionBase, EntradaBase

MAX_MS = 600_000  # 10 minutos: tope razonable para una duración o una pausa


class DemoIn(EntradaBase):
    nombre: str = Field(..., min_length=1, max_length=80, examples=["Demo principal"])
    descripcion: Optional[str] = Field(None, max_length=255)


class DemoUpdateIn(ActualizacionBase):
    nombre: Optional[str] = Field(None, min_length=1, max_length=80)
    descripcion: Optional[str] = Field(None, max_length=255)
    activo: Optional[bool] = None

    @field_validator("nombre", "activo")
    @classmethod
    def _no_nulo(cls, v):
        if v is None:
            raise ValueError("este campo no puede ser nulo")
        return v


class MovimientoDemoIn(EntradaBase):
    id_comando: int = Field(..., gt=0, description="Comando del catálogo de ESTE vehículo")
    orden: int = Field(..., ge=1, le=10_000, description="Posición en la secuencia (única dentro de la demo)")
    duracion_ms: int = Field(..., ge=1, le=MAX_MS, description="Duración del movimiento en milisegundos")
    pausa_ms: int = Field(0, ge=0, le=MAX_MS, description="Pausa posterior en milisegundos")


class MovimientoDemoUpdateIn(ActualizacionBase):
    id_comando: Optional[int] = Field(None, gt=0)
    orden: Optional[int] = Field(None, ge=1, le=10_000)
    duracion_ms: Optional[int] = Field(None, ge=1, le=MAX_MS)
    pausa_ms: Optional[int] = Field(None, ge=0, le=MAX_MS)

    @field_validator("id_comando", "orden", "duracion_ms", "pausa_ms")
    @classmethod
    def _no_nulo(cls, v):
        if v is None:
            raise ValueError("este campo no puede ser nulo")
        return v


class DemoOut(BaseModel):
    id_demo: int
    id_vehiculo: int
    nombre: str
    descripcion: Optional[str] = None
    activo: bool


class MovimientoDemoOut(BaseModel):
    id_demo_movimiento: int
    orden: int
    id_comando: int
    comando: str
    codigo: int
    duracion_ms: int = Field(..., description="Duración del movimiento en milisegundos")
    pausa_ms: int = Field(..., description="Pausa posterior en milisegundos")


class DemoIniciadaOut(BaseModel):
    mensaje: str
    id_vehiculo: int
    id_demo: int
    demo: str
    total_movimientos: int
    websocket: str = Field(..., description="Ruta del WebSocket donde se emiten los eventos")
