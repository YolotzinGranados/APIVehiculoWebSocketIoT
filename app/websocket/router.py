"""WebSocket por vehículo:  ws://localhost:8000/ws/vehiculos/{id_vehiculo}"""
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool

from app.core.dependencies import crear_estado_service
from app.core.exceptions import AppError, NotFoundError
from app.websocket import eventos as ev

logger = logging.getLogger(__name__)
router = APIRouter()

CODIGO_NO_ENCONTRADO = 4404
CODIGO_ERROR_INTERNO = 1011


@router.websocket("/ws/vehiculos/{id_vehiculo}")
async def websocket_vehiculo(websocket: WebSocket, id_vehiculo: int):
    app = websocket.app
    manager = app.state.ws_manager
    await manager.conectar(id_vehiculo, websocket)
    try:
        # Al abrir la conexión: último estado disponible, leído de RDS.
        servicio = crear_estado_service(app.state.db, app.state.executor)
        estado = await run_in_threadpool(servicio.obtener, id_vehiculo)
        await websocket.send_json(ev.evento_estado_inicial(estado))

        # Mantiene la conexión abierta; "ping" -> "pong" para comprobar que sigue viva.
        while True:
            texto = await websocket.receive_text()
            if texto.strip().lower() == "ping":
                await websocket.send_json(ev.evento(ev.PONG, id_vehiculo))
    except WebSocketDisconnect:
        pass  # el cliente se fue: es normal
    except NotFoundError as exc:
        await _cerrar_con_error(websocket, id_vehiculo, exc.mensaje, CODIGO_NO_ENCONTRADO)
    except AppError as exc:
        await _cerrar_con_error(websocket, id_vehiculo, exc.mensaje, CODIGO_ERROR_INTERNO)
    except Exception:
        logger.exception("Error en el WebSocket del vehículo %s", id_vehiculo)
        await _cerrar_con_error(websocket, id_vehiculo, "Error interno del servidor", CODIGO_ERROR_INTERNO)
    finally:
        manager.desconectar(id_vehiculo, websocket)  # no afecta a los demás clientes


async def _cerrar_con_error(websocket: WebSocket, id_vehiculo: int, mensaje: str, codigo: int) -> None:
    try:
        await websocket.send_json(ev.evento(ev.ERROR, id_vehiculo, mensaje=mensaje))
        await websocket.close(code=codigo)
    except Exception:
        pass  # el socket ya estaba cerrado
