from app.core.database import Database
from app.core.exceptions import ConflictError, NotFoundError
from app.models.estado import EstadoOut
from app.models.vehiculo import VehiculoIn, VehiculoUpdateIn
from app.repositories.comando_repository import ComandoRepository
from app.repositories.demo_repository import DemoRepository
from app.repositories.estado_repository import EstadoRepository
from app.repositories.vehiculo_repository import VehiculoRepository


class VehiculoService:
    def __init__(self, db: Database, vehiculos: VehiculoRepository,
                 comandos: ComandoRepository, estados: EstadoRepository,
                 demos: DemoRepository):
        self._db = db
        self._vehiculos = vehiculos
        self._comandos = comandos
        self._estados = estados
        self._demos = demos

    # ---------- reglas compartidas ----------
    def obtener_existente(self, id_vehiculo: int, conn=None) -> dict:
        """Distingue 'recurso inexistente' (404). sp_obtener_vehiculo devuelve vacío, no error."""
        vehiculo = self._vehiculos.obtener(id_vehiculo, conn)
        if vehiculo is None:
            raise NotFoundError(f"El vehículo {id_vehiculo} no existe")
        return vehiculo

    def obtener_activo(self, id_vehiculo: int, conn=None) -> dict:
        vehiculo = self.obtener_existente(id_vehiculo, conn)
        if not vehiculo["activo"]:
            raise ConflictError(f"El vehículo {id_vehiculo} está inactivo")
        return vehiculo

    # ---------- consultas ----------
    def _con_detalle(self, vehiculo: dict, conn) -> dict:
        id_v = vehiculo["id_vehiculo"]
        estado = self._estados.obtener(id_v, conn) or EstadoOut.sin_registro(id_v, vehiculo["nombre"])
        return {
            **vehiculo,
            "comandos": self._comandos.listar_por_vehiculo(id_v, conn),
            "estado": estado,
            "demos": self._demos.listar(id_v, conn),
        }

    def listar(self, incluir_detalle: bool = True) -> list[dict]:
        with self._db.connection() as conn:  # una sola conexión para toda la consulta
            vehiculos = self._vehiculos.listar(conn)
            if not incluir_detalle:
                return vehiculos
            return [self._con_detalle(v, conn) for v in vehiculos]

    def obtener(self, id_vehiculo: int) -> dict:
        with self._db.connection() as conn:
            return self._con_detalle(self.obtener_existente(id_vehiculo, conn), conn)

    # ---------- escrituras ----------
    def crear(self, datos: VehiculoIn) -> dict:
        id_vehiculo = self._vehiculos.crear(
            datos.nombre, datos.modelo, datos.descripcion, datos.microcontrolador)
        return self._vehiculos.obtener(id_vehiculo)

    def actualizar(self, id_vehiculo: int, datos: VehiculoUpdateIn) -> dict:
        actual = self.obtener_existente(id_vehiculo)  # el SP no informa filas afectadas
        nuevo = {**actual, **datos.model_dump(exclude_unset=True)}
        self._vehiculos.actualizar(
            id_vehiculo, nuevo["nombre"], nuevo["modelo"], nuevo["descripcion"],
            nuevo["microcontrolador"], bool(nuevo["activo"]))
        return self._vehiculos.obtener(id_vehiculo)

    def eliminar(self, id_vehiculo: int) -> None:
        self.obtener_existente(id_vehiculo)
        self._vehiculos.eliminar(id_vehiculo)  # RDS elimina en cascada comandos, estado, historial y demos
