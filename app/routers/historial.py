from fastapi import APIRouter, Depends

from app.core.dependencies import get_historial_service
from app.models.historial import HistorialOut
from app.routers.comunes import BD, NO_ENCONTRADO, IdVehiculo
from app.services.historial_service import HistorialService

router = APIRouter(prefix="/vehiculos/{id_vehiculo}/historial", tags=["Historial"])


@router.get(
    "",
    response_model=HistorialOut,
    summary="Últimos 10 movimientos individuales",
    description=(
        "Devuelve **como máximo** los 10 movimientos individuales más recientes, del más "
        "reciente al más antiguo. Si hay menos de 10, devuelve solo los disponibles; RDS "
        "conserva el historial completo. Los movimientos de DEMO nunca aparecen aquí. "
        "Un vehículo sin movimientos devuelve `movimientos: []` (200).\n\n"
        "**Stored Procedures:** `sp_obtener_vehiculo` (validación), `sp_obtener_historial`."
    ),
    responses={**NO_ENCONTRADO, **BD},
)
def obtener_historial(
    id_vehiculo: IdVehiculo,
    servicio: HistorialService = Depends(get_historial_service),
):
    return servicio.ultimos(id_vehiculo)
