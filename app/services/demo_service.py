from app.core.database import Database
from app.core.exceptions import ConflictError, NotFoundError
from app.models.demo import DemoIn, DemoUpdateIn, MovimientoDemoIn, MovimientoDemoUpdateIn
from app.repositories.comando_repository import ComandoRepository
from app.repositories.demo_repository import DemoRepository
from app.services.vehiculo_service import VehiculoService

NOMBRES_DETENER = {"DETENER", "PARAR", "STOP", "ALTO"}


class DemoService:
    def __init__(self, db: Database, vehiculos: VehiculoService,
                 demos: DemoRepository, comandos: ComandoRepository):
        self._db = db
        self._vehiculos = vehiculos
        self._demos = demos
        self._comandos = comandos

    # ---------- consultas ----------
    def listar(self, id_vehiculo: int) -> list[dict]:
        with self._db.connection() as conn:
            self._vehiculos.obtener_existente(id_vehiculo, conn)
            return self._demos.listar(id_vehiculo, conn)

    def obtener_de_vehiculo(self, id_vehiculo: int, id_demo: int, conn) -> dict:
        """No existe un SP para una sola demo: se busca en las del vehículo,
        lo que además garantiza que la demo le pertenece."""
        self._vehiculos.obtener_existente(id_vehiculo, conn)
        for demo in self._demos.listar(id_vehiculo, conn):
            if demo["id_demo"] == id_demo:
                return demo
        raise NotFoundError(f"La demo {id_demo} no existe para el vehículo {id_vehiculo}")

    def movimientos(self, id_vehiculo: int, id_demo: int) -> list[dict]:
        with self._db.connection() as conn:
            self.obtener_de_vehiculo(id_vehiculo, id_demo, conn)
            return self._demos.obtener_movimientos(id_demo, conn)  # ya ordenados por 'orden'

    # ---------- demos ----------
    def crear(self, id_vehiculo: int, datos: DemoIn) -> dict:
        with self._db.connection() as conn:
            self._vehiculos.obtener_existente(id_vehiculo, conn)
        id_demo = self._demos.crear(id_vehiculo, datos.nombre, datos.descripcion)
        with self._db.connection() as conn:
            return self.obtener_de_vehiculo(id_vehiculo, id_demo, conn)

    def actualizar(self, id_vehiculo: int, id_demo: int, datos: DemoUpdateIn) -> dict:
        with self._db.connection() as conn:
            actual = self.obtener_de_vehiculo(id_vehiculo, id_demo, conn)
        nuevo = {**actual, **datos.model_dump(exclude_unset=True)}
        self._demos.actualizar(id_demo, nuevo["nombre"], nuevo["descripcion"], bool(nuevo["activo"]))
        with self._db.connection() as conn:
            return self.obtener_de_vehiculo(id_vehiculo, id_demo, conn)

    def eliminar(self, id_vehiculo: int, id_demo: int) -> None:
        with self._db.connection() as conn:
            self.obtener_de_vehiculo(id_vehiculo, id_demo, conn)
        self._demos.eliminar(id_demo)  # sus movimientos se eliminan en cascada

    # ---------- movimientos de demo ----------
    def _validar_comando_del_vehiculo(self, id_vehiculo: int, id_comando: int, conn) -> None:
        comando = next((c for c in self._comandos.listar_por_vehiculo(id_vehiculo, conn)
                        if c["id_comando"] == id_comando), None)
        if comando is None:
            raise NotFoundError(
                f"El comando {id_comando} no existe en el catálogo del vehículo {id_vehiculo}")
        if not comando["activo"]:
            raise ConflictError(f"El comando '{comando['nombre']}' está inactivo")

    def _obtener_movimiento(self, id_demo: int, id_demo_movimiento: int, conn) -> dict:
        for mov in self._demos.obtener_movimientos(id_demo, conn):
            if mov["id_demo_movimiento"] == id_demo_movimiento:
                return mov
        raise NotFoundError(f"El movimiento {id_demo_movimiento} no existe en la demo {id_demo}")

    @staticmethod
    def _verificar_orden_libre(movimientos: list[dict], orden: int, excluir=None) -> None:
        for m in movimientos:
            if m["id_demo_movimiento"] != excluir and m["orden"] == orden:
                raise ConflictError(f"Ya existe un movimiento con orden {orden} en esta demo")

    def agregar_movimiento(self, id_vehiculo: int, id_demo: int, datos: MovimientoDemoIn) -> dict:
        with self._db.connection() as conn:
            self.obtener_de_vehiculo(id_vehiculo, id_demo, conn)
            self._validar_comando_del_vehiculo(id_vehiculo, datos.id_comando, conn)
            self._verificar_orden_libre(self._demos.obtener_movimientos(id_demo, conn), datos.orden)
        self._demos.agregar_movimiento(id_demo, datos.id_comando, datos.orden,
                                       datos.duracion_ms, datos.pausa_ms)
        with self._db.connection() as conn:  # el SP no devuelve el id: 'orden' es único en la demo
            return next(m for m in self._demos.obtener_movimientos(id_demo, conn)
                        if m["orden"] == datos.orden)

    def actualizar_movimiento(self, id_vehiculo: int, id_demo: int, id_demo_movimiento: int,
                              datos: MovimientoDemoUpdateIn) -> dict:
        cambios = datos.model_dump(exclude_unset=True)
        with self._db.connection() as conn:
            self.obtener_de_vehiculo(id_vehiculo, id_demo, conn)
            actual = self._obtener_movimiento(id_demo, id_demo_movimiento, conn)
            nuevo = {**actual, **cambios}
            if "id_comando" in cambios:
                self._validar_comando_del_vehiculo(id_vehiculo, nuevo["id_comando"], conn)
            if "orden" in cambios:
                self._verificar_orden_libre(self._demos.obtener_movimientos(id_demo, conn),
                                            nuevo["orden"], excluir=id_demo_movimiento)
        self._demos.actualizar_movimiento(id_demo_movimiento, nuevo["id_comando"], nuevo["orden"],
                                          nuevo["duracion_ms"], nuevo["pausa_ms"])
        with self._db.connection() as conn:
            return self._obtener_movimiento(id_demo, id_demo_movimiento, conn)

    def eliminar_movimiento(self, id_vehiculo: int, id_demo: int, id_demo_movimiento: int) -> None:
        with self._db.connection() as conn:
            self.obtener_de_vehiculo(id_vehiculo, id_demo, conn)
            self._obtener_movimiento(id_demo, id_demo_movimiento, conn)
        self._demos.eliminar_movimiento(id_demo_movimiento)

    # ---------- preparación para ejecutar ----------
    def preparar_ejecucion(self, id_vehiculo: int, id_demo: int) -> dict:
        """Valida TODO antes de emitir el primer evento: vehículo activo, demo existente,
        activa y del vehículo, y que cada movimiento use un comando activo de ese vehículo."""
        with self._db.connection() as conn:
            self._vehiculos.obtener_activo(id_vehiculo, conn)
            demo = self.obtener_de_vehiculo(id_vehiculo, id_demo, conn)
            if not demo["activo"]:
                raise ConflictError(f"La demo {id_demo} está inactiva")
            movimientos = self._demos.obtener_movimientos(id_demo, conn)  # N movimientos, no una secuencia fija
            catalogo = {c["id_comando"]: c for c in self._comandos.listar_por_vehiculo(id_vehiculo, conn)}
        if not movimientos:
            raise ConflictError(f"La demo {id_demo} no tiene movimientos configurados")
        for m in movimientos:
            c = catalogo.get(m["id_comando"])
            if c is None or not c["activo"]:
                raise ConflictError(
                    f"El movimiento de orden {m['orden']} usa un comando inactivo o ajeno al vehículo")
        detener = next((c for c in catalogo.values()
                        if c["activo"] and c["nombre"].strip().upper() in NOMBRES_DETENER), None)
        return {"demo": demo, "movimientos": movimientos, "comando_detener": detener}
