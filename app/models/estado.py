from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EstadoOut(BaseModel):
    """Último estado registrado del vehículo (tabla estado_vehiculo)."""
    id_vehiculo: int
    vehiculo: Optional[str] = Field(None, description="Nombre del vehículo")
    id_comando: Optional[int] = None
    comando: Optional[str] = Field(None, description="Último comando ejecutado")
    codigo: Optional[int] = None
    conectado: bool = Field(False, description="Conexión confirmada del microcontrolador")
    fecha_actualizacion: Optional[datetime] = None

    @staticmethod
    def sin_registro(id_vehiculo: int, nombre: str) -> dict:
        """Estado por defecto cuando el vehículo existe pero aún no tiene estado."""
        return {
            "id_vehiculo": id_vehiculo, "vehiculo": nombre, "id_comando": None,
            "comando": None, "codigo": None, "conectado": False,
            "fecha_actualizacion": None,
        }
