from app.core.database import Database
from app.models.estado import EstadoOut
from app.repositories.estado_repository import EstadoRepository
from app.services.vehiculo_service import VehiculoService


class EstadoService:
    def __init__(self, db: Database, vehiculos: VehiculoService, estados: EstadoRepository):
        self._db = db
        self._vehiculos = vehiculos
        self._estados = estados

    def obtener(self, id_vehiculo: int) -> dict:
        with self._db.connection() as conn:
            vehiculo = self._vehiculos.obtener_existente(id_vehiculo, conn)
            return self._estados.obtener(id_vehiculo, conn) or EstadoOut.sin_registro(
                id_vehiculo, vehiculo["nombre"])
