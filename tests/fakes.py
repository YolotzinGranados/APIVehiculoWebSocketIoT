"""RDS simulado en memoria para probar la API sin conexión a AWS.

Imita los 21 Stored Procedures reales (script/vehiculo_iot_routines.sql) y las
restricciones de las tablas: UNIQUE (vehiculo,codigo), (vehiculo,nombre), (demo,orden),
FK en cascada, RESTRICT de demo_movimientos -> comandos, y transacciones con rollback.
"""
import copy
from contextlib import contextmanager
from datetime import datetime, timedelta

from app.core.exceptions import ConflictError, DatabaseError
from app.core.stored_procedures import ALLOWED_PROCEDURES

T0 = datetime(2026, 10, 2, 18, 0, 0)


class FakeRDS:
    """Hace de Database (connection/transaction) y de StoredProcedureExecutor (call/call_one)."""

    def __init__(self):
        self.llamadas: list[str] = []      # SP invocados (para verificar qué se llamó)
        self.fallar_en: str | None = None  # simula una falla de RDS en un SP concreto
        self._reloj = 0
        self.d = {
            "vehiculos": {}, "comandos": {}, "estado": {}, "historial": [],
            "demos": {}, "movs": {},
            "seq": {"vehiculo": 0, "comando": 0, "historial": 0, "demo": 0, "mov": 0},
        }

    # ------------------------------------------------------------ interfaz Database
    @contextmanager
    def connection(self):
        yield None

    @contextmanager
    def transaction(self):
        instantanea = copy.deepcopy(self.d)
        try:
            yield None
        except Exception:
            self.d = instantanea  # ROLLBACK
            raise

    def ping(self):
        return True

    def close(self):
        pass

    # ------------------------------------------------------------ interfaz Executor
    def call(self, procedure, params=(), conn=None):
        assert procedure in ALLOWED_PROCEDURES, procedure
        self.llamadas.append(procedure)
        if self.fallar_en == procedure:
            raise DatabaseError("fallo simulado de RDS")
        return getattr(self, procedure)(*params)

    def call_one(self, procedure, params=(), conn=None):
        filas = self.call(procedure, params, conn)
        return filas[0] if filas else None

    # ------------------------------------------------------------ utilidades
    def _ahora(self):
        self._reloj += 1
        return T0 + timedelta(seconds=self._reloj)

    def _id(self, clave):
        self.d["seq"][clave] += 1
        return self.d["seq"][clave]

    # ------------------------------------------------------------ vehículos
    def sp_crear_vehiculo(self, nombre, modelo, descripcion, micro):
        i = self._id("vehiculo")
        self.d["vehiculos"][i] = dict(id_vehiculo=i, nombre=nombre, modelo=modelo, descripcion=descripcion,
                                      microcontrolador=micro, fecha_registro=self._ahora(), activo=1)
        return [{"id_vehiculo": i}]

    def sp_obtener_vehiculos(self):
        return [dict(v) for _, v in sorted(self.d["vehiculos"].items())]

    def sp_obtener_vehiculo(self, id_v):
        v = self.d["vehiculos"].get(id_v)
        return [dict(v)] if v else []

    def sp_actualizar_vehiculo(self, id_v, nombre, modelo, descripcion, micro, activo):
        if id_v in self.d["vehiculos"]:
            self.d["vehiculos"][id_v].update(nombre=nombre, modelo=modelo, descripcion=descripcion,
                                             microcontrolador=micro, activo=int(activo))
        return []

    def sp_eliminar_vehiculo(self, id_v):
        self.d["vehiculos"].pop(id_v, None)
        cmds = [c for c, v in self.d["comandos"].items() if v["id_vehiculo"] == id_v]
        demos = [x for x, v in self.d["demos"].items() if v["id_vehiculo"] == id_v]
        for x in demos:
            self.sp_eliminar_demo(x)
        for c in cmds:
            del self.d["comandos"][c]
        self.d["estado"].pop(id_v, None)
        self.d["historial"] = [h for h in self.d["historial"] if h["id_vehiculo"] != id_v]
        return []

    # ------------------------------------------------------------ comandos
    def _unico_comando(self, id_v, nombre, codigo, excluir=None):
        for c in self.d["comandos"].values():
            if c["id_vehiculo"] == id_v and c["id_comando"] != excluir and (
                    c["codigo"] == codigo or c["nombre"].casefold() == nombre.casefold()):
                raise ConflictError("UNIQUE violado en comandos")

    def sp_crear_comando(self, id_v, nombre, codigo, descripcion):
        if id_v not in self.d["vehiculos"]:
            raise ConflictError("FK vehiculo")
        self._unico_comando(id_v, nombre, codigo)
        i = self._id("comando")
        self.d["comandos"][i] = dict(id_comando=i, id_vehiculo=id_v, nombre=nombre, codigo=codigo,
                                     descripcion=descripcion, activo=1)
        return [{"id_comando": i}]

    def sp_obtener_comandos_vehiculo(self, id_v):
        cs = [dict(c) for c in self.d["comandos"].values() if c["id_vehiculo"] == id_v]
        return sorted(cs, key=lambda c: c["codigo"])

    def sp_actualizar_comando(self, id_c, nombre, codigo, descripcion, activo):
        c = self.d["comandos"].get(id_c)
        if c:
            self._unico_comando(c["id_vehiculo"], nombre, codigo, excluir=id_c)
            c.update(nombre=nombre, codigo=codigo, descripcion=descripcion, activo=int(activo))
        return []

    def sp_eliminar_comando(self, id_c):
        if any(m["id_comando"] == id_c for m in self.d["movs"].values()):
            raise ConflictError("RESTRICT: comando en uso por una demo")
        self.d["comandos"].pop(id_c, None)
        for e in self.d["estado"].values():
            if e["id_comando"] == id_c:
                e["id_comando"] = None
        for h in self.d["historial"]:
            if h["id_comando"] == id_c:
                h["id_comando"] = None
        return []

    # ------------------------------------------------------------ estado
    def sp_actualizar_estado(self, id_v, id_c, conectado):
        self.d["estado"][id_v] = dict(id_vehiculo=id_v, id_comando=id_c, conectado=int(conectado),
                                      fecha_actualizacion=self._ahora())
        return []

    def sp_obtener_estado(self, id_v):
        e = self.d["estado"].get(id_v)
        if not e:
            return []
        c = self.d["comandos"].get(e["id_comando"])
        return [dict(id_vehiculo=id_v, vehiculo=self.d["vehiculos"][id_v]["nombre"],
                     id_comando=e["id_comando"], comando=c["nombre"] if c else None,
                     codigo=c["codigo"] if c else None, conectado=e["conectado"],
                     fecha_actualizacion=e["fecha_actualizacion"])]

    # ------------------------------------------------------------ historial
    def sp_registrar_historial(self, id_v, id_c, origen):
        self.d["historial"].append(dict(id_historial=self._id("historial"), id_vehiculo=id_v,
                                        id_comando=id_c, fecha_hora=self._ahora(), origen=origen))
        return []

    def sp_obtener_historial(self, id_v):
        filas = []
        for h in sorted((h for h in self.d["historial"] if h["id_vehiculo"] == id_v),
                        key=lambda h: (h["fecha_hora"], h["id_historial"]), reverse=True):
            c = self.d["comandos"].get(h["id_comando"])
            filas.append(dict(id_historial=h["id_historial"], id_vehiculo=id_v,
                              comando=c["nombre"] if c else None, codigo=c["codigo"] if c else None,
                              fecha_hora=h["fecha_hora"], origen=h["origen"]))
        return filas

    # ------------------------------------------------------------ demos
    def sp_crear_demo(self, id_v, nombre, descripcion):
        i = self._id("demo")
        self.d["demos"][i] = dict(id_demo=i, id_vehiculo=id_v, nombre=nombre, descripcion=descripcion, activo=1)
        return [{"id_demo": i}]

    def sp_obtener_demos(self, id_v):
        return [dict(d) for _, d in sorted(self.d["demos"].items()) if d["id_vehiculo"] == id_v]

    def sp_actualizar_demo(self, id_d, nombre, descripcion, activo):
        if id_d in self.d["demos"]:
            self.d["demos"][id_d].update(nombre=nombre, descripcion=descripcion, activo=int(activo))
        return []

    def sp_eliminar_demo(self, id_d):
        self.d["demos"].pop(id_d, None)
        self.d["movs"] = {k: m for k, m in self.d["movs"].items() if m["id_demo"] != id_d}
        return []

    def sp_agregar_movimiento_demo(self, id_d, id_c, orden, duracion, pausa):
        if any(m["id_demo"] == id_d and m["orden"] == orden for m in self.d["movs"].values()):
            raise ConflictError("UNIQUE violado en demo_movimientos (demo, orden)")
        i = self._id("mov")
        self.d["movs"][i] = dict(id_demo_movimiento=i, id_demo=id_d, id_comando=id_c, orden=orden,
                                 duracion_ms=duracion, pausa_ms=pausa)
        return []

    def sp_obtener_movimientos_demo(self, id_d):
        filas = []
        for m in sorted((m for m in self.d["movs"].values() if m["id_demo"] == id_d), key=lambda m: m["orden"]):
            c = self.d["comandos"][m["id_comando"]]
            filas.append(dict(id_demo_movimiento=m["id_demo_movimiento"], orden=m["orden"],
                              id_comando=m["id_comando"], comando=c["nombre"], codigo=c["codigo"],
                              duracion_ms=m["duracion_ms"], pausa_ms=m["pausa_ms"]))
        return filas

    def sp_actualizar_movimiento_demo(self, id_m, id_c, orden, duracion, pausa):
        if id_m in self.d["movs"]:
            self.d["movs"][id_m].update(id_comando=id_c, orden=orden, duracion_ms=duracion, pausa_ms=pausa)
        return []

    def sp_eliminar_movimiento_demo(self, id_m):
        self.d["movs"].pop(id_m, None)
        return []


