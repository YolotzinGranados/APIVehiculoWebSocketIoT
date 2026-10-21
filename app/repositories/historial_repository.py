from app.repositories.base import BaseRepository


class HistorialRepository(BaseRepository):
    def registrar(self, id_vehiculo, id_comando, origen, conn=None) -> None:
        self._sp.call("sp_registrar_historial", (id_vehiculo, id_comando, origen), conn)

    def obtener(self, id_vehiculo: int, conn=None) -> list[dict]:
        """El SP devuelve TODO el historial (más reciente primero); el límite lo aplica el servicio."""
        return self._sp.call("sp_obtener_historial", (id_vehiculo,), conn)
