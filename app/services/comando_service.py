from typing import Optional

from app.core.database import Database
from app.core.exceptions import ConflictError, NotFoundError
from app.models.comando import ComandoIn, ComandoUpdateIn
from app.repositories.comando_repository import ComandoRepository
from app.repositories.demo_repository import DemoRepository
from app.services.vehiculo_service import VehiculoService


class ComandoService:
    def __init__(self, db: Database, vehiculos: VehiculoService,
                 comandos: ComandoRepository, demos: DemoRepository):
        self._db = db
        self._vehiculos = vehiculos
        self._comandos = comandos
        self._demos = demos

    def listar_por_vehiculo(self, id_vehiculo: int) -> list[dict]:
        with self._db.connection() as conn:
            self._vehiculos.obtener_existente(id_vehiculo, conn)  # 404 si no existe
            return self._comandos.listar_por_vehiculo(id_vehiculo, conn)  # [] = válido sin resultados

    def obtener_de_vehiculo(self, id_vehiculo: int, id_comando: int, conn=None) -> dict:
        """No hay SP para un solo comando: se busca en el catálogo del vehículo,
        lo que además garantiza que el comando le pertenece."""
        for comando in self._comandos.listar_por_vehiculo(id_vehiculo, conn):
            if comando["id_comando"] == id_comando:
                return comando
        raise NotFoundError(f"El comando {id_comando} no existe en el vehículo {id_vehiculo}")

    @staticmethod
    def _verificar_duplicados(catalogo: list[dict], nombre: str, codigo: int,
                              excluir: Optional[int] = None) -> None:
        # La base usa collation _ai_ci (sin mayúsculas/acentos); casefold() lo aproxima.
        # La restricción UNIQUE de RDS sigue siendo la última defensa.
        for c in catalogo:
            if c["id_comando"] == excluir:
                continue
            if c["codigo"] == codigo:
                raise ConflictError(f"Ya existe un comando con el código {codigo} en este vehículo")
            if c["nombre"].casefold() == nombre.casefold():
                raise ConflictError(f"Ya existe un comando llamado '{c['nombre']}' en este vehículo")

    def crear(self, id_vehiculo: int, datos: ComandoIn) -> dict:
        with self._db.connection() as conn:
            self._vehiculos.obtener_existente(id_vehiculo, conn)
            catalogo = self._comandos.listar_por_vehiculo(id_vehiculo, conn)
        self._verificar_duplicados(catalogo, datos.nombre, datos.codigo)
        id_comando = self._comandos.crear(id_vehiculo, datos.nombre, datos.codigo, datos.descripcion)
        return self.obtener_de_vehiculo(id_vehiculo, id_comando)

    def actualizar(self, id_vehiculo: int, id_comando: int, datos: ComandoUpdateIn) -> dict:
        with self._db.connection() as conn:
            self._vehiculos.obtener_existente(id_vehiculo, conn)
            actual = self.obtener_de_vehiculo(id_vehiculo, id_comando, conn)
            catalogo = self._comandos.listar_por_vehiculo(id_vehiculo, conn)
        nuevo = {**actual, **datos.model_dump(exclude_unset=True)}
        self._verificar_duplicados(catalogo, nuevo["nombre"], nuevo["codigo"], excluir=id_comando)
        self._comandos.actualizar(id_comando, nuevo["nombre"], nuevo["codigo"],
                                  nuevo["descripcion"], bool(nuevo["activo"]))
        return self.obtener_de_vehiculo(id_vehiculo, id_comando)

    def eliminar(self, id_vehiculo: int, id_comando: int) -> None:
        with self._db.connection() as conn:
            self._vehiculos.obtener_existente(id_vehiculo, conn)
            self.obtener_de_vehiculo(id_vehiculo, id_comando, conn)
            for demo in self._demos.listar(id_vehiculo, conn):
                for mov in self._demos.obtener_movimientos(demo["id_demo"], conn):
                    if mov["id_comando"] == id_comando:
                        raise ConflictError(
                            f"El comando está en uso en la demo '{demo['nombre']}'; "
                            "quítalo de la demo antes de eliminarlo")
        self._comandos.eliminar(id_comando)
