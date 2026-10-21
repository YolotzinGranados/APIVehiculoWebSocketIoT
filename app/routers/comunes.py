"""Piezas compartidas por los routers: respuestas de error documentadas y tipos de ruta."""
from typing import Annotated

from fastapi import Path

from app.models.common import ErrorResponse


def _r(descripcion: str) -> dict:
    return {"model": ErrorResponse, "description": descripcion}


NO_ENCONTRADO = {404: _r("El recurso no existe")}
CONFLICTO = {409: _r("Conflicto con el estado actual de los datos")}
AUTH = {
    401: _r("Falta o es inválida la cabecera X-API-Key"),
    403: _r("La clave no tiene permisos suficientes (se requiere admin)"),
}
BD = {503: _r("Base de datos no disponible")}

IdVehiculo = Annotated[int, Path(gt=0, description="Identificador del vehículo")]
IdComando = Annotated[int, Path(gt=0, description="Identificador del comando")]
IdDemo = Annotated[int, Path(gt=0, description="Identificador de la demo")]
IdMovimientoDemo = Annotated[int, Path(gt=0, description="Identificador del movimiento de la demo")]
