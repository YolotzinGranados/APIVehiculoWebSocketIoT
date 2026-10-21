"""Pruebas automáticas de la API contra un RDS simulado.
Ejecutar:  pytest -q        (requiere:  pip install -r requirements-dev.txt)
"""
from app.core.stored_procedures import ALLOWED_PROCEDURES
from tests.conftest import ADMIN, CONTROL

WS = "/ws/vehiculos/{}"


def sembrar_demo(client, duracion=30, pausa=0):
    """Demo 1 con 3 movimientos (AVANZAR, SUBIR_BRAZO, RETROCEDER)."""
    for orden, cmd in enumerate([1, 3, 2], start=1):
        r = client.post("/vehiculos/1/demos/1/movimientos", headers=ADMIN,
                        json={"id_comando": cmd, "orden": orden, "duracion_ms": duracion, "pausa_ms": pausa})
        assert r.status_code == 201, r.text


def historial_total(rds, id_v=1):
    return len([h for h in rds.d["historial"] if h["id_vehiculo"] == id_v])


# ============================ GET ============================
class TestConsultas:
    def test_listar_con_y_sin_detalle(self, client):
        r = client.get("/vehiculos")
        assert r.status_code == 200 and len(r.json()) == 3
        assert {"comandos", "estado", "demos"} <= set(r.json()[0])
        r = client.get("/vehiculos?incluir_detalle=false")
        assert "comandos" not in r.json()[0]

    def test_inexistente_404_y_vacio_200(self, client):
        assert client.get("/vehiculos/99").status_code == 404
        assert client.get("/vehiculos/99/historial").status_code == 404
        r = client.get("/vehiculos/2/historial")
        assert r.status_code == 200 and r.json()["movimientos"] == []
        assert client.get("/vehiculos/0").status_code == 422

    def test_estado_sin_registro(self, client):
        r = client.get("/vehiculos/1/estado")
        assert r.status_code == 200 and r.json()["comando"] is None and r.json()["conectado"] is False

    def test_historial_maximo_10_y_orden(self, client, rds):
        for _ in range(15):
            rds.sp_registrar_historial(1, 1, "API")
        j = client.get("/vehiculos/1/historial").json()
        assert j["total"] == 10 and j["limite"] == 10
        ids = [m["id_historial"] for m in j["movimientos"]]
        assert ids == sorted(ids, reverse=True) and ids[0] == 15
        assert historial_total(rds) == 15  # RDS conserva todo

    def test_historial_menos_de_10(self, client, rds):
        for _ in range(3):
            rds.sp_registrar_historial(1, 1, "API")
        assert client.get("/vehiculos/1/historial").json()["total"] == 3

    def test_get_no_modifica_datos(self, client, rds):
        antes = repr(rds.d)
        for url in ["/vehiculos", "/vehiculos/1", "/vehiculos/1/comandos", "/vehiculos/1/estado",
                    "/vehiculos/1/historial", "/vehiculos/1/demos"]:
            client.get(url)
        assert repr(rds.d) == antes
        assert not [p for p in rds.llamadas if p.startswith(("sp_crear", "sp_actualizar", "sp_eliminar",
                                                              "sp_registrar", "sp_agregar"))]


# ============================ seguridad ============================
class TestSeguridad:
    def test_sin_clave_401(self, client):
        assert client.post("/vehiculos/1/movimientos", json={"id_comando": 1}).status_code == 401
        assert client.post("/vehiculos/1/eliminar").status_code == 401

    def test_clave_invalida_401(self, client):
        r = client.post("/vehiculos/1/movimientos", json={"id_comando": 1}, headers={"X-API-Key": "mala"})
        assert r.status_code == 401

    def test_control_no_puede_eliminar_403(self, client, rds):
        r = client.post("/vehiculos/1/eliminar", headers=CONTROL)
        assert r.status_code == 403 and 1 in rds.d["vehiculos"]

    def test_control_si_puede_mover_y_admin_tambien(self, client):
        assert client.post("/vehiculos/1/movimientos", json={"id_comando": 1}, headers=CONTROL).status_code == 201
        assert client.post("/vehiculos/1/movimientos", json={"id_comando": 2}, headers=ADMIN).status_code == 201


