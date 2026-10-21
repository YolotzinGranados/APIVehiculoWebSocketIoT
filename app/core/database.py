"""Pool de conexiones a Amazon RDS (MySQL) con manejo de transacciones."""
import logging
import threading
import time
from contextlib import contextmanager
from typing import Iterator, Optional

from mysql.connector import errors as mysql_errors
from mysql.connector import pooling

from app.core.config import Settings
from app.core.exceptions import ServiceUnavailableError

logger = logging.getLogger(__name__)

POOL_ESPERA_MAX = 3.0  # segundos que se espera una conexión libre antes de rendirse


class Database:
    """Administra el pool. El pool se crea de forma perezosa (primer uso),
    así la API arranca aunque RDS no esté disponible en ese momento."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._pool: Optional[pooling.MySQLConnectionPool] = None
        self._lock = threading.Lock()

    def _get_pool(self) -> pooling.MySQLConnectionPool:
        if self._pool is None:
            with self._lock:
                if self._pool is None:
                    s = self._settings
                    self._pool = pooling.MySQLConnectionPool(
                        pool_name="vehiculo_iot_pool",
                        pool_size=s.db_pool_size,
                        host=s.db_host,
                        port=s.db_port,
                        user=s.db_user,
                        password=s.db_password.get_secret_value(),
                        database=s.db_name,
                        charset="utf8mb4",
                        autocommit=False,
                        connection_timeout=s.db_connect_timeout,
                    )
        return self._pool

    def _adquirir(self):
        """Toma una conexión; si el pool está agotado espera un momento en vez de fallar."""
        pool = self._get_pool()
        limite = time.monotonic() + POOL_ESPERA_MAX
        while True:
            try:
                return pool.get_connection()
            except mysql_errors.PoolError:
                if time.monotonic() >= limite:
                    raise
                time.sleep(0.05)

    @contextmanager
    def connection(self) -> Iterator:
        """Entrega una conexión del pool y SIEMPRE la libera."""
        try:
            conn = self._adquirir()
        except mysql_errors.Error as exc:
            # El detalle va solo al log del servidor, nunca al cliente.
            logger.error("No se pudo obtener conexión a RDS: [%s] %s",
                         getattr(exc, "errno", "?"), exc)
            raise ServiceUnavailableError("Base de datos no disponible") from exc
        try:
            yield conn
        finally:
            conn.close()  # devuelve la conexión al pool

    @contextmanager
    def transaction(self) -> Iterator:
        """Transacción atómica: commit si todo sale bien, rollback si hay error."""
        with self.connection() as conn:
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def ping(self) -> bool:
        with self.connection() as conn:
            cur = conn.cursor()
            try:
                cur.execute("SELECT 1")
                cur.fetchall()
            finally:
                cur.close()
        return True

    def close(self) -> None:
        self._pool = None  # las conexiones del pool se cierran al terminar el proceso
