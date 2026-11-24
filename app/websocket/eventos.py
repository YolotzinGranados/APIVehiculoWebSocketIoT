"""Formato de los mensajes que viajan por WebSocket.

Todos los eventos llevan: tipo, id_vehiculo, comando, codigo y marca_temporal (UTC, ISO-8601).
Según el tipo se añaden campos propios (origen, id_demo, orden, duracion_ms, ...).
"""
from datetime import datetime, timezone
from typing import Any, Optional

# Movimiento individual
ESTADO_INICIAL = "estado_inicial"
MOVIMIENTO = "movimiento"
# DEMO
DEMO_INICIO = "demo_inicio"
DEMO_MOVIMIENTO = "demo_movimiento"
DEMO_FIN = "demo_fin"
DEMO_CANCELADA = "demo_cancelada"
DEMO_ERROR = "demo_error"
# Otros
ERROR = "error"
PONG = "pong"


def _iso(valor: Any) -> Optional[str]:
    return valor.isoformat() if isinstance(valor, datetime) else None


def evento(tipo: str, id_vehiculo: int, comando: Optional[str] = None,
           codigo: Optional[int] = None, **extra: Any) -> dict:
    return {
        "tipo": tipo,
        "id_vehiculo": id_vehiculo,
        "comando": comando,
        "codigo": codigo,
        "marca_temporal": datetime.now(timezone.utc).isoformat(),
        **extra,
    }


def evento_estado_inicial(estado: dict) -> dict:
    return evento(
        ESTADO_INICIAL, estado["id_vehiculo"],
        comando=estado.get("comando"), codigo=estado.get("codigo"),
        conectado=bool(estado.get("conectado")),
        fecha_actualizacion=_iso(estado.get("fecha_actualizacion")),
    )