# ============================ movimiento individual ============================
class TestMovimientoIndividual:
    def test_exito_actualiza_estado_e_historial(self, client, rds):
        r = client.post("/vehiculos/1/movimientos", json={"id_comando": 1, "origen": "web"}, headers=CONTROL)
        assert r.status_code == 201
        j = r.json()
        assert j["comando"] == "AVANZAR" and j["origen"] == "WEB" and j["estado"]["comando"] == "AVANZAR"
        assert rds.d["estado"][1]["id_comando"] == 1
        assert historial_total(rds) == 1 and rds.d["historial"][0]["origen"] == "WEB"

    def test_conectado_no_se_asume_verdadero(self, client, rds):
        client.post("/vehiculos/1/movimientos", json={"id_comando": 1}, headers=CONTROL)
        assert rds.d["estado"][1]["conectado"] == 0
        rds.d["estado"][1]["conectado"] = 1  # el microcontrolador (práctica futura) lo marcaría
        client.post("/vehiculos/1/movimientos", json={"id_comando": 2}, headers=CONTROL)
        assert rds.d["estado"][1]["conectado"] == 1  # se conserva

    def _rechazo(self, client, rds, id_v, id_c, codigo):
        antes = repr(rds.d)
        r = client.post(f"/vehiculos/{id_v}/movimientos", json={"id_comando": id_c}, headers=CONTROL)
        assert r.status_code == codigo, r.text
        assert repr(rds.d) == antes  # ni estado ni historial cambiaron

    def test_rechazos_no_modifican_nada(self, client, rds):
        self._rechazo(client, rds, 99, 1, 404)   # vehículo inexistente
        self._rechazo(client, rds, 3, 7, 409)    # vehículo inactivo
        self._rechazo(client, rds, 1, 99, 404)   # comando inexistente
        self._rechazo(client, rds, 1, 6, 404)    # comando de OTRO vehículo
        self._rechazo(client, rds, 1, 5, 409)    # comando inactivo

    def test_origen_demo_reservado_y_campos_extra(self, client):
        assert client.post("/vehiculos/1/movimientos", json={"id_comando": 1, "origen": "DEMO"}, headers=CONTROL).status_code == 422
        assert client.post("/vehiculos/1/movimientos", json={"id_comando": 1, "x": 1}, headers=CONTROL).status_code == 422

    def test_transaccion_rollback_si_falla_el_historial(self, client, rds):
        rds.fallar_en = "sp_registrar_historial"
        antes = repr(rds.d)
        r = client.post("/vehiculos/1/movimientos", json={"id_comando": 1}, headers=CONTROL)
        assert r.status_code == 500
        assert repr(rds.d) == antes  # el estado actualizado se revirtió junto con el historial

    def test_notifica_solo_a_clientes_del_vehiculo_y_tras_commit(self, client, rds):
        with client.websocket_connect(WS.format(1)) as a, client.websocket_connect(WS.format(1)) as b, \
                client.websocket_connect(WS.format(2)) as otro:
            for ws in (a, b, otro):
                assert ws.receive_json()["tipo"] == "estado_inicial"
            r = client.post("/vehiculos/1/movimientos", json={"id_comando": 3}, headers=CONTROL)
            assert r.json()["clientes_notificados"] == 2
            for ws in (a, b):
                m = ws.receive_json()
                assert (m["tipo"], m["id_vehiculo"], m["comando"], m["codigo"]) == ("movimiento", 1, "SUBIR_BRAZO", 5)
                assert "marca_temporal" in m
            # un POST rechazado NO emite evento; el siguiente mensaje que llega al cliente es el 'pong'
            client.post("/vehiculos/1/movimientos", json={"id_comando": 99}, headers=CONTROL)
            a.send_text("ping")
            assert a.receive_json()["tipo"] == "pong"
            otro.send_text("ping")
            assert otro.receive_json()["tipo"] == "pong"  # el vehículo 2 jamás recibió el movimiento del 1


# ============================ WebSocket ============================
class TestWebSocket:
    def test_estado_inicial_desde_rds(self, client, rds):
        rds.sp_actualizar_estado(1, 4, False)
        with client.websocket_connect(WS.format(1)) as ws:
            m = ws.receive_json()
            assert m["tipo"] == "estado_inicial" and m["comando"] == "DETENER" and m["codigo"] == 9

    def test_vehiculo_inexistente(self, client):
        with client.websocket_connect(WS.format(99)) as ws:
            assert ws.receive_json()["tipo"] == "error"

    def test_desconexion_no_afecta_a_otros(self, client):
        with client.websocket_connect(WS.format(1)) as a:
            a.receive_json()
            with client.websocket_connect(WS.format(1)) as b:
                b.receive_json()
            # b se desconectó; a sigue recibiendo
            r = client.post("/vehiculos/1/movimientos", json={"id_comando": 1}, headers=CONTROL)
            assert r.json()["clientes_notificados"] == 1
            assert a.receive_json()["tipo"] == "movimiento"


