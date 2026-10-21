from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from legacy.estado import Estado
from Websocket_IoT.legacy.status_service import StatusService
from app.websocket.websocket_manager import WebSocketManager

import os
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
app = FastAPI(title="Servidor IoT", description="API HTTP y WebSocket para práctica IoT", version="1.0")

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
    await websocket.send_json(status_service.obtener_estado())
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_manager.desconectar(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
    import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

app = FastAPI()

# ---------------------------------------------------------
# 1. Modelo y Servicio
# ---------------------------------------------------------
class StatusService:
    # Ruta requerida según el ejercicio (paso 30)
    FILE_PATH = "app/data/status.json"

    @classmethod
    def get_status(cls) -> dict:
        """Lee el estado desde app/data/status.json"""
        try:
            with open(cls.FILE_PATH, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Estado por defecto si el archivo no existe o está vacío
            return {"status": False}

    @classmethod
    def save_status(cls, data: dict):
        """Crea la carpeta si no existe y guarda el nuevo estado."""
        os.makedirs(os.path.dirname(cls.FILE_PATH), exist_ok=True)
        with open(cls.FILE_PATH, "w") as f:
            json.dump(data, f)

# ---------------------------------------------------------
# 2. Gestor de WebSockets
# ---------------------------------------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def enviar_a_todos(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

# ---------------------------------------------------------
# 3. Endpoints REST
# ---------------------------------------------------------

# Requisito 19: GET /status
@app.get("/status")
def get_status():
    """Consulta status.json y devuelve el estado actual."""
    return StatusService.get_status()


# Requisito 20: POST /status
@app.post("/status")
async def update_status(estado: Estado):
    """Guarda el nuevo valor y notifica a los clientes WebSocket."""
    nuevo_estado = estado.model_dump()
    StatusService.save_status(nuevo_estado)
    
    # Llamar a enviar_a_todos para notificar
    await manager.enviar_a_todos(nuevo_estado)
    
    return {"message": "Estado actualizado exitosamente", "data": nuevo_estado}

# ---------------------------------------------------------
# 4. Endpoint WebSocket
# ---------------------------------------------------------

# Requisito 21: WebSocket /ws
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Acepta conexión, envía estado inicial y la mantiene activa."""
    await manager.connect(websocket)
    
    # Enviar el estado actual al conectarse
    estado_actual = StatusService.get_status()
    await websocket.send_json(estado_actual)
    
    try:
        while True:
            # Mantiene la conexión activa (escuchando si el cliente envía algo)
            # Si solo es de una vía (Server->Client), esto evita que se cierre.
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        # Retira al cliente cuando se desconecta
        manager.disconnect(websocket)