from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from app.core.dependencies import get_estado_service, get_movimiento_service, get_ws_manager
from app.core.security import requiere_control
from app.models.estado import EstadoOut
from app.models.movimiento import MovimientoEjecutadoOut, MovimientoIn
from app.routers.comunes import AUTH, BD, CONFLICTO, NO_ENCONTRADO, IdVehiculo
from app.services.estado_service import EstadoService
from app.services.movimiento_service import MovimientoService
from app.websocket import eventos as ev
from app.websocket.websocket_manager import WebSocketManager

router = APIRouter(prefix="/vehiculos/{id_vehiculo}", tags=["Estado"])


@router.get(
    "/estado",
    response_model=EstadoOut,
    summary="Último estado registrado del vehículo",
    description=(
        "Devuelve el último comando y la marca de actualización. Si el vehículo existe pero "
        "nunca ha tenido estado, responde 200 con `comando: null` y `conectado: false`. "
        "No modifica datos.\n\n"
        "**Stored Procedures:** `sp_obtener_vehiculo` (validación), `sp_obtener_estado`."
    ),
    responses={**NO_ENCONTRADO, **BD},
)
def obtener_estado(id_vehiculo: IdVehiculo, servicio: EstadoService = Depends(get_estado_service)):
    return servicio.obtener(id_vehiculo)


@router.post(
    "/movimientos",
    status_code=201,
    response_model=MovimientoEjecutadoOut,
    dependencies=[Depends(requiere_control)],
    summary="Ejecutar un movimiento individual",
    description=(
        "Ejecuta un comando **existente** del catálogo del vehículo. Valida que el vehículo exista y "
        "esté activo, y que el comando exista, esté activo y **pertenezca a ese vehículo**.\n\n"
        "Actualiza el estado y registra el historial en **una sola transacción**; recién después del "
        "COMMIT notifica por WebSocket. Si se rechaza, no cambia nada y no se emite ningún evento. "
        "`conectado` se conserva: una solicitud HTTP no prueba que el microcontrolador esté conectado.\n\n"
        "Requiere clave **control** o **admin** (`X-API-Key`).\n\n"
        "**Stored Procedures:** `sp_obtener_vehiculo`, `sp_obtener_comandos_vehiculo` (validaciones), "
        "`sp_obtener_estado`, `sp_actualizar_estado`, `sp_registrar_historial`."
    ),
    responses={**AUTH, **NO_ENCONTRADO, **CONFLICTO, **BD},
)
async def ejecutar_movimiento(
    id_vehiculo: IdVehiculo,
    datos: MovimientoIn,
    servicio: MovimientoService = Depends(get_movimiento_service),
    manager: WebSocketManager = Depends(get_ws_manager),
):
    # El servicio (bloqueante) corre en un hilo; si lanza una excepción, aquí no se notifica nada.
    resultado = await run_in_threadpool(servicio.ejecutar, id_vehiculo, datos.id_comando, datos.origen)

    # Llegar aquí significa que RDS ya confirmó (COMMIT). Ahora sí se notifica.
    notificados = await manager.enviar_a_vehiculo(id_vehiculo, ev.evento(
        ev.MOVIMIENTO, id_vehiculo, comando=resultado["comando"], codigo=resultado["codigo"],
        id_comando=resultado["id_comando"], origen=resultado["origen"]))
    return {**resultado, "clientes_notificados": notificados}
