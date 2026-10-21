"""Construcción e inyección de servicios para los endpoints."""
from fastapi import Depends, Request

from app.core.database import Database
from app.core.stored_procedures import StoredProcedureExecutor
from app.repositories.comando_repository import ComandoRepository
from app.repositories.demo_repository import DemoRepository
from app.repositories.estado_repository import EstadoRepository
from app.repositories.historial_repository import HistorialRepository
from app.repositories.vehiculo_repository import VehiculoRepository
from app.services.comando_service import ComandoService
from app.services.demo_runner import DemoRunner
from app.services.demo_service import DemoService
from app.services.estado_service import EstadoService
from app.services.historial_service import HistorialService
from app.services.movimiento_service import MovimientoService
from app.services.vehiculo_service import VehiculoService
from app.websocket.websocket_manager import WebSocketManager


# ---- fábricas simples (también las usa el endpoint WebSocket) ----
def crear_vehiculo_service(db: Database, sp: StoredProcedureExecutor) -> VehiculoService:
    return VehiculoService(db, VehiculoRepository(sp), ComandoRepository(sp),
                           EstadoRepository(sp), DemoRepository(sp))


def crear_estado_service(db: Database, sp: StoredProcedureExecutor) -> EstadoService:
    return EstadoService(db, crear_vehiculo_service(db, sp), EstadoRepository(sp))


# ---- dependencias de FastAPI ----
def get_db(request: Request) -> Database:
    return request.app.state.db


def get_executor(request: Request) -> StoredProcedureExecutor:
    return request.app.state.executor


def get_ws_manager(request: Request) -> WebSocketManager:
    return request.app.state.ws_manager


def get_demo_runner(request: Request) -> DemoRunner:
    return request.app.state.demo_runner


def get_vehiculo_service(db: Database = Depends(get_db),
                         sp: StoredProcedureExecutor = Depends(get_executor)) -> VehiculoService:
    return crear_vehiculo_service(db, sp)


def get_comando_service(db: Database = Depends(get_db),
                        sp: StoredProcedureExecutor = Depends(get_executor),
                        vehiculos: VehiculoService = Depends(get_vehiculo_service)) -> ComandoService:
    return ComandoService(db, vehiculos, ComandoRepository(sp), DemoRepository(sp))


def get_estado_service(db: Database = Depends(get_db),
                       sp: StoredProcedureExecutor = Depends(get_executor)) -> EstadoService:
    return crear_estado_service(db, sp)


def get_historial_service(db: Database = Depends(get_db),
                          sp: StoredProcedureExecutor = Depends(get_executor),
                          vehiculos: VehiculoService = Depends(get_vehiculo_service)) -> HistorialService:
    return HistorialService(db, vehiculos, HistorialRepository(sp))


def get_movimiento_service(db: Database = Depends(get_db),
                           sp: StoredProcedureExecutor = Depends(get_executor),
                           vehiculos: VehiculoService = Depends(get_vehiculo_service)) -> MovimientoService:
    return MovimientoService(db, vehiculos, ComandoRepository(sp), EstadoRepository(sp),
                             HistorialRepository(sp))


def get_demo_service(db: Database = Depends(get_db),
                     sp: StoredProcedureExecutor = Depends(get_executor),
                     vehiculos: VehiculoService = Depends(get_vehiculo_service)) -> DemoService:
    return DemoService(db, vehiculos, DemoRepository(sp), ComandoRepository(sp))