# ============================ DEMO ============================
class TestDemo:
    def test_demo_completa_sin_historial(self, client, rds):
        sembrar_demo(client, duracion=30, pausa=10)
        client.post("/vehiculos/1/movimientos", json={"id_comando": 1}, headers=CONTROL)
        antes = historial_total(rds)
        with client.websocket_connect(WS.format(1)) as ws:
            assert ws.receive_json()["tipo"] == "estado_inicial"
            r = client.post("/vehiculos/1/demos/1/iniciar", headers=CONTROL)
            assert r.status_code == 202 and r.json()["total_movimientos"] == 3
            inicio = ws.receive_json()
            assert inicio["tipo"] == "demo_inicio" and inicio["total_movimientos"] == 3
            movs = [ws.receive_json() for _ in range(3)]
            assert [m["tipo"] for m in movs] == ["demo_movimiento"] * 3
            assert [m["orden"] for m in movs] == [1, 2, 3]
            assert [m["comando"] for m in movs] == ["AVANZAR", "SUBIR_BRAZO", "RETROCEDER"]
            assert all(m["duracion_ms"] == 30 and m["pausa_ms"] == 10 for m in movs)
            assert ws.receive_json()["tipo"] == "demo_fin"
        assert historial_total(rds) == antes                              # ningún movimiento de la DEMO en el historial
        assert rds.d["estado"][1]["id_comando"] == 2                      # último comando de la DEMO: RETROCEDER

    def test_demo_no_llama_a_registrar_historial(self, client, rds):
        sembrar_demo(client, duracion=10)
        rds.llamadas.clear()
        with client.websocket_connect(WS.format(1)) as ws:
            ws.receive_json()
            client.post("/vehiculos/1/demos/1/iniciar", headers=CONTROL)
            while ws.receive_json()["tipo"] != "demo_fin":
                pass
        assert "sp_registrar_historial" not in rds.llamadas
        assert rds.llamadas.count("sp_actualizar_estado") == 3

    def test_validaciones_de_inicio(self, client, rds):
        assert client.post("/vehiculos/1/demos/1/iniciar", headers=CONTROL).status_code == 409   # sin movimientos
        assert client.post("/vehiculos/1/demos/99/iniciar", headers=CONTROL).status_code == 404  # no existe
        assert client.post("/vehiculos/2/demos/1/iniciar", headers=CONTROL).status_code == 404   # demo de otro vehículo
        assert client.post("/vehiculos/3/demos/1/iniciar", headers=CONTROL).status_code == 409   # vehículo inactivo
        assert client.post("/vehiculos/1/demos/1/iniciar").status_code == 401                     # sin clave
        sembrar_demo(client)
        client.post("/vehiculos/1/demos/1/actualizar", json={"activo": False}, headers=ADMIN)
        assert client.post("/vehiculos/1/demos/1/iniciar", headers=CONTROL).status_code == 409   # demo inactiva

    def test_no_dos_demos_simultaneas_y_cancelacion(self, client, rds):
        sembrar_demo(client, duracion=5000)  # largas: dan tiempo a cancelar
        with client.websocket_connect(WS.format(1)) as ws:
            ws.receive_json()
            assert client.post("/vehiculos/1/demos/1/iniciar", headers=CONTROL).status_code == 202
            assert ws.receive_json()["tipo"] == "demo_inicio"
            assert ws.receive_json()["tipo"] == "demo_movimiento"
            # segunda DEMO en el mismo vehículo -> 409
            assert client.post("/vehiculos/1/demos/1/iniciar", headers=CONTROL).status_code == 409
            # no se puede eliminar el vehículo ni la demo mientras corre
            assert client.post("/vehiculos/1/eliminar", headers=ADMIN).status_code == 409
            assert client.post("/vehiculos/1/demos/1/eliminar", headers=ADMIN).status_code == 409
            # cancelar: inmediato, aunque falten ~5 s del movimiento en curso
            assert client.post("/vehiculos/1/demos/cancelar", headers=CONTROL).status_code == 200
            m = ws.receive_json()
            assert m["tipo"] == "demo_cancelada" and m["accion"] == "DETENER"
            ws.send_text("ping")
            assert ws.receive_json()["tipo"] == "pong"  # no llegó ningún movimiento posterior
        assert rds.d["estado"][1]["id_comando"] == 4  # DETENER quedó como último comando
        assert "sp_registrar_historial" not in rds.llamadas
        # ya no hay DEMO activa: cancelar de nuevo -> 404, e iniciar otra vez -> 202
        assert client.post("/vehiculos/1/demos/cancelar", headers=CONTROL).status_code == 404
        assert client.post("/vehiculos/1/demos/1/iniciar", headers=CONTROL).status_code == 202
        client.post("/vehiculos/1/demos/cancelar", headers=CONTROL)

    def test_demo_no_bloquea_otras_solicitudes(self, client):
        sembrar_demo(client, duracion=3000)
        client.post("/vehiculos/1/demos/1/iniciar", headers=CONTROL)
        # mientras la DEMO avanza, el resto de la API responde con normalidad
        assert client.get("/vehiculos/1").status_code == 200
        assert client.post("/vehiculos/2/movimientos", json={"id_comando": 6}, headers=CONTROL).status_code == 201
        client.post("/vehiculos/1/demos/cancelar", headers=CONTROL)

    def test_falla_de_rds_termina_de_forma_controlada(self, client, rds):
        sembrar_demo(client, duracion=10)
        rds.fallar_en = "sp_actualizar_estado"  # RDS falla desde el primer movimiento (determinista)
        with client.websocket_connect(WS.format(1)) as ws:
            ws.receive_json()
            client.post("/vehiculos/1/demos/1/iniciar", headers=CONTROL)
            assert ws.receive_json()["tipo"] == "demo_inicio"
            m = ws.receive_json()
            assert m["tipo"] == "demo_error" and "mensaje" in m
        rds.fallar_en = None
        assert client.post("/vehiculos/1/demos/1/iniciar", headers=CONTROL).status_code == 202  # quedó libre
        client.post("/vehiculos/1/demos/cancelar", headers=CONTROL)


