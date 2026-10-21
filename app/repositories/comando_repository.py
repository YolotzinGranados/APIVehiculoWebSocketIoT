from app.repositories.base import BaseRepository


class ComandoRepository(BaseRepository):
    def crear(self, id_vehiculo, nombre, codigo, descripcion, conn=None) -> int:
        fila = self._sp.call_one(
            "sp_crear_comando", (id_vehiculo, nombre, codigo, descripcion), conn)
        return fila["id_comando"]

    def listar_por_vehiculo(self, id_vehiculo: int, conn=None) -> list[dict]:
        return self._sp.call("sp_obtener_comandos_vehiculo", (id_vehiculo,), conn)

    def actualizar(self, id_comando, nombre, codigo, descripcion, activo, conn=None) -> None:
        self._sp.call("sp_actualizar_comando",
                      (id_comando, nombre, codigo, descripcion, activo), conn)

    def eliminar(self, id_comando: int, conn=None) -> None:
        self._sp.call("sp_eliminar_comando", (id_comando,), conn)
