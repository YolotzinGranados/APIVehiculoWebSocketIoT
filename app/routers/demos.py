from typing import List

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from app.core.dependencies import get_demo_runner, get_demo_service
from app.core.exceptions import ConflictError
from app.core.security import requiere_admin, requiere_control
from app.models.common import MensajeOut
from app.models.demo import (
    DemoIn, DemoIniciadaOut, DemoOut, DemoUpdateIn, MovimientoDemoIn,
    MovimientoDemoOut, MovimientoDemoUpdateIn,
)
from app.routers.comunes import AUTH, BD, CONFLICTO, NO_ENCONTRADO, IdDemo, IdMovimientoDemo, IdVehiculo
from app.services.demo_runner import DemoRunner
from app.services.demo_service import DemoService

router = APIRouter(prefix="/vehiculos/{id_vehiculo}/demos", tags=["DEMO"])
ERR_LECTURA = {**NO_ENCONTRADO, **BD}
ERR_ADMIN = {**AUTH, **NO_ENCONTRADO, **CONFLICTO, **BD}


# ===================== consultas =====================
@router.get(
    "",
    response_model=List[DemoOut],
    summary="Listar las DEMO de un vehículo",
    description=(
        "Una DEMO es una secuencia configurable de N movimientos.\n\n"
        "**Stored Procedures:** `sp_obtener_vehiculo` (validación), `sp_obtener_demos`."
    ),
    responses=ERR_LECTURA,
)
def listar_demos(id_vehiculo: IdVehiculo, servicio: DemoService = Depends(get_demo_service)):
    return servicio.listar(id_vehiculo)


@router.get(
    "/{id_demo}/movimientos",
    response_model=List[MovimientoDemoOut],
    summary="Movimientos ordenados de una DEMO",
    description=(
        "Devuelve los N movimientos de la DEMO por `orden`, con su duración y pausa en ms. "
        "La demo debe pertenecer al vehículo indicado.\n\n"
        "**Stored Procedures:** `sp_obtener_vehiculo`, `sp_obtener_demos` (validan pertenencia), "
        "`sp_obtener_movimientos_demo`."
    ),
    responses=ERR_LECTURA,
)
def listar_movimientos_demo(id_vehiculo: IdVehiculo, id_demo: IdDemo,
                            servicio: DemoService = Depends(get_demo_service)):
    return servicio.movimientos(id_vehiculo, id_demo)


# ===================== administración de demos (admin) =====================
@router.post(
    "", status_code=201, response_model=DemoOut, dependencies=[Depends(requiere_admin)],
    summary="Crear una DEMO",
    description="Requiere clave **admin**.\n\n**Stored Procedures:** `sp_obtener_vehiculo`, `sp_crear_demo`, `sp_obtener_demos`.",
    responses=ERR_ADMIN,
)
def crear_demo(id_vehiculo: IdVehiculo, datos: DemoIn, servicio: DemoService = Depends(get_demo_service)):
    return servicio.crear(id_vehiculo, datos)


@router.post(
    "/{id_demo}/actualizar", response_model=DemoOut, dependencies=[Depends(requiere_admin)],
    summary="Actualizar una DEMO",
    description="Actualización parcial. Requiere clave **admin**.\n\n**Stored Procedures:** `sp_obtener_demos` (pertenencia), `sp_actualizar_demo`.",
    responses=ERR_ADMIN,
)
def actualizar_demo(id_vehiculo: IdVehiculo, id_demo: IdDemo, datos: DemoUpdateIn,
                    servicio: DemoService = Depends(get_demo_service)):
    return servicio.actualizar(id_vehiculo, id_demo, datos)


@router.post(
    "/{id_demo}/eliminar", response_model=MensajeOut, dependencies=[Depends(requiere_admin)],
    summary="Eliminar una DEMO (destructivo)",
    description=(
        "Elimina la demo y, en cascada, sus movimientos. Se rechaza (409) si la demo se está ejecutando. "
        "Requiere clave **admin**.\n\n**Stored Procedures:** `sp_obtener_demos` (pertenencia), `sp_eliminar_demo`."
    ),
    responses=ERR_ADMIN,
)
def eliminar_demo(id_vehiculo: IdVehiculo, id_demo: IdDemo,
                  servicio: DemoService = Depends(get_demo_service),
                  runner: DemoRunner = Depends(get_demo_runner)):
    ejecucion = runner.activa(id_vehiculo)
    if ejecucion and ejecucion.id_demo == id_demo:
        raise ConflictError("La demo se está ejecutando; cancélala primero")
    servicio.eliminar(id_vehiculo, id_demo)
    return {"mensaje": "Demo eliminada", "id": id_demo}


# ===================== movimientos de una demo (admin) =====================
@router.post(
    "/{id_demo}/movimientos", status_code=201, response_model=MovimientoDemoOut,
    dependencies=[Depends(requiere_admin)],
    summary="Agregar un movimiento a una DEMO",
    description=(
        "El comando debe ser un comando **activo de este vehículo**; `orden` debe ser único en la demo. "
        "Requiere clave **admin**.\n\n"
        "**Stored Procedures:** `sp_obtener_demos`, `sp_obtener_comandos_vehiculo`, `sp_obtener_movimientos_demo` "
        "(validaciones), `sp_agregar_movimiento_demo`."
    ),
    responses=ERR_ADMIN,
)
def agregar_movimiento(id_vehiculo: IdVehiculo, id_demo: IdDemo, datos: MovimientoDemoIn,
                       servicio: DemoService = Depends(get_demo_service)):
    return servicio.agregar_movimiento(id_vehiculo, id_demo, datos)