# ============================ administración (CRUD) ============================
class TestAdministracion:
    def test_vehiculo_crud(self, client):
        r = client.post("/vehiculos", json={"nombre": "  Nuevo  ", "microcontrolador": "ESP32"}, headers=ADMIN)
        assert r.status_code == 201 and r.json()["nombre"] == "Nuevo"
        i = r.json()["id_vehiculo"]
        r = client.post(f"/vehiculos/{i}/actualizar", json={"modelo": "Z9"}, headers=ADMIN)
        assert r.json()["modelo"] == "Z9" and r.json()["nombre"] == "Nuevo"  # parcial: conserva lo demás
        assert client.post(f"/vehiculos/{i}/actualizar", json={}, headers=ADMIN).status_code == 422
        assert client.post(f"/vehiculos/{i}/actualizar", json={"nombre": None}, headers=ADMIN).status_code == 422
        assert client.post(f"/vehiculos/{i}/eliminar", headers=ADMIN).json()["id"] == i
        assert client.get(f"/vehiculos/{i}").status_code == 404
        assert client.post("/vehiculos/999/eliminar", headers=ADMIN).status_code == 404

    def test_comando_crud_y_duplicados(self, client):
        r = client.post("/vehiculos/1/comandos", json={"nombre": "GIRAR", "codigo": 7}, headers=ADMIN)
        assert r.status_code == 201
        i = r.json()["id_comando"]
        assert client.post("/vehiculos/1/comandos", json={"nombre": "otro", "codigo": 7}, headers=ADMIN).status_code == 409
        assert client.post("/vehiculos/1/comandos", json={"nombre": "girar", "codigo": 8}, headers=ADMIN).status_code == 409
        assert client.post("/vehiculos/99/comandos", json={"nombre": "x", "codigo": 1}, headers=ADMIN).status_code == 404
        assert client.post(f"/vehiculos/1/comandos/{i}/actualizar", json={"descripcion": "d"}, headers=ADMIN).json()["descripcion"] == "d"
        assert client.post(f"/vehiculos/2/comandos/{i}/actualizar", json={"descripcion": "d"}, headers=ADMIN).status_code == 404  # ajeno
        assert client.post(f"/vehiculos/1/comandos/{i}/eliminar", headers=ADMIN).status_code == 200

    def test_no_se_elimina_comando_en_uso_por_demo(self, client):
        sembrar_demo(client)
        assert client.post("/vehiculos/1/comandos/1/eliminar", headers=ADMIN).status_code == 409

    def test_movimientos_de_demo_crud_y_validaciones(self, client):
        base = "/vehiculos/1/demos/1/movimientos"
        ok = {"id_comando": 1, "orden": 1, "duracion_ms": 500, "pausa_ms": 100}
        r = client.post(base, json=ok, headers=ADMIN)
        assert r.status_code == 201
        m = r.json()["id_demo_movimiento"]
        assert client.post(base, json=ok, headers=ADMIN).status_code == 409                                  # orden repetido
        assert client.post(base, json={**ok, "orden": 2, "id_comando": 6}, headers=ADMIN).status_code == 404  # comando ajeno
        assert client.post(base, json={**ok, "orden": 2, "id_comando": 5}, headers=ADMIN).status_code == 409  # comando inactivo
        assert client.post(base, json={**ok, "orden": 2, "duracion_ms": 0}, headers=ADMIN).status_code == 422
        assert client.post(base, json={**ok, "orden": 2, "pausa_ms": -1}, headers=ADMIN).status_code == 422
        r = client.post(f"{base}/{m}/actualizar", json={"duracion_ms": 900}, headers=ADMIN)
        assert r.json()["duracion_ms"] == 900 and r.json()["pausa_ms"] == 100
        assert client.get(base).json()[0]["duracion_ms"] == 900
        assert client.post(f"{base}/999/eliminar", headers=ADMIN).status_code == 404
        assert client.post(f"{base}/{m}/eliminar", headers=ADMIN).status_code == 200
        assert client.get(base).json() == []

    def test_demo_crud(self, client):
        r = client.post("/vehiculos/1/demos", json={"nombre": "Otra"}, headers=ADMIN)
        assert r.status_code == 201
        i = r.json()["id_demo"]
        assert client.post(f"/vehiculos/1/demos/{i}/actualizar", json={"activo": False}, headers=ADMIN).json()["activo"] is False
        assert client.post(f"/vehiculos/1/demos/{i}/eliminar", headers=ADMIN).status_code == 200
        assert client.post(f"/vehiculos/1/demos/{i}/eliminar", headers=ADMIN).status_code == 404


