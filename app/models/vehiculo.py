from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.comando import ComandoOut
from app.models.common import ActualizacionBase, EntradaBase
from app.models.demo import DemoOut
from app.models.estado import EstadoOut


class VehiculoIn(EntradaBase):
    nombre: str = Field(..., min_length=1, max_length=80, examples=["Excavadora IoT"])
    modelo: Optional[str] = Field(None, max_length=80, examples=["Modelo X"])
    descripcion: Optional[str] = Field(None, max_length=255)
    microcontrolador: Optional[str] = Field(None, max_length=50, examples=["ESP8266"])


class VehiculoUpdateIn(ActualizacionBase):
    nombre: Optional[str] = Field(None, min_length=1, max_length=80)
    modelo: Optional[str] = Field(None, max_length=80)
    descripcion: Optional[str] = Field(None, max_length=255)
    microcontrolador: Optional[str] = Field(None, max_length=50)
    activo: Optional[bool] = None

    @field_validator("nombre", "activo")
    @classmethod
    def _no_nulo(cls, v):
        if v is None:
            raise ValueError("este campo no puede ser nulo")
        return v


class VehiculoOut(BaseModel):
    id_vehiculo: int
    nombre: str
    modelo: Optional[str] = None
    descripcion: Optional[str] = None
    microcontrolador: Optional[str] = None
    fecha_registro: Optional[datetime] = None
    activo: bool


class VehiculoDetalleOut(VehiculoOut):
    """Vehículo con sus comandos, último estado y DEMO asociadas."""
    comandos: Optional[List[ComandoOut]] = None
    estado: Optional[EstadoOut] = None
    demos: Optional[List[DemoOut]] = None
