from app.repositories.base import BaseRepository


class EstadoRepository(BaseRepository):
    def actualizar(self, id_vehiculo, id_comando, conectado, conn=None) -> None:
        self._sp.call("sp_actualizar_estado", (id_vehiculo, id_comando, conectado), conn)

    def obtener(self, id_vehiculo: int, conn=None):
        return self._sp.call_one("sp_obtener_estado", (id_vehiculo,), conn)

    def registrar_comando(self, id_vehiculo: int, id_comando: int, conn=None) -> None:
        """Actualiza el último comando CONSERVANDO el valor actual de `conectado`.

        Recibir una solicitud HTTP no demuestra que el microcontrolador esté conectado,
        así que nunca se asume True: se mantiene lo que ya hay (False si no había estado).
        """
        actual = self.obtener(id_vehiculo, conn)
        conectado = bool(actual["conectado"]) if actual else False
        self.actualizar(id_vehiculo, id_comando, conectado, conn)
