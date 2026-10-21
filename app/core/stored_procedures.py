"""Único punto de la aplicación que ejecuta Stored Procedures (parámetros enlazados)."""
import logging
from typing import Any, Optional, Sequence

from mysql.connector import errors as mysql_errors

from app.core.database import Database
from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    DatabaseError,
    ServiceUnavailableError,
)

logger = logging.getLogger(__name__)

# Los 21 SP existentes. Cualquier otro nombre se rechaza.
ALLOWED_PROCEDURES = frozenset({
    # Vehículos
    "sp_crear_vehiculo", "sp_obtener_vehiculos", "sp_obtener_vehiculo",
    "sp_actualizar_vehiculo", "sp_eliminar_vehiculo",
    # Comandos
    "sp_crear_comando", "sp_obtener_comandos_vehiculo",
    "sp_actualizar_comando", "sp_eliminar_comando",
    # Estado
    "sp_actualizar_estado", "sp_obtener_estado",
    # Historial
    "sp_registrar_historial", "sp_obtener_historial",
    # Demos
    "sp_crear_demo", "sp_obtener_demos", "sp_actualizar_demo", "sp_eliminar_demo",
    # Movimientos de demo
    "sp_agregar_movimiento_demo", "sp_obtener_movimientos_demo",
    "sp_actualizar_movimiento_demo", "sp_eliminar_movimiento_demo",
})

# Códigos de MySQL que indican pérdida o fallo de conexión
_CONNECTION_ERRNOS = {2002, 2003, 2006, 2013, 2055}


class StoredProcedureExecutor:
    def __init__(self, db: Database):
        self._db = db

    def call(
        self,
        procedure: str,
        params: Sequence[Any] = (),
        conn=None,
    ) -> list[dict]:
        """Ejecuta un SP y devuelve sus filas como lista de diccionarios.

        - conn=None: usa su propia conexión y hace commit al terminar.
        - conn=<conexión>: participa en una transacción externa (db.transaction());
          el commit/rollback lo decide quien abrió la transacción.
        """
        if procedure not in ALLOWED_PROCEDURES:
            raise ValueError(f"Procedimiento no permitido: {procedure}")

        if conn is not None:
            return self._execute(conn, procedure, params)

        with self._db.connection() as own_conn:
            try:
                rows = self._execute(own_conn, procedure, params)
                own_conn.commit()
                return rows
            except Exception:
                own_conn.rollback()
                raise

    def call_one(
        self, procedure: str, params: Sequence[Any] = (), conn=None
    ) -> Optional[dict]:
        rows = self.call(procedure, params, conn)
        return rows[0] if rows else None

    @staticmethod
    def _execute(conn, procedure: str, params: Sequence[Any]) -> list[dict]:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.callproc(procedure, tuple(params))
            rows: list[dict] = []
            for result in cursor.stored_results():
                nombres = result.column_names
                for fila in result.fetchall():
                    # Según la versión del conector, las filas pueden llegar como tupla: se normaliza a dict.
                    rows.append(fila if isinstance(fila, dict) else dict(zip(nombres, fila)))
            return rows
        except mysql_errors.Error as exc:
            raise StoredProcedureExecutor._translate(procedure, exc) from exc
        finally:
            cursor.close()

    @staticmethod
    def _translate(procedure: str, exc: mysql_errors.Error):
        # El detalle completo solo va al log del servidor, nunca al cliente.
        logger.error("Fallo en %s: [%s] %s", procedure, getattr(exc, "errno", "?"), exc)
        if isinstance(exc, mysql_errors.IntegrityError):
            return ConflictError("La operación viola una restricción de datos (duplicado o relación)")
        if isinstance(exc, mysql_errors.DataError):
            return BadRequestError("Los datos enviados no son válidos para la base de datos")
        if getattr(exc, "errno", None) in _CONNECTION_ERRNOS or isinstance(
            exc, (mysql_errors.InterfaceError, mysql_errors.PoolError)
        ):
            return ServiceUnavailableError("Base de datos no disponible")
        return DatabaseError("Error al ejecutar la operación en la base de datos")
