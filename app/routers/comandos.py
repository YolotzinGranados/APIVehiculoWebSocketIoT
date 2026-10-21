from typing import List

from fastapi import APIRouter, Depends

from app.core.dependencies import get_comando_service
from app.core.security import requiere_admin
from app.models.comando import ComandoIn, ComandoOut, ComandoUpdateIn
from app.models.common import MensajeOut
from app.routers.comunes import AUTH, BD, CONFLICTO, NO_ENCONTRADO, IdComando, IdVehiculo
from app.services.comando_service import ComandoService

router = APIRouter(prefix="/vehiculos/{id_vehiculo}/comandos", tags=["Comandos"])


@router.get(
    "",
    response_model=List[ComandoOut],
    summary="Catálogo de comandos de un vehículo",
    description=(
        "Cada vehículo tiene su propio catálogo, ordenado por código. Un vehículo existente "
        "sin comandos devuelve `[]` (200); uno inexistente devuelve 404.\n\n"
        "**Stored Procedures:** `sp_obtener_vehiculo` (validación), `sp_obtener_comandos_vehiculo`."
    ),
    responses={**NO_ENCONTRADO, **BD},
)
def listar_comandos(id_vehiculo: IdVehiculo, servicio: ComandoService = Depends(get_comando_service)):
    return servicio.listar_por_vehiculo(id_vehiculo)


@router.post(
    "",
    status_code=201,
    response_model=ComandoOut,
    dependencies=[Depends(requiere_admin)],
    summary="Crear un comando en el catálogo del vehículo",
    description=(
        "Agrega un comando **nuevo** al catálogo (no ejecuta nada; para mover el vehículo usa "
        "`POST /vehiculos/{id}/movimientos`). Código y nombre deben ser únicos dentro del vehículo. "
        "Requiere clave **admin**.\n\n"
        "**Stored Procedures:** `sp_obtener_vehiculo`, `sp_obtener_comandos_vehiculo` (validaciones), `sp_crear_comando`."
    ),
    responses={**AUTH, **NO_ENCONTRADO, **CONFLICTO, **BD},
)
def crear_comando(id_vehiculo: IdVehiculo, datos: ComandoIn,
                  servicio: ComandoService = Depends(get_comando_service)):
    return servicio.crear(id_vehiculo, datos)


@router.post(
    "/{id_comando}/actualizar",
    response_model=ComandoOut,
    dependencies=[Depends(requiere_admin)],
    summary="Actualizar un comando",
    description=(
        "Actualización parcial. Requiere clave **admin**.\n\n"
        "**Stored Procedures:** `sp_obtener_comandos_vehiculo` (pertenencia y duplicados), `sp_actualizar_comando`."
    ),
    responses={**AUTH, **NO_ENCONTRADO, **CONFLICTO, **BD},
)
def actualizar_comando(id_vehiculo: IdVehiculo, id_comando: IdComando, datos: ComandoUpdateIn,
                       servicio: ComandoService = Depends(get_comando_service)):
    return servicio.actualizar(id_vehiculo, id_comando, datos)


@router.post(
    "/{id_comando}/eliminar",
    response_model=MensajeOut,
    dependencies=[Depends(requiere_admin)],
    summary="Eliminar un comando (destructivo)",
    description=(
        "Se rechaza (409) si el comando está en uso en alguna demo. Requiere clave **admin**.\n\n"
        "**Stored Procedures:** `sp_obtener_comandos_vehiculo`, `sp_obtener_demos`, "
        "`sp_obtener_movimientos_demo` (validaciones), `sp_eliminar_comando`."
    ),
    responses={**AUTH, **NO_ENCONTRADO, **CONFLICTO, **BD},
)
def eliminar_comando(id_vehiculo: IdVehiculo, id_comando: IdComando,
                     servicio: ComandoService = Depends(get_comando_service)):
    servicio.eliminar(id_vehiculo, id_comando)
    return {"mensaje": "Comando eliminado", "id": id_comando}
