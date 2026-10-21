from app.core.database import Database
from app.core.exceptions import ConflictError, NotFoundError
from app.repositories.comando_repository import ComandoRepository
from app.repositories.estado_repository import EstadoRepository
from app.repositories.historial_repository import HistorialRepository
from app.services.vehiculo_service import VehiculoService


class MovimientoService:
    """Movimiento INDIVIDUAL: ejecuta un comando existente del catálogo.
    (Crear un comando nuevo es otra operación: POST /vehiculos/{id}/comandos.)"""

    def __init__(self, db: Database, vehiculos: VehiculoService, comandos: ComandoRepository,
                 estados: EstadoRepository, historial: HistorialRepository):
        self._db = db
        self._vehiculos = vehiculos
        self._comandos = comandos
        self._estados = estados
        self._historial = historial

    def ejecutar(self, id_vehiculo: int, id_comando: int, origen: str) -> dict:
        """Valida y registra el movimiento en UNA transacción:
        sp_actualizar_estado + sp_registrar_historial hacen COMMIT juntos o ninguno.
        Si algo se rechaza, se lanza la excepción ANTES de escribir y el estado/historial no cambian."""
        with self._db.transaction() as conn:
            # --- validaciones (solo lectura) ---
            self._vehiculos.obtener_activo(id_vehiculo, conn)
            comando = next((c for c in self._comandos.listar_por_vehiculo(id_vehiculo, conn)
                            if c["id_comando"] == id_comando), None)
            if comando is None:
                # No existe, o existe pero es de OTRO vehículo: se rechaza igual.
                raise NotFoundError(
                    f"El comando {id_comando} no existe en el catálogo del vehículo {id_vehiculo}")
            if not comando["activo"]:
                raise ConflictError(f"El comando '{comando['nombre']}' está inactivo")

            # --- escritura atómica ---
            self._estados.registrar_comando(id_vehiculo, id_comando, conn)
            self._historial.registrar(id_vehiculo, id_comando, origen, conn)
            estado = self._estados.obtener(id_vehiculo, conn)
        # El COMMIT ya se hizo al salir del bloque: recién ahora es seguro notificar por WebSocket.
        return {
            "id_vehiculo": id_vehiculo,
            "id_comando": id_comando,
            "comando": comando["nombre"],
            "codigo": comando["codigo"],
            "origen": origen,
            "fecha_hora": estado["fecha_actualizacion"],
            "estado": estado,
        }