def sembrar(rds: FakeRDS) -> None:
    """Datos de ejemplo parecidos a los de tu base:
    v1 Excavadora (comandos propios), v2 inactivo, v3 con un comando de otro vehículo."""
    rds.sp_crear_vehiculo("Excavadora IoT", "Modelo X", "Vehículo de construcción", "ESP8266")  # 1
    rds.sp_crear_vehiculo("Grúa IoT", "Modelo G", None, "ESP32")                                  # 2
    rds.sp_crear_vehiculo("Inactivo", None, None, None)                                           # 3
    rds.d["vehiculos"][3]["activo"] = 0
    for nombre, codigo in [("AVANZAR", 1), ("RETROCEDER", 2), ("SUBIR_BRAZO", 5), ("DETENER", 9)]:
        rds.sp_crear_comando(1, nombre, codigo, None)   # ids 1..4
    rds.sp_crear_comando(1, "OBSOLETO", 20, None)       # id 5
    rds.d["comandos"][5]["activo"] = 0
    rds.sp_crear_comando(2, "GIRAR", 1, None)           # id 6 (pertenece al vehículo 2)
    rds.sp_crear_comando(3, "AVANZAR", 1, None)         # id 7 (vehículo inactivo)
    rds.sp_crear_demo(1, "Demo principal", "Secuencia automática")  # demo 1
    rds.llamadas.clear()
