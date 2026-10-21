"""Ejecuta DEMOs en segundo plano y emite sus eventos por WebSocket.

Reglas que cumple:
  * Lee los N movimientos de RDS (sp_obtener_movimientos_demo, vía DemoService); no hay secuencia fija.
  * Respeta duracion_ms y pausa_ms de cada movimiento.
  * Actualiza el último comando con sp_actualizar_estado mientras avanza.
  * NUNCA escribe en el historial: este módulo ni siquiera importa HistorialRepository.
  * Una sola DEMO por vehículo a la vez (el registro es síncrono, por eso no hay carrera).
  * Cancelación inmediata y prioritaria (asyncio.Event) y finalización segura (DETENER).
  * No bloquea el servidor: las esperas son asyncio y las llamadas a RDS van en hilos.
  * Emitir un mensaje NO confirma ejecución física; el microcontrolador se integra en otra práctica.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.core.database import Database
from app.core.exceptions import ConflictError, NotFoundError
from app.core.stored_procedures import StoredProcedureExecutor
from app.repositories.estado_repository import EstadoRepository
from app.websocket import eventos as ev
from app.websocket.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


class _DemoCancelada(Exception):
    """Señal interna: el usuario pidió cancelar."""


@dataclass
class EjecucionDemo:
    id_vehiculo: int
    id_demo: int
    nombre: str
    total: int
    cancelar: asyncio.Event = field(default_factory=asyncio.Event)
    tarea: Optional[asyncio.Task] = None
    iniciada: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class DemoRunner:
    def __init__(self, db: Database, executor: StoredProcedureExecutor, manager: WebSocketManager):
        self._db = db
        self._estados = EstadoRepository(executor)
        self._manager = manager
        self._activas: dict[int, EjecucionDemo] = {}

    # ---------- API pública ----------
    def activa(self, id_vehiculo: int) -> Optional[EjecucionDemo]:
        return self._activas.get(id_vehiculo)

    def iniciar(self, id_vehiculo: int, preparacion: dict) -> EjecucionDemo:
        """Registra y lanza la DEMO. Es SÍNCRONO a propósito: comprobar y registrar sin
        ningún 'await' en medio hace imposible que dos solicitudes inicien a la vez."""
        if id_vehiculo in self._activas:
            raise ConflictError("Ya hay una DEMO en ejecución para este vehículo; cancélala o espera a que termine")
        demo = preparacion["demo"]
        ejecucion = EjecucionDemo(id_vehiculo, demo["id_demo"], demo["nombre"], len(preparacion["movimientos"]))
        self._activas[id_vehiculo] = ejecucion
        ejecucion.tarea = asyncio.create_task(self._ejecutar(ejecucion, preparacion))
        return ejecucion

    async def cancelar(self, id_vehiculo: int) -> EjecucionDemo:
        ejecucion = self._activas.get(id_vehiculo)
        if ejecucion is None:
            raise NotFoundError(f"No hay una DEMO en ejecución para el vehículo {id_vehiculo}")
        ejecucion.cancelar.set()  # prioridad: corta cualquier espera en curso
        try:
            await asyncio.wait_for(asyncio.shield(ejecucion.tarea), timeout=5)
        except asyncio.TimeoutError:
            logger.warning("La DEMO del vehículo %s tardó en confirmar su cancelación", id_vehiculo)
        return ejecucion

    async def apagar(self) -> None:
        """Al cerrar el servidor: cancela las DEMOs vivas de forma ordenada."""
        tareas = []
        for ejecucion in list(self._activas.values()):
            ejecucion.cancelar.set()
            if ejecucion.tarea:
                tareas.append(ejecucion.tarea)
        if tareas:
            await asyncio.wait(tareas, timeout=3)

    # ---------- ejecución ----------
    async def _ejecutar(self, ej: EjecucionDemo, prep: dict) -> None:
        id_v = ej.id_vehiculo
        base = {"id_demo": ej.id_demo, "demo": ej.nombre, "total_movimientos": ej.total}
        try:
            await self._emitir(id_v, ev.evento(ev.DEMO_INICIO, id_v, **base))
            for mov in prep["movimientos"]:
                self._verificar(ej)
                await asyncio.to_thread(self._actualizar_estado, id_v, mov["id_comando"])
                self._verificar(ej)  # la cancelación tiene prioridad sobre emitir el movimiento
                await self._emitir(id_v, ev.evento(
                    ev.DEMO_MOVIMIENTO, id_v, comando=mov["comando"], codigo=mov["codigo"],
                    orden=mov["orden"], duracion_ms=mov["duracion_ms"], pausa_ms=mov["pausa_ms"], **base))
                await self._esperar(ej, mov["duracion_ms"])
                await self._esperar(ej, mov["pausa_ms"])
            await self._emitir(id_v, ev.evento(ev.DEMO_FIN, id_v, **base))
        except _DemoCancelada:
            accion = await self._finalizacion_segura(id_v, prep)
            await self._emitir(id_v, ev.evento(ev.DEMO_CANCELADA, id_v, accion=accion, **base))
        except asyncio.CancelledError:
            raise  # apagado del servidor
        except Exception:
            logger.exception("Fallo en la DEMO %s del vehículo %s", ej.id_demo, id_v)
            accion = await self._finalizacion_segura(id_v, prep)
            await self._emitir(id_v, ev.evento(
                ev.DEMO_ERROR, id_v, accion=accion,
                mensaje="La DEMO se detuvo por un error interno", **base))
        finally:
            if self._activas.get(id_v) is ej:
                del self._activas[id_v]

    @staticmethod
    def _verificar(ej: EjecucionDemo) -> None:
        if ej.cancelar.is_set():
            raise _DemoCancelada()

    @staticmethod
    async def _esperar(ej: EjecucionDemo, milisegundos: int) -> None:
        """Espera sin bloquear y se interrumpe al instante si se cancela."""
        if ej.cancelar.is_set():
            raise _DemoCancelada()
        if milisegundos <= 0:
            return
        try:
            await asyncio.wait_for(ej.cancelar.wait(), timeout=milisegundos / 1000)
        except asyncio.TimeoutError:
            return  # la espera terminó normalmente
        raise _DemoCancelada()

    async def _emitir(self, id_vehiculo: int, mensaje: dict) -> None:
        try:
            await self._manager.enviar_a_vehiculo(id_vehiculo, mensaje)
        except Exception:
            logger.exception("No se pudo emitir el evento %s", mensaje.get("tipo"))

    def _actualizar_estado(self, id_vehiculo: int, id_comando: int) -> None:
        with self._db.transaction() as conn:  # solo sp_obtener_estado + sp_actualizar_estado
            self._estados.registrar_comando(id_vehiculo, id_comando, conn)

    async def _finalizacion_segura(self, id_vehiculo: int, prep: dict) -> Optional[str]:
        """Deja el último comando en DETENER (si el catálogo lo tiene). Sin historial."""
        detener = prep.get("comando_detener")
        if not detener:
            return None
        try:
            await asyncio.to_thread(self._actualizar_estado, id_vehiculo, detener["id_comando"])
            return detener["nombre"]
        except Exception:
            logger.exception("No se pudo dejar el vehículo %s en DETENER", id_vehiculo)
            return None
