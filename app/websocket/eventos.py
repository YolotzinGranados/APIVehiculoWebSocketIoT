
"""Eventos WebSocket para la excavadora IoT."""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

# Movimiento individual
ESTADO_INICIAL = "estado_inicial"
MOVIMIENTO = "movimiento"

# DEMO
DEMO_INICIO = "demo_inicio"
DEMO_MOVIMIENTO = "demo_movimiento"
DEMO_FIN = "demo_fin"
DEMO_CANCELADA = "demo_cancelada"
DEMO_ERROR = "demo_error"

# Otros eventos
ERROR = "error"
PONG = "pong"


def _iso(valor: Any) -> Optional[str]:
    return valor.isoformat() if isinstance(valor, datetime) else None


def evento(
    tipo: str,
    id_vehiculo: int,
    comando: Optional[str] = None,
    codigo: Optional[int] = None,
    **extra: Any
) -> dict:
    return {
        "tipo": tipo,
        "id_vehiculo": id_vehiculo,
        "comando": comando,
        "codigo": codigo,
        "marca_temporal": datetime.now(timezone.utc).isoformat(),
        **extra,
        "event_id": uuid4().hex,
    }


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
