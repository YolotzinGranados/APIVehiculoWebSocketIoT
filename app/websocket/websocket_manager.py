"""Gestor de conexiones WebSocket agrupadas por vehículo.

Evolución del WebSocketManager de la práctica anterior (lista única de clientes):
ahora hay un conjunto de clientes POR vehículo, de modo que cada cliente recibe
solo los eventos del vehículo que monitorea. Se conserva el patrón de limpiar
clientes caídos sin afectar a los demás.
"""
import asyncio
import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger(__name__)

TIMEOUT_ENVIO = 2.0  # un cliente lento no debe retrasar al resto


class WebSocketManager:
    def __init__(self):
        self._clientes: dict[int, set[WebSocket]] = defaultdict(set)

    async def conectar(self, id_vehiculo: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self._clientes[id_vehiculo].add(websocket)
        logger.info("WS conectado al vehículo %s (%s clientes)", id_vehiculo, self.total_clientes(id_vehiculo))

    def desconectar(self, id_vehiculo: int, websocket: WebSocket) -> None:
        clientes = self._clientes.get(id_vehiculo)
        if clientes is not None:
            clientes.discard(websocket)  # discard: no falla si ya se había retirado
            if not clientes:
                del self._clientes[id_vehiculo]

    def total_clientes(self, id_vehiculo: int) -> int:
        return len(self._clientes.get(id_vehiculo, ()))

    @staticmethod
    async def _enviar_seguro(websocket: WebSocket, mensaje: dict) -> bool:
        try:
            await asyncio.wait_for(websocket.send_json(mensaje), timeout=TIMEOUT_ENVIO)
            return True
        except Exception:  # desconexión, timeout o socket cerrado
            return False

    async def enviar_a_vehiculo(self, id_vehiculo: int, mensaje: dict) -> int:
        """Envía a los clientes de ESE vehículo. Devuelve cuántos lo recibieron."""
        clientes = list(self._clientes.get(id_vehiculo, ()))
        if not clientes:
            return 0
        resultados = await asyncio.gather(*(self._enviar_seguro(ws, mensaje) for ws in clientes))
        for ws, ok in zip(clientes, resultados):
            if not ok:
                logger.info("WS caído en vehículo %s: se retira del gestor", id_vehiculo)
                self.desconectar(id_vehiculo, ws)
        return sum(resultados)
