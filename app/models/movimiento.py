from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.common import EntradaBase
from app.models.estado import EstadoOut


class MovimientoIn(EntradaBase):
    """Ejecutar un comando que YA existe en el catálogo del vehículo
    (no crea comandos nuevos: para eso está POST /vehiculos/{id}/comandos)."""
    id_comando: int = Field(..., gt=0, examples=[1])
    origen: str = Field("API", pattern=r"^[A-Z0-9_]{2,30}$",
                        description="Quién origina el movimiento (se guarda en el historial). 'DEMO' está reservado.",
                        examples=["API"])

    @field_validator("origen", mode="before")
    @classmethod
    def _mayusculas(cls, v):
        return v.strip().upper() if isinstance(v, str) else v

    @field_validator("origen")
    @classmethod
    def _no_demo(cls, v):
        if v == "DEMO":
            raise ValueError("'DEMO' está reservado: los movimientos de una DEMO nunca van al historial")
        return v


class MovimientoEjecutadoOut(BaseModel):
    id_vehiculo: int
    id_comando: int
    comando: str
    codigo: int
    origen: str
    fecha_hora: datetime
    estado: EstadoOut
    clientes_notificados: int = Field(..., description="Clientes WebSocket de este vehículo a los que se envió el evento")
