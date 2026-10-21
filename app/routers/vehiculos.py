from typing import List

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_demo_runner, get_vehiculo_service
from app.core.exceptions import ConflictError
from app.core.security import requiere_admin
from app.models.common import MensajeOut
from app.models.vehiculo import VehiculoDetalleOut, VehiculoIn, VehiculoOut, VehiculoUpdateIn
from app.routers.comunes import AUTH, BD, CONFLICTO, NO_ENCONTRADO, IdVehiculo
from app.services.demo_runner import DemoRunner
from app.services.vehiculo_service import VehiculoService

router = APIRouter(prefix="/vehiculos", tags=["Vehículos"])


@router.get(
    "",
    response_model=List[VehiculoDetalleOut],
    response_model_exclude_unset=True,
    summary="Listar todos los vehículos",
    description=(
        "Devuelve todos los vehículos. Por defecto incluye, para cada uno, su catálogo de "
        "comandos, su último estado y sus DEMO. Con `incluir_detalle=false` devuelve solo "
        "los datos del vehículo. No modifica datos.\n\n"
        "**Stored Procedures:** `sp_obtener_vehiculos`, `sp_obtener_comandos_vehiculo`, "
        "`sp_obtener_estado`, `sp_obtener_demos`."
    ),
    responses={**BD},
)
def listar_vehiculos(
    incluir_detalle: bool = Query(True, description="Incluir comandos, estado y demos"),
    servicio: VehiculoService = Depends(get_vehiculo_service),
):
    return servicio.listar(incluir_detalle)


@router.get(
    "/{id_vehiculo}",
    response_model=VehiculoDetalleOut,
    summary="Consultar un vehículo por su identificador",
    description=(
        "Devuelve el vehículo con sus comandos, último estado y DEMO asociadas. "
        "Si aún no tiene estado, `estado.conectado` es `false` y el comando es `null`.\n\n"
        "**Stored Procedures:** `sp_obtener_vehiculo`, `sp_obtener_comandos_vehiculo`, "
        "`sp_obtener_estado`, `sp_obtener_demos`."
    ),
    responses={**NO_ENCONTRADO, **BD},
)
def obtener_vehiculo(id_vehiculo: IdVehiculo, servicio: VehiculoService = Depends(get_vehiculo_service)):
    return servicio.obtener(id_vehiculo)


@router.post(
    "",
    status_code=201,
    response_model=VehiculoOut,
    dependencies=[Depends(requiere_admin)],
    summary="Crear un vehículo",
    description="Requiere clave **admin** (`X-API-Key`).\n\n**Stored Procedures:** `sp_crear_vehiculo`, `sp_obtener_vehiculo`.",
    responses={**AUTH, **BD},
)
def crear_vehiculo(datos: VehiculoIn, servicio: VehiculoService = Depends(get_vehiculo_service)):
    return servicio.crear(datos)


@router.post(
    "/{id_vehiculo}/actualizar",
    response_model=VehiculoOut,
    dependencies=[Depends(requiere_admin)],
    summary="Actualizar un vehículo",
    description=(
        "Actualización parcial: solo se modifican los campos enviados. Requiere clave **admin**.\n\n"
        "**Stored Procedures:** `sp_obtener_vehiculo` (validación), `sp_actualizar_vehiculo`."
    ),
    responses={**AUTH, **NO_ENCONTRADO, **BD},
)
def actualizar_vehiculo(id_vehiculo: IdVehiculo, datos: VehiculoUpdateIn,
                        servicio: VehiculoService = Depends(get_vehiculo_service)):
    return servicio.actualizar(id_vehiculo, datos)


@router.post(
    "/{id_vehiculo}/eliminar",
    response_model=MensajeOut,
    dependencies=[Depends(requiere_admin)],
    summary="Eliminar un vehículo (destructivo)",
    description=(
        "**Operación destructiva:** RDS elimina en cascada sus comandos, estado, historial y demos. "
        "Requiere clave **admin**. Se rechaza (409) si tiene una DEMO en ejecución.\n\n"
        "**Stored Procedures:** `sp_obtener_vehiculo` (validación), `sp_eliminar_vehiculo`."
    ),
    responses={**AUTH, **NO_ENCONTRADO, **CONFLICTO, **BD},
)
def eliminar_vehiculo(id_vehiculo: IdVehiculo,
                      servicio: VehiculoService = Depends(get_vehiculo_service),
                      runner: DemoRunner = Depends(get_demo_runner)):
    if runner.activa(id_vehiculo):
        raise ConflictError("El vehículo tiene una DEMO en ejecución; cancélala primero")
    servicio.eliminar(id_vehiculo)
    return {"mensaje": "Vehículo eliminado", "id": id_vehiculo}
