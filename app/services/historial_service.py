from app.core.database import Database
from app.repositories.historial_repository import HistorialRepository
from app.services.vehiculo_service import VehiculoService

HISTORIAL_LIMITE = 10  # regla del proyecto: máximo 10 movimientos individuales


class HistorialService:
    def __init__(self, db: Database, vehiculos: VehiculoService, historial: HistorialRepository):
        self._db = db
        self._vehiculos = vehiculos
        self._historial = historial

    def ultimos(self, id_vehiculo: int) -> dict:
        with self._db.connection() as conn:
            self._vehiculos.obtener_existente(id_vehiculo, conn)
            filas = self._historial.obtener(id_vehiculo, conn)  # ya viene del más reciente al más antiguo
        movimientos = filas[:HISTORIAL_LIMITE]  # RDS conserva todo; la API entrega máximo 10
        return {
            "id_vehiculo": id_vehiculo,
            "limite": HISTORIAL_LIMITE,
            "total": len(movimientos),
            "movimientos": movimientos,
        }
