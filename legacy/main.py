"""Aplicación histórica de la práctica anterior. No forma parte de la API IoT actual.

Para consultar esta versión archivada: uvicorn legacy.main:app --port 8001
La aplicación activa es app.main:app.
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from legacy.estado import Estado
from legacy.status_service import StatusService
from legacy.websocket_manager_v1 import WebSocketManager

app = FastAPI(title="Servidor IoT - versión anterior", version="1.0.0")
status_service = StatusService()
websocket_manager = WebSocketManager()


@app.get("/status")
def obtener_estado():
    return status_service.obtener_estado()


@app.post("/status")
async def cambiar_estado(estado: Estado):
    nuevo_estado = status_service.guardar_estado(estado.status)
    await websocket_manager.enviar_a_todos(nuevo_estado)
    return nuevo_estado


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket_manager.conectar(websocket)
    try:
        await websocket.send_json(status_service.obtener_estado())
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        websocket_manager.desconectar(websocket)