# ============================ cobertura de los 21 SP ============================
def test_los_21_sp_estan_integrados(client, rds):
    """Recorre los endpoints y comprueba que NINGÚN SP quedó sin integración funcional."""
    c = client
    i = c.post("/vehiculos", json={"nombre": "Cobertura"}, headers=ADMIN).json()["id_vehiculo"]
    c.post(f"/vehiculos/{i}/actualizar", json={"modelo": "m"}, headers=ADMIN)
    cid = c.post(f"/vehiculos/{i}/comandos", json={"nombre": "A", "codigo": 1}, headers=ADMIN).json()["id_comando"]
    c.post(f"/vehiculos/{i}/comandos/{cid}/actualizar", json={"descripcion": "d"}, headers=ADMIN)
    c.post(f"/vehiculos/{i}/movimientos", json={"id_comando": cid}, headers=CONTROL)
    did = c.post(f"/vehiculos/{i}/demos", json={"nombre": "d"}, headers=ADMIN).json()["id_demo"]
    c.post(f"/vehiculos/{i}/demos/{did}/actualizar", json={"descripcion": "x"}, headers=ADMIN)
    mid = c.post(f"/vehiculos/{i}/demos/{did}/movimientos",
                 json={"id_comando": cid, "orden": 1, "duracion_ms": 5}, headers=ADMIN).json()["id_demo_movimiento"]
    c.post(f"/vehiculos/{i}/demos/{did}/movimientos/{mid}/actualizar", json={"pausa_ms": 1}, headers=ADMIN)
    for url in ["/vehiculos", f"/vehiculos/{i}", f"/vehiculos/{i}/comandos", f"/vehiculos/{i}/estado",
                f"/vehiculos/{i}/historial", f"/vehiculos/{i}/demos", f"/vehiculos/{i}/demos/{did}/movimientos"]:
        assert c.get(url).status_code == 200
    c.post(f"/vehiculos/{i}/demos/{did}/movimientos/{mid}/eliminar", headers=ADMIN)
    c.post(f"/vehiculos/{i}/demos/{did}/eliminar", headers=ADMIN)
    c.post(f"/vehiculos/{i}/comandos/{cid}/eliminar", headers=ADMIN)
    c.post(f"/vehiculos/{i}/eliminar", headers=ADMIN)
    assert set(rds.llamadas) == ALLOWED_PROCEDURES, ALLOWED_PROCEDURES - set(rds.llamadas)
