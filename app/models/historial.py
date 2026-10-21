from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class HistorialItemOut(BaseModel):
    id_historial: int
    id_vehiculo: int
    comando: Optional[str] = None
    codigo: Optional[int] = None
    fecha_hora: datetime
    origen: str


class HistorialOut(BaseModel):
    id_vehiculo: int
    limite: int = Field(..., description="Máximo de movimientos devueltos")
    total: int = Field(..., description="Movimientos devueltos en esta respuesta")
    movimientos: List[HistorialItemOut]
