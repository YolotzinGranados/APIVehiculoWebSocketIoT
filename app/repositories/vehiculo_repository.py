from app.repositories.base import BaseRepository


class VehiculoRepository(BaseRepository):
    def crear(self, nombre, modelo, descripcion, microcontrolador, conn=None) -> int:
        fila = self._sp.call_one(
            "sp_crear_vehiculo", (nombre, modelo, descripcion, microcontrolador), conn)
        return fila["id_vehiculo"]

    def listar(self, conn=None) -> list[dict]:
        return self._sp.call("sp_obtener_vehiculos", (), conn)

    def obtener(self, id_vehiculo: int, conn=None):
        return self._sp.call_one("sp_obtener_vehiculo", (id_vehiculo,), conn)

    def actualizar(self, id_vehiculo, nombre, modelo, descripcion,
                   microcontrolador, activo, conn=None) -> None:
        self._sp.call("sp_actualizar_vehiculo",
                      (id_vehiculo, nombre, modelo, descripcion, microcontrolador, activo), conn)

    def eliminar(self, id_vehiculo: int, conn=None) -> None:
        self._sp.call("sp_eliminar_vehiculo", (id_vehiculo,), conn)
