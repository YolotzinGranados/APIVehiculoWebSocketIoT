from app.repositories.base import BaseRepository


class DemoRepository(BaseRepository):
    # ---- demos ----
    def crear(self, id_vehiculo, nombre, descripcion, conn=None) -> int:
        fila = self._sp.call_one("sp_crear_demo", (id_vehiculo, nombre, descripcion), conn)
        return fila["id_demo"]

    def listar(self, id_vehiculo: int, conn=None) -> list[dict]:
        return self._sp.call("sp_obtener_demos", (id_vehiculo,), conn)

    def actualizar(self, id_demo, nombre, descripcion, activo, conn=None) -> None:
        self._sp.call("sp_actualizar_demo", (id_demo, nombre, descripcion, activo), conn)

    def eliminar(self, id_demo: int, conn=None) -> None:
        self._sp.call("sp_eliminar_demo", (id_demo,), conn)

    # ---- movimientos de demo ----
    def agregar_movimiento(self, id_demo, id_comando, orden, duracion_ms, pausa_ms, conn=None) -> None:
        self._sp.call("sp_agregar_movimiento_demo",
                      (id_demo, id_comando, orden, duracion_ms, pausa_ms), conn)

    def obtener_movimientos(self, id_demo: int, conn=None) -> list[dict]:
        return self._sp.call("sp_obtener_movimientos_demo", (id_demo,), conn)

    def actualizar_movimiento(self, id_demo_movimiento, id_comando, orden,
                              duracion_ms, pausa_ms, conn=None) -> None:
        self._sp.call("sp_actualizar_movimiento_demo",
                      (id_demo_movimiento, id_comando, orden, duracion_ms, pausa_ms), conn)

    def eliminar_movimiento(self, id_demo_movimiento: int, conn=None) -> None:
        self._sp.call("sp_eliminar_movimiento_demo", (id_demo_movimiento,), conn)