@router.post(
    "/{id_demo}/movimientos/{id_demo_movimiento}/actualizar", response_model=MovimientoDemoOut,
    dependencies=[Depends(requiere_admin)],
    summary="Actualizar un movimiento de una DEMO",
    description=(
        "Actualización parcial. Requiere clave **admin**.\n\n"
        "**Stored Procedures:** `sp_obtener_movimientos_demo` (pertenencia), `sp_actualizar_movimiento_demo`."
    ),
    responses=ERR_ADMIN,
)
def actualizar_movimiento(id_vehiculo: IdVehiculo, id_demo: IdDemo, id_demo_movimiento: IdMovimientoDemo,
                          datos: MovimientoDemoUpdateIn, servicio: DemoService = Depends(get_demo_service)):
    return servicio.actualizar_movimiento(id_vehiculo, id_demo, id_demo_movimiento, datos)


@router.post(
    "/{id_demo}/movimientos/{id_demo_movimiento}/eliminar", response_model=MensajeOut,
    dependencies=[Depends(requiere_admin)],
    summary="Eliminar un movimiento de una DEMO (destructivo)",
    description=(
        "Requiere clave **admin**.\n\n"
        "**Stored Procedures:** `sp_obtener_movimientos_demo` (pertenencia), `sp_eliminar_movimiento_demo`."
    ),
    responses=ERR_ADMIN,
)
def eliminar_movimiento(id_vehiculo: IdVehiculo, id_demo: IdDemo, id_demo_movimiento: IdMovimientoDemo,
                        servicio: DemoService = Depends(get_demo_service)):
    servicio.eliminar_movimiento(id_vehiculo, id_demo, id_demo_movimiento)
    return {"mensaje": "Movimiento eliminado", "id": id_demo_movimiento}


# ===================== ejecución (control) =====================
@router.post(
    "/{id_demo}/iniciar", status_code=202, response_model=DemoIniciadaOut,
    dependencies=[Depends(requiere_control)],
    summary="Iniciar una DEMO (se emite por WebSocket)",
    description=(
        "Valida que la demo exista, esté activa y pertenezca al vehículo, y responde **202** de inmediato: "
        "la secuencia se emite en segundo plano por `ws://localhost:8000/ws/vehiculos/{id}` "
        "(`demo_inicio`, un `demo_movimiento` por cada uno de los N movimientos y `demo_fin`).\n\n"
        "Respeta `duracion_ms` y `pausa_ms`, actualiza el último comando en RDS y **nunca escribe en el "
        "historial**. Solo una DEMO a la vez por vehículo (409 si ya hay una). Emitir un mensaje no "
        "confirma ejecución física. Requiere clave **control** o **admin**.\n\n"
        "**Stored Procedures:** `sp_obtener_vehiculo`, `sp_obtener_demos`, `sp_obtener_comandos_vehiculo`, "
        "`sp_obtener_movimientos_demo` (lectura); `sp_obtener_estado` + `sp_actualizar_estado` en cada movimiento."
    ),
    responses={**AUTH, **NO_ENCONTRADO, **CONFLICTO, **BD},
)
async def iniciar_demo(id_vehiculo: IdVehiculo, id_demo: IdDemo,
                       servicio: DemoService = Depends(get_demo_service),
                       runner: DemoRunner = Depends(get_demo_runner)):
    preparacion = await run_in_threadpool(servicio.preparar_ejecucion, id_vehiculo, id_demo)
    ejecucion = runner.iniciar(id_vehiculo, preparacion)  # 409 si ya hay una DEMO en este vehículo
    return {
        "mensaje": "DEMO aceptada: sigue su avance por WebSocket",
        "id_vehiculo": id_vehiculo,
        "id_demo": ejecucion.id_demo,
        "demo": ejecucion.nombre,
        "total_movimientos": ejecucion.total,
        "websocket": f"/ws/vehiculos/{id_vehiculo}",
    }


@router.post(
    "/cancelar", response_model=MensajeOut, dependencies=[Depends(requiere_control)],
    summary="Cancelar (DETENER) la DEMO en ejecución",
    description=(
        "Suspende de inmediato la emisión de los movimientos posteriores y emite `demo_cancelada` por "
        "WebSocket. La cancelación tiene prioridad sobre cualquier espera. Si el catálogo del vehículo tiene "
        "un comando `DETENER`, queda como último comando (sin tocar el historial). "
        "Requiere clave **control** o **admin**.\n\n**Stored Procedures:** `sp_actualizar_estado` (solo si hay comando DETENER)."
    ),
    responses={**AUTH, **NO_ENCONTRADO, **BD},
)
async def cancelar_demo(id_vehiculo: IdVehiculo, runner: DemoRunner = Depends(get_demo_runner)):
    ejecucion = await runner.cancelar(id_vehiculo)
    return {"mensaje": "DEMO cancelada", "id": ejecucion.id_demo}
