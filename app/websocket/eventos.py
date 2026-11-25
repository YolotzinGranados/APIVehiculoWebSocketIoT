
"""Eventos WebSocket de vehículos IoT."""
from datetime import datetime, timezone
from typing import Any, Optional
import uuid

ESTADO_INICIAL = "estado_inicial"
MOVIMIENTO = "movimiento"

DEMO_INICIO = "demo_inicio"
DEMO_MOVIMIENTO = "demo_movimiento"
DEMO_FIN = "demo_fin"
DEMO_CANCELADA = "demo_cancelada"
DEMO_ERROR = "demo_error"

ERROR = "error"
PONG = "pong"

EVENTOS_CON_MOVIMIENTO = {
    MOVIMIENTO,
    DEMO_MOVIMIENTO,
}


def _iso(valor: Any) -> Optional[str]:
    return valor.isoformat() if isinstance(valor, datetime) else None


def evento(
    tipo: str,
    id_vehiculo: int,
    comando: Optional[str] = None,
    codigo: Optional[int] = None,
    **extra: Any
) -> dict:

    resultado = {
        "tipo": tipo,
        "id_vehiculo": id_vehiculo,
        "comando": comando,
        "codigo": codigo,
        "marca_temporal": datetime.now(timezone.utc).isoformat(),
        **extra,
    }

    if tipo in EVENTOS_CON_MOVIMIENTO:
        resultado["event_id"] = uuid.uuid4().hex

    return resultado


def evento_estado_inicial(estado: dict) -> dict:
    return evento(
        ESTADO_INICIAL,
        estado["id_vehiculo"],
        comando=estado.get("comando"),
        codigo=estado.get("codigo"),
        conectado=bool(estado.get("conectado")),
        fecha_actualizacion=_iso(
            estado.get("fecha_actualizacion")
        ),
    )
